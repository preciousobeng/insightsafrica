#!/usr/bin/env python3
"""Compute SPI-3 (Standardised Precipitation Index, 3-month window) from CHIRPS
monthly rainfall data.

SPI-3 is the McKee et al. (1993), WMO-standard precipitation index using a
3-month rolling sum.  It fits a gamma distribution (with Thom zero-handling) to
the 1991-2020 reference period for each area and calendar month, converts the
observed 3-month sum to a cumulative probability via the fitted gamma, then maps
that probability through the inverse standard-normal CDF.

THIS IS NOT A Z-SCORE.  A z-score is (x-mean)/std; SPI is a gamma-based
probability transform.  Acceptance Test A (reference-period normality) will fail
a z-score implementation.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import re

import numpy as np
from scipy.stats import gamma, norm  # type: ignore[import-untyped]

BASE_DIR = Path(__file__).resolve().parent.parent
WMO_CATEGORIES = [
    (2.0, None, "extremely_wet"),
    (1.5, 1.99, "very_wet"),
    (1.0, 1.49, "moderately_wet"),
    (-0.99, 0.99, "near_normal"),
    (-1.49, -1.0, "moderately_dry"),
    (-1.99, -1.5, "severely_dry"),
    (None, -2.0, "extremely_dry"),
]
SPI_PLATEAU = 3.09  # clamp [-3.09, 3.09]

# Regex to extract YYYY.MM from stats filenames like
#   chirps-v2.0.2025.06_ghana.json
# The tail after the last version-like dot is always "{year}.{month}_{country}".
_FILENAME_DATE_RE = re.compile(r"\.(\d{4})\.(\d{2})_[a-z]+\.json$")


def _parse_year_month_from_filename(fpath: Path) -> tuple[int, int] | None:
    """Extract (year, month) from a chirps-v2.0 stats filename, or None."""
    m = _FILENAME_DATE_RE.search(fpath.name)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def categorise_spi(spi: float) -> str:
    """Return McKee / WMO SPI category label for a scalar SPI value."""
    for lo, hi, label in WMO_CATEGORIES:
        if (lo is None or spi >= lo) and (hi is None or spi <= hi):
            return label
    return "near_normal"  # fallback (shouldn't reach)


def _year_month_index(year: int, month: int) -> int:
    """Return a monotonic integer key for chronological ordering."""
    return year * 12 + (month - 1)


# ---------------------------------------------------------------------------
# data ingestion
# ---------------------------------------------------------------------------


def _read_all_stats(country: str) -> dict[tuple[int, int], dict[str, Any]]:
    """Read every CHIRPS-v2.0 monthly stats file for *country*.

    Returns dict  ``(year, month) -> parsed JSON``.
    """
    stats_dir = BASE_DIR / "data" / "archive" / country / "stats"
    if not stats_dir.is_dir():
        raise FileNotFoundError(
            f"Stats directory not found: {stats_dir}\n"
            f"Run scripts/compute_ltm_baseline.py and "
            f"scripts/compute_anomaly.py first to generate input files."
        )

    result: dict[tuple[int, int], dict[str, Any]] = {}
    for fpath in sorted(stats_dir.glob("chirps-v2.0.*_*.json")):
        ym = _parse_year_month_from_filename(fpath)
        if ym is None:
            continue
        year, month = ym
        with open(fpath, encoding="utf-8") as fh:
            result[(year, month)] = json.load(fh)
    return result


def _build_monthly_series(
    stats: dict[tuple[int, int], dict[str, Any]],
) -> dict[str, list[tuple[int, int, float]]]:
    """Return per-area monthly rainfall series from raw stats.

    Key = ``"level_name|area_name"`` (pipe-separated to avoid collisions).
    Each value is a chronologically sorted list of ``(year, month, mean_mm)``.
    """
    series: dict[str, list[tuple[int, int, float]]] = defaultdict(list)
    for (year, month), data in sorted(stats.items()):
        zonal = data.get("zonal_stats", {})
        for level_name, areas in zonal.items():
            for area_name, vals in areas.items():
                mean = vals.get("mean")
                if mean is None:
                    # Small areas under a CHIRPS pixel can have a null mean — treat
                    # as a missing month (the 3-month sum will skip it), not zero.
                    continue
                key = f"{level_name}|{area_name}"
                series[key].append((year, month, float(mean)))
    return series


# ---------------------------------------------------------------------------
# 3-month rolling sum
# ---------------------------------------------------------------------------


def _three_month_sum(
    lookup: dict[tuple[int, int], float],
    year: int,
    month: int,
) -> float | None:
    """Compute sum of *month*, *month-1*, *month-2* rainfall.

    Returns ``None`` if any of the three months is missing (insufficient data).
    Spans year boundary correctly (e.g. Feb 2024 uses Dec 2023 + Jan 2024 +
    Feb 2024).
    """
    months_needed: list[tuple[int, int]] = []
    for offset in (2, 1, 0):  # oldest first
        ym = year
        mm = month - offset
        while mm <= 0:
            mm += 12
            ym -= 1
        months_needed.append((ym, mm))

    vals = [lookup.get(m) for m in months_needed]
    if any(v is None for v in vals):
        return None
    return round(sum(vals), 1)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# gamma fit + SPI transform
# ---------------------------------------------------------------------------


def _fit_gamma_zero_adjusted(
    ref_vals: list[float],
) -> dict[str, float]:
    """Fit gamma distribution to *ref_vals* using Thom zero-handling.

    Returns a fit dict with **full-precision** shape & scale.
    Call ``_round_fit_for_output()`` to get the display-ready version for the
    JSON output block.
    """
    n = len(ref_vals)
    if n == 0:
        return {"shape": 0.0, "scale": 0.0, "p_zero": 0.0, "n_ref": 0}

    non_zero = np.array([float(v) for v in ref_vals if v > 0], dtype=np.float64)
    nz = len(non_zero)
    q = float((n - nz) / n)

    fit: dict[str, float] = {"p_zero": q, "n_ref": float(n)}

    if nz >= 3:
        try:
            shape, _loc, scale = gamma.fit(non_zero, floc=0)
            fit["shape"] = float(shape)
            fit["scale"] = float(scale)
        except Exception:
            # MLE fit failed (e.g. degenerate data) — fall back to MoM
            non_zero = non_zero[:2] if len(non_zero) >= 2 else non_zero
            m = float(np.mean(non_zero))
            v = float(np.var(non_zero)) if len(non_zero) > 1 else m * 0.1
            if m <= 0:
                m = 1e-6
            if v <= 0:
                v = 1e-6
            fit["shape"] = float(m * m / v) if v > 0 else 0.0
            fit["scale"] = float(v / m) if m > 0 else 0.0
    elif nz > 0:
        # Too few non-zeros for MLE — method of moments
        m = float(np.mean(non_zero))
        v = float(np.var(non_zero)) if nz > 1 else m * 0.1
        if m <= 0:
            m = 1e-6
        if v <= 0:
            v = 1e-6
        fit["shape"] = float(m * m / v) if v > 0 else 0.0
        fit["scale"] = float(v / m) if m > 0 else 0.0
    else:
        # All reference values are zero — gamma is degenerate
        fit["shape"] = 0.0
        fit["scale"] = 0.0

    return fit


def _round_fit_for_output(fit: dict[str, float]) -> dict[str, float]:
    """Return display-ready fit block with shape/scale rounded to 2 dp."""
    return {
        "shape": round(fit["shape"], 2),
        "scale": round(fit["scale"], 2),
        "p_zero": round(fit["p_zero"], 4),
        "n_ref": int(fit["n_ref"]),
    }


def _spi_from_fit(sum_3mo: float, fit: dict[str, float]) -> float:
    """Compute SPI for *sum_3mo* given a pre-computed gamma fit dict.

    H(x) = p_zero + (1-p_zero) * GammaCDF(x ; shape, scale, floc=0)
    SPI  = inverseNormalCDF(H(x))
    Clamped to [-3.09, 3.09].
    """
    q = fit["p_zero"]
    shape = fit.get("shape", 0.0)
    scale = fit.get("scale", 0.0)

    # ---- compute H(x) ----------------------------------------------------
    if sum_3mo <= 0:
        h = q
    elif shape <= 0 or scale <= 0:
        # Degenerate gamma – treat any positive observation as extreme wet
        h = 1.0
    else:
        cdf = float(gamma.cdf(sum_3mo, a=shape, loc=0, scale=scale))
        h = q + (1.0 - q) * cdf

    # ---- inverse normal (clamped to avoid ±inf at extremes) ---------------
    eps = 1e-10
    h_clipped = float(np.clip(h, eps, 1.0 - eps))
    spi = float(norm.ppf(h_clipped))
    return round(float(np.clip(spi, -SPI_PLATEAU, SPI_PLATEAU)), 2)


# ---------------------------------------------------------------------------
# core computation
# ---------------------------------------------------------------------------


def compute_spi3(
    country: str,
    year: int,
    month: int,
    window: int = 3,
    baseline_start: int = 1991,
    baseline_end: int = 2020,
) -> dict[str, Any]:
    """Compute SPI-3 for a single target month.

    Returns the full JSON-serialisable result dict (matches section 4 of the
    SPI-3 brief).
    """
    if window != 3:
        raise NotImplementedError("Only window=3 is implemented in Sprint 1")

    # ---- 1. read all raw stats --------------------------------------------
    raw = _read_all_stats(country)

    # ---- 2. build contiguous per-area monthly series -----------------------
    series = _build_monthly_series(raw)

    # Perf: pre-compute a flat lookup  area_key -> (ym_idx -> mm_rainfall)
    # and keep a list of (ym_idx, year, month) for filtering.
    area_lookup: dict[str, dict[tuple[int, int], float]] = {}
    area_data: dict[str, list[tuple[int, int, float]]] = {}
    for key, vals in series.items():
        data_pts = sorted(vals, key=lambda x: _year_month_index(x[0], x[1]))
        area_data[key] = data_pts
        area_lookup[key] = {(y, m): v for y, m, v in data_pts}

    # ---- 3. compute 3-month sums for every available month per area --------
    # sum_series[key] = list of (year, month, sum_3mo or None)
    sum_series: dict[str, list[tuple[int, int, float | None]]] = {}
    for key, pts in area_data.items():
        row: list[tuple[int, int, float | None]] = []
        for y, m, _v in pts:
            sm = _three_month_sum(area_lookup[key], y, m)
            row.append((y, m, sm))
        sum_series[key] = row

    # ---- 4. build reference-period catalogue per area per calendar month ---
    # ref_fits[(area_key, calendar_month)] = fit dict
    ref_fits: dict[tuple[str, int], dict[str, float]] = {}
    for key, rows in sum_series.items():
        # collect 3-month sums by calendar month within reference period
        ref_by_cal_month: dict[int, list[float]] = defaultdict(list)
        for y, m, sm in rows:
            if baseline_start <= y <= baseline_end and sm is not None:
                ref_by_cal_month[m].append(sm)

        for cal_m, vals in ref_by_cal_month.items():
            ref_fits[(key, cal_m)] = _fit_gamma_zero_adjusted(vals)

    # ---- 5. compute SPI for the target month per area ---------------------
    result_zonal: dict[str, dict[str, dict[str, Any]]] = {}
    num_skipped = 0

    for key, rows in sum_series.items():
        level_name, area_name = key.split("|", 1)
        target = None
        for y, m, sm in rows:
            if y == year and m == month:
                target = sm
                break

        if target is None:
            # No 3-month sum available for this area-month
            entry: dict[str, Any] = {
                "sum_3mo": None,
                "spi3": None,
                "category": None,
                "window": window,
                "months_used": _format_months_used(year, month),
                "fit": None,
                "skip_reason": "insufficient_data",
            }
            num_skipped += 1
        else:
            cal_m = month
            fit = ref_fits.get((key, cal_m))
            if fit is None or fit["n_ref"] == 0:
                entry = {
                    "sum_3mo": target,
                    "spi3": None,
                    "category": None,
                    "window": window,
                    "months_used": _format_months_used(year, month),
                    "fit": _round_fit_for_output(fit) if fit else None,
                    "skip_reason": "no_reference_data",
                }
                num_skipped += 1
            else:
                spi_val = _spi_from_fit(target, fit)
                entry = {
                    "sum_3mo": target,
                    "spi3": spi_val,
                    "category": categorise_spi(spi_val),
                    "window": window,
                    "months_used": _format_months_used(year, month),
                    "fit": _round_fit_for_output(fit),
                }

        result_zonal.setdefault(level_name, {})[area_name] = entry

    generated_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "country": country,
        "year": year,
        "month": month,
        "window": window,
        "reference_period": {"start": baseline_start, "end": baseline_end},
        "generated_utc": generated_utc,
        "skipped_areas": num_skipped,
        "zonal_stats": result_zonal,
    }


def _format_months_used(year: int, month: int) -> list[str]:
    """Return ['YYYY-MM', ...] for the three-month window ending *year*-*month*."""
    result: list[str] = []
    for offset in (2, 1, 0):
        ym = year
        mm = month - offset
        while mm <= 0:
            mm += 12
            ym -= 1
        result.append(f"{ym:04d}-{mm:02d}")
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute SPI-3 from CHIRPS monthly rainfall data."
    )
    parser.add_argument(
        "--country", required=True, type=str, help="Country code, e.g. ghana"
    )
    parser.add_argument("--year", required=True, type=int, help="Target year")
    parser.add_argument("--month", required=True, type=int, help="Target month (1-12)")
    parser.add_argument(
        "--window",
        type=int,
        default=3,
        help="SPI window in months (default: 3; only 3 is implemented in Sprint 1)",
    )
    parser.add_argument(
        "--baseline",
        nargs=2,
        type=int,
        default=[1991, 2020],
        metavar=("START", "END"),
        help="Reference-period start and end years (default: 1991 2020)",
    )
    args = parser.parse_args()

    if not (1 <= args.month <= 12):
        parser.error("month must be 1-12")

    result = compute_spi3(
        country=args.country,
        year=args.year,
        month=args.month,
        window=args.window,
        baseline_start=args.baseline[0],
        baseline_end=args.baseline[1],
    )

    # Write output
    out_dir = BASE_DIR / "data" / "archive" / args.country / "spi"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_name = (
        f"chirps-v2.0.{args.year:04d}.{args.month:02d}_{args.country}_spi3.json"
    )
    out_path = out_dir / out_name

    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, sort_keys=True, ensure_ascii=False)
        fh.write("\n")

    print(f"SPI-3 written to {out_path}")
    if result["skipped_areas"]:
        print(f"  ({result['skipped_areas']} area(s) skipped — insufficient data)")


if __name__ == "__main__":
    main()
