"""
process_rainfall.py

Converts a CHIRPS GeoTIFF into:
  1. A colour-coded PNG overlay (for Leaflet imageOverlay)
  2. A metadata JSON file (bounds, min/max rainfall, date)

Usage:
    python scripts/process_rainfall.py --input data/raw/chirps/chirps-v2.0.2024.12_ghana.tif
    python scripts/process_rainfall.py --input data/raw/chirps/chirps-v2.0.2024.12_nigeria.tif --country nigeria
    python scripts/process_rainfall.py --input ... --colormap RdYlBu_r
"""

import argparse
import json
import re
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import transform_bounds
import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

BASE_DIR      = Path(__file__).parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"
NIGERIA_DIR   = BASE_DIR / "data" / "processed_nigeria"

COUNTRY_BOUNDARIES = {
    "ghana": {
        "regions":   PROCESSED_DIR / "ghana_regions.geojson",
        "districts": PROCESSED_DIR / "ghana_districts.geojson",
    },
    "nigeria": {
        "states": NIGERIA_DIR / "nigeria_states.geojson",
        "lgas":   NIGERIA_DIR / "nigeria_lgas.geojson",
    },
}


def parse_date_from_filename(filename: str) -> dict:
    """Extract year and month from CHIRPS filename."""
    match = re.search(r"(\d{4})\.(\d{2})", filename)
    if match:
        return {"year": int(match.group(1)), "month": int(match.group(2))}
    return {}


MONTH_NAMES = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December",
}


def process(tif_path: Path, colormap: str = "YlGnBu", country: str = "ghana") -> dict:
    """
    Read GeoTIFF, apply colourmap, save PNG + metadata JSON.
    Returns metadata dict.
    """
    out_dir = NIGERIA_DIR if country == "nigeria" else PROCESSED_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    stem = tif_path.stem  # e.g. chirps-v2.0.2024.12_ghana or ..._nigeria
    out_png = out_dir / f"{stem}.png"
    out_meta = out_dir / f"{stem}.json"

    with rasterio.open(tif_path) as src:
        data = src.read(1).astype(float)
        nodata = src.nodata
        bounds = src.bounds

        # Convert bounds to WGS84 lat/lon if needed
        lon_min, lat_min, lon_max, lat_max = transform_bounds(
            src.crs, "EPSG:4326",
            bounds.left, bounds.bottom, bounds.right, bounds.top
        )

    # Mask no-data values
    if nodata is not None:
        data = np.where(data == nodata, np.nan, data)
    data = np.where(data < 0, np.nan, data)  # CHIRPS uses -9999 for no-data

    valid = data[~np.isnan(data)]
    rain_min = float(np.min(valid)) if len(valid) else 0.0
    rain_max = float(np.max(valid)) if len(valid) else 0.0
    rain_mean = float(np.mean(valid)) if len(valid) else 0.0

    print(f"Rainfall range: {rain_min:.1f} – {rain_max:.1f} mm")
    print(f"Mean rainfall:  {rain_mean:.1f} mm")

    # Normalise 0 → rain_max (cap at 95th percentile to avoid outliers washing out colour)
    cap = float(np.percentile(valid, 95)) if len(valid) else rain_max
    norm = mcolors.Normalize(vmin=0, vmax=cap)
    cmap = plt.get_cmap(colormap)

    rgba = cmap(norm(data))          # shape: (H, W, 4)
    rgba[..., 3] = np.where(np.isnan(data), 0, 0.75)  # transparent for no-data

    # Save PNG (matplotlib imsave preserves RGBA)
    plt.imsave(str(out_png), rgba, origin="upper")
    print(f"Saved PNG: {out_png}")

    # Save metadata
    date_info = parse_date_from_filename(tif_path.name)
    month_name = MONTH_NAMES.get(date_info.get("month", 0), "")
    label = f"{month_name} {date_info.get('year', '')}" if month_name else stem

    metadata = {
        "label": label,
        "year": date_info.get("year"),
        "month": date_info.get("month"),
        "bounds": {
            "west": round(lon_min, 6),
            "south": round(lat_min, 6),
            "east": round(lon_max, 6),
            "north": round(lat_max, 6),
        },
        "leaflet_bounds": [
            [round(lat_min, 6), round(lon_min, 6)],
            [round(lat_max, 6), round(lon_max, 6)],
        ],
        "rainfall_mm": {
            "min": round(rain_min, 2),
            "max": round(rain_max, 2),
            "mean": round(rain_mean, 2),
            "colorscale_cap": round(cap, 2),
        },
        "colormap": colormap,
        "png": out_png.name,
    }

    # Zonal statistics per region and district
    zonal = compute_zonal_stats(tif_path, country)
    metadata["zonal_stats"] = zonal

    with open(out_meta, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"Saved metadata: {out_meta}")

    return metadata


def compute_zonal_stats(tif_path: Path, country: str = "ghana") -> dict:
    """
    Compute mean and max rainfall per region and district.
    Returns dict keyed by boundary level, then by area name.
    """
    from rasterstats import zonal_stats

    result = {}

    for level, geojson_path in COUNTRY_BOUNDARIES[country].items():
        if not geojson_path.exists():
            print(f"  Skipping {level} stats — run fetch_boundaries.py first")
            continue

        with open(geojson_path) as f:
            geojson = json.load(f)

        features = geojson.get("features", [])
        stats = zonal_stats(
            features,
            str(tif_path),
            stats=["mean", "max", "min"],
            nodata=-9999,
            geojson_out=False,
        )

        level_stats = {}
        for feature, stat in zip(features, stats):
            props = feature.get("properties", {})
            name = props.get("name", "Unknown")
            region = props.get("region", "")
            key = f"{name}|{region}" if region else name
            level_stats[key] = {
                "mean": round(stat["mean"], 1) if stat["mean"] is not None else None,
                "max":  round(stat["max"],  1) if stat["max"]  is not None else None,
                "min":  round(stat["min"],  1) if stat["min"]  is not None else None,
            }

        result[level] = level_stats
        print(f"  Zonal stats computed for {len(level_stats)} {level}")

    return result


def main():
    parser = argparse.ArgumentParser(description="Process CHIRPS GeoTIFF to PNG overlay")
    parser.add_argument("--input",    required=True, help="Path to clipped GeoTIFF")
    parser.add_argument("--country",  choices=list(COUNTRY_BOUNDARIES), default="ghana")
    parser.add_argument("--colormap", default="YlGnBu", help="Matplotlib colormap name")
    args = parser.parse_args()

    tif_path = Path(args.input)
    if not tif_path.exists():
        print(f"File not found: {tif_path}")
        return

    meta = process(tif_path, args.colormap, args.country)
    print(f"\nLeaflet bounds: {meta['leaflet_bounds']}")
    print(f"Rainfall {meta['label']}: {meta['rainfall_mm']['min']}–{meta['rainfall_mm']['max']} mm")


if __name__ == "__main__":
    main()
