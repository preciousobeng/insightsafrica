"""
fetch_sentinel2.py

Downloads Sentinel-2 L2A imagery for mining sites in Ghana or Nigeria
using the Copernicus Data Space Ecosystem (CDSE) OData API.

Auth: Free account at https://dataspace.copernicus.eu/

Usage:
    python scripts/fetch_sentinel2.py
    python scripts/fetch_sentinel2.py --country nigeria

Environment variables required in .env:
    COPERNICUS_USER=your_email
    COPERNICUS_PASSWORD=your_password
"""

import argparse
import json
import os
import time
from pathlib import Path
from datetime import datetime, timedelta

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_DIR          = Path(__file__).parent.parent
RAW_DIR           = BASE_DIR / "data" / "raw" / "sentinel2"
PROCESSED_DIR     = BASE_DIR / "data" / "processed"
NIGERIA_DIR       = BASE_DIR / "data" / "processed_nigeria"
IVORYCOAST_DIR    = BASE_DIR / "data" / "processed_ivorycoast"
CAPEVERDE_DIR     = BASE_DIR / "data" / "processed_capeverde"

# Ghana artisanal mining (galamsey) hotspots — (lon_min, lat_min, lon_max, lat_max)
GHANA_SITES = [
    {
        "id":       "prestea_bogoso",
        "name":     "Prestea-Bogoso",
        "region":   "Western",
        "category": "artisanal",
        "bbox":     [-2.10, 5.37, -1.85, 5.55],
        "centre":   [-1.992, 5.437],
        "notes":    "Major artisanal mining corridor, Ankobra River tributary",
    },
    {
        "id":       "dunkwa_offin",
        "name":     "Dunkwa-on-Offin",
        "region":   "Central",
        "category": "artisanal",
        "bbox":     [-1.90, 5.85, -1.65, 6.10],
        "centre":   [-1.780, 5.960],
        "notes":    "Offin River basin — severe water body degradation",
    },
    {
        "id":       "obuasi",
        "name":     "Obuasi",
        "region":   "Ashanti",
        "category": "artisanal",
        "bbox":     [-1.80, 6.10, -1.55, 6.35],
        "centre":   [-1.675, 6.200],
        "notes":    "AngloGold boundary area, artisanal mining encroachment",
    },
    {
        "id":       "tarkwa",
        "name":     "Tarkwa",
        "region":   "Western",
        "category": "artisanal",
        "bbox":     [-2.10, 5.20, -1.85, 5.45],
        "centre":   [-1.993, 5.300],
        "notes":    "Gold Fields concession area, active artisanal mining",
    },
    {
        "id":       "akyem_oda",
        "name":     "Akyem Oda",
        "region":   "Eastern",
        "category": "artisanal",
        "bbox":     [-1.10, 5.83, -0.85, 6.05],
        "centre":   [-0.990, 5.929],
        "notes":    "Birim River — heavily affected by small-scale mining",
    },
]

