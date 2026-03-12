# GhanaFloodWatch

**Real-time flood risk intelligence for Ghana — powered by open satellite data.**

Part of the [InsightsAfrica](https://insights.africa) initiative.

---

## What It Does

GhanaFloodWatch provides an interactive, data-driven flood risk dashboard for Ghana,
using freely available satellite and climate data to surface actionable insights for:

- Insurance companies (property/crop underwriting)
- Real estate developers (site selection)
- NGOs and humanitarian organisations (pre-positioning)
- NADMO and local government (disaster response planning)
- Agribusinesses and food supply chain operators

---

## Data Sources (all free/open)

| Source | Data | Update Frequency |
|--------|------|-----------------|
| NASA IMERG | Near real-time global rainfall | Daily / 30-min |
| CHIRPS | Historical rainfall (1981–present) | Monthly |
| Sentinel-1 SAR | Actual flood water detection (radar) | ~6 days |
| MODIS | Land cover, surface water | 8-day / annual |
| Ghana EPA / NADMO | Local flood event records | Ad hoc |

---

## Tech Stack

| Layer | Tool |
|-------|------|
| Data processing | Python: `rasterio`, `geopandas`, `xarray`, `requests` |
| Tile server | `titiler` (FastAPI-based) |
| Backend API | `FastAPI` |
| Frontend | Leaflet.js + HTML/CSS |
| Scheduler | `cron` (data refresh) |
| Hosting | OCI ARM Ubuntu (Oracle Cloud Free Tier) |
| CDN / Tunnel | Cloudflare Tunnel |
| Version control | Git / GitHub |

---

## Project Structure

```
GhanaFloodWatch/
├── data/
│   ├── raw/          # Downloaded source data (IMERG, CHIRPS, Sentinel)
│   ├── processed/    # Processed GeoTIFFs and map tiles
│   └── cache/        # Cached API responses
├── scripts/
│   ├── fetch_chirps.py       # Historical rainfall data
│   ├── fetch_imerg.py        # Near real-time rainfall (NASA Earthdata auth required)
│   └── process_rainfall.py   # Convert raw data to map-ready tiles
├── api/
│   ├── main.py               # FastAPI app entry point
│   └── routes/               # API route handlers
├── frontend/
│   ├── index.html            # Main dashboard
│   ├── css/
│   └── js/
├── notebooks/
│   └── exploration.ipynb     # Data exploration and prototyping
└── docs/
    ├── data_sources.md       # Detailed data source notes
    └── setup.md              # Environment setup guide
```

---

## Roadmap

See [ROADMAP.md](./ROADMAP.md) for the full phased plan.

---

## Setup

See [docs/setup.md](./docs/setup.md) for environment setup instructions.

---

## Phase 1 Focus Areas

- Accra (high urban flood risk, dense population)
- Volta River Basin (major flood corridor)
- Northern Ghana (seasonal flooding, food insecurity overlap)

---

## License

Open source. Built with public data for public benefit.
