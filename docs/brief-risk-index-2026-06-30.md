# Task Brief — Flood Risk Index (Sprint 2)

**Sprint:** Early-Warning Suite, Sprint 2
**Junior (implementer):** DeepSeek (via deepseek_loop.py harness or PR)
**Senior (review + deploy):** Claude
**Owner (domain calls):** Kweku
**Status:** DRAFT 2026-06-30 — for owner review before junior pickup
**Working agreement:** docs/AI-WORKING-AGREEMENT.md (one PR, branch only, no deploy, no env files)
**Depends on:** SPI-3 (Sprint 1, merged to main, commit d37fbfb)

---

## 0. Integrity warning — read first

Unlike SPI-3, **this module is NOT fully empirical.** It blends the SPI-3 rainfall signal (real,
WMO-standard) with **drainage/infrastructure ratings that are currently PLACEHOLDERS** — sourced from
AMA / World Bank documents, not calibrated against observed floods. Real calibration is **blocked on
NADMO district flood records** (the institutional ask via Dr Eric Ofosu-Hene / GMet). Therefore:

- Every Risk Index output **must be tagged `provisional: true`** and treated as EXPERIMENTAL.
- It is **internal/peer-review only** until NADMO calibration — not a public alert.
- The acceptance tests below verify the **combination logic and behaviour**, NOT real-world flood
  prediction accuracy (which we cannot claim until NADMO data lands).

The point of building it now: stand up the plumbing and the model shape so that when NADMO records
arrive, calibration is a parameter-fit, not a rebuild.

## 1. Why this task, and why now

SPI-3 answers "is rainfall unusually high over 3 months?" It deliberately does NOT say "is there flood
danger" — we proved that with the 2014/2015 Accra floods (below-normal 3-month windows; SPI-3 correctly
read them as not-wet). The Risk Index is the layer that turns the rainfall signal into a **danger**
signal by weighting it with **how vulnerable each district is** (drainage quality). Its headline job is
to flag a place like Accra as **structurally at risk even when the 3-month rainfall is unremarkable** —
exactly the gap SPI-3 left open.

## 2. What the Risk Index is (the model)

A per-district monthly score combining **hazard** (rainfall excess, from SPI-3) and **vulnerability**
(drainage rating). Definition for v1 (deliberately simple, testable, and honest about its limits):

1. **Hazard H** from SPI-3 (wet tail only — floods are a wet-side concern):
   - H = 0 for spi3 <= 0
   - H = spi3 / 2.0 for 0 < spi3 < 2.0
   - H = 1 for spi3 >= 2.0
   (Linear ramp, saturating at SPI +2. H is in [0, 1].)
2. **Vulnerability V** from the drainage rating:
   - Good = 0.25, Moderate = 0.50, Poor = 0.75, None = 1.00
   (None = no drainage infrastructure = most vulnerable. V is in (0, 1].)
3. **Risk R** combines a STANDING vulnerability floor with rainfall amplification:
   - R = V * (BASE + (1 - BASE) * H), with **BASE = 0.30**
   - So a poor-drainage district shows meaningful risk even in a dry month (standing exposure),
     and rainfall pushes it higher. R is in [0, 1].
4. **Categories** (provisional thresholds, calibration targets for NADMO):
   - R < 0.25 = low ; 0.25 <= R < 0.50 = moderate ; 0.50 <= R < 0.75 = high ; R >= 0.75 = severe

