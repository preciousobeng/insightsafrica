# InsightsAfrica — Roadmap

_Last updated: 2026-03-21_

---

## Current Build Status (as of 2026-03-20)

| Module | Status |
|---|---|
| FloodWatch — CHIRPS 2024+2025, map, chart, tooltips, boundaries | ✅ Done |
| MineWatch — Sentinel-2 NDVI/NDWI, 5 sites, galamsey_sites.json live | ✅ Done |
| CropWatch — 46 MODIS composites (2024+2025), all farming seasons covered | ✅ Done |
| HeatWatch — Landsat 9 LST, 3 cities (Accra/Kumasi/Tamale), 2024 data live | ✅ Done |
| InsightsAfrica landing page (`index.html`) | ✅ Done |
| InsightsAfrica hub page (`hub.html`) | ✅ Done |
| Real Africa map SVG (Natural Earth 110m, 48 countries) | ✅ Done |
| Auth system — login/signup/forgot password (`login.html`) | ✅ Done |
| Thank You screen post-signup (inspiring copy, email CTA) | ✅ Done |
| Open access — no login gate on platform content | ✅ Done |
| FastAPI backend v0.2.0 | ✅ Done |
| NASA Earthdata credentials in .env | ✅ Ready |
| Copernicus credentials in .env | ✅ Ready |
| Planetary Computer (Landsat) — no auth required | ✅ Ready |
| Domain — insightsafrica.org | ✅ Registered (Cloudflare, Mar 2026) |
| Nigeria boundaries (37 states + 775 LGAs) | ✅ Done — 2026-03-10 |
| Nigeria FloodWatch — CHIRPS 2024+2025 (24 months) | ✅ Done — 2026-03-10 |
| Nigeria HeatWatch — Landsat 9 2024 (Lagos/Kano/Abuja) | ✅ Done — 2026-03-10 |
| Nigeria MineWatch — nigeria_mining_sites.json (10 sites) | ✅ Done — 2026-03-10 |
| Nigeria MineWatch — Sentinel-2 NDVI/NDWI/change PNGs | ✅ Done — 10/10 sites (2026-03-11) |
| Nigeria CropWatch — MODIS NDVI 2024+2025 (46 composites) | ✅ Done — 2026-03-11 |
| Country switcher — Ghana/Nigeria/CdI/Senegal (all hubs) | ✅ Done — 2026-03-14 |
| OCI deployment — insightsafrica.org via Cloudflare Tunnel | ✅ Done — 2026-03-14 |
| Supabase SMTP via Brevo (auth emails live) | ✅ Done — 2026-03-14 |
| HumanWatch — World Bank indicators, 3 countries | ✅ Done — 2026-03-19 |
| Country Profile pages — 5-product radar chart + risk engine | ✅ Done — 2026-03-19 |
| Glowing pulse orbs on SVG map (Ghana/Nigeria/CdI/Senegal) | ✅ Done — 2026-03-19 |
| Côte d'Ivoire hub + full pipeline (FloodWatch/CropWatch/HeatWatch/MineWatch) | ✅ Done — 2026-03-19 |
| Côte d'Ivoire boundaries (GADM 4.1 — 14 districts + 107 sub-prefectures) | ✅ Done — 2026-03-19 |
| Senegal hub (FloodWatch/CropWatch/HeatWatch/MineWatch) | ✅ Done — 2026-03-20 |
| Senegal FloodWatch — CHIRPS 2024+2025 (24 months, 48 files) | ✅ Done — 2026-03-20 |
| Senegal CropWatch — MODIS NDVI 2024+2025 (46 composites, h16v07) | ✅ Done — 2026-03-20 |
| Senegal HeatWatch — Landsat 9 (Dakar/Saint-Louis/Touba, 6 scenes) | ✅ Done — 2026-03-20 |
| Senegal MineWatch — senegal_mining_sites.json (3 sites, Kédougou belt) | ✅ Done — 2026-03-20 |
| Senegal boundaries — GADM 4.1 (14 regions + 45 departments) | ✅ Done — 2026-03-20 |
| Senegal product pages (flood/crop/heat/mine/human/profile) | ✅ Done — 2026-03-21 |
| Senegal MineWatch — Sentinel-2 NDVI/NDWI processed (3 sites) | ✅ Done — 2026-03-21 |
| Senegal HumanWatch — World Bank indicators API + data | ✅ Done — 2026-03-21 |
| Senegal Country Profile — composite risk engine live | ✅ Done — 2026-03-21 |
| Senegal HeatWatch — cities corrected (Dakar/Saint-Louis/Touba) | ✅ Done — 2026-03-21 |
| Country switcher dropdown — all 4 hubs (CdI + Senegal upgraded) | ✅ Done — 2026-03-21 |
| Landing page — removed redundant country/product card sections | ✅ Done — 2026-03-21 |
| Telegram channel @insightsafricaorg — daily automated bulletin | ✅ Done — 2026-03-21 |
| Supabase keepalive monitor — 6-hourly, personal Telegram alert | ✅ Done — 2026-03-21 |

