#!/usr/bin/env python3
"""Flood Risk Index (Sprint 2) — production implementation.

See docs/brief-risk-index-2026-06-30.md.  Exposes the API required by
tests/test_risk_index.py: BASE, V_MAP, H_SATURATION_SPI, hazard_from_spi(),
vulnerability_from_drainage(), risk_score(), categorise_risk(), compute_risk().
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Named constants – NADMO calibration targets.
# ---------------------------------------------------------------------------
BASE = 0.40
V_MAP = {"Good": 0.25, "Moderate": 0.50, "Poor": 0.75, "None": 1.00}
H_SATURATION_SPI = 2.0

# ---------------------------------------------------------------------------
# Core model primitives
# ---------------------------------------------------------------------------


def hazard_from_spi(spi: float) -> float:
    """Hazard component from SPI-3.

    Returns a value in [0, 1]:
    - 0 for spi <= 0
    - linear ramp spi/2 for 0 < spi < 2
    - 1 for spi >= 2
    """
    if spi <= 0.0:
        return 0.0
    if spi >= H_SATURATION_SPI:
        return 1.0
    return spi / H_SATURATION_SPI


def vulnerability_from_drainage(rating: str) -> float:
    """Vulnerability weight from a drainage rating string.

    Raises KeyError if rating is unknown.
    """
    return V_MAP[rating]


def risk_score(spi: float, drainage: str) -> float:
    """Combined risk score R = V * (BASE + (1-BASE) * H), rounded 2 dp.

    Returns a float in [0, 1].
    """
    H = hazard_from_spi(spi)
    V = vulnerability_from_drainage(drainage)
    R = V * (BASE + (1.0 - BASE) * H)
    return round(R, 2)


def categorise_risk(r: float) -> str:
    """Categorise a risk score into low/moderate/high/severe.

    Thresholds: <0.25 low; [0.25,0.5) moderate; [0.5,0.75) high; >=0.75 severe.
    """
    if r < 0.25:
        return "low"
    if r < 0.50:
        return "moderate"
    if r < 0.75:
        return "high"
    return "severe"


# ---------------------------------------------------------------------------
# Key normalisation – strip all whitespace so that e.g.
# "Accra|Greater Accra" becomes "Accra|GreaterAccra", matching the
# convention used in the test suite and the drainage file.
# ---------------------------------------------------------------------------

def _normalise_key(key: str) -> str:
    """Remove all whitespace from a district key."""
    return key.replace(" ", "").replace("\t", "")


# ---------------------------------------------------------------------------
# Full computation (file I/O, aggregation)
# ---------------------------------------------------------------------------


def _load_spi_file(country: str, year: int, month: int) -> dict[str, float]:
    """Load the pre-computed SPI-3 JSON and return a dict of {district_key: spi3 (float)}.

    Handles several common SPI-3 output structures:
      - Top-level dict with a "districts" key mapping to a dict or list.
      - Flat dict where keys are district identifiers, values are spi3 or dicts.
      - Top-level list of per-district dicts.

    Meta keys like "country", "year", etc. are skipped. All SPI values are
    cast to float.

    All returned keys are normalised (whitespace stripped) so that they
    match the drainage file's convention.

    Raises FileNotFoundError with a clear message if the file is missing.
    """
    spi_path = (
        Path(__file__).resolve().parent.parent
        / "data"
        / "archive"
        / country
        / "spi"
        / f"chirps-v2.0.{year}.{month:02d}_{country}_spi3.json"
    )

    if not spi_path.is_file():
        raise FileNotFoundError(
            f"SPI-3 input not found at {spi_path}. "
            "Run scripts/compute_spi.py first."
        )

    with open(spi_path, "r") as f:
        raw = json.load(f)

    # Known meta keys that are never district identifiers
    META_KEYS = {
        "country", "year", "month", "model", "model_version",
        "generated_utc", "districts", "skipped", "params",
    }

    # Helper to safely convert a single value to float, returning None on failure
    def _to_float(val):
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            try:
                return float(val)
            except (ValueError, TypeError):
                return None
        return None

    # Helper to extract the spi3 value from a per-district entry (dict or scalar)
    def _extract_spi(entry):
        if isinstance(entry, dict):
            return _to_float(entry.get("spi3"))
        return _to_float(entry)

    result: dict[str, float] = {}

    if isinstance(raw, dict):
        # SPI files nest district stats under zonal_stats.districts
        if (isinstance(raw.get("zonal_stats"), dict)
                and isinstance(raw["zonal_stats"].get("districts"), dict)):
            for area, val in raw["zonal_stats"]["districts"].items():
                spi_val = _extract_spi(val)
                if spi_val is not None:
                    result[_normalise_key(area)] = spi_val
        # Check for a "districts" key
        elif "districts" in raw:
            districts_raw = raw["districts"]
            if isinstance(districts_raw, dict):
                for area, val in districts_raw.items():
                    spi_val = _extract_spi(val)
                    if spi_val is not None:
                        result[_normalise_key(area)] = spi_val
            elif isinstance(districts_raw, list):
                for entry in districts_raw:
                    if not isinstance(entry, dict):
                        continue
                    area = entry.get("area") or entry.get("name") or entry.get("district")
                    # Also try combining name + region if separate
                    if not area:
                        name = entry.get("name")
                        region = entry.get("region")
                        if name and region:
                            area = f"{name}|{region}"
                    spi_val = _extract_spi(entry)
                    if area and spi_val is not None:
                        result[_normalise_key(area)] = spi_val
            else:
                raise ValueError(
                    f"Unexpected districts type in SPI file {spi_path}: "
                    f"{type(districts_raw).__name__}"
                )
        else:
            # Flat dict — keys are district identifiers, skip meta keys
            for area, val in raw.items():
                if area in META_KEYS:
                    continue
                # Also skip keys that look like metadata dicts
                if isinstance(val, (dict, list)):
                    continue
                spi_val = _extract_spi(val)
                if spi_val is not None:
                    result[_normalise_key(area)] = spi_val

    elif isinstance(raw, list):
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            area = entry.get("area") or entry.get("name") or entry.get("district")
            if not area:
                name = entry.get("name")
                region = entry.get("region")
                if name and region:
                    area = f"{name}|{region}"
            spi_val = _extract_spi(entry)
            if area and spi_val is not None:
                result[_normalise_key(area)] = spi_val

    else:
        raise ValueError(
            f"Unexpected SPI file structure in {spi_path}: "
            f"expected dict or list, got {type(raw).__name__}"
        )

    return result


def _load_drainage_file() -> dict[str, dict]:
    """Load the infrastructure/drainage JSON and return {normalised_key: {"drainage": str}}.

    Handles the known formats:
      - Dict keyed by "Name|Region" -> {"drainage": "...", ...}
      - List of dicts with "District", "Region", and "drainage_rating"/"drainage"/"Drainage_Rating"
      - Dict with a "districts" key containing either of the above

    All returned keys are normalised (whitespace stripped).
    """
    drain_path = (
        Path(__file__).resolve().parent.parent
        / "frontend"
        / "static"
        / "data"
        / "ghana_infrastructure.json"
    )
    if not drain_path.is_file():
        raise FileNotFoundError(
            f"Drainage infrastructure file not found at {drain_path}."
        )
    with open(drain_path, "r") as f:
        raw = json.load(f)

    # Helper: extract drainage rating from a single record that might be a dict or a string
    def _extract_drainage(record):
        if isinstance(record, dict):
            return (
                record.get("drainage_rating")
                or record.get("drainage")
                or record.get("Drainage_Rating")
            )
        if isinstance(record, str):
            return record  # e.g., "Poor"
        return None

    def _build_key(district, region):
        return f"{district}|{region}"

    result: dict[str, dict] = {}

    if isinstance(raw, dict):
        # Case 1: top-level "districts" key
        if "districts" in raw:
            districts_raw = raw["districts"]
            if isinstance(districts_raw, dict):
                for key, info in districts_raw.items():
                    rating = _extract_drainage(info)
                    if rating:
                        result[_normalise_key(key)] = {"drainage": rating}
            elif isinstance(districts_raw, list):
                for entry in districts_raw:
                    if not isinstance(entry, dict):
                        continue
                    district = entry.get("District") or entry.get("name")
                    region = entry.get("Region") or entry.get("region")
                    rating = _extract_drainage(entry)
                    if district and region and rating:
                        result[_normalise_key(_build_key(district, region))] = {"drainage": rating}
            else:
                raise ValueError(
                    f"Unexpected 'districts' type in {drain_path}: "
                    f"{type(districts_raw).__name__}"
                )
        elif not raw:
            # Empty dict – no drainage data
            pass
        else:
            # Case 2: keys are district keys already (e.g., "Accra|GreaterAccra")
            for key, info in raw.items():
                rating = _extract_drainage(info)
                if rating:
                    result[_normalise_key(key)] = {"drainage": rating}

    elif isinstance(raw, list):
        # Case 3: list of district records
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            district = entry.get("District") or entry.get("name")
            region = entry.get("Region") or entry.get("region")
            rating = _extract_drainage(entry)
            if district and region and rating:
                result[_normalise_key(_build_key(district, region))] = {"drainage": rating}

    else:
        raise ValueError(
            f"Unexpected drainage file structure in {drain_path}: "
            f"expected dict or list, got {type(raw).__name__}"
        )

    return result


def compute_risk(country: str, year: int, month: int) -> dict:
    """Full risk index computation for a given country/year/month.

    Returns the top-level output dict as specified in the brief.
    """
    # Load inputs
    spi_data = _load_spi_file(country, year, month)
    drainage_data = _load_drainage_file()

    # Build a set of drainage keys for fast lookup
    drain_keys = set(drainage_data.keys())

    # Build name-only → full-key mapping from drainage (for fallback when SPI
    # keys lack a region, e.g., "Accra" instead of "Accra|GreaterAccra")
    name_to_drain = {}
    for dk in drain_keys:
        if '|' in dk:
            name = dk.split('|')[0]  # already normalized, no extra whitespace
            if name not in name_to_drain:
                name_to_drain[name] = dk

    districts = {}
    skip_count = 0

    for district_key, spi3_float in spi_data.items():
        spi3_rounded = round(spi3_float, 2)

        # Find drainage record for this district
        drain_info = drainage_data.get(district_key)

        # Fallback: if district_key is a name without region, try to match a
        # drainage key that starts with that name + '|'
        if drain_info is None and '|' not in district_key:
            matched_key = name_to_drain.get(district_key)
            if matched_key is None:
                # Try prefix match with all drain keys (e.g., "Accra" -> "Accra|GreaterAccra")
                candidates = [dk for dk in drain_keys if dk.startswith(district_key + '|')]
                if candidates:
                    matched_key = sorted(candidates)[0]
            if matched_key:
                drain_info = drainage_data[matched_key]
                district_key = matched_key  # use the full key for output

        if drain_info is not None:
            rating = drain_info["drainage"]
            try:
                vuln = vulnerability_from_drainage(rating)
            except KeyError:
                # Unknown drainage rating – treat as missing data
                districts[district_key] = {
                    "spi3": spi3_rounded,
                    "drainage": rating,
                    "risk": None,
                    "category": None,
                    "provisional": True,
                    "skip_reason": "no_drainage_data",
                }
                skip_count += 1
                continue

            H = hazard_from_spi(spi3_float)
            R = risk_score(spi3_float, rating)
            cat = categorise_risk(R)

            districts[district_key] = {
                "spi3": spi3_rounded,
                "drainage": rating,
                "hazard": round(H, 2),
                "vulnerability": round(vuln, 2),
                "risk": R,
                "category": cat,
                "provisional": True,
            }
        else:
            # No drainage data for this district -> null risk with skip reason
            districts[district_key] = {
                "spi3": spi3_rounded,
                "drainage": None,
                "risk": None,
                "category": None,
                "provisional": True,
                "skip_reason": "no_drainage_data",
            }
            skip_count += 1

    # Build wrapper
    output = {
        "country": country,
        "year": year,
        "month": month,
        "model_version": "risk-v1",
        "params": {
            "base": BASE,
            "v_map": V_MAP,
            "h_saturation_spi": H_SATURATION_SPI,
        },
        "provisional": True,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "skipped_districts": skip_count,
        "districts": districts,
    }

    return output


# ---------------------------------------------------------------------------
# CLI entry point (mirrors compute_spi.py)
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Compute Flood Risk Index (v1, provisional) from SPI-3 and drainage data."
    )
    parser.add_argument("--country", required=True, help="Country code (e.g. ghana)")
    parser.add_argument("--year", type=int, required=True, help="Year")
    parser.add_argument("--month", type=int, required=True, help="Month (1-12)")

    args = parser.parse_args()

    try:
        result = compute_risk(args.country, args.year, args.month)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # Output path
    out_path = (
        Path(__file__).resolve().parent.parent
        / "data"
        / "archive"
        / args.country
        / "risk"
        / f"chirps-v2.0.{args.year}.{args.month:02d}_{args.country}_risk.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w") as f:
        json.dump(result, f, indent=2, sort_keys=True)

    computed = [d for d in result["districts"].values() if d["risk"] is not None]
    print(f"Risk index written to {out_path}")
    print(f"  Districts computed: {len(computed)}")
    print(f"  Districts skipped (no drainage): {result['skipped_districts']}")


if __name__ == "__main__":
    main()
