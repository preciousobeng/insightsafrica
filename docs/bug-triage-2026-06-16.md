# InsightsAfrica — Bug triage (2026-06-16)

Authoritative triage of the visual bugs found 2026-06-15. Two are resolved, two are confirmed
non-issues, two are real and need a dedicated SERVER session (free-arm2 + imagery API creds).
Open this when running that session.

## Status summary

| Bug | Status | Where |
|-----|--------|-------|
| Crop watch — all countries show "—" + "Run fetch_modis_ndvi.py… activate this module" | FIXED + live | frontend (done) |
| NG mine — Kaduna South: long vertical sliver, offset pointer | REAL — banked | server data |
| IC artisanal mines — same sliver/offset (Tongon, Agbaou, Bonikro, Séguéla) | REAL — banked | server data |
| NG heat — Kano: slashed/triangular overlay, offset | REAL — banked | server data |
| Cape Town heat — not visible | NOT broken | n/a |
| CV mine — Santo Antão | NOT broken | n/a |

## Resolved this session
- **Crop (all 5 shared-template countries: Ghana/Nigeria/Ivory Coast/Senegal/South Africa).**
  Root cause: the flicker-free pre-warm loop (PR #2/#3) iterated a variable named `layers`, but
  crop's fetched array is `allLayers` (crop never declares `layers`). The undefined reference threw
  inside loadLayers' try, the catch swallowed it, and every page showed the "activate this module"
  fallback with no layers/chart. The API returned data fine the whole time. Fix (commit 4216fb9):
  iterate `allLayers`. Verified live — all 5 render. Cape Verde was never affected (its variant has
  no pre-warm line). Harness hardened (commits 2c42f00 + 4f022a4) to catch swallowed catch-block
  errors and to stop using networkidle2 (spurious timeouts).

## Confirmed NOT broken (no action)
- **Cape Town heat:** data is present (2 layers, png + bounds), city_id `capetown` matches CITY_DEFS,
  filter button exists. The heat page defaults to Johannesburg, so Cape Town only appears on
  selection. Live headless repro: selecting Cape Town renders the overlay, 0 JS errors.
- **CV mine — Santo Antão:** served bounds center is (17.1, -25.1), exactly on Santo Antão island,
  square 1.0 aspect. Correctly placed and shaped.

## REAL #1 — Mine overlays: partial Sentinel-2 granule coverage (server data)

### Symptom
Overlay renders as a thin vertical (or horizontal) sliver, and the site marker sits off to the side
of it.

### Root cause (verified, do NOT "fix" the bboxes)
The repo site bboxes in `scripts/fetch_sentinel2.py` are CORRECT. The served `leaflet_bounds` come
from the ACTUAL clipped raster extent, and for these sites the downloaded Sentinel-2 granule only
covered part of the bbox, so the clip (and its bounds + PNG) is a narrow sliver. Healthy sites
(e.g. Ity Gold Mine) have full coverage and a ~1.0 lat/lon span ratio; broken sites are >2 or <0.5.

### Affected sites and their CORRECT bboxes [lon_min, lat_min, lon_max, lat_max]
- Kaduna South Quarrying (Nigeria): [7.2, 9.5, 7.9, 10.4]  — served clip was lon 7.198–7.267 only
- Tongon Gold Mine (Ivory Coast):   [-6.35, 9.15, -5.90, 9.60]
- Agbaou Gold Mine (Ivory Coast):   [-5.52, 5.52, -5.10, 5.96]
- Bonikro Gold Mine (Ivory Coast):  [-5.42, 5.70, -5.02, 6.14]
- Séguéla Gold Mine (Ivory Coast):  [-6.86, 7.71, -6.44, 8.17]

### Fix steps (server: ubuntu@100.123.194.92, needs Copernicus creds in .env)
1. For each affected site, re-fetch Sentinel-2 imagery that fully covers the bbox. The current
   single-granule pick under-covers them — either select a granule whose footprint contains the
   whole bbox, or fetch the neighbouring granule(s) and mosaic before clipping.
2. Re-run process_mining.py for nigeria and ivorycoast (it needs the *_mining_sites.json manifest,
   which fetch_sentinel2.py writes — run fetch first).
3. Redeploy data; the served leaflet_bounds should then span close to the full bbox.

### How to verify (per site)
Fetch the live sites endpoint and compare each site's bounds lat-span to lon-span — the ratio for a
healthy square overlay is ~0.8–1.2. Broken ones are ~2–6 (or ~0.2–0.5). Endpoints:
/api/nigeria/mine/sites and /api/ivorycoast/mine/sites. Also eyeball each overlay sits under its
marker.

## REAL #2 — Kano heat: Landsat reprojection artifact (server image pipeline)

### Symptom
The Kano heat overlay renders slashed/triangular and offset.

### Root cause
The bbox is correct (fetch_landsat.py: [8.4, 11.9, 8.7, 12.2], a clean 0.3° square) and the served
bounds are valid. The PNG itself is warped — the Landsat scene was not cleanly reprojected to
EPSG:4326 before the PNG was rendered, so a non-axis-aligned raster gets drawn as a triangle when
Leaflet stretches it to a lat/lon box.

### Fix steps (server)
1. Inspect how the heat PNG is generated (process_heatwatch.py / fetch_landsat.py) for Kano — check
   the source CRS and that the array is warped/reprojected to EPSG:4326 (north-up, axis-aligned)
   BEFORE the PNG is written. The other heat cities render fine, so compare Kano's source scene CRS
   and footprint against a working one (e.g. Johannesburg).
2. Reproject to 4326, regenerate the Kano heat PNG(s), redeploy.
3. Verify the overlay is rectangular and aligned under the Kano marker.

## Notes
- These two are NOT repo PRs and NOT good DeepSeek delegations — they need server access, the
  Copernicus/Earthdata credentials, and judgement on granule/scene selection.
- Do NOT edit the bbox values in fetch_sentinel2.py / fetch_landsat.py — they are correct. The fix
  is re-acquiring/reprojecting imagery, then reprocessing.
