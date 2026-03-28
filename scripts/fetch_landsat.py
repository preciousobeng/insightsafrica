"""
fetch_landsat.py

Downloads Landsat 9 Collection 2 Level-2 Surface Temperature (ST_B10 / lwir11)
for cities in Ghana or Nigeria via Microsoft Planetary Computer STAC.

No separate account required — Planetary Computer URLs are signed via a free
public SAS API. NASA Earthdata credentials are NOT needed for this source.

Usage:
    python scripts/fetch_landsat.py                           # Ghana all cities, 2024
    python scripts/fetch_landsat.py --city accra
    python scripts/fetch_landsat.py --country nigeria         # all Nigeria cities
    python scripts/fetch_landsat.py --country nigeria --city lagos
    python scripts/fetch_landsat.py --year 2023 --cloud 30
"""

import argparse
import json
import time
from pathlib import Path

import requests

RAW_DIR = Path(__file__).parent.parent / "data" / "raw" / "landsat"

PC_STAC    = "https://planetarycomputer.microsoft.com/api/stac/v1"
PC_SIGN    = "https://planetarycomputer.microsoft.com/api/sas/v1/sign"

COUNTRY_CITIES = {
    "ghana": [
        {
            "id":     "accra",
            "name":   "Accra",
            "region": "Greater Accra",
            "bbox":   [-0.42, 5.45, 0.05, 5.76],
            "centre": [5.6037, -0.1870],
        },
        {
            "id":     "kumasi",
            "name":   "Kumasi",
            "region": "Ashanti",
            "bbox":   [-1.87, 6.54, -1.37, 6.85],
            "centre": [6.6885, -1.6244],
        },
        {
            "id":     "tamale",
            "name":   "Tamale",
            "region": "Northern",
            "bbox":   [-1.05, 9.25, -0.62, 9.56],
            "centre": [9.4034, -0.8424],
        },
    ],
    "nigeria": [
        {
            "id":     "lagos",
            "name":   "Lagos",
            "region": "Lagos State",
            "bbox":   [3.1, 6.3, 3.7, 6.7],
            "centre": [6.5244, 3.3792],
        },
        {
            "id":     "kano",
            "name":   "Kano",
            "region": "Kano State",
            "bbox":   [8.4, 11.9, 8.7, 12.2],
            "centre": [12.0022, 8.5919],
        },
        {
            "id":     "abuja",
            "name":   "Abuja",
            "region": "FCT",
            "bbox":   [7.3, 8.8, 7.6, 9.1],
            "centre": [9.0579, 7.4951],
        },
    ],
    "ivorycoast": [
        {
            "id":     "abidjan",
            "name":   "Abidjan",
            "region": "Lagunes",
            "bbox":   [-4.30, 5.15, -3.70, 5.60],
            "centre": [5.3600, -4.0083],
        },
        {
            "id":     "bouake",
            "name":   "Bouaké",
            "region": "Vallée du Bandama",
            "bbox":   [-5.30, 7.50, -4.80, 7.90],
            "centre": [7.6900, -5.0302],
        },
        {
            "id":     "korhogo",
            "name":   "Korhogo",
            "region": "Savanes",
            "bbox":   [-5.90, 9.20, -5.40, 9.70],
            "centre": [9.4580, -5.6296],
        },
    ],
    "senegal": [
        {
            "id":     "dakar",
            "name":   "Dakar",
            "region": "Dakar",
            "bbox":   [-17.60, 14.55, -17.10, 14.85],
            "centre": [14.70, -17.35],
        },
        {
            "id":     "saint_louis",
            "name":   "Saint-Louis",
            "region": "Saint-Louis",
            "bbox":   [-16.65, 15.90, -16.20, 16.20],
            "centre": [16.05, -16.425],
        },
        {
            "id":     "touba",
            "name":   "Touba",
            "region": "Diourbel",
            "bbox":   [-16.05, 14.75, -15.65, 15.05],
            "centre": [14.90, -15.85],
        },
    ],
    "capeverde": [
        {
            "id":     "praia",
            "name":   "Praia",
            "region": "Santiago",
            "bbox":   [-23.65, 14.85, -23.45, 15.05],
            "centre": [14.930, -23.520],
        },
        {
            "id":     "mindelo",
            "name":   "Mindelo",
            "region": "São Vicente",
            "bbox":   [-25.10, 16.82, -24.90, 16.98],
            "centre": [16.890, -25.000],
        },
        {
            "id":     "santa_maria",
            "name":   "Santa Maria",
            "region": "Sal",
            "bbox":   [-22.97, 16.56, -22.82, 16.68],
            "centre": [16.600, -22.900],
        },
    ],
}


