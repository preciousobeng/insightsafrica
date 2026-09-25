# Administrative hierarchy remediation — Gate 3 stopped

25 September 2026. Production remains at ea1e482; no production files or configuration changed. Original local archive and boundary files are untouched. New boundaries and copied inputs exist only in the isolated worktree.

## Completed

- Gate 1 commit `19e3c35`: explicit administrative-depth mapping, strict shared keys in both rainfall writers and risk handling, collision rejection, population-key validation, documented API identifier version 2 and generated frontend updates.
- Code validation: 83 passed, 16 skipped, 10 warnings. Skips are existing real-data tests whose fixtures are absent in the isolated worktree. Generated pages: 42 identical, 0 differ, 0 errors, 0 missing. Runtime browser validation remains pending; no production-readiness claim is made.
- Gate 2 commit `c22b5a6`: fetched all eleven GADM 4.1 boundary layers into new staging files, validated unique nonblank names, preserved source geometry and source feature counts. Counts: Ghana 16/260; Nigeria 37/775; Côte d'Ivoire 14/33; Senegal 14/45; Cape Verde 22; South Africa 9/52. Côte d'Ivoire level 2 retains 31 regions and 2 autonomous districts. Per-layer samples, types, URLs and hashes are in admin-hierarchy-gate2.json.
- The existing main checkout was not modified. The fix branch is `codex/admin-hierarchy-remediation`, at `/home/kayob/projects/insightsafrica-codex/admin-hierarchy` on Kubuntu.

## Gate 3 failure

The preflight recomputed Cape Verde April 2026 from the copied production raster using corrected staged boundaries and the current archive writer. All 22 areas changed at least one statistic. Count remained 22. Example:

| Area | Statistic | Existing archive | Current writer |
|---|---|---:|---:|
| BoaVista | mean | 1.80 | 1.75 |
| BoaVista | min | 1.36 | 1.30 |
| SãoDomingos | mean | 3.49 | 3.06 |

No recomputed archive JSON was written. The check stopped at the first country, as required; Côte d'Ivoire and South Africa numerical preflight has not run. Derived-product regeneration and production deployment have not begun.

The authorisation says: “If a statistic moves there, stop: something beyond the naming is wrong.” That stop condition was met. It is not an approval-tool rejection or a missing deployment permission.

## Read-only diagnosis

Repeating the same Cape Verde month in memory with the same raster and corrected boundaries establishes:

- `all_touched=False`: **0 of 22** areas differ from the existing archive, across mean/max/min rounded to two decimals.
- `all_touched=True` (current writer): **22 of 22** areas differ.

The existing writer already contained `all_touched=True`; the hierarchy fix did not introduce it. Repository commit `f41ffc9` introduced this setting with the message “fix: all_touched=True in zonal stats so sub-pixel urban districts get data”.

Thus this sample's mismatch is reproducibly explained by raster pixel inclusion, not by corrected names. False uses pixel centres; true includes any pixel touched by a polygon. A full rerun with the current writer would mix a numerical methodology change into the authorised naming repair and could also change the protected null areas. No sampling setting was changed to bypass the gate.

## Required next decision and proposed safe continuation

Agree a sampling-preservation strategy before resuming Phase 3. Recommended: independently establish which sampling setting produced each existing country/month (including local versus production differences), then regenerate with the matching setting and require exact equality for every unaffected area. Do not assume the April Cape Verde result proves the setting for every historical file. Report ambiguous or unmatched files rather than guessing. Preserve null values and the October 1982 South Africa omission.

Once that plan is agreed, complete the full base-statistics comparison, derived regeneration, real-data and browser checks before reconsidering Gate 3. Production backup/read-back and deployment remain conditional on that gate passing. Existing authorisation already covers deployment after a clean gate; it does not waive this numerical stop condition.

## API compatibility and remaining consumer work

The prepared code chooses authorised option (c): a deliberate documented identifier correction, frontend shipped with data, and public version header/notice. Old Côte d'Ivoire regional identifiers are not preserved as aliases because they represent overwritten child statistics and have no faithful one-to-one mapping to the 33 corrected entries. Data version notice is staged only and is not live.

Repository consumers and local Databricks CSV extracts are documented in admin-hierarchy-remediation.md. Anonymous external API consumers and private remote saved queries cannot be exhaustively identified from the repository. No users were contacted and no saved extracts were overwritten.
