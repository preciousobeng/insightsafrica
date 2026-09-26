# Correct administrative identifiers and replay rainfall history without changing sampling

**Deep review: API contract, data pipeline and country configuration.** Kweku explicitly authorised all four phases, including production after passing the local gate and verifying the backup by read-back (25 September 2026 authorisation and revised per-file decision).

GADM geometry was present, but the boundary mapper inferred naming depth from human layer labels. Côte d’Ivoire’s 33 second-level features therefore collapsed into 14 dictionary entries, and several countries exposed top-level keys such as `|Abidjan`. Configure depth explicitly, require strict collision-free keys in both rainfall writers and downstream risk/population handling, and regenerate from the unchanged rasters and corrected boundary names.

## Public behaviour and compatibility

Compatibility option (c): deliberate breaking identifier correction, documented at `/admin-hierarchy-v2.html`, with frontend and data deployed together. Top-level keys use `Name`; child keys use `Name|Parent`. Flood/boundary API responses carry `X-Administrative-Key-Version: 2` and a link to the notice. CSV columns and JSON nesting remain unchanged, and Ghana redirects are retained. The overwritten Côte d’Ivoire child records have no valid one-to-one legacy alias; clients must refresh historical regional extracts and joins.

## Scope

- `api/main.py`: version/notice headers only; no authentication changes.
- `frontend/_config/countries.yml`, generated flood pages and public notice: corrected naming assumptions and CIV 14/33 hierarchy.
- Boundary, rainfall, population and risk scripts: explicit depth, strict keys and collision rejection.
- Replay/audit/deployment scripts, tests and `docs/admin-*`: per-file provenance, exact equality, backup verification, rollback and runtime evidence.
- One coherent task: repair administrative identifiers and regenerate their affected data products.

## Verification

- Empirical sampling audit: 6,552 independent environment/file comparisons; no unmatched or indeterminate files.
- Exact protected rainfall values: 3,264 local and 3,288 production archive files; 264 local and 288 production current layers.
- Protected baseline/anomaly values: 3,270 local and 3,294 production files checked exactly.
- Core tests: 96 passed, 16 existing fixture-dependent skips, 10 warnings. Deployment tests: 3 passed, including rollback after simulated startup failure.
- Generated output: Total 42 | identical 42 | differ 0 | written 0 | errors 0 | missing 0.
- Local and production-preview interactive browser checks: six countries, zero fatal JavaScript errors; fine-level polygons 260/775/33/45/22/52. Expected nulls preserved.
- Production-preview APIs: all countries’ current layers, boundaries, baselines, historical anomalies and archive CSVs; CIV current CSV; Ghana redirects; public version notice; South Africa gap preserved.

## Risks and deferred work

Five countries change sampling method in May 2026 (False through April, True from May); Ghana is True throughout. This repair preserves the existing per-file method and documents the transition. Method alignment remains deferred.

The nine persistent null areas and South Africa October 1982 missing districts level remain unchanged. SPI for all six countries and Ghana risk/outlook are staged validation products; production currently has no corresponding products/routes, so this repair does not introduce them. Final production deployment and live-verification status is recorded separately in the release report.
