"""
compute_anomaly.py

For a given month/year, compares actual district rainfall against the WMO
1991-2020 LTM baseline and writes an anomaly JSON.

Usage:
    python scripts/compute_anomaly.py --country ghana --year 2024 --month 6
    python scripts/compute_anomaly.py --country ghana --year 2024 --month 6 --baseline 1991 2020

Output:
    data/archive/ghana/anomaly/chirps-v2.0.2024.06_ghana_anomaly.json

Schema per area:
    {
      "actual":    154.2,   # mm this month
      "ltm":       167.0,   # mm LTM mean for this calendar month
      "anomaly_mm":  -12.8, # actual - ltm
      "anomaly_pct": -7.7,  # ((actual - ltm) / ltm) * 100
      "std":         55.0,  # LTM std dev
      "z_score":     -0.23, # (actual - ltm) / std  (null if std == 0)
      "category":    "near_normal"
    }

Categories (based on anomaly_pct):
    severe_drought   < -50%
    moderate_drought  -50% to -25%
    mild_drought      -25% to -10%
    near_normal       -10% to +10%
    above_normal      +10% to +25%
    well_above_normal > +25%
"""

import argparse
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent


def categorise(pct: float) -> str:
    if pct < -50:
        return "severe_drought"
    if pct < -25:
        return "moderate_drought"
    if pct < -10:
        return "mild_drought"
    if pct <= 10:
        return "near_normal"
    if pct <= 25:
        return "above_normal"
    return "well_above_normal"


def load_baseline(country: str, ref_start: int, ref_end: int) -> dict:
    path = BASE_DIR / "data" / "archive" / country / f"{country}_ltm_{ref_start}_{ref_end}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Baseline not found: {path}\n"
            f"Run: python scripts/compute_ltm_baseline.py --country {country}"
        )
    with open(path) as f:
        return json.load(f)


def load_actual(country: str, year: int, month: int) -> dict:
    """Load zonal stats for the target month from the archive."""
    stats_dir = BASE_DIR / "data" / "archive" / country / "stats"
    path = stats_dir / f"chirps-v2.0.{year}.{month:02d}_{country}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Archive stats not found: {path}\n"
            f"Run: python scripts/fetch_chirps_archive.py --country {country} "
            f"--start {year}-{month:02d} --end {year}-{month:02d}"
        )
    with open(path) as f:
        return json.load(f)


def compute_anomaly(actual_data: dict, baseline: dict, year: int, month: int) -> dict:
    month_key = str(month)
    ltm_month = baseline["months"].get(month_key, {})
    actual_zonal = actual_data.get("zonal_stats", {})

    result_levels = {}

    for level, actual_areas in actual_zonal.items():
        ltm_areas = ltm_month.get(level, {})
        level_out = {}

        for area, actual_stats in actual_areas.items():
            actual_mm = actual_stats.get("mean")
            if actual_mm is None:
                continue

            ltm_entry = ltm_areas.get(area, {})
            ltm_mean  = ltm_entry.get("mean")
            ltm_std   = ltm_entry.get("std", 0.0)

            if ltm_mean is None or ltm_mean == 0:
                anomaly_mm  = None
                anomaly_pct = None
                z_score     = None
                category    = "no_baseline"
            else:
                anomaly_mm  = round(actual_mm - ltm_mean, 2)
                anomaly_pct = round((anomaly_mm / ltm_mean) * 100, 1)
                z_score     = round(anomaly_mm / ltm_std, 2) if ltm_std and ltm_std > 0 else None
                category    = categorise(anomaly_pct)

            level_out[area] = {
                "actual":      round(actual_mm, 2),
                "ltm":         ltm_mean,
                "anomaly_mm":  anomaly_mm,
                "anomaly_pct": anomaly_pct,
                "std":         ltm_std,
                "z_score":     z_score,
                "category":    category,
            }

        result_levels[level] = level_out
        counts = {}
        for v in level_out.values():
            c = v["category"]
            counts[c] = counts.get(c, 0) + 1
        print(f"  {level}: {len(level_out)} areas | {counts}", flush=True)

    return result_levels


def main():
    parser = argparse.ArgumentParser(description="Compute rainfall anomaly vs LTM baseline")
    parser.add_argument("--country",  default="ghana")
    parser.add_argument("--year",     type=int, required=True)
    parser.add_argument("--month",    type=int, required=True)
    parser.add_argument("--baseline", type=int, nargs=2, default=[1991, 2020],
                        metavar=("START", "END"))
    args = parser.parse_args()

    ref_start, ref_end = args.baseline
    country = args.country

    print(f"Anomaly: {country} {args.year}-{args.month:02d} vs LTM {ref_start}-{ref_end}", flush=True)

    baseline    = load_baseline(country, ref_start, ref_end)
    actual_data = load_actual(country, args.year, args.month)
    anomaly     = compute_anomaly(actual_data, baseline, args.year, args.month)

    out_dir = BASE_DIR / "data" / "archive" / country / "anomaly"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"chirps-v2.0.{args.year}.{args.month:02d}_{country}_anomaly.json"

    payload = {
        "country":          country,
        "year":             args.year,
        "month":            args.month,
        "reference_period": {"start": ref_start, "end": ref_end},
        "anomaly":          anomaly,
    }
    with open(out_path, "w") as f:
        json.dump(payload, f, separators=(",", ":"))

    print(f"\nWritten: {out_path} ({out_path.stat().st_size / 1024:.1f} KB)", flush=True)


if __name__ == "__main__":
    main()
