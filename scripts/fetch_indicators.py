"""
fetch_indicators.py

Fetches World Bank Open Data indicators for Ghana, Nigeria, and Côte d'Ivoire.
No API key required.

Usage:
    python scripts/fetch_indicators.py
    python scripts/fetch_indicators.py --country ghana
    python scripts/fetch_indicators.py --years 15   # how many years of history to fetch

Output:
    data/processed_indicators/ghana_indicators.json
    data/processed_indicators/nigeria_indicators.json
    data/processed_indicators/ivorycoast_indicators.json
"""

import argparse
import json
import time
from datetime import date
from pathlib import Path

import requests

INDICATORS = {
    "child_mortality": {
        "label": "Child mortality (under-5)",
        "unit": "per 1,000 live births",
        "source": "World Bank / UNICEF",
        "wb_code": "SH.DYN.MORT",
        "higher_is_better": False,
    },
    "maternal_mortality": {
        "label": "Maternal mortality ratio",
        "unit": "per 100,000 live births",
        "source": "World Bank / WHO",
        "wb_code": "SH.STA.MMRT",
        "higher_is_better": False,
    },
    "poverty_215": {
        "label": "Poverty headcount (<$2.15/day)",
        "unit": "% of population",
        "source": "World Bank PovcalNet",
        "wb_code": "SI.POV.DDAY",
        "higher_is_better": False,
    },
    "gini": {
        "label": "Gini inequality index",
        "unit": "0–100 scale",
        "source": "World Bank",
        "wb_code": "SI.POV.GINI",
        "higher_is_better": False,
    },
    "health_expenditure": {
        "label": "Health expenditure per capita",
        "unit": "USD",
        "source": "World Bank / WHO",
        "wb_code": "SH.XPD.CHEX.PC.CD",
        "higher_is_better": True,
    },
    "clean_water": {
        "label": "Access to clean water",
        "unit": "% of population",
        "source": "WHO / UNICEF JMP",
        "wb_code": "SH.H2O.BASW.ZS",
        "higher_is_better": True,
    },
    "literacy": {
        "label": "Adult literacy rate",
        "unit": "% of people aged 15+",
        "source": "UNESCO / World Bank",
        "wb_code": "SE.ADT.LITR.ZS",
        "higher_is_better": True,
    },
    "school_enrollment": {
        "label": "Primary school enrollment",
        "unit": "% gross",
        "source": "UNESCO / World Bank",
        "wb_code": "SE.PRM.ENRR",
        "higher_is_better": True,
    },
    "life_expectancy": {
        "label": "Life expectancy at birth",
        "unit": "years",
        "source": "World Bank / UN",
        "wb_code": "SP.DYN.LE00.IN",
        "higher_is_better": True,
    },
}

COUNTRIES = {
    "ghana": {
        "name": "Ghana",
        "wb_code": "GH",
        "iso3": "GHA",
        "output": "ghana_indicators.json",
    },
    "nigeria": {
        "name": "Nigeria",
        "wb_code": "NG",
        "iso3": "NGA",
        "output": "nigeria_indicators.json",
    },
    "ivorycoast": {
        "name": "Côte d'Ivoire",
        "wb_code": "CI",
        "iso3": "CIV",
        "output": "ivorycoast_indicators.json",
    },
}

WB_BASE = "https://api.worldbank.org/v2/country"
OUT_DIR = Path(__file__).parent.parent / "data" / "processed_indicators"


def fetch_indicator(wb_country: str, wb_indicator: str, mrv: int = 15) -> list[dict]:
    """Fetch most-recent-value time series from World Bank API. Returns list of {year, value}."""
    url = f"{WB_BASE}/{wb_country}/indicator/{wb_indicator}"
    params = {"format": "json", "mrv": mrv, "per_page": mrv}
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        payload = r.json()
        if len(payload) < 2 or not payload[1]:
            return []
        points = []
        for entry in payload[1]:
            if entry.get("value") is not None:
                points.append({"year": int(entry["date"]), "value": round(float(entry["value"]), 2)})
        return sorted(points, key=lambda x: x["year"])
    except Exception as e:
        print(f"  WARNING: {wb_indicator} for {wb_country} failed: {e}")
        return []


def build_country_data(country_key: str, mrv: int) -> dict:
    meta = COUNTRIES[country_key]
    print(f"\nFetching {meta['name']} ({meta['wb_code']})...")
    result = {
        "country": meta["name"],
        "country_key": country_key,
        "country_code": meta["iso3"],
        "wb_code": meta["wb_code"],
        "updated": date.today().isoformat(),
        "source": "World Bank Open Data API (api.worldbank.org)",
        "indicators": {},
    }
    for key, meta_ind in INDICATORS.items():
        print(f"  {key}...", end=" ", flush=True)
        trend = fetch_indicator(meta["wb_code"], meta_ind["wb_code"], mrv)
        current = trend[-1] if trend else None
        result["indicators"][key] = {
            "label": meta_ind["label"],
            "unit": meta_ind["unit"],
            "source": meta_ind["source"],
            "wb_indicator": meta_ind["wb_code"],
            "higher_is_better": meta_ind["higher_is_better"],
            "current": current,
            "trend": trend,
        }
        print(f"{'✓ ' + str(current['value']) + ' (' + str(current['year']) + ')' if current else 'no data'}")
        time.sleep(0.3)  # be polite to the API
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--country", choices=list(COUNTRIES.keys()), help="Fetch single country only")
    parser.add_argument("--years", type=int, default=15, help="Years of history to fetch (default: 15)")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    targets = [args.country] if args.country else list(COUNTRIES.keys())

    for country_key in targets:
        data = build_country_data(country_key, args.years)
        out_path = OUT_DIR / COUNTRIES[country_key]["output"]
        out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        print(f"  Saved → {out_path}")

    print("\nDone.")


if __name__ == "__main__":
    main()
