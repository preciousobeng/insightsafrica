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

BASE_DIR      = Path(__file__).parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"
NIGERIA_DIR   = BASE_DIR / "data" / "processed_nigeria"

COUNTRY_CONFIG = {
    "ghana": {
        "processed_dir": PROCESSED_DIR,
        "levels": {
            "regions":   {
                "url":      "https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_GHA_1.json.zip",
                "out_name": "ghana_regions.geojson",
                "level_label": "region",
            },
            "districts": {
                "url":      "https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_GHA_2.json.zip",
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
                "out_name": "nigeria_states.geojson",
                "level_label": "state",
            },
            "lgas": {
                "url":      "https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_NGA_2.json.zip",
                "out_name": "nigeria_lgas.geojson",
                "level_label": "lga",
            },
        },
    },
}


def download_and_extract(name: str, url: str, out_path: Path, level_label: str):
    if out_path.exists():
        print(f"Already exists: {out_path.name}")
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

    # Slim down properties — keep only name fields to reduce file size
    for feature in raw.get("features", []):
        props = feature.get("properties", {})
        if level_label in ("region", "state"):
            feature["properties"] = {
                "name":  props.get("NAME_1", ""),
                "level": level_label,
            }
        else:  # district / lga
            feature["properties"] = {
                "name":   props.get("NAME_2", ""),
                "region": props.get("NAME_1", ""),
                "level":  level_label,
            }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
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
        download_and_extract(name, level["url"], out_path, level["level_label"])

    print("\nBoundaries ready.")


if __name__ == "__main__":
    main()
