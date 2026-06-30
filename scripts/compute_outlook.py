#!/usr/bin/env python3
"""Seasonal Outlook / Prediction (Sprint 3) — implementation.

Required API:
- ORDER, SEASONAL_ORDER, BACKTEST_YEARS, MIN_YEARS (constants)
- tercile_category(value, history) -> str
- skill_score(model_rmse, clim_rmse) -> float
- climatology_forecast(window_totals) -> float
- compute_outlook(country, year, month) -> dict
"""

from __future__ import annotations

import json
import math
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

# statsmodels ARIMA (must be installed)
from statsmodels.tsa.arima.model import ARIMA

# ---------------------------------------------------------------------------
# Module-level constants (part of public API)
# ---------------------------------------------------------------------------
ORDER = (1, 0, 0)
SEASONAL_ORDER = (1, 0, 0, 12)
BACKTEST_YEARS = 10
MIN_YEARS = 20

# Default base directory (overridden by patching in tests)
BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def tercile_category(value: float, history: list[float]) -> str:
    """Classify value as 'below', 'near', or 'above' vs 33rd/67th percentiles."""
    arr = np.array(history)
    p33 = float(np.percentile(arr, 33.33))
    p67 = float(np.percentile(arr, 66.67))
    if value < p33:
        return "below"
    if value > p67:
        return "above"
    return "near"


def skill_score(model_rmse: float, clim_rmse: float) -> float:
    """Compute skill = 1 - model_rmse / clim_rmse.
    If clim_rmse is zero, return 0 (no improvement possible).
    """
    if clim_rmse == 0.0:
        return 0.0
    return 1.0 - model_rmse / clim_rmse


def climatology_forecast(window_totals: list[float]) -> float:
    """Mean of the historical 3-month totals."""
    return float(np.mean(window_totals))


def _target_window(year: int, month: int) -> tuple[list[tuple[int, int]], list[str]]:
    """Return (month_tuples, iso_strings) for the 3-month outlook target window.

    Issuing from (year, month) forecasts months M+1, M+2, M+3.
    """
    result_tuples = []
    result_strs = []
    for i in range(1, 4):
        y = year
        m = month + i
        if m > 12:
            y += 1
            m -= 12
        result_tuples.append((y, m))
        result_strs.append(f"{y:04d}-{m:02d}")
    return result_tuples, result_strs


def _read_monthly_archive(root: Path, country: str) -> dict[str, list[dict]]:
    """Read all monthly JSON files from the archive and return per-district series.

    Returns dict mapping district_name -> list of dicts with keys 'year','month','value'.
    """
    stats_dir = root / "data" / "archive" / country / "stats"
    if not stats_dir.is_dir():
        raise FileNotFoundError(f"Stats directory not found: {stats_dir}")

    district_data: dict[str, list[dict]] = {}
    for fpath in stats_dir.glob(f"chirps-v2.0.*_{country}.json"):
        with open(fpath, "r") as fh:
            record = json.load(fh)
        year = record["year"]
        month = record["month"]
        districts = record["zonal_stats"]["districts"]
        for dname, dvalue in districts.items():
            district_data.setdefault(dname, []).append({
                "year": year,
                "month": month,
                "value": dvalue["mean"]
            })
    return district_data


def _historical_window_totals(
    district_series: list[dict],
    target_months: list[tuple[int, int]],
    issue_year: int,
    issue_month: int
) -> list[float]:
    """Return list of 3-month total rainfall for each historical occurrence of the target
    window that is completely in the past (before the issue date).
    """
    lookup = {}
    for rec in district_series:
        lookup[(rec["year"], rec["month"])] = rec["value"]

    available = set(lookup.keys())
    totals = []
    # For each month in the series, check if it is the first month of a target window
    # that finishes before the issue date.
    for (y, m), val in lookup.items():
        # The target window months are given by target_months[0][1], [1][1], [2][1].
        # We need to find a historical occurrence where the months match.
        if m != target_months[0][1]:
            continue
        # Determine the next two months, handling year boundary
        ym1 = (y, m)
        ym2 = (y, m+1) if m < 12 else (y+1, 1)
        ym3 = (y, m+2) if m < 11 else (y+1, m-10)
        # Check that the month numbers of these two subsequent months match the target
        if ym2[1] != target_months[1][1] or ym3[1] != target_months[2][1]:
            continue
        if ym2 not in available or ym3 not in available:
            continue
        # Only include windows that end strictly before the issue date
        end_tuple = ym3
        if (end_tuple[0] < issue_year) or (end_tuple[0] == issue_year and end_tuple[1] < issue_month):
            total = lookup[ym1] + lookup[ym2] + lookup[ym3]
            totals.append(total)

    return totals


