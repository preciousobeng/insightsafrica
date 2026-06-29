"""Acceptance tests for SPI-3 computation — tests/test_spi.py.

Tests A–G as defined in docs/brief-spi3-2026-06-29.md, section 6.

Run:
    ./venv/bin/python -m pytest tests/test_spi.py -v
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from scipy.stats import gamma, norm

# Ensure the project root is on sys.path so we can import the script.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

# Import the SPI module under test.
import scripts.compute_spi as spi_mod  # type: ignore[import-not-found]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_stats_json(year: int, month: int, zonal: dict) -> dict:
    """Minimal stats file payload."""
    return {"year": year, "month": month, "zonal_stats": zonal}


def _seed_stats_dir(root: Path, country: str, entries: list[tuple[int, int, dict]]):
    """Create a ``data/archive/<country>/stats/`` dir tree and write stats files."""
    stats_dir = root / "data" / "archive" / country / "stats"
    stats_dir.mkdir(parents=True, exist_ok=True)
    for year, month, zonal in entries:
        fname = f"chirps-v2.0.{year:04d}.{month:02d}_{country}.json"
        with open(stats_dir / fname, "w", encoding="utf-8") as fh:
            json.dump(_make_stats_json(year, month, zonal), fh)


def _spi_reference_impl(ref_vals: list[float], obs: float) -> float:
    """Standalone SPI-3 reference using the same Thom algorithm.

    Used by Test C for an independent cross-check.  Returns the computed SPI
    value (unclamped) so we can compare within ±0.05.
    """
    n = len(ref_vals)
    non_zero = np.array([v for v in ref_vals if v > 0], dtype=np.float64)
    nz = len(non_zero)
    q = (n - nz) / n if n > 0 else 0.0

    if obs <= 0:
        h = q
    elif nz < 3:
        # Not enough data for MLE – use MoM as fallback (mirrors compute_spi)
        if nz > 0:
            m = float(np.mean(non_zero))
            v = float(np.var(non_zero)) if nz > 1 else m * 0.1
            if m <= 0:
                m = 1e-6
            if v <= 0:
                v = 1e-6
            scale = v / m
            shape = m / scale
            h = q + (1.0 - q) * float(gamma.cdf(obs, a=shape, loc=0, scale=scale))
        else:
            h = 1.0
    else:
        shape, _loc, scale = gamma.fit(non_zero, floc=0)
        h = q + (1.0 - q) * float(gamma.cdf(obs, a=shape, loc=0, scale=scale))

    eps = 1e-10
    h = float(np.clip(h, eps, 1.0 - eps))
    return float(norm.ppf(h))


def _all_spi_values(output: dict) -> list[float]:
    """Return every non-null ``spi3`` value from a SPI output dict."""
    vals: list[float] = []
    for level_data in output["zonal_stats"].values():
        for entry in level_data.values():
            if entry.get("spi3") is not None:
                vals.append(float(entry["spi3"]))
    return vals


# ---------------------------------------------------------------------------
# Test A — Reference-period normality
# ---------------------------------------------------------------------------


class TestA_ReferencePeriodNormality:
    """By construction, SPI-3 values of the 1991–2020 reference set must be
    approximately standard normal: |mean| < 0.10 and 0.85 < std < 1.15."""

    @pytest.mark.slow
    def test_reference_normality(self):
        """Run SPI across Ghana districts × 12 months and verify normality."""
        # This test requires the full Ghana CHIRPS archive on disk.
        stats_dir = _PROJECT_ROOT / "data" / "archive" / "ghana" / "stats"
        if not stats_dir.is_dir():
            pytest.skip("Ghana stats archive not available")

        # Assemble the reference-set SPI directly (read files ONCE): for each
        # (area, calendar-month) fit the gamma to the ~30 reference 3-month sums
        # and transform those same sums. Looping compute_spi3 over 30 years would
        # re-read all 544 stats files 360x.
        raw = spi_mod._read_all_stats("ghana")
        series = spi_mod._build_monthly_series(raw)
        all_spi: list[float] = []
        for vals in series.values():
            lookup = {(y, m): v for y, m, v in vals}
            for cal_m in range(1, 13):
                sums = [
                    spi_mod._three_month_sum(lookup, y, cal_m)
                    for y in range(1991, 2021)
                ]
                sums = [s for s in sums if s is not None]
                if len(sums) < 20:
                    continue
                fit = spi_mod._fit_gamma_zero_adjusted(sums)
                if fit["n_ref"] == 0:
                    continue
                all_spi.extend(spi_mod._spi_from_fit(s, fit) for s in sums)

        assert len(all_spi) > 0, "No SPI values produced"
        mean_val = float(np.mean(all_spi))
        std_val = float(np.std(all_spi))
        assert abs(mean_val) < 0.10, f"mean={mean_val:.4f} not within ±0.10"
        assert 0.85 < std_val < 1.15, f"std={std_val:.4f} not in (0.85, 1.15)"


# ---------------------------------------------------------------------------
# Test B — Range & completeness
# ---------------------------------------------------------------------------


class TestB_RangeAndCompleteness:
    def test_range(self):
        """Every SPI value is finite, within [-3.09, 3.09], no NaN/inf."""
        stats_dir = _PROJECT_ROOT / "data" / "archive" / "ghana" / "stats"
        if not stats_dir.is_dir():
            pytest.skip("Ghana stats archive not available")

        out = spi_mod.compute_spi3(
            country="ghana", year=2025, month=6, baseline_start=1991, baseline_end=2020
        )
        for level_name, areas in out["zonal_stats"].items():
            for area_name, entry in areas.items():
                spi_val = entry.get("spi3")
                if spi_val is None:
                    assert entry.get("skip_reason"), (
                        f"null SPI for {area_name} without skip_reason"
                    )
                else:
                    assert np.isfinite(spi_val), f"non-finite SPI for {area_name}"
                    assert -3.09 <= spi_val <= 3.09, (
                        f"SPI={spi_val} out of [-3.09, 3.09] for {area_name}"
                    )

    def test_completeness(self):
        """Every area in the source stats is present in the SPI output."""
        stats_dir = _PROJECT_ROOT / "data" / "archive" / "ghana" / "stats"
        if not stats_dir.is_dir():
            pytest.skip("Ghana stats archive not available")

        # Read the target month's source stats
        src_path = stats_dir / "chirps-v2.0.2025.06_ghana.json"
        if not src_path.exists():
            pytest.skip("Target month stats file not found")
        with open(src_path, encoding="utf-8") as fh:
            src = json.load(fh)

        out = spi_mod.compute_spi3(
            country="ghana", year=2025, month=6, baseline_start=1991, baseline_end=2020
        )

        for level_name, areas in src["zonal_stats"].items():
            out_areas = out["zonal_stats"].get(level_name, {})
            for area_name in areas:
                assert area_name in out_areas, (
                    f"{area_name} ({level_name}) missing from SPI output"
                )


# ---------------------------------------------------------------------------
# Test C — Independent cross-check
# ---------------------------------------------------------------------------


class TestC_IndependentCrossCheck:
    def test_cross_check_random(self):
        """For 5 random area-months, agree with standalone reference ±0.05."""
        stats_dir = _PROJECT_ROOT / "data" / "archive" / "ghana" / "stats"
        if not stats_dir.is_dir():
            pytest.skip("Ghana stats archive not available")

        rng = np.random.RandomState(42)

        # Gather all areas from a known month
        src_path = stats_dir / "chirps-v2.0.2025.06_ghana.json"
        if not src_path.exists():
            pytest.skip("2025-06 stats file not found")
        with open(src_path, encoding="utf-8") as fh:
            src = json.load(fh)

        # Pick 5 random (level, area) pairs
        candidates = []
        for lvl, areas in src["zonal_stats"].items():
            for area in areas:
                candidates.append((lvl, area))
        chosen = [
            candidates[i]
            for i in rng.choice(len(candidates), size=min(5, len(candidates)), replace=False)
        ]

        for level_name, area_name in chosen:
            out = spi_mod.compute_spi3(
                country="ghana",
                year=2025,
                month=6,
                baseline_start=1991,
                baseline_end=2020,
            )
            entry = out["zonal_stats"][level_name][area_name]
            if entry.get("spi3") is None:
                continue  # skipped — can't cross-check

            # Build reference set for this area-month from the archive
            ref_vals: list[float] = []
            for y in range(1991, 2021):
                fpath = stats_dir / f"chirps-v2.0.{y:04d}.{6:02d}_ghana.json"
                if not fpath.exists():
                    continue
                with open(fpath, encoding="utf-8") as fh:
                    month_data = json.load(fh)
                area_data = month_data["zonal_stats"].get(level_name, {}).get(area_name)
                if area_data is None:
                    continue
                # Need 3-month sum for the reference month
                lookup = {(y, 6): area_data["mean"]}
                # crude: just load previous 2 months
                for offset in (1, 2):
                    mm = 6 - offset
                    yy = y
                    if mm <= 0:
                        mm += 12
                        yy -= 1
                    prev_path = (
                        stats_dir / f"chirps-v2.0.{yy:04d}.{mm:02d}_ghana.json"
                    )
                    if prev_path.exists():
                        with open(prev_path, encoding="utf-8") as fh2:
                            pd = json.load(fh2)
                        pa = pd["zonal_stats"].get(level_name, {}).get(area_name)
                        if pa:
                            lookup[(yy, mm)] = pa["mean"]
                sm = (
                    lookup.get((y, 6), 0)
                    + lookup.get((y, 5), 0)
                    + lookup.get((y, 4), 0)
                )
                if sm > 0 or len(lookup) == 3:
                    ref_vals.append(sm)

            if len(ref_vals) < 5:
                continue

            ref_spi = _spi_reference_impl(ref_vals, entry["sum_3mo"])
            ref_spi_clamped = float(
                np.clip(ref_spi, -spi_mod.SPI_PLATEAU, spi_mod.SPI_PLATEAU)
            )

            assert abs(entry["spi3"] - ref_spi_clamped) < 0.05, (
                f"{area_name}: ours={entry['spi3']:.3f} ref={ref_spi_clamped:.3f}"
            )


# ---------------------------------------------------------------------------
# Test D — Zero-handling
# ---------------------------------------------------------------------------


class TestD_ZeroHandling:
    def test_reference_with_zeros_yields_finite_spi(self):
        """A reference set containing zero 3-month sums still yields a finite
        SPI — no gamma-fit crash, p_zero reflected in fit."""
        # Dry district: 0 mm for Apr/May/Jun across most reference years,
        # so 3-month sums are zero.  A few reference years have modest rain
        # to give the gamma fit something non-degenerate.
        entries: list[tuple[int, int, dict]] = []
        # Reference period 1991–2020
        for y in range(1991, 2021):
            # Most years completely dry for the target window
            rain = 50.0 if y in (1995, 2005, 2015) else 0.0
            zonal = {
                "regions": {"R": {"mean": 100.0}},
                "districts": {"DryDist|R": {"mean": rain}},
            }
            entries.append((y, 6, zonal))
            entries.append((y, 5, zonal))
            entries.append((y, 4, zonal))
        # Target month: June 2025, with above-zero rain
        target_zonal = {
            "regions": {"R": {"mean": 100.0}},
            "districts": {"DryDist|R": {"mean": 30.0}},
        }
        entries.append((2025, 4, target_zonal))
        entries.append((2025, 5, target_zonal))
        entries.append((2025, 6, target_zonal))

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _seed_stats_dir(root, "ghana", entries)

            with patch.object(spi_mod, "BASE_DIR", root):
                out = spi_mod.compute_spi3(
                    country="ghana", year=2025, month=6
                )

        # The DryDist has 27/30 reference years with zero 3-month sums.
        entry = out["zonal_stats"]["districts"]["DryDist|R"]
        assert entry["spi3"] is not None, "dry district SPI should not be None"
        assert np.isfinite(entry["spi3"]), "dry district SPI must be finite"
        assert "fit" in entry
        assert entry["fit"]["p_zero"] > 0, (
            f"p_zero should be > 0 (most ref years were dry), got {entry['fit']['p_zero']}"
        )


# ---------------------------------------------------------------------------
# Test E — No look-ahead
# ---------------------------------------------------------------------------


class TestE_NoLookAhead:
    def test_no_future_leakage(self):
        """Computing SPI for month M with later months absent yields identical
        output to computing it with later months present."""
        zonal = {"regions": {"R": {"mean": 100.0}}}
        # Build a minimal archive: 1991–2020 ref + Jan–Jun 2025
        entries: list[tuple[int, int, dict]] = []
        for y in range(1991, 2021):
            for m in range(1, 13):
                entries.append((y, m, zonal))
        for m in range(1, 7):  # only Jan–Jun
            entries.append((2025, m, zonal))

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _seed_stats_dir(root, "ghana", entries)

            with patch.object(spi_mod, "BASE_DIR", root):
                out1 = spi_mod.compute_spi3(country="ghana", year=2025, month=6)

            # Now add July–Dec 2025 (future months relative to June)
            for m in range(7, 13):
                entries.append((2025, m, zonal))
            _seed_stats_dir(root, "ghana", entries)

            with patch.object(spi_mod, "BASE_DIR", root):
                out2 = spi_mod.compute_spi3(country="ghana", year=2025, month=6)

        # Strip generated_utc (differs) and compare
        out1.pop("generated_utc", None)
        out2.pop("generated_utc", None)
        assert out1 == out2, (
            "SPI output changed when future months were added — look-ahead leak"
        )


# ---------------------------------------------------------------------------
# Test F — Determinism
# ---------------------------------------------------------------------------


class TestF_Determinism:
    def test_deterministic_output(self):
        """Two consecutive runs produce byte-identical JSON files."""
        zonal = {"regions": {"R": {"mean": 80.0}}}
        entries: list[tuple[int, int, dict]] = []
        for y in range(1991, 2021):
            for m in range(1, 13):
                entries.append((y, m, zonal))
        for m in range(1, 13):
            entries.append((2025, m, zonal))

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _seed_stats_dir(root, "ghana", entries)

            with patch.object(spi_mod, "BASE_DIR", root):
                out1 = spi_mod.compute_spi3(country="ghana", year=2025, month=6)
            with patch.object(spi_mod, "BASE_DIR", root):
                out2 = spi_mod.compute_spi3(country="ghana", year=2025, month=6)

        out1.pop("generated_utc", None)
        out2.pop("generated_utc", None)
        assert out1 == out2, "SPI output is non-deterministic across two runs"


# ---------------------------------------------------------------------------
# Test G — Hindcast sanity
# ---------------------------------------------------------------------------


class TestG_HindcastSanity:
    """Historical rainfall events should show elevated SPI-3.

    Assertions are on the region-level 'GreaterAccra' SPI-3 value.
    """

    @pytest.mark.slow
    def test_g1_1995_july(self):
        """Window ending 1995-07 — ~50-year return-period rainfall (90th pct)."""
        stats_dir = _PROJECT_ROOT / "data" / "archive" / "ghana" / "stats"
        if not stats_dir.is_dir():
            pytest.skip("Ghana stats archive not available")

        out = spi_mod.compute_spi3(country="ghana", year=1995, month=7)
        ga = out["zonal_stats"]["regions"]["GreaterAccra"]
        assert ga["spi3"] is not None, "GreaterAccra SPI is None"
        assert ga["spi3"] >= 1.0, (
            f"Expected SPI >= 1.0 for Jul 1995 GreaterAccra, got {ga['spi3']}"
        )

    @pytest.mark.slow
    def test_g2_2014_june(self):
        """Window ending 2014-06 — 17th-percentile, below-normal (negative control)."""
        stats_dir = _PROJECT_ROOT / "data" / "archive" / "ghana" / "stats"
        if not stats_dir.is_dir():
            pytest.skip("Ghana stats archive not available")

        out = spi_mod.compute_spi3(country="ghana", year=2014, month=6)
        ga = out["zonal_stats"]["regions"]["GreaterAccra"]
        assert ga["spi3"] is not None, "GreaterAccra SPI is None"
        # Per brief: 17th-percentile → below-normal → SPI < 0
        assert ga["spi3"] < 0, (
            f"Expected SPI < 0 for Jun 2014 GreaterAccra (17th pct), got {ga['spi3']}"
        )

    @pytest.mark.slow
    def test_g3_2024_may(self):
        """Window ending 2024-05 — 232 mm, wettest month in live record."""
        stats_dir = _PROJECT_ROOT / "data" / "archive" / "ghana" / "stats"
        if not stats_dir.is_dir():
            pytest.skip("Ghana stats archive not available")

        out = spi_mod.compute_spi3(country="ghana", year=2024, month=5)
        ga = out["zonal_stats"]["regions"]["GreaterAccra"]
        assert ga["spi3"] is not None, "GreaterAccra SPI is None"
        assert ga["spi3"] >= 1.0, (
            f"Expected SPI >= 1.0 for May 2024 GreaterAccra, got {ga['spi3']}"
        )

    @pytest.mark.slow
    def test_g4_2015_june(self):
        """Window ending 2015-06 — 23rd-percentile, below-normal (negative control).
        Per brief: observed -0.91, assert < 0."""
        stats_dir = _PROJECT_ROOT / "data" / "archive" / "ghana" / "stats"
        if not stats_dir.is_dir():
            pytest.skip("Ghana stats archive not available")

        out = spi_mod.compute_spi3(country="ghana", year=2015, month=6)
        ga = out["zonal_stats"]["regions"]["GreaterAccra"]
        assert ga["spi3"] is not None, "GreaterAccra SPI is None"
        # Per brief: 23rd-percentile → below-normal → SPI < 0
        assert ga["spi3"] < 0, (
            f"Expected SPI < 0 for Jun 2015 GreaterAccra (23rd pct), got {ga['spi3']}"
        )

    @pytest.mark.slow
    def test_g5_sign_consistency(self):
        """Every reference-period area-month whose computed H(sum) is below 0.5
        yields negative SPI; above 0.5 yields positive SPI.
        Use a small tolerance band around H=0.5 to handle -0.0 edge cases."""
        stats_dir = _PROJECT_ROOT / "data" / "archive" / "ghana" / "stats"
        if not stats_dir.is_dir():
            pytest.skip("Ghana stats archive not available")

        for month in range(1, 13):
            out = spi_mod.compute_spi3(
                country="ghana",
                year=2020,
                month=month,
                baseline_start=1991,
                baseline_end=2020,
            )
            for level_name, areas in out["zonal_stats"].items():
                for area_name, entry in areas.items():
                    if entry.get("spi3") is None:
                        continue
                    fit = entry.get("fit", {})
                    shape = fit.get("shape", 0)
                    scale = fit.get("scale", 0)
                    p_zero = fit.get("p_zero", 0)
                    if shape <= 0 or scale <= 0:
                        continue
                    sm = entry["sum_3mo"]
                    # Mixture CDF H(x) — SPI=0 at H(x)=0.5, not at gamma median
                    cdf = float(gamma.cdf(sm, a=shape, loc=0, scale=scale))
                    h_val = p_zero + (1.0 - p_zero) * cdf
                    # Use a small tolerance band around H=0.5 so values that
                    # round to ±0.00 at the median don't fail strict <0 / >0
                    if h_val < 0.49:
                        assert entry["spi3"] < 0, (
                            f"{area_name} m={month}: H={h_val:.3f} < 0.5"
                            f" but SPI={entry['spi3']} >= 0"
                        )
                    elif h_val > 0.51:
                        assert entry["spi3"] > 0, (
                            f"{area_name} m={month}: H={h_val:.3f} > 0.5"
                            f" but SPI={entry['spi3']} <= 0"
                        )


# ---------------------------------------------------------------------------
# Unit tests for internal helpers
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_categorise_spi(self):
        assert spi_mod.categorise_spi(2.5) == "extremely_wet"
        assert spi_mod.categorise_spi(2.0) == "extremely_wet"
        assert spi_mod.categorise_spi(1.7) == "very_wet"
        assert spi_mod.categorise_spi(1.2) == "moderately_wet"
        assert spi_mod.categorise_spi(0.0) == "near_normal"
        assert spi_mod.categorise_spi(-1.2) == "moderately_dry"
        assert spi_mod.categorise_spi(-1.7) == "severely_dry"
        assert spi_mod.categorise_spi(-2.0) == "extremely_dry"
        assert spi_mod.categorise_spi(-3.0) == "extremely_dry"

    def test_three_month_sum_spans_year(self):
        lookup = {(2023, 12): 10.0, (2024, 1): 20.0, (2024, 2): 30.0}
        result = spi_mod._three_month_sum(lookup, 2024, 2)
        assert result == 60.0

    def test_three_month_sum_missing_returns_none(self):
        lookup = {(2024, 1): 10.0, (2024, 2): 20.0}
        result = spi_mod._three_month_sum(lookup, 2024, 2)
        assert result is None

    def test_fit_gamma_all_zeros(self):
        fit = spi_mod._fit_gamma_zero_adjusted([0.0] * 30)
        assert fit["p_zero"] == 1.0
        assert fit["n_ref"] == 30

    def test_fit_gamma_mixed(self):
        rng = np.random.RandomState(42)
        vals = [0.0] * 10 + list(rng.uniform(50, 200, 20).astype(float))
        fit = spi_mod._fit_gamma_zero_adjusted(vals)
        assert fit["p_zero"] == pytest.approx(10 / 30, abs=0.01)
        assert fit["shape"] > 0
        assert fit["scale"] > 0

    def test_parse_year_month_from_filename(self):
        """Filename parser must correctly extract (year, month) despite the
        dot in 'v2.0' — the B1 regression guard."""
        assert spi_mod._parse_year_month_from_filename(
            Path("chirps-v2.0.2020.06_ghana.json")
        ) == (2020, 6)
        assert spi_mod._parse_year_month_from_filename(
            Path("chirps-v2.0.1995.07_ghana.json")
        ) == (1995, 7)
        assert spi_mod._parse_year_month_from_filename(
            Path("chirps-v2.0.2025.12_ghana.json")
        ) == (2025, 12)
        assert spi_mod._parse_year_month_from_filename(
            Path("something-else.json")
        ) is None

    def test_spi_from_fit_clamps(self):
        """Extreme values clamp to [-3.09, 3.09]."""
        fit = {"shape": 2.0, "scale": 50.0, "p_zero": 0.0, "n_ref": 30}
        low = spi_mod._spi_from_fit(0.0, fit)
        high = spi_mod._spi_from_fit(1e9, fit)
        assert low >= -3.09
        assert high <= 3.09
