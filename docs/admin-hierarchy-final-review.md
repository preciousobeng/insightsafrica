# InsightsAfrica administrative hierarchy — completed-work review

26 September 2026. **Release status: deployed and verified live.**

## Root cause

The GADM 4.1 geometry was already present and correct. The mapper selected naming fields from human labels such as “districts” and “regions” rather than explicit administrative depth. In Côte d’Ivoire, that assigned parent names to 33 second-level features. Storing their statistics in a dictionary then silently overwrote repeated keys, leaving 14 entries. Those entries are surviving child statistics, not valid parent aggregates, and cannot be repaired by renaming alone.

For Côte d’Ivoire, Cape Verde and South Africa, the same naming assumption produced blank top-level names and public identifiers beginning with `|`. Risk handling also relied on permissive splitting/prefix matching, allowing incorrect joins to survive downstream.

## Implemented repair

- Explicit administrative depth for every boundary layer; GADM depth selects the naming fields.
- Shared strict `Name` / `Name|Parent` key handling. Reject blank names, ambiguous delimiters and duplicate keys before either rainfall writer emits data. Population and risk handling use the same strict identifiers.
- Corrected and independently validated 11 boundary layers. Côte d’Ivoire retains the distinction between 31 regions and two autonomous districts.
- Regenerated archive/current rainfall from original rasters, with each file’s empirically verified original sampling setting.
- Rebuilt baselines, SPI validation, anomalies, Ghana population, Ghana risk validation and Ghana outlook validation in dependency order.
- Corrected generated frontend naming assumptions and the Côte d’Ivoire coarse/fine hierarchy.

| Country | Coarse features | Fine features |
|---|---:|---:|
| Ghana | 16 regions | 260 districts |
| Nigeria | 37 states | 775 LGAs |
| Côte d’Ivoire | 14 districts | 33 regions/autonomous districts |
| Senegal | 14 regions | 45 departments |
| Cape Verde | 22 features in the existing single `islands` layer | — |
| South Africa | 9 provinces | 52 districts |

## Public API decision

Accepted compatibility option (c): an explicit breaking identifier correction with frontend/data released together. The notice is `/admin-hierarchy-v2.html`; flood and boundary responses include `X-Administrative-Key-Version: 2` and a `Link` to the notice. CSV columns and JSON nesting are preserved. Ghana routes and legacy redirects remain available.

No alias can validly turn the 14 overwritten Côte d’Ivoire child entries into the corrected 33. Saved queries, external extracts and Databricks joins using affected identifiers must refresh from corrected data. The frontend consumer changes are included; external client inventories cannot be exhaustively observed from the repository.

## Exact preservation and provenance

The first-class manifest `admin-perfile-provenance.json` records 6,552 comparisons: 3,264 local files (544 months per country, January 1981–April 2026) and 3,288 production files (548 months, through August 2026). Both sampling settings were tested for every file. No file was unmatched or indeterminate.

Every protected area’s mean/min/max is identical at stored precision. The only rainfall-value exception is the explicitly authorised reconstruction of Côte d’Ivoire second-level data from the original rasters. The 14 collapsed entries become 33 distinct entries in every month. The current map layers also pass at their separate one-decimal stored precision: 264 local and 288 production files.

Additional comparisons confirm all protected baseline/anomaly values are identical: 3,270 local files and 3,294 production files. Ghana population was regenerated and matches the original values and file bytes. Nulls remain null, including the eight Nigerian and one Senegalese permanently-null fine areas. South Africa October 1982 still has no districts level.

## Existing methodology break — unresolved by design

For Nigeria, Côte d’Ivoire, Senegal, Cape Verde and South Africa, production files use `all_touched=False` through April 2026 and `True` from May 2026. Ghana uses `True` throughout the audited history. Trends and anomalies crossing May 2026 therefore mix sampling methods. This is a separate pre-existing data-quality issue. It is recorded in the manifest and public notice; aligning the methods remains deferred and was not performed.

