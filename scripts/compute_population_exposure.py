#!/usr/bin/env python3
"""Compute per-district population for the Risk Index exposure multiplier (TD-2).

Zonal-sums a WorldPop 2020 1km population raster over the district boundaries
(the SAME boundaries used for rainfall zonal stats, so the keys match the SPI /
risk district keys by construction). Writes
data/exposure/{country}_population.json keyed "name|region".

WorldPop is open (CC-BY). Raster fetched on demand; only the small JSON is kept
in git (the .tif is gitignored).

Usage:
    ./venv/bin/python scripts/compute_population_exposure.py --country ghana
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import requests
from rasterstats import zonal_stats

BASE_DIR = Path(__file__).resolve().parent.parent

# WorldPop unconstrained 2020, 1km aggregated, per ISO3
_ISO3 = {"ghana": "GHA", "nigeria": "NGA", "ivorycoast": "CIV",
         "senegal": "SEN", "capeverde": "CPV", "southafrica": "ZAF"}


def _worldpop_url(country: str) -> str:
    iso = _ISO3[country]
    return (f"https://data.worldpop.org/GIS/Population/Global_2000_2020_1km/2020/"
            f"{iso}/{iso.lower()}_ppp_2020_1km_Aggregated.tif")


def main() -> None:
    ap = argparse.ArgumentParser(description="Per-district population for Risk Index exposure.")
    ap.add_argument("--country", required=True, choices=sorted(_ISO3))
    args = ap.parse_args()
    country = args.country

    boundaries = BASE_DIR / "data" / "processed" / f"{country}_districts.geojson"
    if not boundaries.is_file():
        raise FileNotFoundError(
            f"District boundaries not found: {boundaries}\n"
            f"Run scripts/fetch_boundaries.py first (or sync from free-arm2)."
        )

    exp_dir = BASE_DIR / "data" / "exposure"
    exp_dir.mkdir(parents=True, exist_ok=True)
    tif = exp_dir / f"{country}_ppp_2020_1km.tif"

    if not tif.is_file():
        url = _worldpop_url(country)
        print(f"[fetch] {url}")
        resp = requests.get(url, timeout=300)
        resp.raise_for_status()
        tif.write_bytes(resp.content)

    geo = json.loads(boundaries.read_text())
    # all_touched=False avoids double-counting boundary pixels in a population SUM
    stats = zonal_stats(geo["features"], str(tif), stats=["sum"],
                        all_touched=False, nodata=-99999)
    pop: dict[str, float] = {}
    for feat, s in zip(geo["features"], stats):
        p = feat["properties"]
        key = f"{p['name']}|{p['region']}"
        pop[key] = round(float(s["sum"] or 0.0), 0)

    out = exp_dir / f"{country}_population.json"
    out.write_text(json.dumps(pop, indent=2, sort_keys=True) + "\n")
    total = sum(pop.values())
    print(f"[write] {out} — {len(pop)} districts, total {total:,.0f}")


if __name__ == "__main__":
    main()
