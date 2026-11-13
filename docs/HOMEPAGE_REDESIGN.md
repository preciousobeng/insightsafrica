# Homepage redesign — review revision 02

Review branch: `redesign/homepage`. No merge or deployment.
Working copy: `~/projects/insightsafrica-redesign-codex`, moved out of homelab.

## Review fixes

1. **Cron no longer modifies tracked homepage outputs.** Authoring lives in
   frontend/_templates/home.html. The builder always reads that template, including
   on a fresh checkout with no frontend/index.html. The generated index, summary,
   CSV and homepage-output/ directory are untracked and ignored. Evidence is also
   removed from the current Git tree and ignored; it belongs in the Windows handoff.
   No history was rewritten.
2. **MineWatch only compares conservatively matched seasons.** Comparison requires
   the same calendar month and a circular day-of-year distance of at most 45 days.
   This is deliberately stricter than ±45 days alone: May 31 to July 2 is only
   32 days, yet crosses Zamfara's dry-to-wet transition. The available tile therefore
   shows **one Sentinel-2 NDVI frame, July 2, 2026**, with no slider or change claim.
   Even a matched pair is not attribution of mining impact.
3. **Headlines exclude near-zero baselines.** Eligibility uses the unrounded monthly
   1991–2020 LTM >=20 mm. Eligible regions are ranked by absolute percentage departure.
   Wording gives actual mm, a multiple of normal (or percentage below), and same-month
   historical rank. Z scores remain outside the headline.
4. **Normal stays visible.** The BrBG neutral stop is #E3DED4 on the homepage and all
   FloodWatch templates. Covered countries and anomaly-mode administrative areas have
   dark outlines. A browser test injects exactly-normal Ghana on light paper and checks
   both fill and outline.
5. **Cabo Verde has an explicit locator marker** on desktop/mobile maps and the
   FloodWatch thumbnail; it is not presented as island geometry. Natural Earth's
   higher-resolution country polygons remain the public-domain source.
6. **Python is maintainable.** All eight new/changed Python files are formatted with
   Ruff 0.14.4; imports are separated/sorted, unused imports removed, semicolon
   statement chains and dynamic __import__ removed. Pipeline changes need senior review.

The Heat tile now uses a warm sequential temperature palette rather than rainfall
dry-to-wet colours. Crop/Heat tiles remain charts of actual processed observations;
the FloodWatch tile remains an explicitly labelled national rainfall preview.

## Required build and deployment integration

The deployment build entry is:

```sh
python3 scripts/build_frontend.py
```

It delegates to the same homepage builder used at the end of the monthly cron.
Run it in the release checkout **before publishing/serving that checkout**. A Git
pull alone is no longer a complete frontend deployment. The first rollout must account
for frontend/index.html changing from tracked source to ignored generated output:
build the release before switching traffic to it. No production rollout was attempted.

This repository has no existing automated frontend deployment workflow to edit.
The unrelated administrative-data release script is unchanged. The new build command
and these rollout instructions are the frontend build integration for the reviewer
to invoke in the authorized deployment procedure.

The monthly orchestrator rebuilds after successful data updates, skips writes for
dry runs, and sends generator failures through its existing notification channel.
No real updater run, email, contact submission or production write occurred.

```sh
python3 scripts/build_frontend.py --boundaries gadm
python3 scripts/build_pages.py --type flood --verify
python3 -m pytest -q tests/test_homepage_summary.py tests/test_data_cadence.py tests/test_build_pages.py
python3 scripts/preview_homepage.py
```

The preview is loopback-only, 127.0.0.1:8769. It serves static files with compression
and does not implement the contact API. Python needs Pillow, already a matplotlib
dependency. Browser checks use Chrome, puppeteer-core 24.43.1 and axe-core 4.11.0:

```sh
HOMEPAGE_PUPPETEER="$PWD/.ia-qa/node_modules/puppeteer-core" HOMEPAGE_AXE=.ia-qa/node_modules/axe-core/axe.min.js node tests/verify_homepage.mjs
```

## Data, methods and publication limits

