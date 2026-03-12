# InsightsAfrica — Roadmap

_Last updated: 2026-03-11_

---

## Current Build Status (as of 2026-03-10)

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
| Country switcher — hub.html + nigeria/hub.html | ✅ Done — 2026-03-11 |
| OCI deployment | ❌ Not started — runs locally only |

---

## Priority Order — Next Steps

```
✅  insightsafrica.org registered (Cloudflare, Mar 2026)
✅  CropWatch — 46 MODIS composites live (2024+2025)
✅  HeatWatch — Landsat 9 LST, 3 cities, 2024 data live
✅  MineWatch — galamsey_sites.json restored, all 5 sites live
✅  Nigeria boundaries — 37 states + 775 LGAs (2026-03-10)
✅  Nigeria FloodWatch — CHIRPS 2024+2025, 24 months (2026-03-10)
✅  Nigeria HeatWatch — Landsat 9 2024, Lagos×2 / Kano×2 / Abuja×2 scenes (2026-03-10)
✅  Nigeria MineWatch — nigeria_mining_sites.json, 10 sites (2026-03-10)
✅  Nigeria CropWatch — MODIS NDVI 2024+2025 (46 composites)
⚠️  Nigeria MineWatch — 6/10 full, 3/10 baseline-only, 1/10 (jos_tin) failed
✅  Country switcher — hub.html + nigeria/hub.html (2026-03-11)

1.  Local review — Kweku reviews all Nigeria pages before OCI deployment
2.  Verify Nigeria FloodWatch UI loads correctly on server
3.  Supabase SMTP via Resend — 20-min task (config captured in MEMORY.md)
4.  Supabase SMTP — configure Resend (insightsafrica.org verified, same account as blog)
5.  Branded confirmation email template in Supabase dashboard
6.  Deploy to OCI ARM + Cloudflare Tunnel ← makes platform publicly accessible
7.  Wire up insightsafrica.org domain post-deployment
5.  HeatWatch 2025 data               ← fetch_landsat.py --year 2025 for all 3 cities
6.  CropWatch Leaflet time-lapse player ← Play/Pause, date range, speed control
7.  FloodWatch time-lapse player      ← same pattern, 24 monthly layers
8.  "Sign in for alerts" CTA on hub   ← premium upsell entry point
9.  Contact / enquiry form on landing page
8.  NASA IMERG real-time              ← upgrades FloodWatch from monthly to near-real-time
9.  Email/SMS alerts                  ← Africa's Talking for SMS, first monetisation
10. PDF district reports              ← downloadable, branded, second monetisation item
11. Sentinel-1 SAR                    ← proper standing water detection
12. NADMO flood event markers         ← historical flood records
13. Paystack / Stripe                 ← payment infrastructure
14. Nigeria expansion                 ← Phase 4 begins
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
- [ ] **Deploy to OCI ARM via Cloudflare Tunnel** ← NEXT

### Milestone 1.4 — Polish & Launch
- [x] Hub page with product cards
- [x] Proper marketing landing page — 2026-03-09
- [x] "About the data" sections in each module sidebar
- [x] Auth infrastructure (Supabase email/password)
- [x] Register insightsafrica.org (Cloudflare, $7.50/yr — Mar 2026)
- [ ] Configure Supabase SMTP via Resend (insightsafrica.org already on Resend account)
- [ ] Branded confirmation email template in Supabase dashboard
- [ ] Add "Sign in for alerts / reports" CTA on hub
- [ ] Contact / enquiry form on landing page
- [ ] Wire up domain post-OCI deployment

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

- [ ] Nigeria (Lagos flooding well-documented)
- [ ] Côte d'Ivoire
- [ ] Senegal
- [ ] Country-toggle on InsightsAfrica hub

---

## Out of Scope (for now)
- ArcGIS / Esri tooling (open source stack only)
- Mobile app (web-first)
- Real-time river gauge sensors (hardware)
