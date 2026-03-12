"""
process_heatwatch.py

Converts Landsat 9 ST_B10 GeoTIFF → Land Surface Temperature (LST) in °C.
Computes Urban Heat Island (UHI) intensity and saves:
  - PNG:  temperature colour map clipped to city bbox
  - JSON: stats metadata for the API

Landsat C2 L2 ST_B10 DN → Kelvin:
    LST_K = DN * 0.00341802 + 149.0
    LST_C = LST_K - 273.15

UHI intensity = mean(inner urban core) − mean(outer rural ring)

Usage:
    python scripts/process_heatwatch.py                          # Ghana, all cities
    python scripts/process_heatwatch.py --city accra             # Ghana, single city
    python scripts/process_heatwatch.py --country nigeria        # Nigeria, all cities
    python scripts/process_heatwatch.py --country nigeria --city lagos
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

BASE_DIR      = Path(__file__).parent.parent
RAW_DIR       = BASE_DIR / "data" / "raw" / "landsat"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
NIGERIA_DIR   = BASE_DIR / "data" / "processed_nigeria"

COUNTRY_CITIES = {
    "ghana": {
        "accra":  {"name": "Accra",  "region": "Greater Accra",
                   "bbox": [-0.42, 5.45, 0.05, 5.76]},
        "kumasi": {"name": "Kumasi", "region": "Ashanti",
                   "bbox": [-1.87, 6.54, -1.37, 6.85]},
        "tamale": {"name": "Tamale", "region": "Northern",
                   "bbox": [-1.05, 9.25, -0.62, 9.56]},
    },
    "nigeria": {
        "lagos": {"name": "Lagos", "region": "Lagos State",
                  "bbox": [3.1, 6.3, 3.7, 6.7]},
        "kano":  {"name": "Kano",  "region": "Kano State",
                  "bbox": [8.4, 11.9, 8.7, 12.2]},
        "abuja": {"name": "Abuja", "region": "FCT",
                  "bbox": [7.3, 8.8, 7.6, 9.1]},
    },
}

# Landsat C2 L2 scale / offset for surface temperature
ST_SCALE  = 0.00341802
ST_OFFSET = 149.0
ST_FILL   = 0


def read_lst(tif_path: Path, bbox: list) -> np.ndarray:
    """
    Open an ST_B10.TIF, clip to bbox, convert DN → °C.
    bbox: [lon_min, lat_min, lon_max, lat_max]
    Returns float array in Celsius (NaN where nodata).
    """
    import rasterio
    from rasterio.mask import mask as rio_mask
    from shapely.geometry import box as sbox
    from pyproj import Transformer

    geom_wgs84 = sbox(bbox[0], bbox[1], bbox[2], bbox[3])

    with rasterio.open(tif_path) as src:
        # Reproject bbox to the raster's CRS (Landsat is usually UTM)
        if str(src.crs).upper() != "EPSG:4326":
            t = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
            x0, y0 = t.transform(bbox[0], bbox[1])
            x1, y1 = t.transform(bbox[2], bbox[3])
            geom_native = sbox(x0, y0, x1, y1)
        else:
            geom_native = geom_wgs84

        clipped, _ = rio_mask(src, [geom_native], crop=True, filled=True,
                               nodata=ST_FILL)

    dn = clipped[0].astype(float)
    # Fill value → NaN
    dn[dn == ST_FILL] = np.nan

    lst_k = dn * ST_SCALE + ST_OFFSET
    lst_c = lst_k - 273.15

    # Sanity clip: Ghana LST range roughly 10–55 °C
    lst_c = np.where((lst_c < 5) | (lst_c > 60), np.nan, lst_c)
    return lst_c


def compute_uhi(lst_c: np.ndarray) -> float | None:
    """
    Estimate UHI intensity: mean of inner 33% (urban core) minus
    mean of outer ring (rural fringe).
    Returns difference in °C, or None if insufficient valid pixels.
    """
    valid = ~np.isnan(lst_c)
    if valid.sum() < 100:
        return None

    nrows, ncols = lst_c.shape
    r_lo = nrows // 3
    r_hi = 2 * nrows // 3
    c_lo = ncols // 3
    c_hi = 2 * ncols // 3

    urban_mask = np.zeros_like(lst_c, dtype=bool)
    urban_mask[r_lo:r_hi, c_lo:c_hi] = True

    urban = lst_c[urban_mask & valid]
    rural = lst_c[~urban_mask & valid]

    if not len(urban) or not len(rural):
        return None

    return round(float(np.mean(urban) - np.mean(rural)), 2)


def save_lst_png(lst_c: np.ndarray, out_path: Path):
    """Save LST array as a colour-coded RGBA PNG (blue→red temperature scale)."""
    # RdYlBu reversed: blue=cool, red=hot — vmin/vmax tuned for Ghana
    cmap = plt.get_cmap("RdYlBu_r")
    norm = mcolors.Normalize(vmin=20, vmax=42)
    rgba = cmap(norm(lst_c))
    rgba[..., 3] = np.where(np.isnan(lst_c), 0, 0.82)
    plt.imsave(str(out_path), rgba, origin="upper")


def process_city(city_id: str, country: str = "ghana") -> list:
    """Process all downloaded ST_B10 files for a city. Returns list of metadata dicts."""
    city    = COUNTRY_CITIES[country][city_id]
    out_dir = NIGERIA_DIR if country == "nigeria" else PROCESSED_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = RAW_DIR / city_id

    if not raw_dir.exists():
        print(f"  No raw data directory for {city['name']} — run fetch_landsat.py first")
        return []

    tif_files = sorted(raw_dir.glob("*_ST_B10.TIF"))
    if not tif_files:
        print(f"  No ST_B10.TIF files found for {city['name']}")
        return []

    results = []
    for tif in tif_files:
        # Derive date from filename: LC09_L2SP_193056_20240115_*_ST_B10.TIF
        m = re.search(r"_(\d{8})_", tif.name)
        if not m:
            continue
        raw_date = m.group(1)
        date_str = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
        stem     = f"heat_{city_id}_{raw_date}"

        out_png  = out_dir / f"{stem}.png"
        out_json = out_dir / f"{stem}.json"

        if out_json.exists():
            print(f"  Already processed: {stem}")
            with open(out_json) as f:
                results.append(json.load(f))
            continue

        print(f"  Processing: {tif.name}")

        try:
            lst_c = read_lst(tif, city["bbox"])
        except Exception as e:
            print(f"    Error reading {tif.name}: {e}")
            continue

        valid = lst_c[~np.isnan(lst_c)]
        if not len(valid):
            print("    No valid pixels after clip — skipping")
            continue

        mean_c = round(float(np.nanmean(lst_c)), 2)
        max_c  = round(float(np.nanmax(lst_c)),  2)
        min_c  = round(float(np.nanmin(lst_c)),  2)
        uhi    = compute_uhi(lst_c)
        urban_mean = None
        rural_mean = None

        # Compute urban/rural means separately for the JSON
        nrows, ncols = lst_c.shape
        valid_mask   = ~np.isnan(lst_c)
        u_mask = np.zeros_like(lst_c, dtype=bool)
        u_mask[nrows//3:2*nrows//3, ncols//3:2*ncols//3] = True
        u_vals = lst_c[u_mask & valid_mask]
        r_vals = lst_c[~u_mask & valid_mask]
        if len(u_vals):
            urban_mean = round(float(np.mean(u_vals)), 2)
        if len(r_vals):
            rural_mean = round(float(np.mean(r_vals)), 2)

        save_lst_png(lst_c, out_png)
        print(f"    Saved PNG: {out_png.name}  (mean={mean_c}°C  max={max_c}°C  UHI={uhi}°C)")

        bbox = city["bbox"]
        meta = {
            "city_id":   city_id,
            "city_name": city["name"],
            "region":    city["region"],
            "date":      date_str,
            "source":    "Landsat 9 ST_B10 C2 L2",
            "leaflet_bounds": [[bbox[1], bbox[0]], [bbox[3], bbox[2]]],
            "stats": {
                "mean_lst_c":    mean_c,
                "max_lst_c":     max_c,
                "min_lst_c":     min_c,
                "urban_mean_c":  urban_mean,
                "rural_mean_c":  rural_mean,
                "uhi_intensity_c": uhi,
            },
            "png": out_png.name,
        }

        with open(out_json, "w") as f:
            json.dump(meta, f, indent=2)
        print(f"    Saved JSON: {out_json.name}")
        results.append(meta)

    return results


def main():
    all_city_ids = [cid for cc in COUNTRY_CITIES.values() for cid in cc]
    parser = argparse.ArgumentParser(description="Process Landsat LST for cities")
    parser.add_argument("--country", choices=list(COUNTRY_CITIES), default="ghana")
    parser.add_argument("--city",    choices=all_city_ids,
                        help="Process a single city (default: all for selected country)")
    args = parser.parse_args()

    cities = COUNTRY_CITIES[args.country]
    city_ids = [args.city] if args.city else list(cities.keys())

    for city_id in city_ids:
        print(f"\n=== {cities[city_id]['name']} ===")
        results = process_city(city_id, args.country)
        print(f"  {len(results)} layer(s) processed.")

    print("\nDone. Restart uvicorn (or it will auto-reload) to serve new layers.")


if __name__ == "__main__":
    main()