The local read-only snapshot has 549 months per country, January 1981–September 2026:
112 primary administrative areas and 1,277 searchable primary/secondary areas.
National values are spherical-area-weighted administrative means, excluding missing
observations; they are not raster-exact country aggregations. The historical band is
the 1991–2020 mean ± population standard deviation, by calendar month. Ranks compare
the same month since 1981, exclude missing observations and share ranks for ties.
A zero/missing normal is unavailable, not zero; displayed numbers round to one decimal.

Current generated headline:

> September 2026: Eastern Cape, South Africa received 98.4 mm, about 3.5× its September normal; rank 1 of 46 September observations since 1981 (1 = wettest).

**TD-3 stays open. No GADM geometry is published or committed by this work.**
Public outlines, silhouettes and thumbnail geometry use Natural Earth only.
Summary JSON contains numbers, names and stable keys, no geometry. GADM inputs and
optional local geometry stay ignored outside frontend/. A GADM regional publication
URL is rejected. Missing region geometry preserves country shading and other features.

Before region-level launch, separately select licensed boundaries, document their
terms/provenance, complete and validate source-key/admin-code crosswalks, rerun zonal
statistics and baselines, and prepare region TopoJSON with IDs matching the summary.
Only then configure the licensed geometry URL and verify desktop/mobile rendering.
The homepage can launch with country shading while TD-3 remains open. Existing API
GADM district downloads remain a separate exposure, unchanged here.

The generator accepts --boundaries gadm|geoboundaries|codab, --boundary-root,
--crosswalk and --region-geometry-url. Alternative files use
<boundary-root>/<country>/<country>-adm1-mapped.geojson with properties.key/name.
An explicit crosswalk keeps stable IDs across the source change:

```json
{"ghana":{"regions":{"Northern":{"id":"ghana:stable-admin-code","boundary_key":"new-source-key"}}}}
```

## Attribution and dated outputs

- [CHIRPS v2.0, UCSB CHC](https://chc.ucsb.edu/data/chirps): rainfall, public domain.
- [Natural Earth](https://www.naturalearthdata.com/about/terms-of-use/): public-domain
  110m Africa context and 10m covered countries, v5.1.1; provenance beside inputs.
- [MOD13Q1.061](https://doi.org/10.5067/MODIS/MOD13Q1.061): own vegetation-class
  proportions, Senegal 2025-12-19, not crop-yield forecasts.
- [Landsat/USGS](https://www.usgs.gov/centers/eros/data-citation): own Touba surface
  temperatures, 2025-12-29, not air temperature.
- [Copernicus Sentinel-2 terms](https://dataspace.copernicus.eu/terms-and-conditions):
  own Zamfara NDVI site-box frame, 2026-07-02. No administrative mask is published.
- [World Bank terms](https://data.worldbank.org/summary-terms-of-use): context only,
  CC BY 4.0 unless the indicator states an exception.

Dates remain visible. This branch does not refresh older satellite products or
implement the separate CHIRPS v2-to-v3 migration.

## Verification and handoff evidence

50 focused Python tests pass. They include low-baseline headline cases (including
19.99 vs 20 mm), exact rank wording, seasonal comparison rejection, single-frame
selection, clean-checkout template rendering, and two changed-data refreshes in a
temporary Git repository that remains clean throughout.

56 browser assertions pass; six WCAG A/AA scans are clean. Browser checks cover six theme/viewport combinations, no overflow, exact readings,
keyboard controls, reduced motion, one-pass autoplay, the single MineWatch frame,
Cabo Verde markers, exactly-normal Ghana, missing-region fallback, no-JavaScript
tables/maps, persisted theme and mocked contact success/failure/network errors.
Contact payload/behavior is preserved; api/ is unchanged.

Evidence is **ignored and not in the current Git tree**. Fresh screenshots and test
output are copied to the Windows handoff's review-02/ folder. Source file inventory:
HOMEPAGE_CHANGED_FILES.txt. Metrics and checks are in the handoff JSON/text files.
Production delivery still needs validation after an authorized deployment.

Latest local mobile Lighthouse: performance 98, accessibility 100, LCP 2.2 s, CLS 0.002.
