"""
process_crop.py

Processes MODIS MOD13Q1 HDF files into NDVI PNGs for farming regions.
Computes crop stress risk score based on NDVI distribution.

Usage:
    python scripts/process_crop.py --year 2024 --doy 177
    python scripts/process_crop.py --year 2024 --doy 177 --country nigeria
"""

import argparse
import json
import re
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

BASE_DIR          = Path(__file__).parent.parent
RAW_DIR           = BASE_DIR / "data" / "raw" / "modis_ndvi"
PROCESSED_DIR     = BASE_DIR / "data" / "processed"
NIGERIA_DIR       = BASE_DIR / "data" / "processed_nigeria"
IVORYCOAST_DIR    = BASE_DIR / "data" / "processed_ivorycoast"
SENEGAL_DIR       = BASE_DIR / "data" / "processed_senegal"
CAPEVERDE_DIR     = BASE_DIR / "data" / "processed_capeverde"

COUNTRY_OUT_DIRS = {
    "ghana":      PROCESSED_DIR,
    "nigeria":    NIGERIA_DIR,
    "ivorycoast": IVORYCOAST_DIR,
    "senegal":    SENEGAL_DIR,
    "capeverde":  CAPEVERDE_DIR,
}

COUNTRY_BBOXES = {
    "ghana":      {"west": -3.2617, "east":  1.2166, "south":  4.7370, "north": 11.1748},
    "nigeria":    {"west":  2.668,  "east": 14.678,  "south":  4.269,  "north": 13.872},
    "ivorycoast": {"west": -8.601,  "east": -2.493,  "south":  4.341,  "north": 10.740},
    "senegal":    {"west": -17.535, "east": -11.355, "south": 12.307, "north": 16.693},
    "capeverde":  {"west": -25.50,  "east": -22.60,  "south": 14.75,  "north": 17.25},
}

DOY_TO_MONTH = {
     1: "Jan",  17: "Jan",  33: "Feb",  49: "Feb",
     65: "Mar",  81: "Mar",  97: "Apr", 113: "Apr",
    129: "May", 145: "May", 161: "Jun", 177: "Jun",
    193: "Jul", 209: "Jul", 225: "Aug", 241: "Aug",
    257: "Sep", 273: "Sep", 289: "Oct", 305: "Oct",
    321: "Nov", 337: "Nov", 353: "Dec",
}


