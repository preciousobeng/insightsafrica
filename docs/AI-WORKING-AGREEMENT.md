# InsightsAfrica — AI Pair Working Agreement

This document governs how the two AI collaborators work on this repo. Read it in full
before making any change. It is the source of truth; if a task instruction conflicts
with this agreement, the agreement wins and you stop and ask.

## Roles
- **DeepSeek / Copilot — Junior developer.** Implements tasks across the whole codebase.
  Works only on branches. Opens a pull request for every task. Never merges. Never deploys.
- **Claude — Senior engineer.** Reviews every PR, requests changes or approves, merges
  approved PRs to main, and runs the production deploy. Owns the quality and safety gate.
- **Kweku — Owner.** Sets direction, approves high-risk changes, can override either AI.

## The loop (every task follows this)
1. Junior: pull latest main, create a branch, implement ONE logical task.
2. Junior: self-verify (regenerate + verify + headless render — see Verification).
3. Junior: open a PR with the required description (see PR template). Stop there.
4. Senior: review the PR diff against the checklist. Request changes or approve.
5. Junior: address review comments on the same branch, push, re-request review.
6. Senior: merge to main when approved, then deploy and confirm live.

## Golden rules (non-negotiable)
1. **Never commit to main directly. Never force-push anything. Never rewrite history.**
2. **Junior never deploys** to the server (ubuntu@100.123.194.92). Deploy is senior-only.
3. **One task = one branch = one PR.** Keep PRs small and single-purpose. No drive-by edits.
4. **Always pull main and rebase/branch fresh before starting.** This repo has had parallel-AI
   collisions before — stale branches are the cause. Do not let a branch live for days.
5. **Pages are generated.** Never hand-edit a file under frontend/<country>/...; edit the
   template in frontend/_templates/ and regenerate. A PR that hand-edits generated output
   will be rejected.
6. **No secrets in code or commits** — no API keys, tokens, Supabase keys, .env values.
   If you find a hardcoded secret, flag it in the PR; do not "fix" it by moving it elsewhere.

## Scope — Junior may work on any file EXCEPT deploy, but these tiers set review depth
- **Standard review** (most work): frontend templates, config, docs, frontend JS.
- **Deep review — call it out explicitly in the PR description so the senior scrutinises it:**
  - api/main.py and any API routing/auth/rate-limit/CORS change
  - data pipeline scripts (fetch_*, process_*, compute_*, precompute_*, run_full_pipeline.sh)
  - countries.yml structural changes (level keys, counts, api paths, tile prefixes)
  - anything touching Supabase, login, or download-event handling
- **Stop and get Kweku's sign-off BEFORE opening the PR** (note it at the top of the PR):
  - secret/key rotation or auth-model changes
  - destructive data operations (deleting/overwriting processed_* or archive/* data, DB schema)
  - dependency major-version bumps that change a pinned runtime lib used by api/main.py
  - anything you cannot fully verify locally

## PR requirements (Definition of Ready for review)
Open the PR only when ALL of these are true, and put them in the PR description:
1. **What & why** — one paragraph: the task and the user-facing effect.
2. **Files changed** — list, and flag any Deep-review-tier files.
3. **Generated output** — if templates changed, confirm you ran the generator and committed the
   regenerated pages in the same PR. Paste the `--verify` summary line (Total/identical/differ).
4. **Verification** — paste your headless-render result: which page(s), JS error count (must be 0),
   and a sanity count (e.g. polygons rendered, layers loaded).
5. **Scope statement** — confirm the PR does exactly one task and touches nothing outside it.
6. **Risks / follow-ups** — anything you were unsure about or deliberately left out.

A PR missing any of these gets sent back without a code review.

## Verification toolkit (junior must run before every PR)
- Build deps live in the venv: ./venv/bin/python
- Verify (writes nothing, non-zero exit on any diff):
  PYTHONIOENCODING=utf-8:replace ./venv/bin/python scripts/build_pages.py --type TYPE --verify
- Write:
  PYTHONIOENCODING=utf-8:replace ./venv/bin/python scripts/build_pages.py --type TYPE
- Read every diff. After a deliberate change diffs SHOULD appear; confirm each line is intended.
- Runtime render: a page can be valid HTML yet throw on load. System Chrome is /usr/bin/google-chrome;
  install puppeteer-core in /tmp and drive it. Capture pageerror + console errors and count rendered
  map polygons. Static grep and node --check do NOT catch this codebase's runtime errors — headless render is mandatory for any page-behaviour change.

## Senior review checklist (what Claude checks)
- Does the change do exactly what the PR says, and only that?
- Generated pages match the template change (re-run --verify independently); no hand-edited output.
- No secrets, no auth/security regressions, no destructive ops sneaking in.
- Per-country quirks respected (empty p.name countries, IC level inversion, Cape Verde single-level).
- Runtime: re-render the affected page headless; zero JS errors.
- Commit hygiene: small, descriptive messages; branch is current with main.
- If Deep-review or sign-off tier: extra scrutiny and, where required, confirm Kweku approved.

## Merge & deploy (senior only)
- Merge only an approved, green PR that is current with main.
- Pre-deploy gate: re-run the generator + --verify on main, headless-render changed pages.
- Deploy: push main, then on the server git pull (fast-forward only). Frontend is FastAPI StaticFiles,
  so HTML changes go live with no restart; api/main.py changes require sudo systemctl restart insightsafrica.
- Announce the deploy and the live-verification result. Note the previous commit for rollback.
- Rollback: revert the merge commit, redeploy. Never fix-forward under pressure on prod.

## Collision avoidance (this repo's recurring failure mode)
- Branch from fresh main; never from another in-flight branch.
- Don't open two PRs that touch the same template/file simultaneously — sequence them.
- If a PR sits more than a day, rebase it on main before review.
- If the server ever shows uncommitted local edits, do NOT stash/discard blindly — they may be
  manual hotfixes; diff them against origin/main first (this has happened, the edits were redundant).

## Escalation
- Blocked, ambiguous, or a task needs a product/data decision: stop, write the question in the PR
  (or a docs/ note) and tag it for Kweku. Do not guess on irreversible or data-shape decisions.
- The Ivory Coast flood level-inversion is the current example: it needs real-data verification and
  is owned by Kweku/senior — do not "fix" it from a junior PR.

## Communication & context
- Durable context goes in docs/ (like this file and the session/handoff notes), not buried in commits.
- Commit messages: imperative, scoped (e.g. "feat(#10): ..."), explain the why when non-obvious.
- No AI co-author trailers in commit messages.
