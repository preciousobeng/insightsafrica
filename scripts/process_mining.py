"""
process_mining.py

Downloads specific Sentinel-2 L2A bands for each mining site,
computes NDVI and NDWI for baseline and recent periods,
generates change detection PNGs and updates the sites JSON.

Supports Ghana (artisanal/galamsey) and Nigeria (artisanal + oil/gas impact).

Bands used:
  B03 (Green, 10m)  — for NDWI
  B04 (Red,   10m)  — for NDVI
  B08 (NIR,   10m)  — for NDVI + NDWI

Indices:
  NDVI   = (B08 - B04) / (B08 + B04)   vegetation health (-1 to +1)
  NDWI   = (B03 - B08) / (B03 + B08)   water body detection (-1 to +1)
  Change = recent_NDVI - baseline_NDVI  loss shown as red

Usage:
    python scripts/process_mining.py
    python scripts/process_mining.py --site prestea_bogoso
    python scripts/process_mining.py --country nigeria
    python scripts/process_mining.py --country nigeria --site ogoniland
"""

import argparse
import json
import os
import zipfile
import time
from pathlib import Path

import numpy as np
import requests
from dotenv import load_dotenv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

load_dotenv()

BASE_DIR      = Path(__file__).parent.parent
RAW_DIR       = BASE_DIR / "data" / "raw" / "sentinel2"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
NIGERIA_DIR   = BASE_DIR / "data" / "processed_nigeria"
SENEGAL_DIR   = BASE_DIR / "data" / "processed_senegal"

COUNTRY_SITES_FILE = {
    "ghana":   PROCESSED_DIR / "galamsey_sites.json",
    "nigeria": NIGERIA_DIR   / "nigeria_mining_sites.json",
    "senegal": SENEGAL_DIR   / "senegal_mining_sites.json",
}

COUNTRY_OUT_DIR = {
    "ghana":   PROCESSED_DIR,
    "nigeria": NIGERIA_DIR,
    "senegal": SENEGAL_DIR,
}

# PNG prefix per country
COUNTRY_PNG_PREFIX = {
    "ghana":   "galamsey",
    "nigeria": "nigeria",
    "senegal": "senegal",
}

CDSE_TOKEN_URL   = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
CDSE_DOWNLOAD    = "https://download.dataspace.copernicus.eu/odata/v1/Products({id})/$value"

# Sentinel-2 band filenames by resolution
BAND_RESOLUTION = {
    "B03": "R10m",
    "B04": "R10m",
    "B08": "R10m",
}


# ── Authentication ──────────────────────────────────────────────────────────

def get_token() -> str:
    user     = os.getenv("COPERNICUS_USER")
    password = os.getenv("COPERNICUS_PASSWORD")
    if not user or not password:
        raise EnvironmentError("COPERNICUS_USER / COPERNICUS_PASSWORD not set in .env")
    resp = requests.post(CDSE_TOKEN_URL, data={
        "client_id":  "cdse-public",
        "username":   user,
        "password":   password,
        "grant_type": "password",
    }, timeout=30)
    resp.raise_for_status()
    return resp.json()["access_token"]


# ── Band extraction from product zip ────────────────────────────────────────

def find_band_in_zip(zf: zipfile.ZipFile, band: str, resolution: str) -> str | None:
    """Locate a band file inside a Sentinel-2 .SAFE zip."""
    suffix = f"_{band}_{resolution[1:]}.jp2"  # R10m → 10m
    matches = [n for n in zf.namelist() if n.endswith(suffix) and "IMG_DATA" in n]
    return matches[0] if matches else None


