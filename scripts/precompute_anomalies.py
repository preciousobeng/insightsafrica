"""
precompute_anomalies.py

Batch-computes anomaly JSONs for all months in the archive that have both
actual stats and a valid LTM baseline. Skips months already computed.

Usage:
    python scripts/precompute_anomalies.py --country ghana
    python scripts/precompute_anomalies.py --country ghana --force
"""

import argparse
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent

# Import from sibling script
sys.path.insert(0, str(Path(__file__).parent))
from compute_anomaly import load_baseline, compute_anomaly


def main():
    parser = argparse.ArgumentParser(description="Pre-compute anomaly JSONs for all archive months")
    parser.add_argument("--country",  default="ghana")
    parser.add_argument("--baseline", type=int, nargs=2, default=[1991, 2020],
                        metavar=("START", "END"))
    parser.add_argument("--force", action="store_true", help="Recompute even if output exists")
    args = parser.parse_args()

    ref_start, ref_end = args.baseline
    country = args.country

    stats_dir = BASE_DIR / "data" / "archive" / country / "stats"
    anomaly_dir = BASE_DIR / "data" / "archive" / country / "anomaly"
    anomaly_dir.mkdir(parents=True, exist_ok=True)

    stat_files = sorted(stats_dir.glob(f"chirps-v2.0.*_{country}.json"))
    if not stat_files:
        print(f"No archive stats found in {stats_dir}")
        sys.exit(1)

    print(f"Loading baseline {country} {ref_start}-{ref_end} ...", flush=True)
    baseline = load_baseline(country, ref_start, ref_end)

    done = skipped = failed = 0

    for stat_file in stat_files:
        with open(stat_file) as f:
            actual_data = json.load(f)

        year  = actual_data.get("year")
        month = actual_data.get("month")
        if year is None or month is None:
            continue

        out_path = anomaly_dir / f"chirps-v2.0.{year}.{month:02d}_{country}_anomaly.json"

        if out_path.exists() and not args.force:
            skipped += 1
            continue

        try:
            anomaly = compute_anomaly(actual_data, baseline, year, month)
            payload = {
                "country":          country,
                "year":             year,
                "month":            month,
                "reference_period": {"start": ref_start, "end": ref_end},
                "anomaly":          anomaly,
            }
            with open(out_path, "w") as f:
                json.dump(payload, f, separators=(",", ":"))
            done += 1
            if done % 50 == 0:
                print(f"  {done} done ({year}-{month:02d}) ...", flush=True)
        except Exception as e:
            print(f"  ERROR {year}-{month:02d}: {e}", flush=True)
            failed += 1

    print(f"\nDone: {done} computed, {skipped} skipped, {failed} failed out of {len(stat_files)} months")


if __name__ == "__main__":
    main()
