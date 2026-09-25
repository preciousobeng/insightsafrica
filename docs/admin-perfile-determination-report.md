# Full per-file determination — passed before regeneration

25 September 2026. Implements CODEX_GATE3_DECISION_v2_perfile.md.

All **6,552 archive files** were independently compared with both sampling settings: 3,264 local (544 per country) and 3,288 production (548 per country). Every file matched exactly one setting. Unmatched: 0. Indeterminate: 0. No archive regeneration was performed by this determination step.

| Country | Local selection | Production selection |
|---|---|---|
| Ghana | True for all 544 files | True for all 548 files |
| Nigeria | False for all 544 files | False through 2026-04 (544); True from 2026-05 (4) |
| Côte d'Ivoire | False for all 544 files | False through 2026-04 (544); True from 2026-05 (4) |
| Senegal | False for all 544 files | False through 2026-04 (544); True from 2026-05 (4) |
| Cape Verde | False for all 544 files | False through 2026-04 (544); True from 2026-05 (4) |
| South Africa | False for all 544 files | False through 2026-04 (544); True from 2026-05 (4) |

True/False means `all_touched`. Each result is empirical exact equality at stored precision for every mean/min/max, including nulls, in every existing level except the explicitly exempt corrupted Côte d'Ivoire regional level. Missing South Africa October 1982 districts were not filled or repaired.

## Provenance deliverable

`admin-perfile-provenance.json` records every file, its environment, source JSON hash, raster hash, both settings' difference counts and examples, uniquely matching setting, original level counts and null-mean keys. The manifest also records staged boundary hashes and the transition month per country. Computations shared identical raster/boundary inputs for efficiency, but each environment's stored JSON was compared separately. The copied production input files were checked against live production by a checksum-based read-only rsync dry run; no differences were reported.

Runtime: Python 3.12.3; rasterstats 0.21.0; rasterio 1.3.10; NumPy 1.26.4; Shapely 2.0.3. The full determination used the existing rasterstats calculation without the migration geometry cache. The later replay cache has separately matched unmodified rasterstats for all 775 Nigerian LGA outputs under both settings, and passed grid/sampling/nodata regression tests. Replay still requires exact per-file equality before writing any staged output.

## Independent data-quality finding

Production Nigeria, Côte d'Ivoire, Senegal, Cape Verde and South Africa all change sampling methodology in **May 2026**. Trends and anomalies crossing that boundary mix methods. This predates the naming repair, is not corrected by it, and is deliberately preserved here. Alignment to all_touched=True remains the separately deferred methodology v2. The nine historical null areas are protected as sampling evidence; they are not described as an unavoidable resolution limitation.

## Remaining gates

Current map-layer JSON is being checked separately at its own stored precision before replacement. Staged local regeneration, derived-product validation, full diff, runtime browser checks, verified production backup and live deployment are not claimed complete by this determination report.

The actual production inventory has baselines/anomalies but no SPI/risk/outlook artifacts or risk API route. Newly generated SPI/risk/outlook outputs are to be validated locally; no unrelated API surface will be added. Population/drainage and risk/outlook implementations are Ghana-specific. This limitation must be reported explicitly rather than claiming a live risk route was verified.