## Validation

- Main suite: 96 passed, 16 skipped, 10 warnings. Skips are existing real-data fixtures absent from the isolated checkout, not full-archive replay failures.
- Deployment tests: 3 passed, covering successful replacement, rollback after simulated startup failure, and refusal to introduce new product types or unsafe paths.
- Generated pages: 42 total, 42 identical, zero differing/error/missing pages.
- Both local and production-preview browser checks passed across all six flood pages with zero fatal JavaScript errors. Fine-level polygons: 260/775/33/45/22/52; anomaly counts reflect the preserved nulls.
- Production-preview API checks passed for all current layers, boundaries, baselines, anomaly history, archive CSVs, Côte d’Ivoire current CSV, Ghana redirects and the public notice.
- The same API checks and all six interactive map checks passed against `https://insightsafrica.org` after deployment. The redirect verifier needed consistent request headers: its initial default-client request received HTTP 403, while the redirects themselves were correct; the corrected verifier passed.
- Final on-host integrity check passed for all 6,882 deployed files and all 3,288 unchanged original rasters. The service is active, and the production checkout has no tracked modifications; the pre-existing untracked South Africa indicators file was preserved.
- Both Ghana outlook runs completed for all 260 districts. Browser checks used an isolated cache after the desktop recovery; the user's font cache remained unchanged.

Production currently has no SPI/risk/outlook artifacts or routes. Latest SPI for all six countries and Ghana risk/outlook are validation artifacts in the isolated trees, not new deployed features. The authorised “live risk index” check cannot be performed against a route that does not exist; the staged risk calculation validates all 260 Ghana districts instead.

## Backup and deployment

Verified production backup: `/home/ubuntu/insightsafrica-backups/admin-hierarchy-20260926`.

The 10,170-file archive was read back, every JSON parsed and every member hash checked. Backup SHA256: `ec6b078fc3284f1507d80c099f7aa53ccd2ef3295756fa677d78f4e82d7cf736`. Its archive and current-layer hashes also match the audited production inputs.

The release overlay contains only 6,882 existing products: 3,288 base-stat files, 3,288 anomaly files, six baselines, 288 current layers, 11 boundaries and the unchanged Ghana population file. TIFFs, images and unrelated indicators are preserved. The deployment script rechecks backup/source/release hashes, stops the service while code and data are replaced, and restores the previous code/data if startup verification fails.

Previous production commit: `ea1e482c2493e1394afb7d7881f656cd75f1bafe`.

Deployed commit: `a059a1022cd07d415ac6a12fcc8ce61b1f8a3fde`. The coordinated replacement/startup check completed in 26.65 seconds without rollback. Production is pinned to this detached commit; the review branch also contains the later verification reports and verifier-header correction. GitHub main was not moved or force-pushed.

Release directory: `/home/ubuntu/insightsafrica-releases/admin-hierarchy-20260926`. It contains the deployment result, overlay manifest, integrity report and release files. Live evidence is recorded in `admin-api-live.json` and `admin-browser-live.json`.

The regenerated local archive and local validation products are at `/home/kayob/projects/insightsafrica-codex/admin-hierarchy/data/admin-remediation-output/local`; the independent production replay is beside it under `production`. The original local checkout `/home/kayob/projects/insightsafrica` remains untouched. No original local files were overwritten to perform the local gate.

## Review and rollback

Changes are preserved on `codex/admin-hierarchy-remediation`; no history was rewritten. A review-ready PR description is included. A GitHub PR has not been created because no authenticated PR tool is available in this environment.

Rollback: stop `insightsafrica`, verify the backup hash and manifest, restore the backed-up data under `/home/ubuntu/insightsafrica`, check out the previous commit, then start the service and verify the old release. The deployment helper exercises this sequence automatically on a startup failure. Preserve the backup until consumers have accepted the corrected identifiers.
