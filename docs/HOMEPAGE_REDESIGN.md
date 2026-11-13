# Homepage redesign — review handoff

Branch: `redesign/homepage`. Base: `c7a65e4` (fresh upstream main).
Work is isolated in `~/projects/homelab/insightsafrica-redesign-codex`.
No merge, deployment, production writes, updater execution, real contact submission or API changes.

## Delivered

A static HTML/vanilla-JavaScript homepage with the warm ink/paper/laterite/ochre palette,
self-hosted Fraunces and IBM Plex fonts, persisted dark/light views, keyboard-accessible
country tabs and place search, historical rainfall lines, a 24-month choropleth timeline,
actual dated observation thumbnails, and a Sentinel-2 NDVI before/after slider.
The map plays one pass when visible, stops at the latest month and stops on interaction.
Reduced-motion visitors get the latest frame without autoplay.

The saved HTML contains the latest headline, both responsive country maps, all 112
latest regional observations, six complete national monthly tables and country/CSV
links. A JavaScript or optional-geometry failure retains those fallbacks.
On phones the map crops to West Africa and shows South Africa in a separate-scale inset.

The contact function is byte-equivalent to main's original handler, moved into an
external script with the same fields, POST /api/contact contract, responses and reset
behavior. Browser checks intercept all contact requests; none reached a real endpoint.
FloodWatch changes are limited to the continuous BrBG anomaly palette/legend and readable
tooltip text in all three templates and their six generated pages. No auth, quotas,
CSV clamping, risk calculations or raster clipping changed.

## Archive and method

The production archive was read-only copied into ignored local development data.
All six countries have 549 contiguous months, January 1981 through September 2026.
There are 112 first-level areas and 1,277 searchable primary/secondary areas:

| Country | Primary areas | Searchable areas |
| --- | ---: | ---: |
| Ghana | 16 | 276 |
| Nigeria | 37 | 812 |
| Côte d'Ivoire | 14 | 47 |
| Senegal | 14 | 59 |
| Cabo Verde | 22 municipalities | 22 |
| South Africa | 9 | 61 |

National series are **spherical-area-weighted administrative zonal means**, excluding
missing observations. They are not a new raster-exact country aggregation.
The band is the monthly mean ± population standard deviation of the 30 national
values in 1991–2020. Latest-year lines stop where the archive stops.
Regional percentages and z scores use each area's archived 1991–2020 normal.
Percent of normal is 100 + percentage departure; a zero/missing normal stays unavailable.
Rainfall is rounded to one decimal after calculation. Missing observations stay null.
Ranks compare the same calendar month since 1981; 1 is wettest, ties share rank,
and unavailable years are excluded. “Last as wet or wetter” is a year in that same-month record.

Headline selection takes the largest absolute regional percentage departure, with a
deterministic tie-break. Current headline:

> September 2026: Northern Cape, South Africa received 644.9% more rain than normal.

Large percentages in dry climates should be read with the mm total and baseline context,
not interpreted as a flood forecast. The regional table gives the actual total and z score.

## Geometry and TD-3: precise publication boundary

**TD-3 remains open. No GADM-derived geometry is committed or published by this change.**
The public Africa outline, country fills, country-tab silhouettes and FloodWatch thumbnail
all use Natural Earth public-domain geometry. Source versions and SHA-256 provenance are
beside the source files. `homepage_summary.json` contains numbers, stable IDs, keys and
names; it contains no geometry, coordinates, arcs or bounding boxes.

Ignored GADM inputs remain under data/ for development calculations, as authorized.
The optional local geometry exporter defaults outside frontend/ to ignored
`.ia-local-geometry/` and refuses an output beneath frontend/. It is not used by
the public page or the evidence set. The summary defaults to a null region URL;
supplying a region URL with `--boundaries gadm` is rejected.

Before a **regional** hero can go live, TD-3 must separately:

1. Select and document licensed boundary releases covering the intended administrative
   levels in all six countries, including attribution and redistribution terms.
2. Complete the source-key/admin-code crosswalk and validate every match and parent
   relationship. Preserve the explicit stable IDs through the boundary change.
3. Re-run the zonal statistics and 1991–2020 baselines against those boundaries; check
   names, missing coverage, ranks and national aggregation before replacing outputs.
4. Generate a licensed region TopoJSON whose feature IDs match the summary's region
   IDs and whose properties contain country slugs. Review its provenance and geometry.
5. Regenerate with the chosen boundary source/crosswalk and explicit licensed region
   URL; verify desktop region tooltips and mobile country shading before launch.

Generator choices are `--boundaries gadm|geoboundaries|codab`, `--boundary-root`,
`--crosswalk` and `--region-geometry-url`. Alternative source inputs use
`<boundary-root>/<country>/<country>-adm1-mapped.geojson` with a canonical
`properties.key` or `properties.name`. The crosswalk shape is:

```json
{"ghana":{"regions":{"Northern":{"id":"ghana:stable-admin-code","boundary_key":"new-source-key"}}}}
```

Without an override, stable internal IDs hash country + level + canonical archive key.
A future crosswalk supplies real admin codes without changing the frontend join.
Neither alternative boundaries nor reprocessed statistics are selected in this branch.
If TD-3 is not complete at launch, **the homepage can ship with Natural Earth country
shading**. A missing regional file is tested to fall back to those countries without
breaking the chart or search. Existing API district downloads remain a separate TD-3 exposure.

