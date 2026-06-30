"""Acceptance tests for the Seasonal Outlook / Prediction layer — FROZEN by the senior.

TDD: the junior writes scripts/compute_outlook.py to satisfy these; it must NOT edit
this file. See docs/brief-prediction-2026-06-30.md.

Required engine API (scripts/compute_outlook.py):
- Constants: ORDER=(1,0,0), SEASONAL_ORDER=(1,0,0,12), BACKTEST_YEARS=10, MIN_YEARS=20.
- tercile_category(value: float, history: list[float]) -> str   # below/near/above vs 33rd/67th pct
- skill_score(model_rmse: float, clim_rmse: float) -> float      # 1 - model/clim
- climatology_forecast(window_totals: list[float]) -> float      # mean
- compute_outlook(country, year, month) -> dict                  # full pipeline, issued FROM (year,month)

Behavioural tests use small synthetic archives (fast) — do NOT fit SARIMA on 260 real districts here.
Run: ./venv/bin/python -m pytest tests/test_outlook.py -v
"""

from __future__ import annotations

import json
import math
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

import scripts.compute_outlook as ol  # type: ignore[import-not-found]


# ---------------------------------------------------------------------------
# synthetic archive helpers
# ---------------------------------------------------------------------------

def _seasonal_series(n_years: int, base: float, amp: float, seed: int) -> list[float]:
    rng = np.random.RandomState(seed)
    out = []
    for _y in range(n_years):
        for m in range(1, 13):
            val = base + amp * math.sin(2 * math.pi * m / 12.0) + rng.normal(0, 5)
            out.append(max(0.0, round(float(val), 1)))
    return out


def _seed_archive(root: Path, country: str, districts: dict[str, list[float]],
                  start_year: int):
    """districts: name|region -> monthly series starting at start_year-01."""
    stats_dir = root / "data" / "archive" / country / "stats"
    stats_dir.mkdir(parents=True, exist_ok=True)
    # transpose to per (year,month)
    n = max(len(s) for s in districts.values())
    for i in range(n):
        year = start_year + i // 12
        month = i % 12 + 1
        dist_block = {}
        for key, series in districts.items():
            if i < len(series):
                dist_block[key] = {"mean": series[i]}
        payload = {"year": year, "month": month,
                   "zonal_stats": {"districts": dist_block}}
        fn = stats_dir / f"chirps-v2.0.{year:04d}.{month:02d}_{country}.json"
        with open(fn, "w") as fh:
            json.dump(payload, fh)


# ---------------------------------------------------------------------------
# helper unit tests
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_skill_score(self):
        assert ol.skill_score(0.5, 1.0) == pytest.approx(0.5)
        assert ol.skill_score(1.0, 1.0) == pytest.approx(0.0)
        assert ol.skill_score(2.0, 1.0) == pytest.approx(-1.0)

    def test_climatology_is_mean(self):
        vals = [100.0, 200.0, 300.0]
        assert ol.climatology_forecast(vals) == pytest.approx(200.0)

    def test_tercile_category(self):
        hist = list(range(0, 100))  # 0..99, p33~33, p67~66
        assert ol.tercile_category(10, hist) == "below"
        assert ol.tercile_category(50, hist) == "near"
        assert ol.tercile_category(90, hist) == "above"

    def test_constants(self):
        assert tuple(ol.ORDER) == (1, 0, 0)
        assert tuple(ol.SEASONAL_ORDER) == (1, 0, 0, 12)
        assert ol.MIN_YEARS == 20


# ---------------------------------------------------------------------------
# integration tests on synthetic archives
# ---------------------------------------------------------------------------

def _run(root: Path, country, year, month):
    with patch.object(ol, "BASE_DIR", root):
        return ol.compute_outlook(country, year, month)