def _compute_district_outlook(district_series: list[dict],
                              target_months: list[tuple[int, int]],
                              issue_year: int,
                              issue_month: int,
                              n_years_backtest: int,
                              min_years: int) -> dict | None:
    """Compute outlook for one district. Returns dict or None if insufficient history."""
    lookup = {}
    for rec in district_series:
        lookup[(rec["year"], rec["month"])] = rec["value"]

    # Collect all historical 3-month window totals that end before the issue date.
    historical_totals = _historical_window_totals(
        district_series, target_months, issue_year, issue_month
    )

    if len(historical_totals) < min_years:
        return None  # insufficient history

    # Climatology forecast (mean of historical totals)
    clim_forecast = climatology_forecast(historical_totals)

    # Persistence: the most recent observed 3-month total ending at the issue month.
    m1 = (issue_year, issue_month - 2) if issue_month >= 3 else (issue_year - 1, issue_month + 10)
    m2 = (issue_year, issue_month - 1) if issue_month >= 2 else (issue_year - 1, issue_month + 11)
    m3 = (issue_year, issue_month)
    if (m1 in lookup) and (m2 in lookup) and (m3 in lookup):
        persistence_value = lookup[m1] + lookup[m2] + lookup[m3]
    else:
        persistence_value = clim_forecast

    # Build the monthly time series for SARIMA: all monthly values up to issue date.
    sorted_series = sorted(district_series, key=lambda x: (x["year"], x["month"]))
    series_values = []
    for rec in sorted_series:
        if (rec["year"], rec["month"]) <= (issue_year, issue_month):
            series_values.append(rec["value"])

    # ---- Skill: rolling-origin backtest ----
    rmse_model = 0.0
    rmse_clim = 0.0
    n_origins = 0

    for offset_y in range(1, n_years_backtest + 1):
        origin_year = issue_year - offset_y
        if origin_year < min(rec["year"] for rec in district_series):
            break
        origin_target_months, _ = _target_window(origin_year, issue_month)

        # Actual observed total for that target window
        if (origin_target_months[0] in lookup and
            origin_target_months[1] in lookup and
            origin_target_months[2] in lookup):
            actual = (lookup[origin_target_months[0]] +
                      lookup[origin_target_months[1]] +
                      lookup[origin_target_months[2]])
        else:
            continue

        # Data up to the origin's issue month
        origin_data = []
        for rec in district_series:
            if (rec["year"], rec["month"]) <= (origin_year, issue_month):
                origin_data.append(rec["value"])
        if len(origin_data) < min_years * 12:
            continue

        # Climatology for this origin (mean of all windows ending before origin's issue date)
        clim_origin_totals = _historical_window_totals(
            district_series, origin_target_months, origin_year, issue_month
        )
        clim_forecast_origin = climatology_forecast(clim_origin_totals) if clim_origin_totals else clim_forecast

        # Model forecast for this origin
        try:
            model = ARIMA(origin_data, order=ORDER, seasonal_order=SEASONAL_ORDER,
                          enforce_stationarity=False, enforce_invertibility=False)
            fitted = model.fit()
            forecast = fitted.forecast(steps=3)
            model_forecast = float(np.sum(forecast))
        except Exception:
            model_forecast = clim_forecast_origin  # fallback to origin climatology

        rmse_model += (model_forecast - actual) ** 2
        rmse_clim += (clim_forecast_origin - actual) ** 2
        n_origins += 1

    if n_origins > 0:
        rmse_model = math.sqrt(rmse_model / n_origins)
        rmse_clim = math.sqrt(rmse_clim / n_origins)
    else:
        rmse_model = 0.0
        rmse_clim = 1.0

    skill = skill_score(rmse_model, rmse_clim)

    # ---- SARIMA forecast for the current issue ----
    model_forecast_current = None
    if len(series_values) >= min_years * 12:
        try:
            model = ARIMA(series_values, order=ORDER, seasonal_order=SEASONAL_ORDER,
                          enforce_stationarity=False, enforce_invertibility=False)
            fitted = model.fit()
            forecast = fitted.forecast(steps=3)
            model_forecast_current = float(np.sum(forecast))
        except Exception:
            model_forecast_current = None

    # Determine issued forecast and method
    if skill > 0 and model_forecast_current is not None:
        issued_value = model_forecast_current
        method = "sarima"
    else:
        issued_value = clim_forecast
        method = "climatology_fallback"

    # Tercile bounds
    arr = np.array(historical_totals)
    p33 = round(float(np.percentile(arr, 33.33)), 1)
    p67 = round(float(np.percentile(arr, 66.67)), 1)

    # Category
    category = tercile_category(issued_value, historical_totals)

    result = {
        "issued_from": f"{issue_year:04d}-{issue_month:02d}",
        "target_window": [f"{ym[0]:04d}-{ym[1]:02d}" for ym in target_months],
        "forecast_3mo_mm": round(issued_value, 1),
        "category": category,
        "method": method,
        "skill_score": round(skill, 2),
        "benchmarks": {
            "climatology_mm": round(clim_forecast, 1),
            "persistence_mm": round(persistence_value, 1),
        },
        "tercile_bounds_mm": {
            "p33": p33,
            "p67": p67,
        },
        "n_years": len(historical_totals),
        "experimental": True,
    }
    result["_window_history"] = historical_totals  # for test C debugging

    return result


