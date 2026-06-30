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
  fell. Degrades to neutral where population is absent (other countries until their raster is run).
- **STILL PENDING (needs NADMO) — drainage re-weighting.** Even with exposure, Ga West/Ga North (None
  drainage, ~170-207k) still top the list because None (V=1.0) > Poor (V=0.75) and the central core is
  rated Poor. Re-weighting the V-map / BASE / "None" semantics against NADMO observed floods is the
  remaining half — it is the calibration the Risk Index brief anticipates.

Does not block anything; the Risk Index remains correctly labelled provisional until the NADMO half lands.
