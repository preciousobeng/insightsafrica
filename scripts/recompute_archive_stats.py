"""
recompute_archive_stats.py

Re-runs zonal stats over already-downloaded clipped TIFFs in the archive,
overwriting the stats JSONs. Use after changing zonal_stats parameters
(e.g. all_touched=True) — avoids re-downloading any CHIRPS data.

Usage:
    python scripts/recompute_archive_stats.py --country ghana
"""

import argparse
import json
import re
from pathlib import Path

from fetch_chirps_archive import COUNTRY_BOUNDARIES, compute_stats

BASE_DIR = Path(__file__).parent.parent

TIF_RE = re.compile(r"chirps-v2\.0\.(\d{4})\.(\d{2})_(\w+)\.tif$")


def main():
    parser = argparse.ArgumentParser(description="Recompute zonal stats from existing archive TIFFs")
    parser.add_argument("--country", choices=list(COUNTRY_BOUNDARIES), default="ghana")
    args = parser.parse_args()

    country = args.country
    tifs_dir  = BASE_DIR / "data" / "archive" / country / "tifs"
    stats_dir = BASE_DIR / "data" / "archive" / country / "stats"
    stats_dir.mkdir(parents=True, exist_ok=True)

    tifs = sorted(tifs_dir.glob("chirps-v2.0.*.tif"))
    if not tifs:
        raise SystemExit(f"No TIFFs found in {tifs_dir}")

    print(f"Recomputing stats for {country}: {len(tifs)} months", flush=True)

    for i, tif in enumerate(tifs, 1):
        m = TIF_RE.search(tif.name)
        if not m:
            print(f"  Skipping unrecognised file: {tif.name}", flush=True)
            continue
        year, month = int(m.group(1)), int(m.group(2))

        zonal = compute_stats(tif, country)
        payload = {"country": country, "year": year, "month": month, "zonal_stats": zonal}

        out = stats_dir / f"chirps-v2.0.{year}.{month:02d}_{country}.json"
        with open(out, "w") as f:
            json.dump(payload, f, separators=(",", ":"))

        if i % 50 == 0 or i == len(tifs):
            print(f"  [{i}/{len(tifs)}] {year}-{month:02d}", flush=True)

    print("Done.", flush=True)


if __name__ == "__main__":
    main()
