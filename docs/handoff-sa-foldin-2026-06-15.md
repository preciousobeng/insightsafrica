# Handoff for DeepSeek — Fold South Africa flood into the shared template

Follow the AI working agreement (docs/AI-WORKING-AGREEMENT.md). Branch, one PR, no deploy.
Senior (Claude) has already de-risked the data side — read the "Why this is safe" note below.

## Goal
Delete frontend/_templates/flood_southafrica.html and have South Africa's flood page
generate correctly from the shared frontend/_templates/flood.html, driven by a
coarse_empty_name flag. End state: one less variant, SA served by the shared template.

## Why this is safe (senior pre-check, already done)
SA province boundaries have an EMPTY p.name; the name lives in p.region. The live anomaly
data confirms the key format:
- provinces:  '|EasternCape', '|Gauteng', '|KwaZulu-Natal'   (empty name + '|' + region)
- districts:  'AlfredNzo|EasternCape'                         (name + '|' + region)
The coarse_empty_name key logic below produces exactly these, so it matches prod data.

## Reference
The exact pattern exists in DROPPED commit 74861fc — view it:
    git show 74861fc -- frontend/_templates/flood.html
DO NOT cherry-pick it: the shared flood.html has changed since (it now has the flicker-free
crossfade). RE-APPLY the coarse_empty_name logic by hand onto the CURRENT shared flood.html.

## Steps

1. countries.yml: under southafrica (top level, same indent as slug/name), add:
       coarse_empty_name: true
   No other country gets this flag.

2. Shared flood.html — make the coarse-level name/key logic conditional. Near the top of the
   <script>, add a Jinja set (after the `let layers = []` line):
       {% set coarse_name = 'p.region' if c.get('coarse_empty_name') else 'p.name' %}

   Then change these spots (use the 74861fc reference for exact text):
   a) buildTooltipContent key (the `const key = (level === '{{ c.levels.fine.key }}' && p.region) ...`):
      wrap in {% if c.get('coarse_empty_name') %} branch that emits
        const key = p.region ? p.name + '|' + p.region : p.name;
      {% else %} the existing multi-line version {% endif %}
   b) the second `const key = ...` (in the anomaly apply/summary function, single-line): same conditional.
   c) the three coarse-level display-name spots that currently read `p.name + ' {{ c.flood.coarse_noun }}'`:
      change `p.name` to `{{ coarse_name }}` in all three (anomaly no-data return, anomaly return, rainfall header).

   For every NON-coarse_empty_name country (nigeria/senegal/etc.) the output MUST be byte-identical
   to now — coarse_name defaults to p.name and the {% else %} branch is the existing code. Confirm
   this with --verify (see below): flood for nigeria/senegal must stay identical.

3. Delete frontend/_templates/flood_southafrica.html.

4. Regenerate: PYTHONIOENCODING=utf-8:replace ./venv/bin/python scripts/build_pages.py --type flood

5. Verify:
   - --verify: nigeria + senegal MUST be identical (you didn't change their output).
   - SA will now DIFFER from the old committed page (it was generated from the variant). That's expected.
     Produce the diff of the new SA page vs the OLD committed one and put it IN THE PR DESCRIPTION.
     Every diff must be one of these EXPECTED/intended changes — flag anything else for senior review:
       * province tooltips "X Region" -> "X Province" (region_noun token, an intended fix)
       * "Load states on startup" -> "Load provinces on startup" (default_visible token)
       * a `label` variable being inlined (functionally identical)
     RED FLAGS that mean STOP: any province name rendering blank/empty; any key NOT of the form
     '|Region' at province level; loss of the crossfade; loss of anomaly mode.
   - Headless render against an HTTP origin (NOT file://). The senior will do the live anomaly-mode
     check, but you must confirm 0 uncaught JS errors locally. If you cannot serve it over HTTP, say so.

## What the senior will verify before merge (so you know the bar)
- Generated SA keys match the live data ('|Region' provinces, 'name|region' districts).
- Live headless render of SA flood in ANOMALY mode: provinces fill by category, tooltips show
  province names (not blank), 0 JS errors.
- nigeria/senegal unchanged.

## Scope
ONLY the SA fold-in: countries.yml flag, shared flood.html conditionals, delete the SA variant,
regenerated flood pages. Do NOT touch Ivory Coast (level-inversion is senior-owned). Do NOT touch
other page types.
