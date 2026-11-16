# Runtime patch dependency maintenance
Base: c7a65e4. No application, data, authentication-model or scientific-stack change.

Prepared separately from the large grouped Dependabot update:
- python-dotenv 1.2.2 -> 1.2.4
- schedule 1.2.1 -> 1.2.2
- slowapi 0.1.9 -> 0.1.10
- development-only respx floor >=0.21 -> >=0.23.1

49 targeted tests pass in an isolated Python 3.14 environment with main's FastAPI pin.
This includes API-key/cap/download contracts, page generation, monthly cadence and
temporary local PostgreSQL authorization tests. New contact tests prove that the
fourth hourly request returns 429 before SMTP, and oversized input is rejected.
SMTP and Supabase HTTP calls are mocked; no real message, account or key is created.

Two existing deprecation warnings remain (Starlette TestClient/httpx and SlowAPI
asyncio introspection). No scientific package, production environment or database
migration was changed, and no actual updater/scheduled job was run.

Do not blanket-merge the grouped minor-and-patch branch: it also changes SciPy,
statsmodels, rasterio, geopandas, netCDF4, h5py, shapely, TiTiler and other packages.
The separate FastAPI/security-floors proposal passed 27 API/build tests in another
isolated environment, but its full scientific/TileServer dependency compatibility
has not been established. NumPy 2 / pandas 3 remain separate work.
