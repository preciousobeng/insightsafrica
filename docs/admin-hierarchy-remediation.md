# Administrative hierarchy remediation — code gate

Owner authorisation: CODEX_AUTHORISATION_admin_hierarchy_remediation.md, 25 September 2026. Production is authorised only after the stated technical gates; no further permission is needed. Null statistics and the October 1982 South Africa omission remain out of scope.

## API compatibility decision (PR description)

**Option (c): deliberate documented breaking identifier correction, with frontend and data shipped together.** Keep existing JSON nesting and CSV columns. Top-level `|Name` becomes `Name`; children use `Name|Parent`. Publish `/admin-hierarchy-v2.html` and a version-2 response header on flood/boundary APIs. No legacy alias can faithfully represent the corrupted Côte d'Ivoire regional rows: those are overwritten child values under parent names. Repeating them as aliases would preserve misleading geography. Clients must refresh affected data rather than join old and new regional entries.

## Consumer inventory and limits

- API layer factories, latest Ghana layer, rainfall CSV and archive CSV expose stored keys. Boundary factories and downloads expose the corresponding properties. Anomaly, SPI, risk and outlook endpoints expose derived keys. All must switch together with the data; in-memory CSV caches require process restart.
- Shared flood template plus Ghana and Cape Verde variants join rainfall/anomaly/SPI with boundary names and parents; regenerate all six pages. Remove South Africa's empty-name workaround. Nigeria hover must use the actual `region` parent field.
- Ghana `/ghana`, legacy redirects and `/api/flood/*` remain routed unchanged, with existing Ghana identifiers retained.
- LTM, SPI, anomaly, population exposure, risk and outlook consume the identifiers. SPI's `level|area` split is intentionally a single split of a composite identifier, not the defective area parser. Risk and exposure now use shared validated key handling.
- Local saved extracts identified in Downloads/insightsafrica_databricks: `ia_ltm_reference.csv` and `ia_spi3.csv`, with `area_name`/`parent_name` columns, plus Databricks_InsightsAfrica_StepByStep.docx. These are downstream copies, not production inputs. They must be re-exported after a successful release; they have not been edited.
- Repository searches cannot identify every anonymous external API consumer, private notebook or remote saved query. No exhaustive external-user inventory is claimed. The breaking-change notice and response version expose the contract correction publicly; no messages are sent to users.

## Code changes requiring deep review

Boundary mapping explicitly uses GADM depth, retains source type (31 regions versus two autonomous districts), validates existing files and refuses implicit overwrite. Both rainfall writers and population writer reject blank/duplicate keys before raster calculation. Risk parsing rejects invalid identifiers and only resolves unambiguous exact-name fallbacks. Regression tests exercise all eleven country layers, 33 Côte d'Ivoire features, null preservation and actual writer rejection paths.

## Gates

1. Code tests and generated-page verification; no data writes.
2. Fetch boundaries into a new staging tree, validate counts, source geometry and keys, commit evidence.
3. Local-only raster regeneration and dependent products; compare semantic values, preserve nulls and October 1982 omission. A changed top-level statistic in Cape Verde, Côte d'Ivoire or South Africa stops the phase.
4. Only after Gate 3 passes: verified read-back backup before any production overwrite; deploy code/frontend and regenerate dependencies together; live checks and rollback evidence.