# ---------------------------------------------------------------------------
# Main compute_outlook function
# ---------------------------------------------------------------------------

def compute_outlook(country: str, year: int, month: int) -> dict:
    """Full pipeline: read archive, compute per-district outlook, return wrapper dict."""
    target_tuples, target_strs = _target_window(year, month)
    issued_from_str = f"{year:04d}-{month:02d}"

    district_map = _read_monthly_archive(BASE_DIR, country)

    districts_out = {}
    skipped_count = 0
    for dname, series in district_map.items():
        result = _compute_district_outlook(
            series,
            target_tuples,
            year,
            month,
            BACKTEST_YEARS,
            MIN_YEARS
        )
        if result is None:
            districts_out[dname] = {
                "issued_from": issued_from_str,
                "target_window": target_strs,
                "forecast_3mo_mm": None,
                "category": None,
                "method": None,
                "skill_score": None,
                "benchmarks": {"climatology_mm": None, "persistence_mm": None},
                "tercile_bounds_mm": {"p33": None, "p67": None},
                "n_years": 0,
                "experimental": True,
                "skip_reason": "insufficient_history"
            }
            skipped_count += 1
        else:
            districts_out[dname] = result

    wrapper = {
        "country": country,
        "issued_from": issued_from_str,
        "target_window": target_strs,
        "model": "outlook-v1",
        "params": {
            "order": list(ORDER),
            "seasonal_order": list(SEASONAL_ORDER),
            "backtest_years": BACKTEST_YEARS,
            "min_years": MIN_YEARS,
        },
        "experimental": True,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "skipped_districts": skipped_count,
        "districts": districts_out,
    }
    return wrapper


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def _main():
    import argparse
    parser = argparse.ArgumentParser(description="Seasonal Outlook v1")
    parser.add_argument("--country", required=True)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True)
    args = parser.parse_args()

    out = compute_outlook(args.country, args.year, args.month)

    out_dir = BASE_DIR / "data" / "archive" / args.country / "outlook"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"chirps-v2.0.{args.year:04d}.{args.month:02d}_{args.country}_outlook3.json"
    with open(out_path, "w") as fh:
        json.dump(out, fh, indent=2, sort_keys=True)
    print(f"Outlook written to {out_path}")


if __name__ == "__main__":
    _main()

