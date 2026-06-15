# Handoff for DeepSeek — Uniform 360px sidebar across crop/heat/mine

Follow the AI working agreement. Branch, one PR, no deploy. This PR is LAYOUT ONLY (CSS width).
Do NOT touch any chart logic — that is a separate, not-yet-scoped ticket (see Phase 2 note).

## Why
FloodWatch sidebars were widened 320 -> 360px (commits f7fffe3 + c2781e0) to fit the year-on-year
chart. Now the other modules look narrower than flood when you navigate between them within a country.
This PR makes crop/heat/mine match flood at 360px. Hub is excluded (different layout — see below).

## Scope — set the module sidebar width to 360px in these templates
The sidebar rule is `.sidebar { ... width: <N>px; ... }`. Change that width value to 360px.
NOTE the source value is NOT uniform — mine has two different starting widths. Set them ALL to 360:

- crop (6 files, all currently 320px): crop.html, crop_ghana.html, crop_ivorycoast.html,
  crop_senegal.html, crop_southafrica.html, crop_capeverde.html
- heat (6 files, all currently 320px): heat.html, heat_ghana.html, heat_ivorycoast.html,
  heat_senegal.html, heat_southafrica.html, heat_capeverde.html
- mine (6 files, MIXED source): mine.html / mine_ghana.html / mine_southafrica.html are 320px;
  mine_ivorycoast.html / mine_senegal.html / mine_capeverde.html are 280px. All -> 360px.

Only change the `.sidebar` width. Do not touch the mobile media-query overrides (the `@media`
block that restacks the sidebar on small screens) — those are intentionally different.

## EXCLUDE — do not touch
- hub.html and all hub_*.html — hub is a centered KPI-card layout (max-width ~560px), it has no
  module sidebar, so 360px does not apply. Leave hub entirely alone.
- All chart / tooltip / colour logic in every file. Layout width only.

## Steps
1. Edit the 18 templates above: `.sidebar` width -> 360px.
2. Regenerate: for each type run
   PYTHONIOENCODING=utf-8:replace ./venv/bin/python scripts/build_pages.py --type crop
   ...and the same for heat and mine. Commit templates + regenerated pages together.
3. Verify with --verify for crop/heat/mine: each should be 6/6 identical (generated == committed).
   The per-file diff vs main should be ONLY the width line (one line per template, plus the same
   one line in each regenerated page). If any file shows more than the width change, STOP and flag it.
4. Headless render one page per type against an HTTP origin (NOT file://): 0 uncaught JS errors,
   and eyeball that the wider sidebar doesn't clip or break the existing content (mine's 280->360
   jump is the biggest — confirm the site list / cards still lay out fine).

## Verification to put in the PR
- List of files changed (should be 18 templates + their regenerated pages).
- --verify output for crop/heat/mine (6/6 identical each).
- Confirmation that hub was NOT touched.
- Headless render result (0 JS errors) for at least crop, heat, mine — including a mine variant
  that went 280->360.

## Phase 2 — NOT in this PR (separate ticket, needs assessment first)
Do not attempt these now. Bringing the flood chart UX (per-year palette + index-mode tooltip) to
the other modules is NOT mechanical, because each module's chart differs:
- crop: NDVI chart uses day-of-year (DOY) on the x-axis, not 12 months — the month-column index
  tooltip and MONTH_SHORT labels do not map directly.
- heat: city/scene chart has a different structure.
- mine: change chart is NDVI/NDWI based, not rainfall-by-month.
- hub: KPI cards, no chart at all.
Each needs its own assessment of whether the year-colour + index-tooltip pattern even applies. Flag
this as a follow-up; the senior will scope it separately.
