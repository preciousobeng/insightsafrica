"""Acceptance tests for the Flood Risk Index (Sprint 2) — FROZEN by the senior.

These define the contract the engine (scripts/compute_risk_index.py) must satisfy.
The junior implements the engine to make these pass; it must NOT edit this file.

Tests A–G + helpers, per docs/brief-risk-index-2026-06-30.md section 6.

Required engine API (scripts/compute_risk_index.py):
- Constants: BASE (= 0.40), V_MAP (dict drainage->weight, Good/Moderate/Poor/None =
  0.25/0.5/0.75/1.0), H_SATURATION_SPI (= 2.0).
- hazard_from_spi(spi: float) -> float        # 0 for spi<=0; spi/2 for 0<spi<2; 1 for spi>=2
- vulnerability_from_drainage(rating: str) -> float   # via V_MAP
- risk_score(spi: float, drainage: str) -> float      # V * (BASE + (1-BASE)*H), rounded 2 dp, in [0,1]
- categorise_risk(r: float) -> str            # low/moderate/high/severe per thresholds
- compute_risk(country, year, month) -> dict  # reads SPI + drainage files, full output dict

Run: ./venv/bin/python -m pytest tests/test_risk_index.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

import scripts.compute_risk_index as rix  # type: ignore[import-not-found]

_SPI_2015_06 = (
    _PROJECT_ROOT / "data" / "archive" / "ghana" / "spi"
    / "chirps-v2.0.2015.06_ghana_spi3.json"
)
_DRAINAGE = _PROJECT_ROOT / "frontend" / "static" / "data" / "ghana_infrastructure.json"


# ---------------------------------------------------------------------------
# Helper unit tests — the model primitives
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_hazard_ramp(self):
        assert rix.hazard_from_spi(-1.0) == 0.0
        assert rix.hazard_from_spi(0.0) == 0.0
        assert rix.hazard_from_spi(1.0) == pytest.approx(0.5, abs=1e-6)
        assert rix.hazard_from_spi(2.0) == pytest.approx(1.0, abs=1e-6)
        assert rix.hazard_from_spi(3.0) == pytest.approx(1.0, abs=1e-6)

    def test_vulnerability_map(self):
        assert rix.vulnerability_from_drainage("Good") == pytest.approx(0.25)
        assert rix.vulnerability_from_drainage("Moderate") == pytest.approx(0.50)
        assert rix.vulnerability_from_drainage("Poor") == pytest.approx(0.75)
        assert rix.vulnerability_from_drainage("None") == pytest.approx(1.00)

    def test_base_constant(self):
        assert rix.BASE == pytest.approx(0.40)

    def test_risk_score_known_points(self):
        # dry month (hazard 0): standing exposure floor
        assert rix.risk_score(0.0, "Poor") == pytest.approx(0.30, abs=1e-6)
        assert rix.risk_score(0.0, "None") == pytest.approx(0.40, abs=1e-6)
        assert rix.risk_score(0.0, "Good") == pytest.approx(0.10, abs=1e-6)
        # saturated wet (hazard 1): V scales fully
        assert rix.risk_score(2.0, "Poor") == pytest.approx(0.75, abs=1e-6)
        assert rix.risk_score(2.0, "Good") == pytest.approx(0.25, abs=1e-6)

    def test_categorise_thresholds(self):
        assert rix.categorise_risk(0.10) == "low"
        assert rix.categorise_risk(0.24) == "low"
        assert rix.categorise_risk(0.25) == "moderate"
        assert rix.categorise_risk(0.49) == "moderate"
        assert rix.categorise_risk(0.50) == "high"
        assert rix.categorise_risk(0.74) == "high"
        assert rix.categorise_risk(0.75) == "severe"
        assert rix.categorise_risk(1.0) == "severe"


# ---------------------------------------------------------------------------
# A — Monotonic in rainfall
# ---------------------------------------------------------------------------

class TestA_MonotonicRainfall:
    def test_non_decreasing_in_spi(self):
        vals = [rix.risk_score(s, "Poor") for s in (-1.0, 0.0, 1.0, 2.0, 3.0)]
        assert vals == sorted(vals), f"risk not non-decreasing in spi: {vals}"

    def test_strictly_higher_when_wet(self):
        assert rix.risk_score(2.0, "Poor") > rix.risk_score(0.0, "Poor")


# ---------------------------------------------------------------------------
# B — Monotonic in vulnerability
# ---------------------------------------------------------------------------

class TestB_MonotonicVulnerability:
    def test_worse_drainage_higher_risk(self):
        spi = 1.0
        none = rix.risk_score(spi, "None")
        poor = rix.risk_score(spi, "Poor")
        mod = rix.risk_score(spi, "Moderate")
        good = rix.risk_score(spi, "Good")
        assert none > poor > mod > good, f"{none} {poor} {mod} {good}"


# ---------------------------------------------------------------------------
# C — Standing exposure (the value-add over SPI-3)
# ---------------------------------------------------------------------------

class TestC_StandingExposure:
    def test_poor_and_none_flag_when_dry(self):
        # below-normal rainfall, but vulnerable drainage -> at least moderate
        assert rix.categorise_risk(rix.risk_score(0.0, "Poor")) in ("moderate", "high", "severe")
        assert rix.categorise_risk(rix.risk_score(-1.0, "None")) in ("moderate", "high", "severe")
        assert rix.risk_score(0.0, "Poor") >= 0.25
        assert rix.risk_score(-1.0, "None") >= 0.25

    def test_good_drainage_low_when_dry(self):
        assert rix.categorise_risk(rix.risk_score(0.0, "Good")) == "low"


# ---------------------------------------------------------------------------
# D — 2015 Accra hindcast (headline; ties to the SPI-3 negative control)
# ---------------------------------------------------------------------------

class TestD_AccraHindcast:
    def _out(self):
        if not _SPI_2015_06.is_file() or not _DRAINAGE.is_file():
            pytest.skip("2015-06 SPI or drainage file not available")
        return rix.compute_risk("ghana", 2015, 6)

    def test_accra_flags_despite_dry_window(self):
        out = self._out()
        d = out["districts"]["Accra|GreaterAccra"]
        # SPI-3 read June 2015 as below-normal for Accra...
        assert d["spi3"] < 0, f"expected Accra spi3<0, got {d['spi3']}"
        # ...yet the Risk Index flags it moderate+ because drainage is Poor.
        assert d["category"] in ("moderate", "high", "severe"), (
            f"Accra should flag moderate+ despite dry window, got {d['category']} (risk {d['risk']})"
        )
        assert d["risk"] >= 0.25


# ---------------------------------------------------------------------------
# E — Range & completeness
# ---------------------------------------------------------------------------

class TestE_RangeCompleteness:
    def _out(self):
        if not _SPI_2015_06.is_file() or not _DRAINAGE.is_file():
            pytest.skip("2015-06 SPI or drainage file not available")
        return rix.compute_risk("ghana", 2015, 6)

    def test_risk_bounds_and_categories(self):
        out = self._out()
        for key, d in out["districts"].items():
            if d["risk"] is None:
                assert d.get("skip_reason") == "no_drainage_data", f"{key} null without skip_reason"
                continue
            assert 0.0 <= d["risk"] <= 1.0, f"{key} risk out of [0,1]: {d['risk']}"
            assert d["category"] == rix.categorise_risk(d["risk"]), f"{key} miscategorised"

    def test_districts_without_drainage_skipped_not_dropped(self):
        out = self._out()
        skipped = [k for k, d in out["districts"].items() if d["risk"] is None]
        assert skipped, "expected some SPI districts to lack drainage data (only ~39 of 260 covered)"
        for k in skipped:
            assert out["districts"][k].get("skip_reason") == "no_drainage_data"


# ---------------------------------------------------------------------------
# F — Provisional tagging + auditable params
# ---------------------------------------------------------------------------

class TestF_Provisional:
    def _out(self):
        if not _SPI_2015_06.is_file() or not _DRAINAGE.is_file():
            pytest.skip("2015-06 SPI or drainage file not available")
        return rix.compute_risk("ghana", 2015, 6)

    def test_provisional_flags_and_params(self):
        out = self._out()
        assert out.get("provisional") is True, "top wrapper must be provisional"
        assert out["params"]["base"] == pytest.approx(0.40)
        assert out["params"]["h_saturation_spi"] == pytest.approx(2.0)
        assert "v_map" in out["params"]
        for d in out["districts"].values():
            assert d.get("provisional") is True


# ---------------------------------------------------------------------------
# G — Determinism
# ---------------------------------------------------------------------------

class TestG_Determinism:
    def test_deterministic(self):
        if not _SPI_2015_06.is_file() or not _DRAINAGE.is_file():
            pytest.skip("2015-06 SPI or drainage file not available")
        a = rix.compute_risk("ghana", 2015, 6)
        b = rix.compute_risk("ghana", 2015, 6)
        a.pop("generated_utc", None)
        b.pop("generated_utc", None)
        assert a == b


# ---------------------------------------------------------------------------
# Exposure multiplier (v2, TD-2) — population-weighted risk
# ---------------------------------------------------------------------------

class TestExposure:
    def test_exposure_factor_helper(self):
        import math
        pmin, pmax = math.log(10_000), math.log(1_000_000)
        # bounds
        assert rix.exposure_factor(1_000_000, pmin, pmax) == pytest.approx(rix.EXP_MAX, abs=1e-6)
        assert rix.exposure_factor(10_000, pmin, pmax) == pytest.approx(rix.EXP_MIN, abs=1e-6)
        # monotonic: denser -> higher factor
        assert rix.exposure_factor(500_000, pmin, pmax) > rix.exposure_factor(50_000, pmin, pmax)
        # neutral when population missing or range degenerate
        assert rix.exposure_factor(None, pmin, pmax) == 1.0
        assert rix.exposure_factor(0, pmin, pmax) == 1.0
        assert rix.exposure_factor(50_000, 5.0, 5.0) == 1.0

    def _out(self):
        if not _SPI_2015_06.is_file() or not _DRAINAGE.is_file():
            pytest.skip("2015-06 SPI or drainage file not available")
        out = rix.compute_risk("ghana", 2015, 6)
        if out["params"].get("exposure_source") is None:
            pytest.skip("population/exposure data not available")
        return out

    def test_scored_districts_carry_exposure(self):
        out = self._out()
        assert out["params"]["exp_min"] == pytest.approx(rix.EXP_MIN)
        assert out["params"]["exp_max"] == pytest.approx(rix.EXP_MAX)
        for k, d in out["districts"].items():
            if d["risk"] is None:
                continue
            assert "population" in d and "exposure" in d and "base_risk" in d
            assert rix.EXP_MIN - 1e-6 <= d["exposure"] <= rix.EXP_MAX + 1e-6
            # risk is the exposure-weighted base, bounded
            assert 0.0 <= d["risk"] <= 1.0

    def test_denser_district_higher_exposure(self):
        out = self._out()
        d = out["districts"]
        # AblekumaNorth (dense, ~0.5M) must have a higher exposure factor than
        # ShaiOsudoku (sparse, ~60k) — the value-add that fixes the inversion.
        dense = d.get("AblekumaNorth|GreaterAccra")
        sparse = d.get("ShaiOsudoku|GreaterAccra")
        if not dense or not sparse or dense["risk"] is None or sparse["risk"] is None:
            pytest.skip("expected Accra districts not present")
        assert dense["exposure"] > sparse["exposure"]
