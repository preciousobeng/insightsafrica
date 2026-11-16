# Public surface maintenance review
Deep review: api/main.py and static serving. Base: c7a65e4.

Source/config URLs and the old admin-hierarchy URL now return 404. Necessary
identifier and sampling-method guidance remains public at data-key-version.html,
and the administrative version header links there. Do not hide scientific caveats.

Processed mounts serve only flat PNG names referenced by recognised product
metadata. Arbitrary JSON, GeoJSON, source files, unreferenced PNGs and symlink
escapes are not served. Metadata changes invalidate the per-mount manifest.

Bulk boundary download routes return 410 and the six FloodWatch pages no longer
advertise those downloads. Interactive /api/.../boundaries/{level} routes remain
available, so GADM geometry still reaches browsers. TD-3 remains unresolved.

X-Frame-Options: DENY is added; security.txt uses the site's existing contact address.
HSTS edge settings, CSP enforcement, API/CSV authorization, quotas and clamping are
unchanged. HTML redirects are removed from OpenAPI; existing optional download
authentication is described without introducing a key requirement.

Validation: 53 targeted tests passed, including frozen API-key cap tests. Six
FloodWatch browser renders used synthetic geometry/data and cached pinned
Leaflet/Chart.js; each rendered one polygon with zero uncaught JS errors and no
bulk-boundary link. Server allowlist contracts are separately tested against real
temporary files. Generator: Total 6 | identical 6 | differ 0.

Reproduce with venv/bin/python -m pytest -q tests/test_public_surface.py
tests/test_api_key_downloads.py tests/test_api_key_database_cap.py
tests/test_admin_api_contract.py tests/test_build_pages.py tests/test_api_keys.py
(all on one command line). Browser harness: tests/verify_public_surface.mjs;
MAINTENANCE_PUPPETEER points to puppeteer-core. Cached public JS/CSS goes under
ignored node_modules/maintenance-assets; URLs are the exact versions in the
existing templates. No production dataset, Supabase, account or SMTP call is used.

No merge, deployment, database migration or Cloudflare change was performed.
