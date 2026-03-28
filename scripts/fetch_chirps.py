"""
fetch_chirps.py

Downloads CHIRPS monthly rainfall GeoTIFF for a given country.
No authentication required.

Usage:
    python scripts/fetch_chirps.py --year 2024 --month 3
    python scripts/fetch_chirps.py --year 2024 --month 3 --country nigeria

CHIRPS data: https://data.chc.ucsb.edu/products/CHIRPS-2.0/
"""

import argparse
from pathlib import Path
import requests

COUNTRY_BBOXES = {
    "ghana": {
        "west": -3.2617, "east":  1.2166,
        "south": 4.7370, "north": 11.1748,
    },
    "nigeria": {
        "west":  2.668,  "east": 14.678,
        "south": 4.269,  "north": 13.872,
    },
    "ivorycoast": {
        "west": -8.601,  "east": -2.493,
        "south": 4.341,  "north": 10.740,
    },
    "senegal": {
        "west": -17.535, "east": -11.355,
        "south": 12.307, "north": 16.693,
    },
    "capeverde": {
        "west": -25.50, "east": -22.60,
        "south": 14.75, "north": 17.25,
    },
}

CHIRPS_BASE = "https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_monthly/tifs"
RAW_DIR = Path(__file__).parent.parent / "data" / "raw" / "chirps"


def build_url(year: int, month: int) -> str:
    filename = f"chirps-v2.0.{year}.{month:02d}.tif.gz"
    return f"{CHIRPS_BASE}/{filename}"


def download_chirps(year: int, month: int) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    url = build_url(year, month)
    gz_filename = url.split("/")[-1]
    gz_path = RAW_DIR / gz_filename
    tif_path = RAW_DIR / gz_filename.replace(".gz", "")

    if tif_path.exists():
        print(f"Already downloaded: {tif_path.name}")
        return tif_path

    print(f"Downloading: {url}")
    response = requests.get(url, stream=True, timeout=120)
    response.raise_for_status()
    with open(gz_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    print(f"Saved: {gz_path}")

    import gzip, shutil
    with gzip.open(gz_path, "rb") as f_in:
        with open(tif_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
    gz_path.unlink()
    print(f"Decompressed: {tif_path.name}")
    return tif_path


def clip_to_country(tif_path: Path, country: str) -> Path:
    """Clip a global GeoTIFF to the country bounding box."""
    import rasterio
    from rasterio.mask import mask
    from shapely.geometry import box

    bbox = COUNTRY_BBOXES[country]
    out_path = tif_path.parent / tif_path.name.replace(".tif", f"_{country}.tif")

    if out_path.exists():
        print(f"Clip already exists: {out_path.name}")
        return out_path

    country_geom = box(bbox["west"], bbox["south"], bbox["east"], bbox["north"])
    with rasterio.open(tif_path) as src:
        clipped, transform = mask(src, [country_geom], crop=True)
        profile = src.profile.copy()
        profile.update({"height": clipped.shape[1], "width": clipped.shape[2], "transform": transform})
        with rasterio.open(out_path, "w", **profile) as dst:
            dst.write(clipped)

    print(f"Clipped to {country}: {out_path.name}")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Fetch CHIRPS monthly rainfall")
    parser.add_argument("--year",    type=int, required=True, help="Year (e.g. 2024)")
    parser.add_argument("--month",   type=int, required=True, help="Month (1-12)")
    parser.add_argument("--country", choices=list(COUNTRY_BBOXES), default="ghana")
    args = parser.parse_args()

    tif_path = download_chirps(args.year, args.month)
    clipped  = clip_to_country(tif_path, args.country)
    print(f"\nDone. {args.country.title()} rainfall GeoTIFF: {clipped}")


if __name__ == "__main__":
    main()
