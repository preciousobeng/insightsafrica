"""
fetch_boundaries.py

Downloads administrative boundary GeoJSON from GADM 4.1.
  Ghana:   Level 1 = 16 Regions,  Level 2 = 261 Districts
  Nigeria: Level 1 = 37 States,   Level 2 = 774 LGAs

Source: https://gadm.org (UC Davis, free for non-commercial use)

Usage:
    python scripts/fetch_boundaries.py
    python scripts/fetch_boundaries.py --country nigeria
"""

import argparse
import json
import zipfile
import io
from pathlib import Path
import requests

try:
    from .admin_keys import build_key, parse_key, feature_keys, unique_name_match
except ImportError:  # direct script execution
    from admin_keys import build_key, parse_key, feature_keys, unique_name_match

BASE_DIR          = Path(__file__).parent.parent
PROCESSED_DIR     = BASE_DIR / "data" / "processed"
NIGERIA_DIR       = BASE_DIR / "data" / "processed_nigeria"
IVORYCOAST_DIR    = BASE_DIR / "data" / "processed_ivorycoast"
SENEGAL_DIR       = BASE_DIR / "data" / "processed_senegal"
CAPEVERDE_DIR     = BASE_DIR / "data" / "processed_capeverde"
SOUTHAFRICA_DIR   = BASE_DIR / "data" / "processed_southafrica"

COUNTRY_CONFIG = {
    "ghana": {
        "processed_dir": PROCESSED_DIR,
        "levels": {
            "regions":   {
                "url":      "https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_GHA_1.json.zip",
                "admin_level": 1,
                "out_name": "ghana_regions.geojson",
                "level_label": "region",
            },
            "districts": {
                "url":      "https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_GHA_2.json.zip",
                "admin_level": 2,
                "out_name": "ghana_districts.geojson",
                "level_label": "district",
            },
        },
    },
    "nigeria": {
        "processed_dir": NIGERIA_DIR,
        "levels": {
            "states": {
                "url":      "https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_NGA_1.json.zip",
                "admin_level": 1,
                "out_name": "nigeria_states.geojson",
                "level_label": "state",
            },
            "lgas": {
                "url":      "https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_NGA_2.json.zip",
                "admin_level": 2,
                "out_name": "nigeria_lgas.geojson",
                "level_label": "lga",
            },
        },
    },
    "ivorycoast": {
        "processed_dir": IVORYCOAST_DIR,
        "levels": {
            "districts": {
                "url":      "https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_CIV_1.json.zip",
                "admin_level": 1,
                "out_name": "ivorycoast_districts.geojson",
                "level_label": "district",
            },
            "regions": {
                "url":      "https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_CIV_2.json.zip",
                "admin_level": 2,
                "out_name": "ivorycoast_regions.geojson",
                "level_label": "region",
            },
        },
    },
    "senegal": {
        "processed_dir": SENEGAL_DIR,
        "levels": {
            "regions": {
                "url":      "https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_SEN_1.json.zip",
                "admin_level": 1,
                "out_name": "senegal_regions.geojson",
                "level_label": "region",
            },
            "departments": {
                "url":      "https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_SEN_2.json.zip",
                "admin_level": 2,
                "out_name": "senegal_departments.geojson",
                "level_label": "department",
            },
        },
    },
    "capeverde": {
        "processed_dir": CAPEVERDE_DIR,
        "levels": {
            "islands": {
                "url":      "https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_CPV_1.json.zip",
                "admin_level": 1,
                "out_name": "capeverde_islands.geojson",
                "level_label": "island",
            },
        },
    },
    "southafrica": {
        "processed_dir": SOUTHAFRICA_DIR,
        "levels": {
            "provinces": {
                "url":      "https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_ZAF_1.json.zip",
                "admin_level": 1,
                "out_name": "southafrica_provinces.geojson",
                "level_label": "province",
            },
            "districts": {
                "url":      "https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_ZAF_2.json.zip",
                "admin_level": 2,
                "out_name": "southafrica_districts.geojson",
                "level_label": "district",
            },
        },
    },
}


def validate_boundaries(raw: dict, admin_level: int) -> list[str]:
    features = raw.get("features", [])
    if admin_level not in (1, 2) or not features:
        raise ValueError("Expected a nonempty level-1 or level-2 boundary layer")
    for feature in features:
        props = feature.get("properties", {})
        if props.get("admin_level") != admin_level:
            raise ValueError("Boundary needs controlled refresh: missing/wrong admin_level")
        if admin_level == 2 and not props.get("region"):
            raise ValueError("Level-2 area requires a parent")
        if admin_level == 1 and props.get("region"):
            raise ValueError("Level-1 area must not have a parent")
    return feature_keys(features)


def map_boundaries(raw: dict, level_label: str, admin_level: int) -> dict:
    from copy import deepcopy
    result = deepcopy(raw)
    if admin_level not in (1, 2):
        raise ValueError("Unsupported administrative depth")
    for feature in result.get("features", []):
        props = feature.get("properties", {})
        mapped = {"name": props.get(f"NAME_{admin_level}"),
                  "level": level_label, "admin_level": admin_level,
                  "admin_type": props.get(f"TYPE_{admin_level}")}
        if admin_level == 2:
            mapped["region"] = props.get("NAME_1")
        feature["properties"] = mapped
    validate_boundaries(result, admin_level)
    return result


def download_and_extract(name: str, url: str, out_path: Path, level_label: str, admin_level: int):
    if out_path.exists():
        existing = json.loads(out_path.read_text())
        validate_boundaries(existing, admin_level)
        print(f"Already exists and validated: {out_path.name}")
        return

    print(f"Downloading {name} from GADM...")
    response = requests.get(url, timeout=120)
    response.raise_for_status()

    # Extract GeoJSON from zip
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        json_files = [f for f in z.namelist() if f.endswith(".json")]
        if not json_files:
            raise ValueError(f"No JSON file found in zip for {name}")
        json_name = json_files[0]
        print(f"  Extracting: {json_name}")
        with z.open(json_name) as jf:
            raw = json.load(jf)

    raw = map_boundaries(raw, level_label, admin_level)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "x") as f:
        json.dump(raw, f)

    feature_count = len(raw.get("features", []))
    print(f"  Saved: {out_path.name} ({feature_count} features)")


def main():
    parser = argparse.ArgumentParser(description="Fetch GADM administrative boundaries")
    parser.add_argument("--country", choices=list(COUNTRY_CONFIG), default="ghana")
    args = parser.parse_args()

    config = COUNTRY_CONFIG[args.country]
    processed_dir = config["processed_dir"]

    for name, level in config["levels"].items():
        out_path = processed_dir / level["out_name"]
        download_and_extract(name, level["url"], out_path, level["level_label"], level["admin_level"])

    print("\nBoundaries ready.")


if __name__ == "__main__":
    main()