def extract_ndvi(hdf_paths: list, bbox: dict) -> np.ndarray:
    """
    Extract and mosaic NDVI from one or more MODIS MOD13Q1 HDF files.
    Uses pyhdf (no GDAL HDF4 driver required).

    Ghana spans 2 tiles: h17v07 + h17v08 (vertical mosaic, same column).
    Nigeria spans 4 tiles: h17v07/h17v08 (west column) + h18v07/h18v08 (east column)
    requiring a 2×2 horizontal+vertical mosaic.

    Returns the clipped NDVI array (float, NaN where nodata).
    """
    from pyhdf.SD import SD, SDC
    import re

    # Approximate WGS84 bounds for each MODIS tile (sinusoidal projection,
    # rectangular approximation sufficient for visualization overlays).
    TILE_BOUNDS = {
        "h15v07": {"west": -31.5, "east": -18.5, "south": 10.0, "north": 20.0},
        "h16v07": {"west": -18.5, "east": -5.0, "south": 10.0, "north": 20.0},
        "h16v08": {"west": -18.5, "east": -5.0, "south":  0.0, "north": 10.0},
        "h17v07": {"west":  -5.0, "east":  8.5, "south": 10.0, "north": 20.0},
        "h17v08": {"west":  -5.0, "east":  8.4, "south":  0.0, "north": 10.0},
        "h18v07": {"west":   8.0, "east": 21.5, "south": 10.0, "north": 20.0},
        "h18v08": {"west":   8.0, "east": 21.5, "south":  0.0, "north": 10.0},
    }

    tiles = {}
    for p in hdf_paths:
        m = re.search(r"(h\d{2}v\d{2})", p.name)
        if not m:
            continue
        tile_id = m.group(1)
        if tile_id not in TILE_BOUNDS:
            continue
        hdf = SD(str(p), SDC.READ)
        sds = hdf.select("250m 16 days NDVI")
        raw = sds[:].astype(float)
        hdf.end()
        # Apply MODIS scale factor; -3000 is the fill value
        tiles[tile_id] = np.where(raw == -3000, np.nan, raw * 0.0001)

    if not tiles:
        raise ValueError(f"No recognisable MODIS tiles found in: {[p.name for p in hdf_paths]}")

    # ── Mosaic strategy ────────────────────────────────────────────────────
    # If both columns present (h17 + h18): 2×2 mosaic
    #   top row:    [h17v07 | h18v07]  (north band)
    #   bottom row: [h17v08 | h18v08]  (south band)
    # If only h17 column: 2-tile vertical mosaic (Ghana)
    # Fallback: single tile

    has_h16 = "h16v07" in tiles or "h16v08" in tiles
    has_h17 = "h17v07" in tiles or "h17v08" in tiles
    has_h18 = "h18v07" in tiles or "h18v08" in tiles

    def col_mosaic(north_key, south_key):
        """Vertical mosaic of one column (north above south)."""
        if north_key in tiles and south_key in tiles:
            return np.vstack([tiles[north_key], tiles[south_key]])
        return tiles.get(north_key) or tiles.get(south_key)

    def hstack_cols(col_w, col_e):
        """Horizontally concatenate two column mosaics, padding to equal height."""
        h = max(col_w.shape[0], col_e.shape[0])
        if col_w.shape[0] < h:
            col_w = np.vstack([col_w, np.full((h - col_w.shape[0], col_w.shape[1]), np.nan)])
        if col_e.shape[0] < h:
            col_e = np.vstack([col_e, np.full((h - col_e.shape[0], col_e.shape[1]), np.nan)])
        return np.hstack([col_w, col_e])

    has_h15 = "h15v07" in tiles or "h15v08" in tiles

    if has_h15 and not has_h16 and not has_h17 and not has_h18:
        # Cape Verde: single tile h15v07
        mosaic = tiles.get("h15v07") or list(tiles.values())[0]
        mb = TILE_BOUNDS["h15v07"]
    elif has_h16 and has_h17 and not has_h18:
        # Ivory Coast: h16 (west) + h17 (east) — 2×2 mosaic
        col16 = col_mosaic("h16v07", "h16v08")
        col17 = col_mosaic("h17v07", "h17v08")
        mosaic = hstack_cols(col16, col17)
        mb = {"west": -18.5, "east": 8.5, "south": 0.0, "north": 20.0}
    elif has_h17 and has_h18:
        # Nigeria: h17 (west) + h18 (east) — 2×2 mosaic
        col17 = col_mosaic("h17v07", "h17v08")
        col18 = col_mosaic("h18v07", "h18v08")
        mosaic = hstack_cols(col17, col18)
        mb = {"west": -5.0, "east": 21.5, "south": 0.0, "north": 20.0}
    else:
        mosaic = col_mosaic("h17v07", "h17v08") or list(tiles.values())[0]
        if "h17v07" in tiles and "h17v08" in tiles:
            mb = {"west": -5.0, "east": 8.4, "south": 0.0, "north": 20.0}
        elif "h17v07" in tiles:
            mb = TILE_BOUNDS["h17v07"]
        else:
            mb = TILE_BOUNDS["h17v08"]

    # Clip mosaic to country bbox using linear index mapping
    nrows, ncols = mosaic.shape
    lon_span = mb["east"] - mb["west"]
    lat_span = mb["north"] - mb["south"]

    c0 = max(0, int((bbox["west"] - mb["west"]) / lon_span * ncols))
    c1 = min(ncols, int((bbox["east"] - mb["west"]) / lon_span * ncols) + 1)
    r0 = max(0, int((mb["north"] - bbox["north"]) / lat_span * nrows))
    r1 = min(nrows, int((mb["north"] - bbox["south"]) / lat_span * nrows) + 1)

    return mosaic[r0:r1, c0:c1]


