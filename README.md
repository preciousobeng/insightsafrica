# InsightsAfrica — Satellite Intelligence Platform for Africa

[![Licence: CC BY-NC 4.0](https://img.shields.io/badge/Licence-CC%20BY--NC%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/)

**Live platform:** [insightsafrica.org](https://insightsafrica.org)

InsightsAfrica is an open-access satellite intelligence platform that monitors environmental risk across Africa. It delivers interactive, data-driven intelligence on **flood risk**, **illegal mining**, **crop health**, and **urban heat** — currently covering **Ghana** and **Nigeria**.

The platform is built on freely available satellite data (Sentinel-2, CHIRPS, MODIS, Landsat 9) and is designed for governments, NGOs, researchers, insurers, and agribusinesses operating in West Africa.

---

## What It Does

### FloodWatch
Monthly rainfall accumulation maps derived from CHIRPS (Climate Hazards Group InfraRed Precipitation with Station data). Covers **24 months of historical data (2024–2025)** at district/state level.

- Ghana: all 16 regions, district boundaries
- Nigeria: all 37 states + FCT, 775 LGAs

Use cases: flood risk underwriting, humanitarian pre-positioning, infrastructure site selection, NADMO/NEMA disaster preparedness.

### MineWatch
Satellite change detection for illegal and artisanal mining sites using Sentinel-2 multispectral imagery. Tracks vegetation loss (NDVI), water body changes (NDWI), and land surface change over time.

- Ghana: 5 galamsey (illegal gold mining) sites across the Ashanti, Western, and Eastern regions
- Nigeria: 10 sites — 5 artisanal mining sites (Jos Plateau, Zamfara) + 5 oil/gas impact sites (Niger Delta: Ogoniland, Warri, Imo Delta)

Use cases: environmental compliance monitoring, ESG due diligence, regulatory enforcement, academic research.

### CropWatch
Vegetation health monitoring using MODIS MOD13Q1 NDVI composites. Tracks crop stress indicators across major farming regions over time.

- Ghana: key farming regions, 24 months of composites
- Nigeria: 46 MODIS composites (23 × 2024 + 23 × 2025)

Use cases: agricultural insurance, food security early warning, commodity forecasting.

### HeatWatch
Urban heat mapping derived from Landsat 9 thermal band. Compares land surface temperature across city zones.

- Ghana: Accra, Kumasi, Tamale (2024)
- Nigeria: Lagos (×2 zones), Kano (×2 zones), Abuja (×2 zones) (2024)

Use cases: urban planning, climate adaptation, public health risk mapping.

---

## Coverage

| Country | Modules | Admin Boundaries | Data Period |
|---------|---------|-----------------|-------------|
| Ghana | FloodWatch, MineWatch, CropWatch, HeatWatch | Regions + Districts | 2024–2025 |
| Nigeria | FloodWatch, MineWatch, CropWatch, HeatWatch | 37 States + 775 LGAs | 2024–2025 |

---

## Data Sources

| Dataset | Provider | Resolution | Coverage |
|---------|----------|-----------|---------|
| CHIRPS v2.0 | UCSB Climate Hazards Center | 0.05° (~5km) | Monthly rainfall |
| Sentinel-2 MSI | ESA Copernicus / CDSE | 10m | Mining change detection |
| MODIS MOD13Q1 | NASA EOSDIS | 250m | Vegetation (NDVI) |
| Landsat 9 OLI/TIRS | USGS / NASA Earthdata | 30m (thermal: 100m) | Urban heat |
| Admin boundaries | GADM / NBS Nigeria / GSS Ghana | — | District/state/LGA polygons |

All source data is open access under their respective provider terms.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Data processing | Python — `rasterio`, `geopandas`, `xarray`, `numpy`, `requests` |
| Backend API | FastAPI (Python) |
| Frontend | Leaflet.js, vanilla HTML/CSS/JS |
| Hosting | Oracle Cloud Infrastructure ARM (free tier) |
| Tunnel / CDN | Cloudflare Tunnel + Cloudflare proxy |
| Auth | Supabase (email confirmation, JWT) |
| SMTP | Brevo (transactional email) |

---

## Platform Structure

```
insightsafrica.org/          Landing page
insightsafrica.org/hub.html  Ghana Intelligence Hub
insightsafrica.org/flood/    Ghana FloodWatch
insightsafrica.org/mine/     Ghana MineWatch
insightsafrica.org/crop/     Ghana CropWatch
insightsafrica.org/heat/     Ghana HeatWatch

insightsafrica.org/nigeria/hub.html  Nigeria Intelligence Hub
insightsafrica.org/nigeria/flood/    Nigeria FloodWatch
insightsafrica.org/nigeria/mine/     Nigeria MineWatch
insightsafrica.org/nigeria/crop/     Nigeria CropWatch
insightsafrica.org/nigeria/heat/     Nigeria HeatWatch
```

---

## Target Users

- **Governments & regulators** — NADMO, NEMA, EPA Ghana, state environmental agencies
- **NGOs & humanitarian organisations** — flood early warning, food security monitoring
- **Insurance & finance** — parametric crop/flood insurance underwriting
- **Agribusinesses** — crop stress monitoring, yield forecasting inputs
- **Researchers & academics** — open environmental data for West Africa
- **ESG & compliance teams** — mining impact verification, supply chain due diligence

---

## Roadmap

- [x] Ghana — all four modules live (v0.1.0)
- [x] Nigeria — all four modules live (v0.3.0)
- [ ] HeatWatch 2025 data (Ghana + Nigeria)
- [ ] FloodWatch time-lapse animation player
- [ ] Alert subscriptions (email notifications for high-risk periods)
- [ ] Additional country coverage (Kenya, Côte d'Ivoire planned)
- [ ] API access tier for developers and researchers

---

## Enquiries

For research collaboration, data access, or partnership enquiries:
**info@insightsafrica.org** | [insightsafrica.org](https://insightsafrica.org)

---

## Licence

This project is licensed under [Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)](https://creativecommons.org/licenses/by-nc/4.0/).

You may use, share, and adapt this work for **non-commercial purposes** with attribution. Commercial use requires explicit written permission.

For commercial licensing: **info@insightsafrica.org**

---

*Built on open satellite data for open environmental intelligence.*
