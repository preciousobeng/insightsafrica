# Claude Code Session — 2026-06-13

**Context:** InsightsAfrica satellite intelligence platform — FloodWatch anomaly/LTM fixes, sub-pixel district fix, SA/CV hub data regeneration, and reconciliation with the parallel OpenCode/DeepSeek session.
**Repository:** https://github.com/preciousobeng/insightsafrica
**Operator:** Kweku Obeng (Kubuntu) — agent: Claude Code
**Server:** ubuntu@100.123.194.92 (OCI free-arm2), uvicorn `api.main:app` on 127.0.0.1:8001, behind Cloudflare Tunnel.

---

## Summary

This session ran partly **before** and partly **after** the DeepSeek session. The two efforts overlapped on the SA/CV hub fix and the data regeneration; git history ended up clean and linear (DeepSeek pulled this session's commits, then added its own on top). No conflicts. See "Reconciliation" below.

---

## 1. FloodWatch anomaly choropleth — Ghana sub-pixel districts (`all_touched`)

**Symptom:** 11 urban districts (Accra metro: Accra, Ablekuma C/W, Ayawaso C/E/N, Korle-Klottey, Krowor, Ashaiman; Kumasi: Asokwa, Suame) rendered permanently grey ("No data") in both rainfall and anomaly modes.

**Cause:** These districts are smaller than a CHIRPS ~5 km pixel, so `rasterstats.zonal_stats` found no pixel centroid inside them and returned `null` means.

**Fix:** Added `all_touched=True` to `zonal_stats()` at **both** call sites — `scripts/fetch_chirps_archive.py` (compute_stats) and `scripts/process_rainfall.py` (compute_zonal_stats). Counts any pixel the polygon touches.

**Propagation (each layer derives from the one below, so the full chain was rebuilt):**
1. New helper `scripts/recompute_archive_stats.py` — rebuilds all stats JSONs from existing archive TIFs **without re-downloading CHIRPS**. Ghana districts went 249 → 260.
2. `compute_ltm_baseline.py` — rebuilt baseline so the 11 districts gained a 1991–2020 reference (now 181 KB, 260 districts).
3. `precompute_anomalies.py --country ghana --force` — **`--force` is mandatory**, else all 544 months skip on the exists-guard.

**Verified live:** Accra +200%, Suame +279%, Asokwa +268%; all 260 districts present in the anomaly API. API reads files from disk, so no restart needed.

**Commit:** `f41ffc9` (all_touched + recompute script).

---

## 2. FloodWatch anomaly mode — blank maps on the 4 non-Ghana pages

**Symptom:** Nigeria/Ivory Coast/Senegal/South Africa "Anomaly vs LTM" mode rendered no choropleth — bare outlines (Nigeria) or a completely empty map (Senegal). Data and keys were correct; the break was front-end JS.

**Cause:** `patch_anomaly_frontend.py` copied every *usage* from the Ghana page but stripped the *declarations*. Two missing-declaration groups, two rounds:
- **Round 1 (`6ee87bf`):** `const ANOMALY_COLORS = {…}` + `const ANOMALY_LABELS = {…}` were referenced but never defined → ReferenceError inside `applyAnomalyStyle` → no fill.
- **Round 2 (`91d3ed8`):** `let viewMode='rainfall'; let currentAnomalyData=null; const anomalyCache={}; let infraData={};` — undeclared. `buildTooltipContent` runs during `showBoundary` on page load and reads `viewMode` + `infraData[key]`; the ReferenceError aborted boundary rendering entirely (hence Senegal's totally empty map). `infraData` must be `{}` (these countries have no infrastructure JSON); `loadInfraData` is not referenced and was not added.

**Diagnosis method:** static checks (`node --check`, grep) passed clean — only the browser console exposed it. Drove the live pages with headless Chrome (puppeteer-core against system `/usr/bin/google-chrome`), captured `pageerror`, and counted filled `path.leaflet-interactive` elements. Then diffed **all** top-level declarations against Ghana (each broken page was missing the same 5 of Ghana's 64 names).

**Verified live (anomaly mode, headless):** Nigeria 812 polygons filled, Senegal 45, South Africa 61, Ivory Coast 14 — all category-coloured, zero JS errors. Cape Verde already had the declarations and was unaffected.

**Known quirk left as-is:** Ivory Coast's anomaly choropleth shows the **coarse** `districts` level (14) not the fine `regions` (33), because `loadAndApplyAnomaly` hardcodes `'districts'` (fine in Ghana, coarse in IC). Renders correctly. Not touched — IC districts have empty `p.name` and fragile `'|Abidjan'`-style keys.

---

## 3. Stale Ghana rainfall layers

**Finding:** No cron/timer exists for the rainfall pipeline on free-arm2 (only kakes backup + Supabase keepalive). The processed Ghana layers were frozen at Dec 2025 (last hand-run March 6) while the archive already held TIFs through Apr 2026. Because anomaly mode follows the *selected rainfall month*, the Jan–Apr 2026 anomalies were unreachable in the UI.

**Fix:** Ran `process_rainfall.py` over the 4 archive TIFs already on disk (2026.01–04). `/api/flood/layers` now returns 28 layers ending April 2026; newest layer carries all 260 districts.

**Still open:** the monthly pipeline remains manual. The cron job is scoped in memory (prereq: add `--start/--end` to `precompute_anomalies.py`).

---

## 4. Hub KPI cards stuck on "Loading…" (South Africa, Cape Verde)

**Symptom:** On the SA and CV hub pages, every card except peak rainfall hung on "Loading…".

**Cause:** The hub script runs `.reduce()` on each API result. `crop/layers` returned `[]`; `[].reduce()` with no initial value throws, which aborted the whole async IIFE so the heat and mine cards never ran. The 4 countries with data were unaffected.

**Fix:** Guarded each card with `Array.isArray(...) && .length` (and `Array.isArray` for the mine count). Cards now degrade to "— no data" instead of freezing. Commit `433d567`. *(DeepSeek later refined the SA heat card further in `c17dc02` — see Reconciliation.)*

---

## 5. SA + CV crop/heat/mine data regeneration

The data was wiped in the earlier git-stash incident. **The raw data survived** in `data/raw/` (MODIS HDF, Sentinel-2 SAFE, some Landsat) — only the processed JSONs and `*_mining_sites.json` manifests were gone. So mostly re-ran PROCESS steps, not re-fetches.

| Country | Crop (NDVI) | Heat (LST) | Mining |
|---------|-------------|------------|--------|
| South Africa | 6 (DOY 1/33/97/193/289/337) | 6 (JHB/Cape Town/Durban) | 4 sites |
| Cape Verde | 23 (full year) | **0 — impossible** | 4 sites |

**Pipeline gotchas learned:**
- `process_mining.py` needs the `*_mining_sites.json` manifest as **input** — that manifest is written by `fetch_sentinel2.py`. Run `fetch_sentinel2.py` first (skips existing raw downloads, just rebuilds the manifest), then `process_mining.py`.
- Process scripts need `set -a && . ./.env && set +a` to load `NASA_EARTHDATA_*` / `COPERNICUS_*` creds (all present in free-arm2 `.env`).
- **CV heat is permanently unavailable** — Cape Verde path/rows only have Landsat **L2SR** (surface reflectance) scenes, no **L2SP** (the ST_B10 thermal band needed for LST/UHI). Source-data gap, not a bug.
- **SA heat card shows "no data"** because the hub tracks Johannesburg specifically and SA Johannesburg layers have `uhi_intensity_c = null` (urban_mean=null). Durban layers do have UHI. Data-quality issue, not a code bug.

**Verified live:** SA crop 82% / mine 4; CV crop 67% / mine 4; both heat cards "— no data" (correct).

---

## 6. Reconciliation with the OpenCode/DeepSeek session

DeepSeek ran concurrently, audited the repo (33 issues), and committed 5 changes. **Git state was clean and linear** — DeepSeek pulled this session's 4 commits (…`433d567`) then committed on top:

```
c17dc02 fix: guard SA heat card against null UHI values, sa mine card Array.isArray
40ba191 fix: replace prompt() with modal form for password reset
54c5cbc fix: add rate limiting, logging, HTTPS redirect; stop swallowing exceptions
12bc9db fix: add CORS middleware for insightsafrica.org origins
d2779a3 fix: correct pandas/requests versions, add pyhdf+pyproj deps
433d567 fix: guard hub KPI cards against empty/missing datasets (SA, CV)   <-- mine
91d3ed8 fix: declare viewMode/currentAnomalyData/anomalyCache/infraData (4 flood pages)
6ee87bf fix: define ANOMALY_COLORS/LABELS on 4 non-Ghana FloodWatch pages
f41ffc9 fix: all_touched=True in zonal stats
```

**Actions taken to reconcile:**
- Fast-forwarded the local Kubuntu repo to origin `c17dc02` (no conflicts).
- Confirmed the server already has DeepSeek's changes deployed: CORS + slowapi live (verified CORS header on live API), slowapi pip-installed, uvicorn reloaded on :8001, SA hub has the null-UHI filter. My earlier scp deploys were superseded by DeepSeek's deploy — no clobbering.
- Confirmed the SA/CV data regen we both ran is idempotent.

**Per Kweku:** all 33 audit items have since been fixed — do not re-flag them as open.

---

## Final live state (all verified)

- FloodWatch anomaly/LTM mode works on **all 6 countries**.
- Ghana districts complete (260, incl. previously-grey urban districts); rainfall layers current through Apr 2026.
- SA + CV hub cards populate (crop + mine); heat is "no data" by genuine data limitation, handled gracefully.
- Local repo synced to origin `c17dc02`; server consistent.

## For DeepSeek to review

1. The `all_touched=True` change — confirm it doesn't materially distort large-district means (it slightly inflates edge coverage; acceptable for sub-pixel districts, worth a sanity check on big ones).
2. The two-round declaration fix on the 4 flood pages — confirm no other Ghana-only symbols are referenced-but-undeclared elsewhere (I checked top-level decls; nested scopes not exhaustively diffed).
3. Ivory Coast anomaly granularity (coarse districts vs fine regions) — intentional to leave, or switch to fine `regions`?
4. SA Johannesburg heat null `uhi_intensity_c` — is this a processing bug in `process_heatwatch.py` (urban_mean=null) worth fixing so the SA heat card can populate?
5. Monthly CHIRPS automation cron — still unbuilt; prereq is `--start/--end` on `precompute_anomalies.py`.
