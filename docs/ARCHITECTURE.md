# InsightsAfrica — Flood Early-Warning Suite: Architecture & Layer Flow

**Living document.** This is the single map of how the analytical layers fit together, what each one
does, and its status. Update it whenever a layer is added or changes; the iteration log at the bottom
is the running history. Last updated: 2026-06-30.

---

## 1. The grand scheme in one paragraph

We turn raw satellite rainfall into a trustworthy flood early-warning service for African cities. Raw
data flows up through a stack of analytical layers, each one more meaningful than the last: from
"how much rain fell" → "is that unusual" → "is it unusually high by a rigorous global standard" → "does
that mean danger here" → "what is likely next" → "what should be done." The top of the stack is
delivered to people and agencies through maps, an API, and an alert ticker. SPI-3 is the rigour layer;
the Risk Index is the layer that turns rigour into danger.

## 2. The layer stack (data flows UP)

```
   DELIVERY        [ Maps / API / Telegram alert ticker ]   <- what users & agencies see
       ^
   ----+---------------------------------------------------
       |
   L7  | ACTION TRIGGERS      per-district "if risk crosses X, do Y" (NADMO playbook)   [PLANNED]
   L6  | PREDICTION           short look-ahead: trend / ARIMA on the signal             [PLANNED]
   L5  | RISK INDEX           SPI-3  x  drainage vulnerability  = danger score          [DONE-prov]
   L4  | SPI-3                WMO gamma-standardised "unusually wet/dry?" one number     [DONE]
   L3  | ANOMALY vs LTM       % above/below the 30-yr normal + z-score                   [LIVE]
   L2  | LTM BASELINE         the 1991-2020 normal, per place per month (WMO ref)        [LIVE]
   L1  | RAINFALL (mm)        monthly satellite rainfall, per district                   [LIVE]
       |
   ----+---------------------------------------------------
       ^
   DATA FOUNDATION  [ CHIRPS rainfall 1981-now | admin boundaries | drainage/IFT |
                      NADMO flood records (NOT YET - the calibration gate) ]
```

Each layer consumes the one(s) below it. Nothing skips a layer.

## 3. Layer-by-layer

| # | Layer | What it answers | Built from | Status | Empirical? |
|---|-------|-----------------|------------|--------|-----------|
| L1 | Rainfall (mm) | How much rain fell here this month? | CHIRPS satellite + boundaries | LIVE, 6 countries | Yes |
| L2 | LTM Baseline | What is "normal" rain here for this month? | L1 over 1991-2020 (WMO) | LIVE, 6 countries | Yes |
| L3 | Anomaly vs LTM | Is this month above/below normal, and by how much? | L1 vs L2 (%, z-score) | LIVE on all 6 FloodWatch maps | Yes |
| L4 | **SPI-3** | Is the last 3 months unusually wet/dry, on a rigorous global standard? | L1 + L2, gamma transform | **DONE (merged, not deployed)** | Yes |
| L5 | **Risk Index** | Does the rainfall signal mean DANGER here? | L4 + drainage/IFT ratings | **DONE (provisional)** | **No — provisional** |
| L6 | Prediction | What is likely next month / this season? | L3/L4 time series (trend, ARIMA) | Planned | Yes |
| L7 | Action Triggers | What should NADMO actually do, per district? | L5 + NADMO thresholds | Planned | Needs NADMO |

**Why L4 vs L3:** the Anomaly layer (L3) and SPI-3 (L4) both answer "is rainfall unusual," but SPI-3 is
the WMO-standard, statistically rigorous, cross-region-comparable version. L3 is the readable everyday
view; L4 is the scientifically defensible one the Risk Index and peer-review build on.

**Why L5 is the turning point:** L1-L4 all describe RAINFALL. L5 is the first layer that describes
DANGER, by weighting rainfall with how vulnerable a place is (drainage). It is the first thing worth
calling "early warning" — but it is provisional until calibrated (see section 5).

## 4. Delivery layer (how the top of the stack reaches people)

| Channel | What it is | Status |
|---------|-----------|--------|
| FloodWatch maps | Per-country interactive maps; today toggle Rainfall (L1) / Anomaly (L3) | LIVE, 6 countries |
| API | FastAPI route factory serving each layer's JSON | LIVE for L1-L3; L4/L5 endpoints not built yet |
| Alert ticker | Telegram push (currently OSINT news via Crucix) | LIVE for news; flood-risk alerts = future (needs L5+L7) |
| Product cards | FloodWatch / MineWatch / CropWatch / HeatWatch / HumanWatch per country + hub KPIs | LIVE |