def compute_stress_score(ndvi: np.ndarray) -> dict:
    """
    Simple stress score based on NDVI distribution.
    Returns dict with % area in each stress category.
    """
    valid = ndvi[~np.isnan(ndvi)]
    if not len(valid):
        return {}

    categories = {
        "severe_stress":   float(np.mean(valid < 0.2)  * 100),
        "moderate_stress": float(np.mean((valid >= 0.2) & (valid < 0.4)) * 100),
        "fair":            float(np.mean((valid >= 0.4) & (valid < 0.6)) * 100),
        "healthy":         float(np.mean(valid >= 0.6)  * 100),
        "mean_ndvi":       round(float(np.mean(valid)), 4),
        "min_ndvi":        round(float(np.min(valid)),  4),
        "max_ndvi":        round(float(np.max(valid)),  4),
    }
    return categories


def process(hdf_paths: list, year: int, doy: int, country: str = "ghana") -> dict:
    out_dir = COUNTRY_OUT_DIRS.get(country, PROCESSED_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    bbox  = COUNTRY_BBOXES[country]
    label = f"{DOY_TO_MONTH.get(doy, f'DOY{doy}')} {year}"
    stem  = f"ndvi_{year}_{doy:03d}_{country}"

    out_png  = out_dir / f"{stem}.png"
    out_meta = out_dir / f"{stem}.json"

    print(f"Extracting NDVI from {len(hdf_paths)} tile(s)…")
    ndvi = extract_ndvi(hdf_paths, bbox)

    valid = ndvi[~np.isnan(ndvi)]
    print(f"NDVI range: {np.nanmin(ndvi):.3f} – {np.nanmax(ndvi):.3f}  mean: {np.nanmean(ndvi):.3f}")

    # Save PNG — RdYlGn: red=stressed, green=healthy
    norm = mcolors.Normalize(vmin=0, vmax=0.8)
    cmap = plt.get_cmap("RdYlGn")
    rgba = cmap(norm(ndvi))
    rgba[..., 3] = np.where(np.isnan(ndvi), 0, 0.8)
    plt.imsave(str(out_png), rgba, origin="upper")
    print(f"Saved PNG: {out_png.name}")

    stress = compute_stress_score(ndvi)

    # Approximate leaflet bounds (country extent after clip)
    meta = {
        "label":  label,
        "year":   year,
        "doy":    doy,
        "source": "MODIS MOD13Q1 250m",
        "leaflet_bounds": [
            [bbox["south"], bbox["west"]],
            [bbox["north"], bbox["east"]],
        ],
        "stress_score": stress,
        "png": out_png.name,
    }

    with open(out_meta, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"Saved metadata: {out_meta.name}")
    return meta


def main():
    parser = argparse.ArgumentParser(description="Process MODIS NDVI for crop watch")
    parser.add_argument("--year",    type=int, required=True)
    parser.add_argument("--doy",     type=int, required=True)
    parser.add_argument("--country", choices=list(COUNTRY_BBOXES), default="ghana")
    args = parser.parse_args()

    pattern = f"*A{args.year}{args.doy:03d}*.hdf"
    files = list(RAW_DIR.glob(pattern))
    if not files:
        print(f"No HDF files found for year={args.year} doy={args.doy:03d}")
        print(f"Run: python scripts/fetch_modis_ndvi.py --country {args.country} "
              f"--year {args.year} --doy {args.doy}")
        return

    process(files, args.year, args.doy, args.country)


if __name__ == "__main__":
    main()
