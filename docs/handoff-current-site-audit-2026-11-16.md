# Current site maintenance audit
16 November 2026 · Codex · main c7a65e4

The redesign branch remains parked at a077246. This audit and the maintenance
branches do not merge, deploy, change Cloudflare settings or run a Supabase migration.

## Findings checked against current main

| Review claim | Code and history check | Action |
| --- | --- | --- |
| API-key RPC fix is unmerged | Already in main as 3f3c7a5 | Preserve; no duplicate implementation |
| API-key cap race is unmerged | Already in main as e0bf117 | Preserve; frozen acceptance tests unchanged |
| Contact hardening is unmerged/no rate limiting | Main includes 66fedb8/7fd0963; contact is limited to 3/hour and 10/day, with bounded fields and header sanitisation | Preserve; absence of rate-limit headers is not proof of absence |
| Password recovery is a dead link | Main includes the recovery flow and session-handling fix | Preserve and browser-test; Privacy Policy link is still a placeholder |
| Anonymous downloads bypass the advertised requirement | Recent-window anonymous downloads are deliberate; API keys/valid sessions unlock the supported full ranges | Correct wording; do not change authorization or CSV clamping |
| Download-events RLS fix is pending | 559aff6 is not in main | Existing branch is ready for senior review; database state remains unverified |
| HSTS disabled at edge | Main already sets max-age=31536000; supplied passive review saw max-age=0 on live responses | Owner must inspect Cloudflare override; no dashboard change made |
| CSP report-only | Confirmed in code; existing pages depend on inline scripts | Keep report-only until a separate migration is tested |
| Source/admin files and processed folders publicly mounted | Confirmed broad StaticFiles mounts | Prepare restrictive serving and preserve required interactive map routes |
| Supabase CDN floats on @2 | Confirmed login/hub templates | Pin and self-host the exact SDK, with provenance |
| Privacy notice absent | Confirmed placeholder privacy link and contact form | Prepare owner-reviewable notice; do not invent retention/controller facts |
| Tablet navigation and inconsistent claims | Confirmed in current homepage source | Correct current pages, not the parked redesign |

## Existing fixes and dependency triage

- codex/download-event-rls (559aff6): three tests passed against a **disposable local
  PostgreSQL cluster**, not Supabase. Reapplication was tested, client reads/writes
  were denied, service-role insert remained possible, and existing data survived.
  The migration is additive security policy/grants work, with no record deletion.
  Senior/owner must review database compatibility and apply the migration separately.
  Do not assume a Git merge applies SQL to Supabase.
- security/contact-endpoint-hardening: already in main.
- codex/api-key-rpc: equivalent fix is already in main.
- fix/api-key-cap-race: already in main.
- security/oct22-dep-bumps: pending; includes FastAPI and transitive security floors.
  It needs isolated runtime and dependency-resolution testing; a version list alone
  does not demonstrate compatibility with titiler or the scientific stack.
- NumPy 2 / pandas 3 and scientific-stack changes remain separate work. Do not merge
  major scientific dependency upgrades as routine website maintenance.
- backlog/paper-audit-findings: not merged. TD-3 is absent from main's TECH-DEBT.md;
  maintenance documentation must record the actual GADM exposure and remaining work.

Baseline targeted tests on c7a65e4: 22 passed (API-key downloads, database cap, page build).
The isolated maintenance environment uses main's backend pins; no production packages changed.

## Serving changes must preserve the maps

