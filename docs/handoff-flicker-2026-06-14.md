# InsightsAfrica — Handoff for DeepSeek / Copilot (2026-06-14)

You are picking up work on the InsightsAfrica repo. Read this whole brief before
touching anything. The repo is shared with other agents and a human — follow the
guardrails or you will create a collision.

## Repo & environment
- Local: ~/projects/insightsafrica (Kubuntu). Server (prod): ubuntu@100.123.194.92 (Tailscale), at ~/insightsafrica.
- Current origin/main HEAD: 16afd71.
- Python venv with build deps (jinja2, pyyaml): ./venv/bin/python
- Pages are GENERATED, not hand-edited: shared templates in frontend/_templates/<type>.html,
  per-country config in frontend/_config/countries.yml, generator scripts/build_pages.py.
- Per-country variant files take precedence: frontend/_templates/<type>_<slug>.html beats the shared <type>.html.

## Guardrails (do not skip)
1. Work on a branch, not main. Name it feat/flicker-propagation. Open a normal merge; never rewrite main.
2. Never hard-reset or force-push — there is parallel work and a human on this repo.
3. Do not deploy. Leave deployment to Kweku. Commit + push your branch only.
4. Do not touch api/main.py, the data pipeline scripts (fetch_*, process_*, compute_*), or the
   weather/coords/counts in countries.yml unless a task explicitly says so.
5. After any template change, regenerate AND verify. Commit the template and the regenerated pages together.

## How to regenerate & verify
- Verify only (writes nothing, exits non-zero on any diff):
  PYTHONIOENCODING=utf-8:replace ./venv/bin/python scripts/build_pages.py --type TYPE --verify
- Write:
  PYTHONIOENCODING=utf-8:replace ./venv/bin/python scripts/build_pages.py --type TYPE
- After a deliberate change the diff SHOULD appear — read every diff and confirm each changed line is intended.
- Runtime check: a page can be valid HTML but throw at load. Render headless — system Chrome is at
  /usr/bin/google-chrome; install puppeteer-core in /tmp and drive it. Capture pageerror + console
  errors and count rendered map polygons. Static grep and node --check will NOT catch the runtime
  errors this codebase is prone to.

---

## TASK 1 (primary) — Propagate the flicker-free map swap everywhere

Background: the rainfall / animation map blinked white between frames because the old image overlay
was removed before the new one finished loading. The fix is already implemented in the shared
frontend/_templates/flood.html — read its displayLayer function and its loadLayers function and copy
that exact approach:
- displayLayer: build the next L.imageOverlay at opacity 0, add it, and only remove the previous
  overlay once the new image element reports loaded (immediately if already complete, otherwise on its
  load event). This is the flicker-free crossfade.
- loadLayers: right after the layers array is fetched and confirmed non-empty, pre-warm the browser
  cache by creating an Image for each layer png so the crossfade has tiles ready.

Apply the SAME two changes to every template that renders a Leaflet image overlay and still uses the
old remove-then-add swap. Inspect each of these for a displayLayer / overlay function first:
- Shared templates: crop.html, heat.html, mine.html. Skip human.html, profile.html, hub.html unless a
  grep shows they actually mount a map overlay.
- Flood variants that still flicker: flood_ghana.html, flood_ivorycoast.html, flood_capeverde.html.
  Do NOT change flood_southafrica.html — it is the source pattern and is already correct.
- Any crop/heat/mine per-country variant file that has its own displayLayer.

Use whatever tile-prefix the file already uses: shared templates use the c.tile_prefix token; a
variant may hardcode something like /za-tiles/ — keep that.

Verify per type: run --verify and confirm the ONLY diffs are the displayLayer + preload lines, then
write. Headless-render one page per type, confirm zero JS errors and that the month-stepper still
swaps images.

---

## TASK 2 (optional) — Fold South Africa flood into the shared template

Goal: delete flood_southafrica.html and have SA generate correctly from the shared flood.html.
The solution already exists in dropped local commit 74861fc — read it from the git reflog (show that
commit's version of frontend/_templates/flood.html). It adds a coarse_empty_name flag: SA provinces
have an empty p.name and the name lives in p.region, so the key / header / tooltip logic must use
p.region at the coarse level. Port that approach, set coarse_empty_name: true under southafrica in
countries.yml, regenerate, and headless-verify SA flood renders named provinces plus a working anomaly
mode BEFORE deleting the variant.

---

## TASK 3 — DO NOT DO. Leave Ivory Coast level-inversion alone.

countries.yml says IC is districts=coarse(14) / regions=fine(31), which is geographically correct, but
the committed/variant IC page treats districts as the FINE level. Resolving this needs verification
against the actual anomaly-data and boundary key structure on the server — blindly flipping it WILL
break the live IC page. Kweku is handling this in a dedicated session. The only IC edit allowed: fix
the latent JS bug where a single-quoted string interpolating the country name breaks on the apostrophe
in the French spelling of Ivory Coast — switch that one string to double quotes. Nothing else.

---

## When done
Commit on your branch, push, and tell Kweku the branch name plus a one-line summary of which templates
changed and your headless-verify results. Do not merge or deploy.
