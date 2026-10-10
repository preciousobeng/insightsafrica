# Tech Debt / Backlog

Standing items that are not blocking current sprints but need a deliberate decision.

## TD-1 — numpy pin vs reality is inconsistent (logged 2026-06-29 claude)

`requirements.txt` pins `numpy==1.26.4` (numpy **1.x**), but the environments have drifted:

- **Local dev venv:** numpy 1.26.4 (matches the pin; numpy 1.x).
- **free-arm2 (prod):** was numpy **2.4.3**; installing the pinned `scipy==1.13.1` on 2026-06-29
  pulled it to **2.2.6** (scipy 1.13.1 requires numpy<2.3). The server's compiled C-extensions
  (rasterio, rasterstats, pyhdf, pandas, geopandas, shapely) are built against numpy **2.x** and
  import cleanly at 2.2.6. They would likely break on the pinned 1.26.4 (1.x↔2.x is an ABI boundary).

So the pin matches local but **not** the server, and "fixing" the server to the pin is the dangerous
direction. Decision needed: **commit the platform to numpy 1.x or 2.x**, then make `requirements.txt`,
the local venv, and free-arm2 all consistent with that choice.

Also surfaced at the same time: `h5py`, `netCDF4`, `xarray` are in `requirements.txt` but **not
installed on free-arm2** (ModuleNotFoundError) — whatever uses them isn't run there. Reconcile when
TD-1 is addressed.

Not blocking SPI-3: the gamma fit and norm.ppf live in scipy (stable across numpy minors) and the
output rounds to 2 dp, so senior regen on the server is numerically safe; spot-check fit blocks by
hand at regen time.

## TD-2 — Risk Index v2 calibration: re-weight drainage + add an exposure dimension (logged 2026-07-01 claude)

Comparing our Risk Index (L5) against an independent published flood map — "The Identification of
Flood-Prone Areas in Accra, Ghana Using a Hydrological Screening Method" (MDPI/GeoHazards 2024,
Arc-Malstrom on a 10 m DTM, covering the Odaw River basin / ~23% of GAMA) — surfaced two real flaws:

1. **Convergence (good):** every district in the paper's Odaw-Korle hotspot corridor (Korle-Klottey,
   Accra, Ablekuma Central, Okaikwei North, Ayawaso Central/East, Ga Central) is in our "high" band.
   Two independent methods agree central Accra's Odaw corridor is flood-prone.
2. **Divergence (the flaw):** our model ranks peripheral "None"-drainage districts (Shai Osudoku,
   Ga West, Ga North, Ningo-Prampram, Ada West) as **severe — above** the dense central Korle/Odaw core
   that the literature treats as the epicentre. Cause: the placeholder drainage map rates low-density
   peripheral areas "None" (V=1.0) above the central core's "Poor" (V=0.75), conflating *absence of
   drainage infrastructure* with *flood danger*, with **no exposure/population term** to reflect
   people-and-assets at risk.

**v2 actions:**
- **DONE 2026-07-01 — exposure multiplier.** Risk is now weighted by population (WorldPop 2020 1km,
  zonal-summed per district via scripts/compute_population_exposure.py -> data/exposure/
  ghana_population.json). The factor is a log-population modulator in [0.7, 1.3] (median ~neutral),
  model_version risk-v2. Effect verified: the densest Poor-drainage core districts (Ablekuma North 512k,
  WeijaGbawe 476k) rose to severe while truly-sparse None districts (Shai Osudoku 60k: 1.00 -> 0.88)
  fell. Degrades to neutral where population is absent. **Multi-country exposure rollout HELD (owner
  decision 2026-07-01): the Risk Index is Ghana-only (drainage data exists only for Ghana), so exposure
  for the other 5 would be unused — roll it per-country when that country gets a drainage layer.**
- **STILL PENDING (needs NADMO) — drainage re-weighting.** Even with exposure, Ga West/Ga North (None
  drainage, ~170-207k) still top the list because None (V=1.0) > Poor (V=0.75) and the central core is
  rated Poor. Re-weighting the V-map / BASE / "None" semantics against NADMO observed floods is the
  remaining half — it is the calibration the Risk Index brief anticipates.

Does not block anything; the Risk Index remains correctly labelled provisional until the NADMO half lands.

## TD-3 — Boundary data licence: GADM 4.1 geometry exposed through the API (logged 2026-10-10 claude) — PRIORITY

`scripts/fetch_boundaries.py` downloads GADM 4.1, and the API serves boundary files at `/api/boundaries/*` and
`/api/{country}/boundaries/*`. GADM's terms (gadm.org/license.html) permit non-commercial and academic use,
including maps in academic publications. They distinguish that from **redistribution of the data and from
commercial use, both of which need permission**. Being a free site does not by itself make serving the
GeoJSON permitted, and paid tiers raise the commercial question as well. Displaying a rendered map differs
from serving the geometry. Not legal advice; a decision is needed.

