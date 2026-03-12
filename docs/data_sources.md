# Data Sources

## CHIRPS — Historical Rainfall
- **Provider:** Climate Hazards Group (UC Santa Barbara)
- **Coverage:** Global, 1981–present
- **Resolution:** 0.05° (~5km)
- **Auth required:** No
- **Access:** https://data.chc.ucsb.edu/products/CHIRPS-2.0/
- **Format:** GeoTIFF / NetCDF
- **Update:** Monthly (with ~2 week lag)
- **Use case:** Historical baselines, anomaly detection, drought/flood trends

## NASA IMERG — Near Real-Time Rainfall
- **Provider:** NASA Goddard Space Flight Center
- **Coverage:** Global (60°N–60°S)
- **Resolution:** 0.1° (~10km), 30-min or daily
- **Auth required:** Yes — NASA Earthdata account (free)
- **Access:** https://gpm.nasa.gov/data/imerg
- **Format:** HDF5 / NetCDF
- **Update:** 30-min (late run ~3.5hr delay), daily
- **Use case:** Near real-time rainfall alerts, current flood risk

## Sentinel-1 SAR — Flood Water Detection
- **Provider:** ESA (European Space Agency) / Copernicus
- **Coverage:** Global
- **Resolution:** 10m–40m
- **Auth required:** Copernicus Data Space account (free)
- **Access:** https://dataspace.copernicus.eu/
- **Format:** GeoTIFF (after processing)
- **Update:** ~6 days revisit
- **Use case:** Detecting actual standing water — most accurate flood mapping

## MODIS — Surface Water / Land Cover
- **Provider:** NASA
- **Coverage:** Global
- **Resolution:** 250m–1km
- **Auth required:** NASA Earthdata account (free)
- **Access:** https://lpdaac.usgs.gov/
- **Format:** HDF / GeoTIFF
- **Update:** 8-day composites
- **Use case:** Permanent vs seasonal water bodies, land use context

## Africa GeoPortal — Esri-Powered Open Data Hub
- **URL:** https://www.africageoportal.com/pages/Get%20Started
- **Provider:** Esri (powered by ArcGIS Online)
- **Auth required:** Free registration for full access
- **Contact:** africageoportal@esri.com
- **What it is:** Open mapping community for Africa — data discovery, training, and app creation
- **Key pillars:** Discover (datasets), Learn (training), Create (maps/apps)

### Useful components for InsightsAfrica:
- **Africa Living Atlas** — curated geospatial datasets for Africa (land, environment, admin boundaries)
- **Digital Earth Africa (DEA)** — satellite-derived products:
  - Annual coastlines 2000–2021, rates of change, coastal hotspots
  - Land monitoring, water extent, vegetation (NDVI), urban change
  - Access via: https://www.digitalearthafrica.org / DEA Explorer
- **GRID3** — high-resolution population and infrastructure grids for Africa
- **RCMRD** — Regional Centre for Mapping of Resources for Development (East/Southern Africa)
- **AfriGEO** — African Group on Earth Observations initiative

### Country portals (expansion targets):
- Kenya GeoPortal, Rwanda GeoPortal, Zambia GeoPortal

### Training resources (GIS upskilling):
- Esri Academy — free courses for registered users
- Learning Center — beginner to advanced GIS/remote sensing

### Notes:
- Esri/ArcGIS ecosystem — data and tools are well-documented but platform is proprietary
- DEA products are open/free and highly relevant (NDVI, water, coastline change)
- Good reference for dataset discovery when expanding InsightsAfrica to new countries
- Portal initiatives (country hubs) are a model for the InsightsAfrica multi-country expansion

---

## Ghana Statistical Service (GSS) — Official National Statistics
- **URL:** https://statsghana.gov.gh
- **Auth required:** No (public portal). Microdata Catalogue requires registration.
- **Contact:** info@statsghana.gov.gh | Finance Drive, Accra | +233302664304

### Key live indicators (as of early 2026):
| Indicator | Value | Period |
|---|---|---|
| CPI Inflation | 3.3% | Feb 2026 |
| GDP Growth | 5.6% | 2024 |
| Unemployment | 13.0% | Q3 2025 |
| Population (projected) | 34,378,768 | 2026 |
| Multidimensional Poverty | 21.9% | Q3 2025 |
| Food Insecurity | 38.1% | Q3 2025 |

### Data portals:
- **StatsBank** — time-series data across sectors and regions (StatsBank 2.0 upcoming)
- **Microdata Catalogue** — download raw survey datasets + metadata for research
- **National Reporting Platform** — census findings and demographic data
- **Ghana Gridded Data Portal** — spatial data for planning (population grids)
- **CPI Inflation Calculator** — historical inflation-adjusted values
- **Open Data for Africa** — regional/continental comparisons

### Data categories:
- Population & Housing Census (demographics, household composition)
- Agricultural Census (farm-level statistics, crop production)
- Economic Census (business/industrial activity)
- Labour Force Surveys (employment, unemployment, sector breakdown)
- Consumer/Producer Price Indices
- National Accounts / GDP

### Use cases for InsightsAfrica:
- Food insecurity data — contextual layer for CropWatch (38.1% food insecure as of Q3 2025)
- District-level population — denominator for per-capita flood/crop risk scoring
- Agricultural census — which regions grow what crops (ground truth for CropWatch)
- Unemployment/poverty spatial data — overlay with environmental stress layers
- GDP by sector — mining sector stats to contextualise MineWatch impact

---

## Ghana Bounding Box
```
West:  -3.2617
East:   1.2166
South:  4.7370
North: 11.1748
```
