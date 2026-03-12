"""
fetch_modis_ndvi.py

Downloads MODIS MOD13Q1 NDVI 16-day composite for Ghana or Nigeria.
Resolution: 250m. Free via NASA Earthdata (same account as IMERG).

Product: MOD13Q1.061 — Vegetation Indices 16-Day L3 Global 250m

Auth: NASA Earthdata account — https://urs.earthdata.nasa.gov/
Set in .env:
    NASA_EARTHDATA_USER=your_username
    NASA_EARTHDATA_PASSWORD=your_password

Usage:
    python scripts/fetch_modis_ndvi.py --year 2024 --doy 177
    python scripts/fetch_modis_ndvi.py --year 2024 --doy 177 --country nigeria
    (doy = day of year, 16-day steps: 1,17,33,...,353)
"""

import argparse
import os
from pathlib import Path
import requests
from dotenv import load_dotenv

load_dotenv()

RAW_DIR = Path(__file__).parent.parent / "data" / "raw" / "modis_ndvi"

# MODIS CMR search
CMR_SEARCH = "https://cmr.earthdata.nasa.gov/search/granules.json"

# MODIS 16-day DOY steps
DOY_STEPS = list(range(1, 366, 16))

COUNTRY_BBOXES = {
    "ghana":   {"west": -3.2617, "east": 1.2166, "south": 4.7370, "north": 11.1748},
    "nigeria": {"west":  2.668,  "east": 14.678, "south": 4.269,  "north": 13.872},
}

# MODIS tiles needed per country
# Ghana spans h17v07 + h17v08 (western column only)
# Nigeria spans h17v07/h17v08 (west) + h18v07/h18v08 (east) — 2×2 mosaic
COUNTRY_TILES = {
    "ghana":   ["h17v07", "h17v08"],
    "nigeria": ["h17v07", "h17v08", "h18v07", "h18v08"],
}

# Key farming regions per country
FARMING_REGIONS = {
    "ghana": [
        {"name": "Northern Region", "bbox": [-2.8,  9.0, 0.2, 11.0]},
        {"name": "Brong-Ahafo",     "bbox": [-2.8,  7.0, 0.0,  9.0]},
        {"name": "Volta Region",    "bbox": [-0.2,  6.0, 1.2,  8.5]},
        {"name": "Upper East",      "bbox": [-0.6, 10.2, 1.2, 11.2]},
        {"name": "Upper West",      "bbox": [-2.8, 10.0,-0.8, 11.2]},
    ],
    "nigeria": [
        {"name": "Kano Plains",          "bbox": [7.5, 11.5,  9.5, 12.8]},
        {"name": "Middle Belt (Benue)",  "bbox": [7.5,  7.0,  9.5,  9.0]},
        {"name": "Sokoto Basin",         "bbox": [4.5, 12.0,  6.5, 13.5]},
        {"name": "Anambra/Cross River",  "bbox": [6.5,  5.5,  9.5,  7.0]},
        {"name": "Niger River Valley",   "bbox": [4.5,  9.0,  7.0, 11.5]},
    ],
}


def search_granules(year: int, doy: int, country: str) -> list:
    """Search CMR for MODIS MOD13Q1 granules covering a country."""
    from datetime import datetime, timedelta

    # Compute the actual calendar date for this DOY and search ±1 day.
    target_date = datetime(year, 1, 1) + timedelta(days=doy - 1)
    date_start  = target_date.strftime("%Y-%m-%d")
    date_end    = (target_date + timedelta(days=1)).strftime("%Y-%m-%d")

    bbox = COUNTRY_BBOXES[country]
    tiles = COUNTRY_TILES[country]

    params = {
        "short_name":   "MOD13Q1",
        "version":      "061",
        "temporal":     f"{date_start},{date_end}",
        "bounding_box": f"{bbox['west']},{bbox['south']},{bbox['east']},{bbox['north']}",
        "page_size":    "40",
    }

    resp = requests.get(CMR_SEARCH, params=params, timeout=30)
    resp.raise_for_status()
    entries = resp.json().get("feed", {}).get("entry", [])

    doy_str = f"A{year}{doy:03d}"
    return [
        e for e in entries
        if doy_str in e.get("title", "")
        and any(t in e.get("title", "") for t in tiles)
    ]


def get_earthdata_token(user: str, password: str) -> str:
    """
    Fetch or create a NASA Earthdata Bearer token.
    NASA download servers redirect through OAuth — Basic auth is dropped on
    cross-domain hops.  Bearer tokens survive the redirect chain.
    """
    token_url = "https://urs.earthdata.nasa.gov/api/users/tokens"
    resp = requests.get(token_url, auth=(user, password), timeout=30)
    resp.raise_for_status()
    tokens = resp.json()
    if tokens:
        return tokens[0]["access_token"]

    # No existing token — create one
    create_url = "https://urs.earthdata.nasa.gov/api/users/token"
    resp = requests.post(create_url, auth=(user, password), timeout=30)
    resp.raise_for_status()
    return resp.json()["access_token"]


def download_granule(granule: dict, token: str) -> Path:
    """Download a MODIS HDF granule file using a Bearer token."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    links = [l["href"] for l in granule.get("links", [])
             if l.get("rel") == "http://esipfed.org/ns/fedsearch/1.1/data#"]
    if not links:
        raise ValueError("No download link found for granule")

    url = links[0]
    filename = url.split("/")[-1]
    out_path = RAW_DIR / filename

    if out_path.exists():
        print(f"  Already downloaded: {filename}")
        return out_path

    print(f"  Downloading: {filename}")
    headers = {"Authorization": f"Bearer {token}"}
    session = requests.Session()

    with session.get(url, headers=headers, stream=True,
                     timeout=300, allow_redirects=True) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        downloaded = 0
        with open(out_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 512):
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    print(f"\r  {downloaded/total*100:.0f}%", end="", flush=True)
    print()
    print(f"  Saved: {filename}")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Fetch MODIS NDVI for a country")
    parser.add_argument("--year",    type=int, required=True)
    parser.add_argument("--doy",     type=int, required=True, help="Day of year (1,17,33,...)")
    parser.add_argument("--country", choices=list(COUNTRY_BBOXES), default="ghana")
    args = parser.parse_args()

    user     = os.getenv("NASA_EARTHDATA_USER")
    password = os.getenv("NASA_EARTHDATA_PASSWORD")

    if not user or not password:
        print("NASA_EARTHDATA_USER / NASA_EARTHDATA_PASSWORD not set in .env")
        print("Register free at: https://urs.earthdata.nasa.gov/")
        return

    print("Authenticating with NASA Earthdata…")
    token = get_earthdata_token(user, password)
    print("Authenticated.\n")

    print(f"Searching for MODIS NDVI: {args.country.title()}, Year {args.year}, DOY {args.doy:03d}")
    granules = search_granules(args.year, args.doy, args.country)

    if not granules:
        print("No granules found. Try adjacent DOY values.")
        return

    print(f"Found {len(granules)} granule(s).")
    for g in granules:
        download_granule(g, token)

    print(f"\nNext step: run process_crop.py --country {args.country} to extract NDVI")


if __name__ == "__main__":
    main()