def search_scenes(city: dict, year: int, max_cloud: int = 20) -> list:
    """Search Planetary Computer STAC for Landsat 9 scenes over a city."""
    payload = {
        "collections": ["landsat-c2-l2"],
        "bbox":         city["bbox"],
        "datetime":     f"{year}-01-01/{year}-12-31",
        "query": {
            "platform":       {"in": ["landsat-9"]},
            "eo:cloud_cover": {"lt": max_cloud},
        },
        "limit": 20,
        "sortby": [{"field": "eo:cloud_cover", "direction": "asc"}],
    }
    resp = requests.post(f"{PC_STAC}/search", json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json().get("features", [])


def sign_url(href: str) -> str:
    """Get a short-lived SAS token for a Planetary Computer blob URL."""
    resp = requests.get(PC_SIGN, params={"href": href}, timeout=15)
    resp.raise_for_status()
    return resp.json()["href"]


def download_file(url: str, out_path: Path) -> bool:
    """Stream-download a file, show progress."""
    if out_path.exists():
        print(f"    Already downloaded: {out_path.name}")
        return True

    print(f"    Downloading: {out_path.name}")
    with requests.get(url, stream=True, timeout=300) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        downloaded = 0
        with open(out_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=512 * 1024):
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    print(f"\r    {downloaded/total*100:.0f}%", end="", flush=True)
    print()
    return True


def save_scene_meta(city: dict, item: dict, b10_path: Path):
    """Save scene metadata JSON for use by process_heatwatch.py."""
    props   = item.get("properties", {})
    date_str = props.get("datetime", "")[:10]
    meta = {
        "city_id":   city["id"],
        "city_name": city["name"],
        "region":    city["region"],
        "date":      date_str,
        "source":    "Landsat 9 OLI/TIRS C2 L2 (Planetary Computer)",
        "scene_id":  item.get("id", ""),
        "cloud_pct": props.get("eo:cloud_cover"),
        "b10_file":  b10_path.name,
    }
    meta_path = b10_path.with_suffix(".json")
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)


def main():
    all_city_ids = [c["id"] for cc in COUNTRY_CITIES.values() for c in cc]
    parser = argparse.ArgumentParser(description="Fetch Landsat ST_B10 for cities")
    parser.add_argument("--country", choices=list(COUNTRY_CITIES), default="ghana")
    parser.add_argument("--city",    choices=all_city_ids,
                        help="Single city (default: all cities for selected country)")
    parser.add_argument("--year",    type=int, default=2024)
    parser.add_argument("--cloud",   type=int, default=20,
                        help="Max cloud cover %% (default: 20)")
    args = parser.parse_args()

    cities = [c for c in COUNTRY_CITIES[args.country]
              if not args.city or c["id"] == args.city]

    for city in cities:
        city_dir = RAW_DIR / city["id"]
        city_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n--- {city['name']} ---")
        scenes = search_scenes(city, args.year, args.cloud)

        if not scenes:
            print(f"  No Landsat 9 scenes found (cloud < {args.cloud}%).")
            print("  Try --cloud 40 or a different --year.")
            continue

        print(f"  Found {len(scenes)} scene(s). Downloading up to 2 clearest.")
        acquired = 0

        for item in scenes:
            if acquired >= 2:
                break

            scene_id  = item.get("id", "unknown")
            cloud_pct = item.get("properties", {}).get("eo:cloud_cover", "?")
            date_str  = item.get("properties", {}).get("datetime", "")[:10]
            print(f"  Scene: {scene_id}  cloud={cloud_pct}%  date={date_str}")

            lwir = item.get("assets", {}).get("lwir11")
            if not lwir:
                print("    No lwir11 asset — skipping")
                continue

            href = lwir["href"]

            # Build output filename from scene_id
            # e.g. LC09_L2SP_193056_20240222_02_T1 → LC09_L2SP_193056_20240222_02_T1_ST_B10.TIF
            filename = scene_id + "_ST_B10.TIF"
            # Use actual filename from URL if it ends with _ST_B10.TIF
            url_filename = href.split("/")[-1]
            if url_filename.endswith("_ST_B10.TIF"):
                filename = url_filename

            out_path = city_dir / filename

            try:
                signed = sign_url(href)
                ok = download_file(signed, out_path)
                if ok:
                    save_scene_meta(city, item, out_path)
                    acquired += 1
                    time.sleep(0.5)
            except Exception as e:
                print(f"    Error: {e}")

        if acquired == 0:
            print(f"  Could not download any scenes for {city['name']}.")

    print("\nDone. Next step: python scripts/process_heatwatch.py")


if __name__ == "__main__":
    main()
