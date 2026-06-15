# Handoff for DeepSeek — Fold Ivory Coast flood into the shared template

Follow the AI working agreement. Branch, one PR, no deploy. Senior (Claude) has done the
investigation + design; your job is the mechanical implementation + diff-tuning. This one is
subtle — read the background so you understand WHY, then tune by diffing against the variant.

## Background (why IC is weird — do not "fix" the data)
IC live data, confirmed:
- boundaries: districts = 14 polygons with EMPTY p.name (name in p.region); regions = 33 named polygons
- anomaly data: districts = 14 entries keyed '|Abidjan' (MATCHES district boundaries, works);
  regions = only 14 entries keyed by DISTRICT names (BROKEN — no real 33-region anomaly exists)
So the working anomaly level is DISTRICTS. The page must drive its choropleth/summary off districts.
We are NOT fixing the region data pipeline now (Kweku's call) — fold in at the district level.

## The approach: CONFIG INVERSION (no template logic change except the apostrophe fix)
The shared template puts compound keys + the anomaly summary on c.levels.fine.key, and the bold
border on c.levels.coarse.key. IC's working level (districts) must therefore become fine, and
regions becomes coarse. This maps the template's existing logic onto the levels that work.

### Step 1 — rewrite the ivorycoast levels in countries.yml to INVERTED:
    levels:
      coarse: { key: regions,   label: Regions,   count: 33 }
      fine:   { key: districts, label: Districts, count: 14 }
    default_visible: districts        # districts (now fine) is the working/default level
Remove these orphan tokens from the ivorycoast block — the current shared template does NOT
consume them and they will only confuse: compound_key_level, bold_border_level, fine_empty_name.
Add a comment documenting the inversion + the reason:
    # INVERTED on purpose: districts(14) are geographically coarse but carry the only working
    # anomaly data, so they are mapped to fine.key; region(33) anomaly data is broken (14 wrong
    # entries) so regions is coarse/boundary-only. See docs/handoff-ic-foldin-2026-06-15.md.

### Step 2 — tune the flood.* nouns/buttons by DIFFING (this is the real work)
The current committed frontend/ivorycoast/flood/index.html is generated from the VARIANT and is
the WORKING reference. Generate IC from the shared template and diff against it:
    PYTHONIOENCODING=utf-8:replace ./venv/bin/python scripts/build_pages.py --type flood --verify
IC will show as differ — read the diff. Adjust the ivorycoast flood.* tokens (coarse_noun,
region_noun, summary_noun, fine_mouseover_prop, buttons order/labels, about text, downloads) until
the ONLY remaining differences vs the committed variant page are:
  (a) the apostrophe-quoting fix from Step 3 (one line), and
  (b) clearly-intended improvements you can name in the PR.
RED FLAGS — stop and flag: any district name rendering blank; district choropleth not coloring;
keys at the district level not in '|Region' form; anomaly summary using the broken region data;
loss of crossfade. fine_mouseover_prop for districts should keep keys as '|region' — verify the
chart hover still works.

### Step 3 — apostrophe fix in the SHARED flood.html (required for IC)
Find the line:  '{{ c.display_name }} national mean — hover a boundary'
It is single-quoted; "Côte d'Ivoire" has an apostrophe that breaks the JS string. Change the outer
quotes to DOUBLE quotes (no display_name contains a double quote, so this is safe):
    "{{ c.display_name }} national mean — hover a boundary"
This ripples a 1-line change to ALL flood pages. After regenerating, confirm via --verify that the
ONLY change on nigeria/senegal/southafrica/ghana/capeverde is this single line.

### Step 4 — delete the variant + regenerate
Delete frontend/_templates/flood_ivorycoast.html. Regenerate all flood:
    PYTHONIOENCODING=utf-8:replace ./venv/bin/python scripts/build_pages.py --type flood
Commit templates + regenerated pages together.

## Verification (put results in the PR)
- --verify: nigeria/senegal/southafrica/ghana/capeverde change ONLY on the apostrophe line; IC differs
  intentionally (you list every diff and justify it).
- Generated IC district keys are '|Region' form (e.g. '|Abidjan') — matches live anomaly data.
- Headless render against an HTTP origin (NOT file://): 0 uncaught JS errors.
- The senior will do the live anomaly-mode check (district choropleth colors 14 districts, names show).

## Scope
Only the IC fold-in + the apostrophe fix. Do NOT touch the region data pipeline. Do NOT change other
countries' behaviour beyond the one apostrophe line.
