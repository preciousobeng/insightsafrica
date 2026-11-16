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