---

## Priority Order — Next Steps

```
✅  insightsafrica.org registered (Cloudflare, Mar 2026)
✅  CropWatch — 46 MODIS composites live (2024+2025)
✅  HeatWatch — Landsat 9 LST, 3 cities, 2024 data live
✅  MineWatch — galamsey_sites.json restored, all 5 sites live
✅  Nigeria full pipeline — FloodWatch, HeatWatch, MineWatch, CropWatch (2026-03-10/11)
✅  Country switcher — Ghana/Nigeria/CdI/Senegal across all hubs
✅  OCI deployment — insightsafrica.org live via Cloudflare Tunnel (2026-03-14)
✅  Côte d'Ivoire full pipeline + hub (2026-03-19)
✅  HumanWatch + Country Profile pages (2026-03-19)
✅  Senegal full pipeline + hub (2026-03-20)

✅  Telegram channel @insightsafricaorg + daily bulletin bot (gcloud-vm, Gemini 2.5 Flash, BBC/AJ RSS, 36h dedup) — 2026-03-21
2.  HeatWatch 2025 data               ← fetch_landsat.py --year 2025 for all countries
3.  CropWatch Leaflet time-lapse player ← Play/Pause, date range, speed control
4.  FloodWatch time-lapse player      ← same pattern, 24 monthly layers
5.  "Sign in for alerts" CTA on hub   ← premium upsell entry point
6.  Contact / enquiry form on landing page
7.  NASA IMERG real-time              ← upgrades FloodWatch from monthly to near-real-time
8.  Email/SMS alerts                  ← Africa's Talking for SMS, first monetisation
9.  PDF district reports              ← downloadable, branded, second monetisation item
10. Sentinel-1 SAR                    ← proper standing water detection
11. Paystack / Stripe                 ← payment infrastructure
```

---

## Phase 1 — MVP
**Goal:** Working flood risk dashboard for Ghana. Deployable, shareable, demo-ready.

### Milestone 1.1 — Data Pipeline
- [x] Register NASA Earthdata account (free)
- [x] Script to fetch CHIRPS historical rainfall for Ghana bounding box
- [ ] Script to fetch NASA IMERG near real-time rainfall
- [x] Process raw data into GeoTIFF tiles / PNGs
- [x] Store processed tiles in data/processed/

### Milestone 1.2 — Backend
- [x] FastAPI app serving processed tile data
- [x] Endpoint: `/api/flood/layers` — all CHIRPS layers with zonal stats
- [x] Endpoint: `/api/flood/layers/latest`
- [x] Endpoint: `/api/health` — service status
- [x] Endpoint: `/api/boundaries/{level}` — regions + districts GeoJSON
- [x] Endpoint: `/api/mine/sites` + `/api/mine/changes`
- [x] Endpoint: `/api/crop/layers`
- [x] Endpoint: `/api/heat/layers`

