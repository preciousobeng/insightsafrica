# InsightsAfrica — AI Pair Working Agreement

Version 1.1 (2026-06-14). v1.1 adds: senior-deputy fallback, "one logical task" defined
by intent, committed headless-verify harness, ramp-up coaching clause, and a docs/ notes
convention — all from the junior's review of v1.0.

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
3. **One task = one branch = one PR.** "One task" is scoped by INTENT, not file count. A single
   coherent change that spans many files is one PR — e.g. propagating the flicker-free swap to every
   template is ONE task even though it edits a dozen files, because it is one reviewable intent applied
   uniformly. What is banned is bundling UNRELATED changes into one PR (a bug fix + a refactor + a new
   feature = three PRs). If a PR is large but mechanical and uniform, say so in the description so the
   reviewer knows to expect breadth. When unsure whether two changes belong together, split them.
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

A PR missing any of these gets sent back without a code review — EXCEPT during ramp-up (see below).

### Ramp-up clause (first ~5 PRs)
While both AIs find the rhythm, the senior coaches rather than hard-bounces: for minor checklist
omissions on otherwise-good PRs, the senior fixes-forward or annotates and explains what was missing,
rather than rejecting outright. This grace does NOT apply to the Golden rules or to any
Deep-review / sign-off-tier change — those are strict from PR #1. After ramp-up, the full PR gate applies.

## Verification toolkit (junior must run before every PR)
- Build deps live in the venv: ./venv/bin/python
- Verify (writes nothing, non-zero exit on any diff):
  PYTHONIOENCODING=utf-8:replace ./venv/bin/python scripts/build_pages.py --type TYPE --verify
- Write:
  PYTHONIOENCODING=utf-8:replace ./venv/bin/python scripts/build_pages.py --type TYPE
- Read every diff. After a deliberate change diffs SHOULD appear; confirm each line is intended.
- Runtime render: a page can be valid HTML yet throw on load. Static grep and node --check do NOT
  catch this codebase's runtime errors — a headless render is mandatory for any page-behaviour change.
  Use the committed harness so everyone verifies the same way:
    node scripts/verify_page.mjs <url-or-file>
  Setup (one-time, on whatever machine the junior runs on): install Node, then in the repo run
  `npm i puppeteer-core` (kept out of prod — it is a dev/verify tool only). The harness finds Chrome
  via the CHROME_PATH env var, falling back to /usr/bin/google-chrome. It exits non-zero if there are
  any console/page errors and prints the rendered map-polygon count. If the harness is not yet present
  or you cannot run it, STOP and say so in the PR — do not claim a render you did not perform.

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

### Senior availability / deputy fallback
The junior never deploys, so merge+deploy depends on the senior. This does NOT stall coding: open PRs
QUEUE safely and the junior keeps working on independent branches in the meantime — never blocks on a
merge. If the senior is unavailable and a merge/deploy is genuinely time-sensitive, Kweku is the deputy:
he may merge an approved PR and deploy, or explicitly authorise it. The junior must never self-merge to
unblock, even if PRs pile up — a queue is fine, an unreviewed merge is not.

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
- Durable context goes in docs/, not buried in commits.
- Commit messages: imperative, scoped (e.g. "feat(#10): ..."), explain the why when non-obvious.
- No AI co-author trailers in commit messages.

### docs/ notes convention (so the two AIs never overwrite each other)
Both AIs write notes; without a convention they collide. The rule:
- **Per-author, per-day session notes:** docs/notes/YYYY-MM-DD-<author>.md where <author> is `claude`
  or `deepseek`. You may only create or edit YOUR OWN file. Never edit another author's note — if you
  need to correct or respond to it, write it in your own file and reference theirs.
- **One shared rolling index: docs/STATUS.md.** This is the single current-state-of-the-project file.
  Either AI may update it, but only by APPENDING a dated, attributed entry at the top
  (`## YYYY-MM-DD <author> — <summary>`). Never delete or rewrite another author's STATUS entry; if
  something is now wrong, add a new entry that supersedes it and say so.
- **Task handoffs:** docs/handoff-<topic>-YYYY-MM-DD.md, owned by whoever wrote it.
- This working agreement (docs/AI-WORKING-AGREEMENT.md) is changed only via a PR that the senior
  reviews, or directly by Kweku. Neither AI edits it unilaterally mid-task.