## Source and thumbnail provenance

- Rainfall: [UCSB CHC CHIRPS v2.0](https://chc.ucsb.edu/data/chirps), public domain.
- Outlines: Natural Earth 110m Africa / 10m covered countries, v5.1.1;
  [public-domain terms](https://www.naturalearthdata.com/about/terms-of-use/).
- Crop thumbnail: own processed MOD13Q1 stress-class proportions, Senegal, 2025-12-19.
  It is a chart of observations, not a stock image or yield forecast.
  [MOD13Q1.061](https://doi.org/10.5067/MODIS/MOD13Q1.061).
- Heat thumbnail: own processed Landsat 9 Touba min/mean/max land-surface temperatures,
  2025-12-29. Surface temperature is not air temperature.
  [USGS reuse/citation](https://www.usgs.gov/centers/eros/data-citation).
- Mine slider: own Sentinel-2 NDVI frames for the **same Zamfara Gold Belt site box**,
  2024-05-31 and 2026-07-02. These are vegetation-index images, not natural-colour photos.
  Site-box frames do not publish administrative boundaries.
  [Copernicus terms](https://dataspace.copernicus.eu/terms-and-conditions).
- World Bank is linked for context, not claimed as the source of rainfall:
  [CC BY 4.0 with indicator exceptions](https://data.worldbank.org/summary-terms-of-use/).

Crop/heat dates reflect the available processed products; those older dates remain visible.
No claim is made that every module is current to September 2026. This branch does not refresh
satellite processors or address the separate upcoming CHIRPS v2-to-v3 transition.

## Regenerate and check

From the isolated checkout, using its data snapshot and Python environment with Pillow
(already a matplotlib dependency in requirements):

```sh
python3 scripts/build_homepage_geography.py
python3 scripts/build_homepage_summary.py --boundaries gadm
python3 scripts/build_pages.py --type flood --verify
python3 -m pytest -q tests/test_homepage_summary.py tests/test_data_cadence.py tests/test_build_pages.py
python3 scripts/preview_homepage.py
```

The preview binds **127.0.0.1:8769 only**, serves frontend/, and compresses text assets.
It is a QA helper, not a production server. It does not implement the contact API.

Browser evidence is reproducible with Chrome, puppeteer-core 24.43.1 and axe-core 4.11.0.
Set `HOMEPAGE_PUPPETEER` to the installed module and `HOMEPAGE_AXE` to axe.min.js,
then run `node tests/verify_homepage.mjs`. The test refuses non-loopback origins.
The required audit-only tools can be installed under ignored .ia-qa/:

```sh
npm install --prefix .ia-qa --no-audit --no-fund puppeteer-core@24.43.1 axe-core@4.11.0 lighthouse@12.8.2
HOMEPAGE_PUPPETEER="$PWD/.ia-qa/node_modules/puppeteer-core" HOMEPAGE_AXE=.ia-qa/node_modules/axe-core/axe.min.js node tests/verify_homepage.mjs
CHROME_PATH=/usr/bin/google-chrome node .ia-qa/node_modules/lighthouse/cli/index.js http://127.0.0.1:8769/ --chrome-flags="--headless --no-sandbox" --only-categories=performance,accessibility --output=json --output-path=evidence/homepage/lighthouse-mobile.json --quiet
```

The monthly orchestrator now runs the summary builder after successful updates, skips
it for dry runs, validates all generated content before publishing assets, and reports a nonzero generator exit through its existing failure/email
channel. Only mocked updater tests ran here; no real cron update or email was triggered.

## Validation and evidence

- 39 focused Python tests pass.
- Four deliberate mutations fail their intended tests: wrong weighting, wrong rank-tie
  comparison, zero-normal substitution and removal of the GADM publication guard.
  Source was restored; the clean suite passes. Logs: mutation-checks.json.
- 51 browser assertions exercise themes and persisted preference, range keyboard input,
  exact map readings, country-tab keyboard navigation, search/rank, mine slider,
  mocked contact success/rejection/network failure, one-pass autoplay, reduced motion,
  no-JavaScript tables/maps and missing-region fallback.
- Screenshots at 375/768/1440 in **both verified themes**, plus reduced-motion and
  no-JavaScript phone evidence. Every thumbnail was decoded before capture.
- Six axe WCAG A/AA scans: no violations. This is automated evidence, not a substitute
  for manual screen-reader/user evaluation.
- Internal homepage links/assets resolve. Contact handler matches original main.
  No files under api/ changed. FloodWatch generated pages verify byte-for-byte.
- Real-archive repeat build changes no output bytes or mtimes: generator-run.json.
- Summary: 532,392 bytes raw / 142,896 gzip (<400,000).
  Total homepage JavaScript, including vendored D3/TopoJSON: about 57,831 bytes gzip (<150,000).
  Exact budgets and file inventory: asset-budgets.json.
- Mobile Lighthouse 12.8.2, simulated throttled 4G, local compressed delivery:
  performance 99, accessibility 100, LCP about 2.0 s, CLS 0.003, TBT 0 ms.
  Full settings, exact measurements and audit details: lighthouse-mobile.json.
  These are local lab measurements; production TLS/CDN/compression must be verified
  separately after an authorized deployment. No deployment was performed.

All evidence is under evidence/homepage/. GADM screenshots/geometry are excluded.