### Milestone 1.3 — Frontend
- [x] Leaflet.js map centred on Ghana (CartoDB Voyager basemap)
- [x] Rainfall overlay (colour-coded intensity, YlGnBu)
- [x] Year-on-year grouped bar chart (2024 vs 2025)
- [x] Collapsible year accordion in sidebar
- [x] District + region boundary overlays with per-area tooltips
- [x] MineWatch map with Sentinel-2 NDVI/NDWI/Change imagery
- [x] CropWatch map — 46 MODIS NDVI composites, stress bars, layer switcher
- [x] HeatWatch map — Landsat 9 LST overlay, 3 cities, UHI intensity, temp legend
- [x] InsightsAfrica hub (4 product cards) → hub.html
- [x] InsightsAfrica landing page (index.html) — hero, stats, product cards, audience, data sources
- [x] Real Africa map SVG from Natural Earth GeoJSON (scripts/generate_africa_svg.py)
- [x] Auth system — login/signup/forgot password/thank you screen (login.html + Supabase)
- [x] Open access — platform content public, login reserved for premium features
- [x] Deploy to OCI ARM via Cloudflare Tunnel — 2026-03-14

### Milestone 1.4 — Polish & Launch
- [x] Hub page with product cards
- [x] Proper marketing landing page — 2026-03-09
- [x] "About the data" sections in each module sidebar
- [x] Auth infrastructure (Supabase email/password)
- [x] Register insightsafrica.org (Cloudflare, $7.50/yr — Mar 2026)
- [x] Supabase SMTP via Brevo (auth emails live — 2026-03-14)
- [ ] Branded confirmation email template in Supabase dashboard
- [ ] Add "Sign in for alerts / reports" CTA on hub
- [ ] Contact / enquiry form on landing page

---

## Phase 2 — Monetisation Layer
**Goal:** Add paid features on top of free public dashboard.

- [ ] PDF report generation per district (downloadable, branded)
- [ ] Email alert system — notify subscribers when rainfall exceeds threshold
- [ ] SMS alerts via Africa's Talking API (popular in Ghana, works without smartphones)
- [ ] Simple subscription page (Paystack for Ghana users, Stripe for international)
- [ ] API access tier for B2B clients (insurance, logistics, agri firms)

---

## Phase 3 — Additional Data Layers
**Goal:** Expand insights beyond current modules.

- [ ] NASA IMERG near real-time rainfall (30-min updates, upgrade for FloodWatch)
- [ ] Sentinel-1 SAR actual flood water detection (more accurate than CHIRPS proxy)
- [x] HeatWatch — urban heat island mapping (Landsat 9 thermal, Accra/Kumasi/Tamale, 2024)
- [ ] NADMO historical flood event markers (Ghana disaster records)
- [ ] Volta Basin river level monitoring (Akosombo Dam catchment)
- [ ] Night-time lights data (economic activity / electrification proxy)

---

## Phase 4 — West Africa Expansion
**Goal:** Replicate model across neighbouring countries.

- [x] Nigeria — full pipeline (FloodWatch/CropWatch/HeatWatch/MineWatch) — 2026-03-10/11
- [x] Côte d'Ivoire — full pipeline + hub — 2026-03-19
- [x] Senegal — full pipeline + hub (MODIS tile h16v07, Kédougou mining, groundnut basin) — 2026-03-20
- [x] Country switcher across all hubs (Ghana/Nigeria/CdI/Senegal)
- [x] Glowing pulse orbs on SVG map for all 4 countries
- [x] HumanWatch — World Bank indicators across 4 countries (Senegal added 2026-03-21)
- [x] Country Profile pages — 5-product radar chart + risk engine, all 4 countries — 2026-03-19/21

---

## Phase 5 — Social Publishing
**Goal:** Automated intelligence distribution via social/messaging channels.

- [x] Telegram channel @insightsafricaorg — daily automated bulletin (2026-03-21)
  - BBC Africa + Al Jazeera RSS → Africa keyword filter → Gemini 2.5 Flash → Telegram Bot API
  - Cron on gcloud-vm (07:00 UTC), 36h TTL dedup dict, HTML parse_mode
- [ ] Twitter/X — same pipeline, X Basic tier (~£84/month) when reach justifies cost
- [ ] Newsletter / digest format (weekly PDF or email)

---

## Out of Scope (for now)
- ArcGIS / Esri tooling (open source stack only)
- Mobile app (web-first)
- Real-time river gauge sensors (hardware)