> **Honest limitation (document it, don't hide it):** because the hazard input is a 3-month rainfall
> index, this v1 captures **sustained-rainfall flooding in vulnerable areas**. It still will not catch a
> single-day cloudburst on a dry backdrop from monthly data alone — that needs a future **daily
> rainfall intensity** input (CHIRPS daily or similar). The standing-vulnerability floor (BASE) is what
> lets it flag chronically flood-prone districts (e.g. Accra) regardless of the month's SPI; that is the
> v1 value-add over SPI-3, and the cloudburst-intensity layer is explicitly a later sprint.

BASE and the V / H mappings are **named constants at the top of the module** — they are the parameters
NADMO calibration will later fit. Do not bury them in the logic.

## 3. Inputs (existing, do not change their format)

- **SPI-3:** data/archive/{country}/spi/chirps-v2.0.{YYYY}.{MM}_{country}_spi3.json (Sprint 1 output;
  per-area spi3 + fit block). Run compute_spi.py first if the file is absent (clear FileNotFoundError
  pointing at it).
- **Drainage / IFT:** frontend/static/data/ghana_infrastructure.json — 39 Ghana districts with a
  drainage rating (Good/Moderate/Poor/None) and a placeholder IFT % value. **Coverage gap:** only ~39
  of Ghana's 260 districts are present. Districts with no drainage entry get a **null risk with a skip
  reason** (`no_drainage_data`) — do NOT invent a default rating.
- Ghana only this sprint (only Ghana has the infrastructure layer).

## 4. Output (mirror the SPI/anomaly conventions)

- **Script:** scripts/compute_risk_index.py
- **Path:** data/archive/{country}/risk/chirps-v2.0.{YYYY}.{MM}_{country}_risk.json
- **CLI (mirror compute_spi.py):**
  python scripts/compute_risk_index.py --country ghana --year 2025 --month 6
- **Per-district schema:**

      {
        "spi3": 1.84,
        "drainage": "Poor",
        "hazard": 0.92,
        "vulnerability": 0.75,
        "risk": 0.83,
        "category": "severe",
        "provisional": true
      }

- **Top-level wrapper:** { "country", "year", "month", "model_version": "risk-v1",
  "params": { "base": 0.30, "v_map": {...}, "h_saturation_spi": 2.0 }, "provisional": true,
  "generated_utc", "skipped_districts": <n>, "districts": { district_key: {...} } }
  (Echoing the params block makes every score auditable and records exactly what NADMO will recalibrate.)

- Operate at **district level only** (drainage data is per-district). Use the same district key
  convention as the stats/SPI files: `name|region`.

## 5. Constraints

- House style: BASE_DIR = Path(file).parent.parent, argparse, rounded floats (risk/hazard/vuln to 2 dp),
  clear FileNotFoundError messages naming the upstream script, sort_keys on write, deterministic.
- Touch **only** new files plus requirements if needed. Do NOT modify compute_spi.py, compute_anomaly.py,
  api/main.py, the frontend, or ghana_infrastructure.json.
- No look-ahead, no network. Pure function of the two input files.
- One PR, branch feature/risk-index. No deploy, no server access, no env files.
- Every output record carries `provisional: true`. The top wrapper too.

## 6. Acceptance tests (deliver tests/test_risk_index.py; all must pass)

Behaviour and correctness, not "it runs." These verify the MODEL, not flood-prediction accuracy.

- **A — Monotonic in rainfall.** Holding drainage fixed, risk is non-decreasing as spi3 rises, and
  strictly higher at spi3=+2 than at spi3<=0. (Wetter = more dangerous, all else equal.)
- **B — Monotonic in vulnerability.** Holding spi3 fixed, risk is strictly higher for None than Poor than
  Moderate than Good drainage. (Worse drainage = more dangerous, all else equal.)
- **C — Standing exposure (the value-add over SPI-3).** A Poor- or None-drainage district with spi3 <= 0
  still has risk at or above the `moderate` threshold (>= 0.25) — i.e. chronic vulnerability is flagged
  even in a dry month. A Good-drainage district with spi3 <= 0 is `low`.
- **D — 2015 Accra hindcast (the headline — ties to the SPI-3 negative control).** For window ending
  2015-06, the Greater Accra / Accra-area districts (which SPI-3 read as BELOW normal, i.e. spi3 < 0)
  still come out at **moderate or higher** risk, because their drainage is Poor/None. This proves the
  Risk Index catches the structural danger SPI-3 alone missed. (If Accra districts lack a drainage entry,
  assert on the nearest covered flood-prone district and document it.)
- **E — Range and completeness.** Every risk in [0, 1], finite, categorised correctly at the thresholds.
  Every district present in BOTH the SPI file and the drainage file appears; districts missing drainage
  data appear as null with `skip_reason: "no_drainage_data"`; nothing silently dropped.
- **F — Provisional tag.** Every district record and the top wrapper carry `provisional: true`, and the
  params block echoes BASE + the V map + the SPI saturation point.
- **G — Determinism.** Two runs produce byte-identical output.
- Plus helper unit tests for the hazard ramp (0 at spi<=0, 0.5 at spi=1, 1.0 at spi>=2), the V map, and
  the R formula at known points (e.g. V=0.75, spi3=0 -> R=0.75*0.30=0.225 -> low/moderate boundary).

## 7. Definition of Done

1. scripts/compute_risk_index.py + tests/test_risk_index.py in one PR on feature/risk-index.
2. Tests A–G + helpers green locally against the Ghana SPI + drainage files.
3. Senior review (correctness, house style, no scope creep, provisional tagging present).
4. Output labelled **experimental / provisional** everywhere — NOT a public alert until NADMO calibration.
5. Senior regenerates Ghana risk on free-arm2 and hand-checks 2–3 districts (including an Accra-area one).

## 8. Open decisions (for owner before/at pickup)

- **Q1 — BASE and the V/H mappings.** Proposed BASE=0.30 and Good/Mod/Poor/None = 0.25/0.5/0.75/1.0.
  These are guesses pending NADMO. Accept as v1 placeholders (clearly labelled) or tweak now?
- **Q2 — Coverage gap.** Only ~39/260 districts have drainage data. v1 emits null+skip for the rest.
  Acceptable, or do we want a coarse region-level fallback rating? (Recommend: null for now, honest.)
- **Q3 — Cloudburst/daily layer.** Confirm the daily-rainfall-intensity input is a SEPARATE later sprint,
  not in scope here.
- **Q4 — API/frontend exposure.** OUT of Sprint 2 (compute + tests only), same as SPI-3. The user-facing
  "Flood Risk" view waits until the model is NADMO-calibrated.