**Action:** (1) confirm exactly which endpoints and downloads expose GADM geometry, and in what form;
(2) either seek GADM permission or evaluate an openly licensed source per country. Candidates checked for
Ghana during the flood–health paper audit: OCHA COD-AB (HDX `cod-ab-gha`, CC BY-IGO) and geoBoundaries gbOpen
(ADM2 CC BY 4.0; ADM1 CC BY-SA 2.0, OSM-derived). For each, check exact licence and attribution obligations
(including share-alike), coverage, vintage and suitability for commercial use. Ghana ADM2 geometry
substantially overlaps GADM (per-district IoU 0.90–0.997, 260 units), but **do not assume a swap is
scientifically neutral**. Re-run the zonal statistics and compare. Keys differ (P-codes vs `name|region`),
so a crosswalk is needed across the stats, anomaly, baseline, SPI, risk and population JSONs and the
frontend lookups.

## TD-4 — WorldPop district totals diverge from the 2021 census; Risk Index v2 depends on them (logged 2026-10-10 claude)

`data/exposure/ghana_population.json` (WorldPop unconstrained 2020, 1 km, pixel-centre sums over GADM districts)
was compared with GSS 2021 Census Vol 3A district totals for Greater Accra. Regional totals are within 3%
(5.61M vs 5.46M). District ratios range **0.23–5.1** (e.g. Ayawaso West 384,661 vs 75,303; Ablekuma North
512,207 vs 159,208; Ga South 81,490 vs 350,121). **The cause is not established.** GADM's post-2019 split lines
diverge from GSS district areas (Accra Metro 5.6 vs 20 km²; Weija Gbawe 164 vs 47 km²). Merged parent
clusters still differ (core ~1.55×, periphery 0.48–0.75×). Geography, vintage (2020 vs 2021), product and
aggregation effects remain entangled.

Verified in code: `compute_risk_index.py` loads this file and applies the log-population exposure factor
(TD-2). The effect of the discrepancy on Risk Index categories is a **testable pipeline question**, not yet a
finding. **Action:** keep the Risk Index provisional and non-public (no frontend page references it at the
time of logging). Rerun the index with exposure neutralised and compare the category changes. Do **not**
substitute census totals mapped by district name until boundaries and units are reconciled. Evaluate
WorldPop 100 m constrained / GRID3 before relying on any district exposure. Evidence: flood–health paper
repo, `analysis/geometry_comparison_ga.csv`, `audit_05_clusters.csv`.

## TD-5 — Label low CHIRPS grid support on district anomaly maps (logged 2026-10-10 claude)

District rainfall is the unweighted mean of every CHIRPS 0.05° cell the polygon touches (`all_touched=True`).
In Greater Accra, 9 of 29 districts contain no cell centre, and urban districts are supported by 1.4–2.8
effective cells (1/Σw² of overlap weights, a weight-concentration measure), shared with neighbours.
Small Kumasi districts are likely similar. Adjacent urban districts therefore draw largely on the same grid
cells. **Action (cheap):** compute cells-touched and effective-cell counts per district once, and show a
"limited grid support" note in tooltips and download metadata below a threshold (e.g. < 3). Optional: exact
overlap-area weighting (the paper audit found ~6 mm difference in the Greater Accra annual normal).

## TD-6 — Two latent code defects to review and test (logged 2026-10-10 claude)

Found by code reading during the paper audit. Neither is known to have affected a published output; confirm
with tests before claiming any effect.
1. `compute_population_exposure.py`: `round(float(s["sum"] or 0.0), 0)` records a district with no population
   support as `0` rather than missing. `compute_risk_index.py` treats 0 as neutral, which limits the impact
   there, but other consumers may not. Prefer `None` and add a test.
2. `compute_spi.py`, method-of-moments fallback in `_fit_gamma_zero_adjusted`: `non_zero = non_zero[:2]`
   truncates the sample before the moments are computed. Reached only if the MLE fails. Fix and add a unit
   test with a degenerate series.

## TD-7 — Candidate: reviewed regional method + "how this year compares" view (logged 2026-10-10 claude)

**After** the flood–health paper's method is frozen, and only with explicit estimator/version labels and
pre-deployment checks (the paper calculations do not update the production pipeline): regional/national
rainfall as an area-weighted, exact-overlap mean computed directly on the region polygon (never averaged
from district anomalies), sample-SD z, and gamma SPI-1/SPI-3 per calendar month. Possible frontend card:
"Jan–Apr 2026: highest January–April total in the 1981–2026 CHIRPS record for this footprint (+56%)", with
an SPI-3 strip and an estimand note ("area average over the region outline; not population-weighted").
Audit facts for reference: 5 sampled archive months are pixel-identical to fresh upstream downloads clipped
with `clip_to_country()`, and the Ghana stats JSONs were rebuilt in one pass on 2026-09-26. CHIRPS v2
production ends after Dec 2026, so schedule a v3-transition ticket.
