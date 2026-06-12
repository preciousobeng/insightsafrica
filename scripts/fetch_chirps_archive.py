"""
fetch_chirps_archive.py

Downloads CHIRPS monthly global TIFs, clips to a single country, computes
zonal statistics per admin boundary level, writes a compact stats JSON, then
deletes the raw TIF.  Designed to run as a long overnight job.

Usage:
    python scripts/fetch_chirps_archive.py --country ghana
    python scripts/fetch_chirps_archive.py --country ghana --start 1991-01 --end 2020-12
    python scripts/fetch_chirps_archive.py --country ghana --start 2024-01

Outputs (per month):
    data/archive/ghana/tifs/chirps-v2.0.YYYY.MM_ghana.tif   (clipped, kept)
    data/archive/ghana/stats/chirps-v2.0.YYYY.MM_ghana.json (compact zonal stats)

The global .tif.gz is deleted after clipping.
"""

import argparse
import gzip
import json
import shutil
import sys
import time
from datetime import date
from pathlib import Path

import requests
import rasterio
from rasterio.mask import mask as rio_mask
from rasterstats import zonal_stats
from shapely.geometry import box

BASE_DIR = Path(__file__).parent.parent
BOUNDARIES_DIR = BASE_DIR / "data" / "processed"

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
        "west": -25.50,  "east": -22.60,
        "south": 14.75,  "north": 17.25,
    },
    "southafrica": {
        "west": 16.0,    "east": 33.0,
        "south": -35.0,  "north": -22.0,
    },
}

COUNTRY_BOUNDARIES = {
    "ghana": {
        "regions":   BASE_DIR / "data" / "processed" / "ghana_regions.geojson",
        "districts": BASE_DIR / "data" / "processed" / "ghana_districts.geojson",
    },
    "nigeria": {
        "states": BASE_DIR / "data" / "processed_nigeria" / "nigeria_states.geojson",
        "lgas":   BASE_DIR / "data" / "processed_nigeria" / "nigeria_lgas.geojson",
    },
    "ivorycoast": {
        "districts": BASE_DIR / "data" / "processed_ivorycoast" / "ivorycoast_districts.geojson",
        "regions":   BASE_DIR / "data" / "processed_ivorycoast" / "ivorycoast_regions.geojson",
    },
    "senegal": {
        "regions":     BASE_DIR / "data" / "processed_senegal" / "senegal_regions.geojson",
        "departments": BASE_DIR / "data" / "processed_senegal" / "senegal_departments.geojson",
    },
    "capeverde": {
        "islands": BASE_DIR / "data" / "processed_capeverde" / "capeverde_islands.geojson",
    },
    "southafrica": {
        "provinces": BASE_DIR / "data" / "processed_southafrica" / "southafrica_provinces.geojson",
        "districts":  BASE_DIR / "data" / "processed_southafrica" / "southafrica_districts.geojson",
    },
}

CHIRPS_BASE = "https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_monthly/tifs"


def month_range(start: str, end: str):
    """Yield (year, month) tuples from start to end inclusive. Format: YYYY-MM."""
    sy, sm = int(start[:4]), int(start[5:7])
    ey, em = int(end[:4]),   int(end[5:7])
    y, m = sy, sm
    while (y, m) <= (ey, em):
        yield y, m
        m += 1
        if m > 12:
            m = 1
            y += 1


