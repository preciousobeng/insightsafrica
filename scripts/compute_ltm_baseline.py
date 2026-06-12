"""
compute_ltm_baseline.py

Reads CHIRPS archive stats JSONs and computes the WMO standard Long-Term Mean
(LTM) baseline: monthly means and standard deviations over the 1991-2020
reference period, per district and per region.

Usage:
    python scripts/compute_ltm_baseline.py --country ghana
    python scripts/compute_ltm_baseline.py --country ghana --start 1991 --end 2020

Output:
    data/archive/ghana/ghana_ltm_1991_2020.json

Schema:
    {
      "country": "ghana",
      "reference_period": {"start": 1991, "end": 2020},
      "months": {
        "1": {
          "regions": {
            "Ashanti": {"mean": 12.3, "std": 4.1, "n": 30},
            ...
          },
          "districts": {
            "Kumasi|Ashanti": {"mean": 14.2, "std": 5.0, "n": 30},
            ...
          }
        },
        ...
      }
    }
"""

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent


def load_archive(country: str, ref_start: int, ref_end: int) -> dict:
    """
    Load all stats JSONs within the reference period.
    Returns nested dict: month (1-12) -> level -> area -> list of mean values.
    """
    stats_dir = BASE_DIR / "data" / "archive" / country / "stats"
    if not stats_dir.exists():
        raise FileNotFoundError(f"Archive stats directory not found: {stats_dir}")

    # month -> level -> area -> [values]
    accumulator: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    files_loaded = 0

    for json_file in sorted(stats_dir.glob(f"chirps-v2.0.*_{country}.json")):
        with open(json_file) as f:
            data = json.load(f)

        year  = data.get("year")
        month = data.get("month")

        if year is None or month is None:
            continue
        if not (ref_start <= year <= ref_end):
            continue

        zonal = data.get("zonal_stats", {})
        for level, areas in zonal.items():
            for area, s in areas.items():
                val = s.get("mean")
                if val is not None:
                    accumulator[month][level][area].append(val)

        files_loaded += 1

    print(f"Loaded {files_loaded} months within {ref_start}-{ref_end}", flush=True)
    return accumulator


def compute_baseline(accumulator: dict, ref_start: int, ref_end: int) -> dict:
    """Compute mean and std per month per level per area."""
    months_out = {}

    for month in range(1, 13):
        month_data = accumulator.get(month, {})
        levels_out = {}

        for level, areas in month_data.items():
            areas_out = {}
            for area, values in areas.items():
                if not values:
                    continue
                mean_val = statistics.mean(values)
                std_val  = statistics.stdev(values) if len(values) > 1 else 0.0
                areas_out[area] = {
                    "mean": round(mean_val, 2),
                    "std":  round(std_val,  2),
                    "n":    len(values),
                }
            levels_out[level] = areas_out

        months_out[str(month)] = levels_out

        total_areas = sum(len(v) for v in levels_out.values())
        print(f"  Month {month:02d}: {total_areas} areas across {list(levels_out.keys())}", flush=True)

    return {
        "country": None,
        "reference_period": {"start": ref_start, "end": ref_end},
        "months": months_out,
    }


def main():
    parser = argparse.ArgumentParser(description="Compute WMO LTM baseline from CHIRPS archive")
    parser.add_argument("--country", default="ghana")
    parser.add_argument("--start",   type=int, default=1991, help="Reference period start year")
    parser.add_argument("--end",     type=int, default=2020, help="Reference period end year")
    args = parser.parse_args()

    print(f"Computing LTM baseline: {args.country} | {args.start}-{args.end}", flush=True)

    accumulator = load_archive(args.country, args.start, args.end)
    baseline    = compute_baseline(accumulator, args.start, args.end)
    baseline["country"] = args.country

    out_path = BASE_DIR / "data" / "archive" / args.country / f"{args.country}_ltm_{args.start}_{args.end}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(baseline, f, separators=(",", ":"))

    size_kb = out_path.stat().st_size / 1024
    print(f"\nBaseline written: {out_path} ({size_kb:.1f} KB)", flush=True)


if __name__ == "__main__":
    main()
