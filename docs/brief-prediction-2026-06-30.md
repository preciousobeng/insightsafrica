# Task Brief — Seasonal Outlook / Prediction (Sprint 3)

**Sprint:** Early-Warning Suite, Sprint 3
**Junior (implementer):** DeepSeek (deepseek_loop.py harness, TDD mode — senior owns the tests)
**Senior (review + deploy):** Claude
**Owner (domain calls):** Kweku
**Status:** DRAFT 2026-06-30
**Depends on:** the monthly rainfall archive (same input as SPI-3). statsmodels==0.14.6 (pinned).

---

## 0. Honesty stance (read first)

Monthly rainfall is genuinely hard to forecast — a model often barely beats just using the seasonal
average. So this layer is an **experimental seasonal OUTLOOK, not a confident predictor**, and it is
built to be honest about that:

- The model (SARIMA) is **always reported against two naive benchmarks**: climatology (the historical
  average) and persistence. We only present the model as the issued outlook **where it actually beats
  climatology** (positive skill); otherwise we fall back to climatology and say so.
- Every output is tagged `experimental: true` and carries its **skill score**, so no one can read it as
  more certain than it is.
- This is a WMO/IRI-style tercile outlook (below / near / above normal), which is the standard honest
  way to present seasonal rainfall.

## 1. What it produces

A **3-month seasonal outlook** per district, issued from a given month M: it forecasts the **total
rainfall over the next 3 months (M+1, M+2, M+3)** and expresses it as a tercile category vs that same
calendar window's history.

## 2. The model (v1)

For each district, using its monthly rainfall series (1981-present):

1. **Point forecast (model):** fit SARIMA with a FIXED parsimonious order — `ORDER = (1,0,0)`,
   `SEASONAL_ORDER = (1,0,0,12)` (no per-district order search; deterministic, fast). Forecast M+1..M+3,
   sum to a 3-month total. (enforce_stationarity=False, enforce_invertibility=False for robustness.)
2. **Benchmark — climatology:** the mean of the historical 3-month totals for the SAME target calendar
   window (e.g. if forecasting JAS, the mean of all past Jul+Aug+Sep totals).
3. **Benchmark — persistence:** carry the most recent observed 3-month total forward.
4. **Skill:** a rolling-origin backtest over the last `BACKTEST_YEARS = 10` issuances — RMSE of the model
   vs RMSE of climatology — `skill_score = 1 - RMSE_model / RMSE_clim`. Positive = model beats
   climatology.
5. **Issued outlook:** if `skill_score > 0`, issue the SARIMA forecast and set `method = "sarima"`;
   else issue the climatology value and set `method = "climatology_fallback"`. **Either way** the output
   carries both benchmarks and the skill score.
6. **Tercile category:** classify the issued forecast against the historical distribution of that target
   window — below 33rd pct = `below`, above 67th = `above`, else `near` (normal).

Districts with fewer than `MIN_YEARS = 20` years of usable history are skipped (`insufficient_history`).

## 3. Inputs

- Monthly rainfall: data/archive/{country}/stats/chirps-v2.0.{YYYY}.{MM}_{country}.json (zonal_stats →
  districts → area → mean mm). **Same source and nesting as SPI-3 — read zonal_stats.districts.**
- No drainage, no SPI file needed. Pure function of the rainfall series. Ghana first.

## 4. Output

- **Script:** scripts/compute_outlook.py
- **Path:** data/archive/{country}/outlook/chirps-v2.0.{YYYY}.{MM}_{country}_outlook3.json
- **CLI:** python scripts/compute_outlook.py --country ghana --year 2026 --month 4
  (issues the outlook FROM 2026-04, forecasting May+Jun+Jul 2026)