# Nigeria sites: 5 artisanal (north) + 5 oil/gas impact (Niger Delta)
NIGERIA_SITES = [
    # Artisanal mining — northern Nigeria
    {
        "id":       "zamfara_gold",
        "name":     "Zamfara Gold Belt",
        "region":   "Zamfara",
        "category": "artisanal",
        "bbox":     [6.0, 11.8, 7.0, 12.5],
        "centre":   [6.5, 12.15],
        "notes":    "Active artisanal gold mining, Gusau corridor",
    },
    {
        "id":       "nasarawa_mixed",
        "name":     "Nasarawa Mining Zone",
        "region":   "Nasarawa",
        "category": "artisanal",
        "bbox":     [7.8, 8.2, 8.5, 8.8],
        "centre":   [8.15, 8.5],
        "notes":    "Mixed mineral artisanal mining corridor",
    },
    {
        "id":       "jos_tin",
        "name":     "Jos Plateau Tin Fields",
        "region":   "Plateau",
        "category": "artisanal",
        "bbox":     [8.6, 9.5, 9.3, 10.3],
        "centre":   [8.95, 9.9],
        "notes":    "Historic tin mining, ongoing artisanal activity",
    },
    {
        "id":       "kaduna_quarry",
        "name":     "Kaduna South Quarrying",
        "region":   "Kaduna",
        "category": "artisanal",
        "bbox":     [7.2, 9.5, 7.9, 10.4],
        "centre":   [7.55, 9.95],
        "notes":    "Small-scale quarrying and mineral extraction",
    },
    {
        "id":       "cross_river_lead",
        "name":     "Cross River Lead/Zinc",
        "region":   "Cross River",
        "category": "artisanal",
        "bbox":     [8.5, 5.8, 9.2, 6.7],
        "centre":   [8.85, 6.25],
        "notes":    "Lead-zinc artisanal mining, forest impact",
    },
    # Oil/gas impact — Niger Delta
    {
        "id":       "ogoniland",
        "name":     "Ogoniland",
        "region":   "Rivers",
        "category": "oil_gas",
        "bbox":     [7.0, 4.7, 7.3, 5.0],
        "centre":   [7.15, 4.85],
        "notes":    "Decades of oil spill contamination, UNEP assessment site",
    },
    {
        "id":       "bodo_creek",
        "name":     "Bodo Creek",
        "region":   "Rivers",
        "category": "oil_gas",
        "bbox":     [6.85, 4.35, 7.15, 4.65],
        "centre":   [7.0, 4.5],
        "notes":    "Major oil spill site, mangrove and water contamination",
    },
    {
        "id":       "nembe_bayelsa",
        "name":     "Nembe",
        "region":   "Bayelsa",
        "category": "oil_gas",
        "bbox":     [6.35, 4.45, 6.65, 4.75],
        "centre":   [6.5, 4.6],
        "notes":    "Pipeline corrosion and chronic oil leakage",
    },
    {
        "id":       "warri_creeks",
        "name":     "Warri Creeks",
        "region":   "Delta",
        "category": "oil_gas",
        "bbox":     [5.4, 5.45, 5.7, 5.75],
        "centre":   [5.55, 5.6],
        "notes":    "Active oil operations, flaring and water contamination",
    },
    {
        "id":       "imo_delta",
        "name":     "Imo River Delta",
        "region":   "Imo",
        "category": "oil_gas",
        "bbox":     [6.8, 4.9, 7.1, 5.2],
        "centre":   [6.95, 5.05],
        "notes":    "Riverine oil impact, vegetation and fishery loss",
    },
]

# Ivory Coast (Côte d'Ivoire) — industrial gold mining sites
IVORYCOAST_SITES = [
    {
        "id":       "tongon",
        "name":     "Tongon Gold Mine",
        "region":   "Hambol",
        "category": "industrial",
        "bbox":     [-6.35, 9.15, -5.90, 9.60],
        "centre":   [-6.125, 9.375],
        "notes":    "Barrick Gold open-pit mine, ~250koz/yr, operational since 2010",
    },
    {
        "id":       "ity",
        "name":     "Ity Gold Mine",
        "region":   "Cavally",
        "category": "industrial",
        "bbox":     [-7.75, 7.28, -7.32, 7.72],
        "centre":   [-7.535, 7.500],
        "notes":    "Endeavour Mining open-pit CIL mine, western border area",
    },
    {
        "id":       "agbaou",
        "name":     "Agbaou Gold Mine",
        "region":   "Lôh-Djiboua",
        "category": "industrial",
        "bbox":     [-5.52, 5.52, -5.10, 5.96],
        "centre":   [-5.310, 5.740],
        "notes":    "Endeavour Mining open-pit mine, central-south CIV",
    },
    {
        "id":       "bonikro",
        "name":     "Bonikro Gold Mine",
        "region":   "Lôh-Djiboua",
        "category": "industrial",
        "bbox":     [-5.42, 5.70, -5.02, 6.14],
        "centre":   [-5.220, 5.920],
        "notes":    "Allied Gold open-pit mine, adjacent Agbaou district",
    },
    {
        "id":       "seguela",
        "name":     "Séguéla Gold Mine",
        "region":   "Worodougou",
        "category": "industrial",
        "bbox":     [-6.86, 7.71, -6.44, 8.17],
        "centre":   [-6.650, 7.940],
        "notes":    "Fortuna Silver Mines, opened 2023, ~170koz/yr capacity",
    },
]