FloodWatch uses /api/.../boundaries/{level}; those routes still expose geometry to
the browser. Closing redundant /xx-tiles/*.geojson copies and bulk-download links
does **not** resolve GADM licensing. Removing every boundary response would break
the existing maps. TD-3 requires a separate licensed-boundary swap and recomputation
of zonal statistics/baselines; do not present access filtering as licence clearance.

Processed mounts should serve only PNG assets referenced by product metadata, not
arbitrary directory contents. Templates, config, internal admin pages and source
files should not be reachable through frontend mounts. Public API documentation
should remain available while HTML redirects stay out of its schema.

## Owner and deployment actions
- Cloudflare HSTS: verify HTTPS on the relevant subdomains, then align edge HSTS
  with the intended policy. Do not submit preload as part of this maintenance run.
- Cloudflare API rate rules: configure/review in the dashboard separately; origin
  application rate limits already exist. Do not invent a limit that blocks monthly
  archive/map exploration.
- Privacy: controller/contact identity, retention criteria and lawful bases need
  owner confirmation. Browser privacy text must describe actual use and processors;
  a generic mandatory consent checkbox is not a substitute for this information.
- Supabase: confirm password/leaked-password settings and migration state in its
  dashboard separately. No account, API key, service token or database was changed.
- CHIRPS v3: plan separately before v2's end of production; do not splice v3 months
  into the v2 historical archive, normals or ranks.
- Redesign blockers remain open and its branch is unchanged.

Sources for dashboard/privacy preparation:
[Cloudflare HSTS](https://developers.cloudflare.com/ssl/edge-certificates/additional-options/http-strict-transport-security/),
[Turnstile server validation](https://developers.cloudflare.com/turnstile/get-started/server-side-validation/),
[ICO privacy information](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/individual-rights/the-right-to-be-informed/what-privacy-information-should-we-provide/).

## Prepared branches and combined validation

| Branch | Commit | Purpose |
| --- | --- | --- |
| maintenance/public-surface | ce8f5c3 | Restrict static files/bulk boundary downloads; preserve map APIs, public data-method notes, CSV policy and auth |
| maintenance/site-trust | d7d969f | Pinned self-hosted auth SDK, current-site wording/layout, privacy draft and empty/error hub handling |
| maintenance/runtime-patch-pins | a09b8fe | Three small runtime patches and the development respx floor |
| codex/download-event-rls (existing) | 559aff6 | Separately reviewed SQL migration; not merged/applied by this work |

Combined code was tested by applying branch diffs in a disposable detached checkout;
no branch merge was made. **80 combined tests passed**, including local PostgreSQL
authorization tests. Three deliberate defects were caught: bypassing the processed-file
allowlist, bypassing private frontend path filtering, and tampering with the SDK bytes.
Sources were restored and the clean 80-test suite passed again.

Browser checks on the combined code passed for all six FloodWatch pages (one synthetic
polygon each), ten current-homepage width/theme cases, the real pinned SDK on login/hub,
twelve empty/error hub responses, five mocked password-recovery scenarios and mocked
key management. There were no uncaught JavaScript errors or live auth/email operations.
The repository's headless harness also passed on the individual map/homepage branches.

## Detailed dependency disposition
The existing security/oct22-dep-bumps proposal passed 27 targeted API/build tests in
its own isolated environment. This does not validate the complete scientific/TileServer
environment, and that larger branch is not declared production-ready.

The grouped minor-and-patch update also changes SciPy, statsmodels, rasterio,
geopandas, netCDF4, h5py, shapely, TiTiler and other libraries. Only python-dotenv
1.2.4, schedule 1.2.2, SlowAPI 0.1.10 and development respx >=0.23.1 were separated
into the tested runtime patch branch (49 targeted tests passed there). NumPy 2,
pandas 3, rasterstats and the broader GIS upgrades remain held for scientific
replay/compatibility tests. The older grouped pip proposal's geopandas target is
already the version in main; it should not be merged as if it were a fresh fix.

## Further data-method finding
The existing administrative-key notice documents mixed pixel-sampling methods in
parts of the archive. That scientific limitation was preserved in the new public
data-key-version.html page; it was not discarded with the old admin URL. No rainfall
values, baselines, area keys or processing methods changed in this maintenance run.

CHC's primary page independently confirms that CHIRPS v2 production ends after
December 2026: https://www.chc.ucsb.edu/data/chirps .
Plan v3 separately and recompute a consistent archive/baseline/ranking set.
This maintenance work does not implement or select the migration.

## Remaining gates
The privacy draft must not be published before owner details are confirmed.
Turnstile is deferred by explicit owner choice; existing contact limits are
preserved and explicitly tested. HSTS/Cloudflare rules, Supabase settings and the
live download-events migration state still require owner/senior action. No production
or dashboard setting has been changed, and redesign/homepage remains at a077246.

Additional scope note: large hub-metadata requests and edge-cache optimisation are
recorded follow-ups, not claimed as fixed. Existing auth/rate controls and API policy
were preserved. Turnstile is deferred by explicit owner choice.

Privacy proposal update: controller/retention values are now pre-filled as [CONFIRM]
in maintenance/site-trust (d7d969f), with provider evidence and a separate retention
follow-up. No purge/aggregation implementation or Turnstile change was introduced.
The updated draft passed 12 page/trust tests and 375/800-width layout checks.