- **Per-district schema:**

      {
        "issued_from": "2026-04",
        "target_window": ["2026-05", "2026-06", "2026-07"],
        "forecast_3mo_mm": 412.5,
        "category": "near",
        "method": "sarima",
        "skill_score": 0.12,
        "benchmarks": { "climatology_mm": 398.1, "persistence_mm": 365.0 },
        "tercile_bounds_mm": { "p33": 360.2, "p67": 430.8 },
        "n_years": 44,
        "experimental": true
      }

- **Top wrapper:** { "country", "issued_from", "target_window", "model": "outlook-v1",
  "params": { "order": [1,0,0], "seasonal_order": [1,0,0,12], "backtest_years": 10, "min_years": 20 },
  "experimental": true, "generated_utc", "skipped_districts": <n>, "districts": { key: {...} } }

## 5. Constraints

- House style: BASE_DIR, argparse, rounded floats (mm to 1 dp, skill to 2 dp), clear errors, sort_keys,
  deterministic. SARIMA MLE is deterministic for fixed data+order — no random seed needed, but set fit
  `disp=False` and do not use random restarts.
- **No look-ahead.** Issuing from month M uses rainfall up to and including M only. The backtest at each
  origin uses only data up to that origin. (Tested — see Test E.)
- Touch only new files + requirements. Do not modify compute_spi.py / compute_risk_index.py / the API /
  frontend. One PR, branch feature/prediction.
- Every record + the wrapper carry `experimental: true`.

## 6. Acceptance tests (deliver tests/test_outlook.py; senior-frozen in TDD mode)

Behaviour and honesty, not forecast accuracy. Use small SYNTHETIC tempdir archives for the behavioural
tests (fast — do NOT fit SARIMA on all 260 real districts inside a unit test).

- **Helpers:** `tercile_category(value, history)` (below/near/above vs 33rd/67th pct);
  `skill_score(model_rmse, clim_rmse)` = 1 - model/clim (e.g. (0.5,1.0)->0.5, (1.0,1.0)->0.0,
  (2.0,1.0)->-1.0); `climatology_forecast(window_totals)` = mean (exact).
- **A — Climatology is exact.** On a synthetic district, the climatology benchmark equals the
  independently-computed historical mean of the target 3-month window.
- **B — Honesty fallback.** Construct/patch a case where the model does NOT beat climatology
  (skill_score <= 0): assert `method == "climatology_fallback"` AND the issued `forecast_3mo_mm` equals
  the climatology benchmark. And a case with skill_score > 0 issues `method == "sarima"`.
- **C — Tercile consistency.** The issued `category` equals `tercile_category(forecast_3mo_mm,
  historical window totals)`.
- **D — Min-history skip.** A district with < MIN_YEARS history is skipped with
  `skip_reason == "insufficient_history"`; a long-enough one is present.
- **E — No look-ahead.** compute_outlook(M) with months after M absent from the archive gives the same
  output as with them present.
- **F — Experimental tag + params.** Every district record and the wrapper carry `experimental: true`;
  the wrapper params echo order/seasonal_order/backtest_years/min_years; every record carries both
  benchmarks and a finite skill_score.
- **G — Determinism.** Two runs give byte-identical output (minus generated_utc).
- **Range:** forecast_3mo_mm >= 0 and finite; category in {below, near, above}.

## 7. Definition of Done

1. scripts/compute_outlook.py + tests/test_outlook.py + statsmodels pinned, one PR on feature/prediction.
2. All tests green locally.
3. Senior review + a real-data smoke run on Ghana (a few districts) with the skill scores inspected by
   hand — explicitly checking how often the model actually beats climatology (be honest if it rarely does).
4. Output labelled **experimental** everywhere. Not a public forecast.

## 8. Open decisions

- **Q1 — fixed vs searched SARIMA order.** v1 uses a fixed (1,0,0)(1,0,0,12) for speed/determinism over
  260 districts. Accept, or allow a small per-district search later?
- **Q2 — what if skill is near-universally negative?** Then the honest headline is "climatology is the
  outlook; the model adds little at monthly resolution" — which is a legitimate, publishable finding, not
  a failure. Confirm we present it that way.