# Senegal mining sites
SENEGAL_SITES = [
    {
        "id":       "sabodala_massawa",
        "name":     "Sabodala-Massawa Gold Mine",
        "region":   "Kédougou",
        "category": "industrial",
        "bbox":     [-12.20, 12.50, -11.80, 12.82],
        "centre":   [-12.010, 12.660],
        "notes":    "Endeavour Mining, ~220koz/yr, largest gold mine in Senegal",
    },
    {
        "id":       "kedougou_artisanal",
        "name":     "Kédougou Artisanal Zone",
        "region":   "Kédougou",
        "category": "artisanal",
        "bbox":     [-12.40, 12.35, -11.95, 12.75],
        "centre":   [-12.180, 12.550],
        "notes":    "Artisanal and small-scale gold mining (ASM) across Kédougou Prefecture",
    },
    {
        "id":       "mako",
        "name":     "Mako Mining Corridor",
        "region":   "Kédougou",
        "category": "artisanal",
        "bbox":     [-12.55, 12.70, -12.10, 13.05],
        "centre":   [-12.350, 12.870],
        "notes":    "Emerging artisanal mining area near Mako village",
    },
]


CAPEVERDE_SITES = [
    {
        "id":       "santiago_basalt",
        "name":     "Santiago Basalt Quarry Zone",
        "region":   "Santiago",
        "category": "industrial",
        "bbox":     [-23.60, 14.95, -23.40, 15.15],
        "centre":   [-23.500, 15.050],
        "notes":    "Basalt extraction for construction materials, primary island quarrying zone",
    },
    {
        "id":       "santo_antao_pozzolana",
        "name":     "Santo Antão Pozzolana Zone",
        "region":   "Santo Antão",
        "category": "industrial",
        "bbox":     [-25.20, 17.00, -25.00, 17.20],
        "centre":   [-25.100, 17.100],
        "notes":    "Volcanic pozzolana soil extraction used in cement and construction",
    },
    {
        "id":       "sal_salt_flats",
        "name":     "Sal Salt Flats (Pedra de Lume)",
        "region":   "Sal",
        "category": "artisanal",
        "bbox":     [-22.95, 16.75, -22.83, 16.87],
        "centre":   [-22.890, 16.810],
        "notes":    "Historic crater-lake salt extraction, Pedra de Lume, Sal island",
    },
    {
        "id":       "sao_vicente_quarry",
        "name":     "São Vicente Quarry Zone",
        "region":   "São Vicente",
        "category": "artisanal",
        "bbox":     [-25.06, 16.85, -24.90, 16.95],
        "centre":   [-24.980, 16.900],
        "notes":    "Basalt and aggregate quarrying supplying Mindelo port construction",
    },
]

COUNTRY_SITES = {
    "ghana":      GHANA_SITES,
    "nigeria":    NIGERIA_SITES,
    "ivorycoast": IVORYCOAST_SITES,
    "senegal":    SENEGAL_SITES,
    "capeverde":  CAPEVERDE_SITES,
}

CDSE_TOKEN_URL  = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
CDSE_SEARCH_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
CDSE_DOWNLOAD_BASE = "https://zipper.dataspace.copernicus.eu/odata/v1"


def get_token(user: str, password: str) -> str:
    """Get a short-lived access token from Copernicus Data Space."""
    resp = requests.post(CDSE_TOKEN_URL, data={
        "client_id":  "cdse-public",
        "username":   user,
        "password":   password,
        "grant_type": "password",
    }, timeout=30)
    resp.raise_for_status()
    return resp.json()["access_token"]


def search_products(bbox: list, date_start: str, date_end: str,
                    max_cloud: int = 20) -> list:
    """
    Search for Sentinel-2 L2A products over a bounding box.

    Args:
        bbox: [lon_min, lat_min, lon_max, lat_max]
        date_start: 'YYYY-MM-DD'
        date_end:   'YYYY-MM-DD'
        max_cloud:  maximum cloud cover percentage

    Returns:
        List of product dicts from the CDSE catalogue.
    """
    lon_min, lat_min, lon_max, lat_max = bbox
    aoi = (
        f"POLYGON(({lon_min} {lat_min},{lon_max} {lat_min},"
        f"{lon_max} {lat_max},{lon_min} {lat_max},{lon_min} {lat_min}))"
    )

    params = {
        "$filter": (
            f"Collection/Name eq 'SENTINEL-2' "
            f"and Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'productType' "
            f"  and att/OData.CSC.StringAttribute/Value eq 'S2MSI2A') "
            f"and ContentDate/Start gt {date_start}T00:00:00.000Z "
            f"and ContentDate/Start lt {date_end}T23:59:59.000Z "
            f"and Attributes/OData.CSC.DoubleAttribute/any(att:att/Name eq 'cloudCover' "
            f"  and att/OData.CSC.DoubleAttribute/Value le {max_cloud}.00) "
            f"and OData.CSC.Intersects(area=geography'SRID=4326;{aoi}')"
        ),
        "$orderby": "ContentDate/Start desc",
        "$top": "5",
    }

    resp = requests.get(CDSE_SEARCH_URL, params=params, timeout=60)
    resp.raise_for_status()
    return resp.json().get("value", [])