**Important:** SPI-3 (L4) and the Risk Index (L5) currently have **NO API endpoint and NO map view** —
that frontend/API exposure is a deliberately separate sprint. The first user-visible flood-RISK element
should be the Risk Index, not SPI-3 on its own (SPI-3 alone would overlap the existing Anomaly toggle).

## 5. The NADMO calibration gate (what is blocked, and why it matters)

The Risk Index (L5) and Action Triggers (L7) need **observed flood records** to move from "plausible
model" to "validated tool." Those are the **NADMO district flood records** — the institutional ask via
Dr Eric Ofosu-Hene / GMet. Until they arrive:

- The drainage/IFT ratings feeding L5 are **placeholders** (AMA / World Bank docs), so L5 ships tagged
  `provisional` and stays internal / peer-review only.
- L7 (per-district action thresholds) cannot be set responsibly at all.

Everything BELOW the gate (L1-L4, Prediction L6) is fully empirical and can proceed without NADMO. The
strategy is to build the L5 plumbing now so that, when NADMO data lands, calibration is a parameter-fit
(BASE, the drainage weights, the category thresholds) — not a rebuild.

## 6. Build sequence (sprints)

- **Sprint 1 — SPI-3 (L4): DONE.** Engine + tests, merged to main (d37fbfb). Not deployed.
- **Sprint 2 — Risk Index (L5): DONE (provisional).** docs/brief-risk-index-2026-06-30.md. Provisional
  model (SPI x drainage), compute + tests, Ghana first, merged to main. Experimental until NADMO.
- **Sprint 3+ (candidates, any order):**
  - SPI-3 + Risk API endpoints + a FloodWatch "Risk" view (the user-facing exposure).
  - Replicate SPI-3 (and later Risk) to the other 5 countries.
  - Prediction layer (L6): trend / ARIMA on the SPI/anomaly series — fully empirical, no NADMO needed.
  - Daily-rainfall-intensity input (to catch single-day cloudburst floods L4/L5 miss by design).
  - Methodology / peer-review write-ups per country.

## 7. Design principles (kept across all layers)

- **Honest before impressive.** Each layer states what it does NOT do (e.g. SPI-3 misses cloudbursts;
  Risk Index is provisional until NADMO). Caveats are in the output, not hidden.
- **Auditable.** Every score ships the parameters used to compute it, so any number can be recomputed by
  hand (SPI-3 fit block; Risk Index params block).
- **Compute first, expose later.** Layers are built as data-pipeline scripts + tests, reviewed, then
  exposed to API/frontend in a separate step — so the science is locked before the UI.
- **Senior/junior loop.** Junior (DeepSeek) implements on a branch; senior (Claude) reviews and never
  lets unproven code through; owner (Kweku) makes domain calls. See docs/AI-WORKING-AGREEMENT.md.

---

## Iteration log

- **2026-06-30 (later)** — Risk Index (L5) BUILT + GREEN (compute_risk_index.py + 15 tests), merged to
  main, NOT deployed. Provisional model (BASE=0.40); Accra flags moderate when dry, severe when wet —
  the value-add over SPI-3 proven. Built via the harness in TDD mode (senior froze tests, junior wrote
  engine). 39/260 Ghana districts covered (drainage gap). Status table above: L5 moves BRIEFED -> DONE
  (provisional). Next per owner: Prediction (L6), then replicate SPI-3 to the other 5 countries.
- **2026-06-30** — Architecture doc created. SPI-3 (L4) merged to main (d37fbfb), not deployed. Risk
  Index (L5) brief drafted (docs/brief-risk-index-2026-06-30.md). Decision: hold all user-facing
  (API/frontend) exposure of L4/L5 until the Risk Index is NADMO-calibrated; lock in code on main as we
  go. NADMO records confirmed as the calibration gate for L5/L7.
- **2026-06-29** — SPI-3 (L4) built green via the senior/junior loop; brief self-correction (2014/2015
  Accra floods reframed as negative controls — they are below-normal 3-month windows, which is what
  motivates L5). deepseek_loop.py harness built.
