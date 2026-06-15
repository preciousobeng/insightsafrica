# Handoff for DeepSeek — Crop NDVI chart: per-year colours + index tooltip

Follow the AI working agreement. Branch, one PR, no deploy. This ports the proven FloodWatch chart
UX to crop's NDVI chart. Crop is the ONLY module this applies to (heat/mine charts are not
year-grouped — see docs/scope-phase2-charts-2026-06-15.md).

REFERENCE IMPLEMENTATION: the flood chart in frontend/_templates/flood.html (commits f7fffe3 +
c2781e0). Open it alongside crop.html and mirror its YEAR_COLOURS block, yearColour helper,
interaction setting, tooltip filter, and compact label. Do not re-derive — copy the working pattern
and adapt the few differences below.

## Files to change (6 — all share the identical pattern)
crop.html, crop_ghana.html, crop_ivorycoast.html, crop_senegal.html, crop_southafrica.html,
crop_capeverde.html. Each has the same NDVI_YEAR_COLOURS (2024/2025 only), same grey fallback in
buildNdviChart, same 140px chart container. Apply the same four changes to all six.

## Background
buildNdviChart groups layers by l.year — one LINE dataset per year — over a 23-point DOY x-axis
(MODIS_DOYS / MODIS_LABELS). Same shape as flood (year-series over a time axis), but a LINE chart
over DOY rather than a BAR chart over 12 months. Bug today: NDVI_YEAR_COLOURS defines only 2024 and
2025, so every other year falls back to grey. Crop with pre-2024 data (SA, CV) shows mostly grey lines.

## THE KEY DIFFERENCE vs the flood port (read first)
Flood is a BAR chart, so its colours are bar/border pairs. Crop is a LINE chart, so its colours are
line/fill pairs — the dataset already reads borderColor from col.line and backgroundColor from
col.fill. So when you copy flood's palette + helper, every colour object must be line/fill, NOT
bar/border. Everything else (index tooltip, golden-angle fallback, taller chart) is identical in idea.

## Change 1 — palette + fallback helper
Replace the 2-year NDVI_YEAR_COLOURS map with a 10-year map covering 2018 through 2027, using the
SAME hues as flood.html's YEAR_COLOURS for cross-module consistency, EXCEPT keep crop's current 2024
(green) and 2025 (teal). Each entry is a line/fill pair: line is the solid hue at 0.9 alpha, fill is
the same hue at 0.12 alpha.

Add a helper ndviYearColour(year) that mirrors flood's yearColour: if the year is in the map return
it, otherwise build a golden-angle hue — hue = year multiplied by 137.508, taken mod 360 — and return
a line/fill pair where line is an hsl at that hue (65% sat, 60% light) and fill is the same hsl as an
hsla at 0.12 alpha. This guarantees no year is ever grey.

Then in the dataset map, swap the grey fallback line. Currently it reads the colour as
NDVI_YEAR_COLOURS[year] OR a grey line/fill literal. Change it to call ndviYearColour(year) instead.
Leave borderColor: col.line and backgroundColor: col.fill unchanged.

## Change 2 — index-mode tooltip (hover a DOY shows all years)
Copy flood.html's two tooltip changes:
1. In the chart options, immediately after the maintainAspectRatio line, add the index interaction
   setting (mode index, intersect false) — identical to flood.
2. In the tooltip config, add the same null-dropping filter flood uses (keep only items whose raw
   value is non-null), and simplify the label callback to ONE compact line per year so the multi-year
   tooltip stays readable. The crop value is the year's mean NDVI to 2 decimals, e.g. the label
   returns the year, a colon, and mean_ndvi to two decimal places. DROP the current Healthy% and
   Severe-stress% extra lines — they don't fit a multi-year tooltip.
KEEP crop's existing title callback (it already returns MODIS_LABELS for the hovered index, which is
the correct DOY/month label for this x-axis — do not change it).

## Change 3 — taller chart
The crop chart container is 140px high; change it to 200px (matches flood/mine). It is the inline
style on the div that wraps the ndvi-chart canvas.

## Change 4 — sidebar width
Already 360px (PR #6). No action.

## Why index mode is fine on the DOY axis
The index tooltip groups by x-index, and all year-lines share the same 23 DOY indices, so hovering a
DOY column surfaces every year's NDVI at that DOY. The only DOY-specific element is the tooltip title
label, already handled by the existing title callback — so no x-axis change is needed.

## Verification (put results in the PR)
- Run the generator verify for crop: it must report 6/6 identical after you regenerate.
- The per-file diff vs main must be ONLY: the colour map + helper, the grey-fallback line, the
  interaction line, the tooltip filter + label, and the 140 to 200 height. If anything else changed,
  STOP and flag it.
- Headless render (HTTP origin, NOT file://) a crop page that has pre-2024 data — southafrica/crop or
  capeverde/crop: zero uncaught JS errors; the NDVI lines are coloured, not grey; hovering a DOY shows
  all years at once.

## Scope
Crop only. Do NOT touch heat or mine charts (different structure, not year-grouped). Do NOT change
anything outside the four changes above.
