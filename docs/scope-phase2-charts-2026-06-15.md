# Phase 2 chart UX — scope for crop/heat/mine

Question: can the FloodWatch year-on-year chart UX (per-year palette + golden-angle fallback
so no year is grey, index-mode tooltip so hovering a column shows all years, taller chart) be
applied to the crop / heat / mine module charts? Assessed by reading each module's chart code.

## Verdict

| Module | Chart (`build*Chart`) | Year-grouped? | Grey-year bug? | Flood UX applies? |
|--------|----------------------|---------------|----------------|-------------------|
| **crop** | `buildNdviChart` — line per year over DOY x-axis | YES | YES (worse) | **YES — do it** |
| heat | `buildHeatChart` — LST bars by city + UHI line | NO | NO | No |
| mine | `buildChangeChart` — NDVI/NDWI change by sign | NO | NO | No |

### crop — APPLIES (the one actionable item)
`buildNdviChart` groups layers by `l.year`, one dataset (line) per year, x-axis = the 23 MODIS
DOYs (`MODIS_DOYS` / `MODIS_LABELS`). This is the SAME shape as flood (year-series over a shared
time axis), just `type: 'line'` with DOY labels instead of `type: 'bar'` with months. It carries
the identical grey-fallback bug, in fact worse: `NDVI_YEAR_COLOURS` defines only 2024 and 2025, so
every other year (2020-2023, 2026) hits the grey fallback (`|| { line: 'rgba(148,163,184,0.85)' ...`).
SA/CV crop with 2020+ data show mostly grey lines.

### heat — DOES NOT APPLY
`buildHeatChart` builds ONE bar dataset (Mean LST) coloured per CITY via `CITY_COLOURS[city_id]`,
plus ONE line dataset (UHI intensity). x-axis is chronological scenes ("Joh May '24"). There is no
per-year dataset, so there is no grey-year problem and no per-year palette concept to port. An
index-mode tooltip would only ever surface 2 series (LST + UHI) and each x is a distinct scene, so
the benefit is marginal. Leave the heat chart as-is.
(Tiny UNRELATED note, not Phase 2: `CITY_COLOURS` has a `|| CITY_COLOURS.lagos` fallback, so an
unmapped city would silently share Lagos's colour. Only worth fixing if a new city is ever added.)

### mine — DOES NOT APPLY
`buildChangeChart` is two series (NDVI change, NDWI change) as horizontal bars across SITES, coloured
by the SIGN of the value (green/red, blue/amber). No year dimension, no grey-year problem, already
360px sidebar + 200px chart. Leave as-is.

## Actionable work: crop NDVI chart (one PR, delegatable)
Port the flood chart UX to `buildNdviChart` in crop.html + the 5 crop variants
(crop_ghana, crop_ivorycoast, crop_senegal, crop_southafrica, crop_capeverde). Adaptations for the
LINE chart:

1. **Per-year palette + fallback** — replace `NDVI_YEAR_COLOURS` (2024/25 only) with a curated
   palette covering 2018-2027 AND a `ndviYearColour(year)` helper whose fallback is a golden-angle
   hue (`hue = year * 137.508 % 360`). Because this is a line chart the colour object is
   `{ line: 'hsl(h,65%,55%)', fill: 'hsla(h,65%,55%,0.12)' }` (line + translucent fill), not
   bar/border. Curate the named years as line/fill pairs in the same hues as flood for consistency
   (2020 red, 2021 pink, 2022 lime, 2023 orange, 2024 green-ish/keep, 2025 teal/keep, 2026 purple…).
   Replace the grey `||` fallback at the dataset map with `ndviYearColour(year)`.

2. **Index-mode tooltip** — add `interaction: { mode: 'index', intersect: false }` and a
   `filter: (item) => item.raw != null`, and make the tooltip label one compact line per year
   (`year + ': ' + ndvi.toFixed(2)`) so hovering a DOY shows every year's NDVI at that point.
   Mirror the flood pattern; do NOT re-derive — copy the working flood approach.

3. **Taller chart** — crop chart container is 140px; bump to 200px to match flood/mine.

4. Sidebar width is already 360px (done in PR #6).

### Verification bar (same as flood)
- `--verify --type crop`: 6/6 identical (generated == committed) after regen.
- Diff per file is only the colour map / fallback / tooltip / height lines; nothing else.
- Headless render (HTTP origin) a crop page with pre-2024 data (e.g. southafrica/crop or
  capeverde/crop): 0 uncaught JS errors, lines are coloured (not grey), tooltip shows all years.

## Recommendation
Do crop as a single delegated PR (proven flood pattern, adapted to line/DOY — mechanical with care).
Skip heat and mine: their charts are fundamentally different and have neither the grey-year problem
nor a per-year structure to colour. This closes Phase 2 with one focused PR rather than three.