class TestIntegration:
    def _archive(self, root, n_years=25):
        _seed_archive(root, "ghana",
                      {"Long|R": _seasonal_series(n_years, 80, 40, seed=1),
                       "Other|R": _seasonal_series(n_years, 60, 30, seed=2)},
                      start_year=2000)

    def test_A_climatology_exact(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._archive(root, n_years=25)
            # issue from 2024-12 -> target window Jan/Feb/Mar (months 1,2,3 of next year)
            out = _run(root, "ghana", 2024, 12)
            d = out["districts"]["Long|R"]
            # independently compute climatology of the target window from the archive
            tw = d["target_window"]
            tmonths = [int(m.split("-")[1]) for m in tw]
            stats_dir = root / "data" / "archive" / "ghana" / "stats"
            # gather each historical occurrence of that 3-month window total
            by = {}
            for f in stats_dir.glob("chirps-v2.0.*_ghana.json"):
                j = json.load(open(f))
                v = j["zonal_stats"]["districts"].get("Long|R")
                if v is not None:
                    by[(j["year"], j["month"])] = v["mean"]
            totals = []
            years = sorted({y for (y, m) in by})
            for y in years:
                if all((y, m) in by for m in tmonths):
                    totals.append(sum(by[(y, m)] for m in tmonths))
            assert d["benchmarks"]["climatology_mm"] == pytest.approx(
                round(ol.climatology_forecast(totals), 1), abs=1.0)

    def test_B_honesty_fallback_rule(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._archive(root, n_years=25)
            out = _run(root, "ghana", 2024, 12)
            for key, d in out["districts"].items():
                if d.get("forecast_3mo_mm") is None:
                    continue
                if d["skill_score"] > 0:
                    assert d["method"] == "sarima", f"{key} skill>0 but not sarima"
                else:
                    assert d["method"] == "climatology_fallback", f"{key} skill<=0 not fallback"
                    assert d["forecast_3mo_mm"] == pytest.approx(
                        d["benchmarks"]["climatology_mm"], abs=0.2), f"{key} fallback != clim"

    def test_C_tercile_consistency(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._archive(root, n_years=25)
            out = _run(root, "ghana", 2024, 12)
            d = out["districts"]["Long|R"]
            hist = d.get("_window_history") or None
            # recompute category from tercile bounds the engine published
            p33 = d["tercile_bounds_mm"]["p33"]
            p67 = d["tercile_bounds_mm"]["p67"]
            f = d["forecast_3mo_mm"]
            expected = "below" if f < p33 else ("above" if f > p67 else "near")
            assert d["category"] == expected

    def test_D_min_history_skip(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_archive(root, "ghana",
                          {"Long|R": _seasonal_series(25, 80, 40, seed=1),
                           "Short|R": _seasonal_series(12, 80, 40, seed=3)},
                          start_year=2000)
            out = _run(root, "ghana", 2024, 12)
            assert out["districts"]["Short|R"]["forecast_3mo_mm"] is None
            assert out["districts"]["Short|R"]["skip_reason"] == "insufficient_history"
            assert out["districts"]["Long|R"]["forecast_3mo_mm"] is not None

    def test_E_no_lookahead(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            full = _seasonal_series(25, 80, 40, seed=1)
            # archive up to 2024-12 = 25*12=300 months from 2000-01
            _seed_archive(root, "ghana", {"Long|R": full[:300]}, start_year=2000)
            a = _run(root, "ghana", 2024, 12)
            # add 6 future months
            _seed_archive(root, "ghana", {"Long|R": full[:306]}, start_year=2000)
            b = _run(root, "ghana", 2024, 12)
            a.pop("generated_utc", None); b.pop("generated_utc", None)
            assert a == b, "outlook changed when future months were added (look-ahead leak)"

    def test_F_experimental_and_params(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._archive(root, n_years=25)
            out = _run(root, "ghana", 2024, 12)
            assert out["experimental"] is True
            p = out["params"]
            assert tuple(p["order"]) == (1, 0, 0)
            assert tuple(p["seasonal_order"]) == (1, 0, 0, 12)
            assert p["backtest_years"] == 10 and p["min_years"] == 20
            for d in out["districts"].values():
                assert d["experimental"] is True
                if d.get("forecast_3mo_mm") is not None:
                    assert math.isfinite(d["skill_score"])
                    assert d["forecast_3mo_mm"] >= 0
                    assert d["category"] in ("below", "near", "above")
                    assert "climatology_mm" in d["benchmarks"]
                    assert "persistence_mm" in d["benchmarks"]

    def test_H_model_actually_runs(self):
        # Regression guard (we hit this for real): if the SARIMA fit silently fails
        # and always falls back, every skill_score is exactly 0.0. A working model
        # produces non-zero skill (its RMSE differs from climatology's). Assert the
        # model path actually executed.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._archive(root, n_years=25)
            out = _run(root, "ghana", 2024, 12)
            skills = [v["skill_score"] for v in out["districts"].values()
                      if v.get("forecast_3mo_mm") is not None]
            assert any(s != 0.0 for s in skills), (
                "all skill scores are exactly 0.0 — SARIMA never ran (silent fallback bug)"
            )

    def test_G_determinism(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._archive(root, n_years=25)
            a = _run(root, "ghana", 2024, 12)
            b = _run(root, "ghana", 2024, 12)
            a.pop("generated_utc", None); b.pop("generated_utc", None)
            assert a == b