def save_sites_json(sites: list, out_path: Path):
    """Write mining sites JSON for the MineWatch API."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out = []
    for site in sites:
        bbox = site["bbox"]
        out.append({
            "id":       site["id"],
            "name":     site["name"],
            "region":   site["region"],
            "category": site.get("category", "artisanal"),
            "centre":   site["centre"],
            "bbox":     bbox,
            "notes":    site["notes"],
            "leaflet_bounds": [
                [bbox[1], bbox[0]],
                [bbox[3], bbox[2]],
            ],
            "ndvi_change": None,
            "ndwi_change": None,
            "period":      None,
            "ndvi_png":    None,
            "ndwi_png":    None,
            "change_png":  None,
        })
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"Saved {len(out)} sites to {out_path.name}")


def main():
    parser = argparse.ArgumentParser(description="Fetch Sentinel-2 for mining sites")
    parser.add_argument("--country", choices=list(COUNTRY_SITES), default="ghana")
    args = parser.parse_args()

    sites = COUNTRY_SITES[args.country]
    processed_dir = {
        "nigeria":    NIGERIA_DIR,
        "ivorycoast": IVORYCOAST_DIR,
        "capeverde":  CAPEVERDE_DIR,
    }.get(args.country, PROCESSED_DIR)
    sites_filename = {
        "nigeria":    "nigeria_mining_sites.json",
        "ivorycoast": "ivorycoast_mining_sites.json",
        "capeverde":  "capeverde_mining_sites.json",
    }.get(args.country, "galamsey_sites.json")
    sites_path = processed_dir / sites_filename

    user     = os.getenv("COPERNICUS_USER")
    password = os.getenv("COPERNICUS_PASSWORD")

    if not user or not password:
        print("COPERNICUS_USER / COPERNICUS_PASSWORD not set in .env")
        print("Register free at: https://dataspace.copernicus.eu/")
        print("\nSaving site definitions only (no imagery download).")
        save_sites_json(sites, sites_path)
        return

    print("Authenticating with Copernicus Data Space…")
    token = get_token(user, password)
    print("Authenticated.\n")

    # Search windows: baseline (2 years ago) and recent (last 3 months)
    today     = datetime.utcnow()
    recent_end   = today.strftime("%Y-%m-%d")
    recent_start = (today - timedelta(days=90)).strftime("%Y-%m-%d")
    baseline_end   = (today - timedelta(days=365*2)).strftime("%Y-%m-%d")
    baseline_start = (today - timedelta(days=365*2 + 90)).strftime("%Y-%m-%d")

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    for site in sites:
        print(f"--- {site['name']} ---")
        for label, d_start, d_end in [
            ("baseline", baseline_start, baseline_end),
            ("recent",   recent_start,   recent_end),
        ]:
            products = search_products(site["bbox"], d_start, d_end, max_cloud=15)
            if not products:
                print(f"  {label}: no products found (try relaxing cloud cover)")
                continue
            p = products[0]
            print(f"  {label}: {p['Name']} — cloud {p.get('Attributes',{})}")

            # Save product metadata (actual download is large — ~800MB per tile)
            meta_path = RAW_DIR / f"{site['id']}_{label}.json"
            with open(meta_path, "w") as f:
                json.dump({
                    "site_id":      site["id"],
                    "period":       label,
                    "product_id":   p["Id"],
                    "product_name": p["Name"],
                    "date":         p["ContentDate"]["Start"][:10],
                }, f, indent=2)
            print(f"  Saved product metadata: {meta_path.name}")
        time.sleep(1)

    save_sites_json(sites, sites_path)
    print(f"\nNext step: run process_mining.py --country {args.country}")


if __name__ == "__main__":
    main()