def download_product(product_id: str, product_name: str, token: str) -> Path:
    """Download a full Sentinel-2 product zip. Returns path to saved zip."""
    zip_path = RAW_DIR / f"{product_name}.zip"
    if zip_path.exists():
        print(f"  Already downloaded: {zip_path.name}")
        return zip_path

    url = CDSE_DOWNLOAD.format(id=product_id)
    headers = {"Authorization": f"Bearer {token}"}
    print(f"  Downloading product ({product_name})…")

    session = requests.Session()
    session.headers.update(headers)

    with session.get(url, stream=True, timeout=300, allow_redirects=True) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        downloaded = 0
        with open(zip_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded / total * 100
                    print(f"\r  {pct:.0f}%", end="", flush=True)
    print()
    print(f"  Saved: {zip_path.name}")
    return zip_path


def extract_band(zip_path: Path, band: str, out_dir: Path) -> Path | None:
    """Extract a single band .jp2 from a Sentinel-2 product zip."""
    resolution = BAND_RESOLUTION[band]
    out_path = out_dir / f"{zip_path.stem}_{band}.jp2"

    if out_path.exists():
        return out_path

    with zipfile.ZipFile(zip_path) as zf:
        name = find_band_in_zip(zf, band, resolution)
        if not name:
            print(f"  Band {band} not found in {zip_path.name}")
            return None
        with zf.open(name) as src, open(out_path, "wb") as dst:
            dst.write(src.read())

    return out_path


# ── Raster processing ────────────────────────────────────────────────────────

def read_band_clipped(jp2_path: Path, bbox: list) -> tuple:
    """
    Read a band clipped to a bounding box.
    Returns (data_array, profile).
    bbox: [lon_min, lat_min, lon_max, lat_max]
    """
    import rasterio
    from rasterio.mask import mask
    from shapely.geometry import box

    geom = box(bbox[0], bbox[1], bbox[2], bbox[3])

    with rasterio.open(jp2_path) as src:
        from pyproj import Transformer
        if str(src.crs) != "EPSG:4326":
            t = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
            x_min, y_min = t.transform(bbox[0], bbox[1])
            x_max, y_max = t.transform(bbox[2], bbox[3])
            from shapely.geometry import box as sbox
            geom_native = sbox(x_min, y_min, x_max, y_max)
        else:
            geom_native = geom

        clipped, transform = mask(src, [geom_native], crop=True)
        profile = src.profile.copy()
        profile.update({
            "height": clipped.shape[1],
            "width":  clipped.shape[2],
            "transform": transform,
        })

    data = clipped[0].astype(float)
    data[data == 0] = np.nan
    return data, profile


def compute_index(band_a: np.ndarray, band_b: np.ndarray) -> np.ndarray:
    """Generic normalised difference index: (A - B) / (A + B)."""
    with np.errstate(divide="ignore", invalid="ignore"):
        denom = band_a + band_b
        idx = np.where(denom != 0, (band_a - band_b) / denom, np.nan)
    return np.clip(idx, -1, 1)


def save_index_png(data: np.ndarray, out_path: Path, colormap: str,
                   vmin: float = -1, vmax: float = 1, opacity: float = 0.85):
    """Save a normalised index array as a colour-coded RGBA PNG."""
    norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
    cmap = plt.get_cmap(colormap)
    rgba = cmap(norm(data))
    rgba[..., 3] = np.where(np.isnan(data), 0, opacity)
    plt.imsave(str(out_path), rgba, origin="upper")


# ── Main processing pipeline ─────────────────────────────────────────────────

def process_site(site: dict, token: str, out_dir: Path, png_prefix: str) -> dict:
    """
    Full pipeline for one mining site.
    Downloads bands, computes indices, generates PNGs.
    Returns updated site dict.
    """
    sid  = site["id"]
    bbox = site["bbox"]
    print(f"\n=== {site['name']} ({site['region']}) ===")

    bands_dir = RAW_DIR / sid
    bands_dir.mkdir(parents=True, exist_ok=True)

    indices = {}

    for period in ("baseline", "recent"):
        meta_path = RAW_DIR / f"{sid}_{period}.json"
        if not meta_path.exists():
            print(f"  {period}: no product metadata — run fetch_sentinel2.py first")
            continue

        with open(meta_path) as f:
            meta = json.load(f)

        product_id   = meta["product_id"]
        product_name = meta["product_name"]
        date         = meta["date"]

        print(f"  {period}: {product_name} ({date})")

        zip_path = download_product(product_id, product_name, token)

        band_data = {}
        period_profile = None
        for band in ("B03", "B04", "B08"):
            jp2 = extract_band(zip_path, band, bands_dir)
            if jp2:
                data, prof = read_band_clipped(jp2, bbox)
                band_data[band] = data
                if period_profile is None:
                    period_profile = prof
            else:
                print(f"  Missing band {band} — skipping {period}")
                break

        if len(band_data) < 3:
            continue

        ndvi = compute_index(band_data["B08"], band_data["B04"])
        ndwi = compute_index(band_data["B03"], band_data["B08"])

        indices[period] = {
            "ndvi":    ndvi,
            "ndwi":    ndwi,
            "date":    date,
            "profile": period_profile,
        }

        ndvi_path = out_dir / f"{png_prefix}_{sid}_{period}_ndvi.png"
        ndwi_path = out_dir / f"{png_prefix}_{sid}_{period}_ndwi.png"
        save_index_png(ndvi, ndvi_path, "RdYlGn", vmin=-0.5, vmax=0.8)
        save_index_png(ndwi, ndwi_path, "RdBu",   vmin=-0.5, vmax=0.5)
        print(f"  Saved {period} NDVI/NDWI PNGs")

    # Compute change if both periods available
    ndvi_change = ndwi_change = None
    change_png = None

    if "baseline" in indices and "recent" in indices:
        import rasterio
        from rasterio.warp import reproject, Resampling

        b = indices["baseline"]
        r = indices["recent"]

        def align_to_baseline(src_arr, src_prof, dst_prof):
            if src_arr.shape == (dst_prof["height"], dst_prof["width"]):
                return src_arr
            out = np.full((dst_prof["height"], dst_prof["width"]), np.nan, dtype=np.float32)
            reproject(
                source=src_arr.astype(np.float32),
                destination=out,
                src_transform=src_prof["transform"],
                src_crs=src_prof["crs"],
                dst_transform=dst_prof["transform"],
                dst_crs=dst_prof["crs"],
                resampling=Resampling.bilinear,
                src_nodata=np.nan,
                dst_nodata=np.nan,
            )
            return out

        r_ndvi = align_to_baseline(r["ndvi"], r["profile"], b["profile"])
        r_ndwi = align_to_baseline(r["ndwi"], r["profile"], b["profile"])

        change = r_ndvi - b["ndvi"]
        change_png_path = out_dir / f"{png_prefix}_{sid}_change.png"
        save_index_png(change, change_png_path, "RdYlGn", vmin=-0.5, vmax=0.5)
        print(f"  Saved change detection PNG")

        valid = change[~np.isnan(change)]
        ndvi_change = float(np.mean(valid)) if len(valid) else None
        ndwi_change_arr = r_ndwi - b["ndwi"]
        valid_w = ndwi_change_arr[~np.isnan(ndwi_change_arr)]
        ndwi_change = float(np.mean(valid_w)) if len(valid_w) else None
        change_png = change_png_path.name

        period_label = f"{indices['baseline']['date']} \u2192 {indices['recent']['date']}"
    else:
        period_label = None

    site.update({
        "ndvi_change": round(ndvi_change, 4) if ndvi_change is not None else None,
        "ndwi_change": round(ndwi_change, 4) if ndwi_change is not None else None,
        "period":      period_label,
        "ndvi_png":    f"{png_prefix}_{sid}_recent_ndvi.png" if "recent" in indices else None,
        "ndwi_png":    f"{png_prefix}_{sid}_recent_ndwi.png" if "recent" in indices else None,
        "change_png":  change_png,
    })
    return site


def main():
    parser = argparse.ArgumentParser(description="Process Sentinel-2 mining change detection")
    parser.add_argument("--country", choices=list(COUNTRY_SITES_FILE), default="ghana")
    parser.add_argument("--site",    help="Process a single site by ID (default: all)")
    args = parser.parse_args()

    sites_path = COUNTRY_SITES_FILE[args.country]
    out_dir    = COUNTRY_OUT_DIR[args.country]
    png_prefix = COUNTRY_PNG_PREFIX[args.country]

    out_dir.mkdir(parents=True, exist_ok=True)

    if not sites_path.exists():
        print(f"Sites JSON not found: {sites_path}")
        print(f"Run: python scripts/fetch_sentinel2.py --country {args.country}")
        return

    with open(sites_path) as f:
        all_sites = json.load(f)

    to_process = all_sites
    if args.site:
        to_process = [s for s in all_sites if s["id"] == args.site]
        if not to_process:
            print(f"Site '{args.site}' not found")
            return

    token = get_token()

    updated_by_id = {}
    for site in to_process:
        try:
            updated_by_id[site["id"]] = process_site(site, token, out_dir, png_prefix)
        except Exception as e:
            print(f"  Error processing {site['id']}: {e}")
            updated_by_id[site["id"]] = site
        time.sleep(2)

    # Merge processed sites back into full list
    merged = [updated_by_id.get(s["id"], s) for s in all_sites]
    with open(sites_path, "w") as f:
        json.dump(merged, f, indent=2)
    print(f"\nUpdated {sites_path.name}")


if __name__ == "__main__":
    main()
