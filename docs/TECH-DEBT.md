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