def download_global_tif(year: int, month: int, tmp_dir: Path) -> Path | None:
    filename = f"chirps-v2.0.{year}.{month:02d}.tif.gz"
    url = f"{CHIRPS_BASE}/{filename}"
    gz_path = tmp_dir / filename
    tif_path = tmp_dir / filename.replace(".gz", "")

    if tif_path.exists():
        return tif_path

    print(f"  Downloading {filename} ...", flush=True)
    try:
        resp = requests.get(url, stream=True, timeout=180)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  ERROR downloading {filename}: {e}", flush=True)
        return None

    with open(gz_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=65536):
            f.write(chunk)

    with gzip.open(gz_path, "rb") as f_in, open(tif_path, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    gz_path.unlink()
    return tif_path


def clip_to_country(global_tif: Path, country: str, out_path: Path) -> Path | None:
    if out_path.exists():
        return out_path

    bbox = COUNTRY_BBOXES[country]
    geom = box(bbox["west"], bbox["south"], bbox["east"], bbox["north"])

    try:
        with rasterio.open(global_tif) as src:
            clipped, transform = rio_mask(src, [geom], crop=True)
            profile = src.profile.copy()
            profile.update({
                "height": clipped.shape[1],
                "width":  clipped.shape[2],
                "transform": transform,
            })
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(out_path, "w", **profile) as dst:
            dst.write(clipped)
    except Exception as e:
        print(f"  ERROR clipping to {country}: {e}", flush=True)
        return None

    return out_path


def compute_stats(clipped_tif: Path, country: str) -> dict:
    """Compute zonal stats per boundary level. Returns dict keyed by level name."""
    result = {}
    for level, geojson_path in COUNTRY_BOUNDARIES[country].items():
        if not geojson_path.exists():
            print(f"  Skipping {level} — boundary file not found: {geojson_path}", flush=True)
            continue

        with open(geojson_path) as f:
            geojson = json.load(f)

        features = geojson.get("features", [])
        stats = zonal_stats(
            features,
            str(clipped_tif),
            stats=["mean", "max", "min"],
            nodata=-9999,
            geojson_out=False,
        )

        level_stats = {}
        for feature, stat in zip(features, stats):
            props = feature.get("properties", {})
            name = props.get("name", "Unknown")
            region = props.get("region", "")
            key = f"{name}|{region}" if region else name
            level_stats[key] = {
                "mean": round(stat["mean"], 2) if stat.get("mean") is not None else None,
                "max":  round(stat["max"],  2) if stat.get("max")  is not None else None,
                "min":  round(stat["min"],  2) if stat.get("min")  is not None else None,
            }

        result[level] = level_stats
        print(f"    {level}: {len(level_stats)} areas", flush=True)

    return result


def process_month_multi(year: int, month: int, countries: list, tmp_dir: Path) -> dict:
    """
    Download the global TIF once, then clip + compute stats for each country.
    Returns dict mapping country -> True/False.
    Skips countries whose output JSON already exists.
    """
    # Check which countries still need processing
    pending = []
    for country in countries:
        json_out = BASE_DIR / "data" / "archive" / country / "stats" / f"chirps-v2.0.{year}.{month:02d}_{country}.json"
        if json_out.exists():
            print(f"  {country}: already done, skipping", flush=True)
        else:
            pending.append(country)

    if not pending:
        return {c: True for c in countries}

    t0 = time.time()
    global_tif = download_global_tif(year, month, tmp_dir)
    if global_tif is None:
        return {c: False for c in pending}

    results = {c: True for c in countries}
    for country in pending:
        archive_dir = BASE_DIR / "data" / "archive" / country
        stem    = f"chirps-v2.0.{year}.{month:02d}_{country}"
        tif_out = archive_dir / "tifs"  / f"{stem}.tif"
        json_out = archive_dir / "stats" / f"{stem}.json"

        clipped = clip_to_country(global_tif, country, tif_out)
        if clipped is None:
            results[country] = False
            continue

        print(f"  [{country}] computing zonal stats ...", flush=True)
        zonal = compute_stats(clipped, country)
        payload = {"country": country, "year": year, "month": month, "zonal_stats": zonal}
        json_out.parent.mkdir(parents=True, exist_ok=True)
        with open(json_out, "w") as f:
            json.dump(payload, f, separators=(",", ":"))
        print(f"  [{country}] saved {json_out.name}", flush=True)

    global_tif.unlink(missing_ok=True)
    elapsed = time.time() - t0
    print(f"  {year}-{month:02d} completed in {elapsed:.0f}s", flush=True)
    return results


def main():
    today = date.today()
    default_end = f"{today.year}-{today.month:02d}"
    all_countries = list(COUNTRY_BBOXES.keys())

    parser = argparse.ArgumentParser(description="Fetch CHIRPS archive — one or multiple countries")
    parser.add_argument("--country",   choices=all_countries + ["all"], default=None,
                        help="Single country (or 'all')")
    parser.add_argument("--countries", nargs="+", choices=all_countries,
                        help="Multiple countries — shares each global TIF download")
    parser.add_argument("--start",  default="1981-01",   help="Start month YYYY-MM")
    parser.add_argument("--end",    default=default_end, help="End month YYYY-MM (inclusive)")
    args = parser.parse_args()

    if args.countries:
        countries = args.countries
    elif args.country == "all":
        countries = all_countries
    elif args.country:
        countries = [args.country]
    else:
        countries = ["ghana"]

    tmp_dir = BASE_DIR / "data" / "raw" / "chirps_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    months = list(month_range(args.start, args.end))
    print(f"Archive fetch: {', '.join(countries)} | {args.start} → {args.end} | {len(months)} months", flush=True)

    done = failed = 0
    for i, (year, month) in enumerate(months, 1):
        print(f"\n[{i}/{len(months)}] {year}-{month:02d}", flush=True)
        results = process_month_multi(year, month, countries, tmp_dir)
        done   += sum(1 for v in results.values() if v)
        failed += sum(1 for v in results.values() if not v)

    print(f"\nFinished: {done} done, {failed} failed out of {len(months) * len(countries)} total")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
