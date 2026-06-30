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

**v2 actions (when NADMO data lands, and partly before):**
- Re-weight the drainage V-map and BASE against NADMO observed-flood records (the calibration the
  Risk Index brief already anticipates — this is the concrete target).
- Add a population / built-up exposure multiplier so danger reflects exposure, not just drainage
  absence (the MDPI paper was itself exposure-aware — built for a transport/roadblock study). A
  built-up density or population raster (e.g. WorldPop / GHSL) is a candidate input, no NADMO needed.
- Consider revisiting the "None" semantics — "no formal drainage in an empty floodplain" should not
  outrank "failing drainage in dense Korle".

This does not block anything; the Risk Index is already correctly labelled provisional. It is the
priority refinement once NADMO records arrive (or sooner for the exposure layer).
