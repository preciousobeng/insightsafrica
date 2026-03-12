"""
run_crop_pipeline.py

Batch runner: fetch + process all MODIS NDVI composites for Ghana.
Covers both growing seasons across 2024 and 2025.

16-day DOY steps: 1, 17, 33, … 353  (~23 composites per year → 46 total)

Usage:
    python scripts/run_crop_pipeline.py            # full 2024 + 2025
    python scripts/run_crop_pipeline.py --year 2024
    python scripts/run_crop_pipeline.py --year 2024 --doy 177
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent

DOY_STEPS = list(range(1, 366, 16))   # 23 composites: 1,17,33,…,353
YEARS     = [2024, 2025]


def run(cmd: list) -> bool:
    """Run a subprocess, stream output, return True on success."""
    result = subprocess.run(cmd, cwd=SCRIPT_DIR.parent)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="Batch MODIS NDVI pipeline for Ghana")
    parser.add_argument("--year", type=int, help="Single year (default: 2024 + 2025)")
    parser.add_argument("--doy",  type=int, help="Single DOY (requires --year)")
    args = parser.parse_args()

    years = [args.year] if args.year else YEARS
    doys  = [args.doy]  if args.doy  else DOY_STEPS

    python = sys.executable
    total = len(years) * len(doys)
    done = skipped = failed = 0

    for year in years:
        for doy in doys:
            stem = f"ndvi_{year}_{doy:03d}_ghana"
            out_json = SCRIPT_DIR.parent / "data" / "processed" / f"{stem}.json"

            if out_json.exists():
                print(f"[skip] {stem} already processed")
                skipped += 1
                continue

            print(f"\n{'='*60}")
            print(f"[{done+skipped+failed+1}/{total}] Year {year}  DOY {doy:03d}")
            print(f"{'='*60}")

            # Step 1 — fetch
            ok = run([python, str(SCRIPT_DIR / "fetch_modis_ndvi.py"),
                      "--year", str(year), "--doy", str(doy)])
            if not ok:
                print(f"  [WARN] fetch failed for {year}/{doy:03d} — skipping")
                failed += 1
                continue

            # Step 2 — process
            ok = run([python, str(SCRIPT_DIR / "process_crop.py"),
                      "--year", str(year), "--doy", str(doy)])
            if not ok:
                print(f"  [WARN] process failed for {year}/{doy:03d}")
                failed += 1
                continue

            done += 1
            time.sleep(0.5)  # polite pause between NASA API calls

    print(f"\n{'='*60}")
    print(f"Done.  processed={done}  skipped={skipped}  failed={failed}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
