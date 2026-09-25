# Sampling decision audit — mixed production settings require a stop

25 September 2026. Responds to CODEX_GATE3_DECISION_sampling.md.

## Outcome

The requested empirical determination found a single-setting contradiction in five production countries. Regeneration remains stopped. No archive values, boundary files in service, sampling defaults, derived products or production configuration were changed.

The decision explicitly says: “Where a country's months do not agree on a single setting, stop and report that country. Do not guess, and do not split a country across settings to force a match.” This condition is met for Nigeria, Côte d'Ivoire, Senegal, Cape Verde and South Africa.

## Determination table

Each match means exact equality of stored mean/max/min for every existing area and level in the tested file, except Côte d'Ivoire's corrupted second level. Nulls were compared unchanged. Both sampling settings were tested independently against each environment's archive.

| Country | Local Jan 1981 | Local Apr 2026 | Production Apr 2026 | Production Aug 2026 | Production result |
|---|---|---|---|---|---|
| Ghana | True | True | True | True | No conflict in sampled months |
| Nigeria | False | False | False | True | STOP: mixed |
| Côte d'Ivoire | False | False | False | True | STOP: mixed |
| Senegal | False | False | False | True | STOP: mixed |
| Cape Verde | False | False | False | True | STOP: mixed |
| South Africa | False | False | False | True | STOP: mixed |

True/False refer to `all_touched`. Production Ghana January 1981 also matches True exactly.

Local archives contain 544 files per country through April 2026; production contains 548 through August 2026. The local evidence supports the proposed settings in the two tested months only. It does not establish all-month consistency. Likewise Ghana has not yet passed the complete historical equality check. A full audit/regeneration was not started after the sampled production contradiction was found.

## Numerical evidence

For production April 2026, False reproduces every protected value in the five affected countries. For production August 2026, True reproduces every protected value. Using False in August changes these numbers of area-statistic records (at least one mean/max/min value):

| Country | Areas differing under False in August |
|---|---:|
| Nigeria | 811 |
| Côte d'Ivoire (districts only) | 14 |
| Senegal | 59 |
| Cape Verde | 22 |
| South Africa | 61 |

Full per-file match results, difference counts for both settings and example values are in `admin-sampling-determination.json`.

Inputs are isolated copies of local and production archives. A checksum-based, read-only rsync dry run confirmed the copied production JSON/raster inputs still matched production, with no differences reported. Production code remains ea1e482. Computation used the validated staged GADM boundaries; production files were not replaced.

## What this establishes, and what it does not

This empirically confirms that the split is within production time series as well as between countries. Timestamps were not used to choose a setting. The exact transition month has not been determined; it lies somewhere after the tested April file and no later than the tested August file. No assumption about May–July is made.

The previous characterisation of the nine null areas as an unavoidable resolution limit is superseded by the owner's sampling decision. They remain protected in this repair because filling them would change methodology. No null values were filled or interpolated.

## Required scope decision

The current requirements cannot all be satisfied for these production archives: one setting per country, exact preservation of every historical value, and no methodology change. Applying False everywhere would change the newer months; applying True everywhere would change older months.

Recommended next authorisation, if historical values must remain identical: permit empirical per-file sampling identification for the naming repair, record the matched setting in a separate provenance manifest, require exact equality of all unaffected values, and stop on files that match neither setting. This is a proposal only: per-file selection is explicitly prohibited by the current decision and has NOT been implemented. Aligning everything to True remains the separately deferred methodology v2.

No deployment permission is missing. The blocker is the expressly required numerical/sampling gate. The accepted code and boundary stages remain available on `codex/admin-hierarchy-remediation`; no production rollback is necessary because production was never changed.
