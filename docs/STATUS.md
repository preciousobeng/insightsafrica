# Project Status — rolling index

The single current-state-of-the-project file. **Append** a dated, attributed entry at the top.
Never delete or rewrite another author's entry — if something is now wrong, add a new entry that
supersedes it and say so. Format: `## YYYY-MM-DD <author> — <summary>`.

## 2026-06-29 claude — SPI-3 pre-handoff: data synced, brief corrected

Senior review before the DeepSeek handoff. Three things done: (1) Ghana CHIRPS archive (544 stats
files + ghana_ltm_1991_2020.json) synced from free-arm2 to the local checkout under
data/archive/ghana/ — it is gitignored and was previously absent locally, so tests would have hit
FileNotFoundError. (2) **Correction to my 2026-06-29 entry below: "Tests A–F need no external data"
is wrong** — Tests A (reference normality), C (cross-check) and D (zero-handling) all read the Ghana
archive; only F (determinism) and partial B are dataless. (3) Brief corrected: the Test G region key
is `GreaterAccra` (no space), not "Greater Accra"; and the May-2024 figure is 221.3 mm, not 232 mm
(verified against the stats files). Two SPI spec subtleties left in deliberately as PR-review catches
(per owner): Test A should assert on the pooled distribution not per-cell (n≈30 is flaky per-cell),
and Test G5's "median" must be the H(x)=0.5 mixture median, not the gamma median, when p_zero>0.

## 2026-06-29 claude — Early-Warning Suite kicked off; SPI-3 is Sprint 1

The next phase is the Flood Early-Warning Suite (intelligence layer, district-level). Sprint 1 is
**SPI-3 only** — see docs/brief-spi3-2026-06-29.md (FINALISED). A fresh junior should start at
docs/ONBOARDING-junior.md. Decisions locked with the owner: scipy approved + installed in the venv
(scipy 1.13.1); pytest added (requirements-dev.txt); API/frontend exposure of SPI is OUT of
Sprint 1; Ghana only first, then replicate to the other 5 once green. Test G (hindcast) is locked
against authoritative records — wet asserts: Jul 1995, Jun 2014, May 2024 (SPI-3 >= +1.0), Jun 2015
soft (>= 0.0); dry side via reference-set sign-consistency. NADMO records remain the later
per-district calibration upgrade (institutional ask via Dr Eric Ofosu-Hene). Tests A–F need no
external data and can proceed now.
