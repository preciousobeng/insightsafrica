# Start Here — Junior Developer Onboarding

You are the **junior developer** on InsightsAfrica, working with a senior engineer (Claude)
who reviews and deploys, and the owner (Kweku) who sets direction. You are starting with a
fresh context — this note tells you exactly what to read, what to ignore, and how to run things.
Read this first, then the three items in the reading list. **Do not read the rest of docs/** —
most of it is history from an earlier frontend clean-up and is irrelevant to your task; it will
only confuse a fresh context.

## What the project is (one paragraph)

InsightsAfrica is an open-access satellite-intelligence platform (live at insightsafrica.org)
that maps environmental risk — flood, mining, crop, heat — across African countries. Stack:
a FastAPI backend (api/main.py) serving a static HTML frontend, fed by a set of Python
data-pipeline scripts in scripts/ that turn satellite data into JSON. **For your current task
you work only in the data-pipeline layer (scripts/ and tests/).** You do not touch the API,
the frontend, or deployment.

## Reading list (in order)

1. **docs/AI-WORKING-AGREEMENT.md** — your role and the rules of engagement: branch-only work,
   one PR per task, never merge, never deploy, never touch env files or secrets. Read it in full.
2. **docs/brief-spi3-2026-06-29.md** — your actual task (SPI-3). The brief is the source of
   truth for what to build and how it will be judged.
3. **Two existing scripts to mirror for house style** (read, do not change them):
   scripts/compute_anomaly.py and scripts/compute_ltm_baseline.py. Match their structure —
   BASE_DIR resolution, argparse, file-path conventions, rounded floats, clear error messages.

For environment and data background only if needed: docs/setup.md and docs/data_sources.md.

## Three clarifications a fresh context needs

These correct mismatches you would otherwise hit:

- **Ignore the frontend clean-up history.** Files like docs/handoff-*.md, docs/session-*.md,
  docs/bug-triage-*.md and scripts/verify_page.mjs are about an earlier page-generation effort.
  None of it applies to your backend task. Skip it.
- **The working agreement's "Verification" section is frontend-specific** (it talks about
  build_pages.py and a puppeteer headless render). That does NOT apply here. **Your task is
  backend modelling, and verification is pytest** — the acceptance tests A–G defined in the
  SPI-3 brief. Do not run the frontend verify harness for this work.
- **The README undercounts the data.** README.md predates the historical archive and says the
  platform holds ~24 months for two countries. In reality there is a CHIRPS archive from 1981
  to present for six countries. Your task uses Ghana's archive. **Where the README and the brief
  disagree on data extent, trust the brief.**

## How to run things

- Python lives in the project venv. Invoke scripts as:
  ./venv/bin/python scripts/compute_spi.py --country ghana --year 2025 --month 6
- Run tests with:
  ./venv/bin/python -m pytest tests/ -v
- scipy and pytest are required. scipy is already installed in the project venv; pytest is in
  requirements-dev.txt (./venv/bin/pip install -r requirements-dev.txt). If anything is missing
  when you start, say so and wait for the senior — do NOT pip-install into the production server.

## The rules, in one line

Work on branch feature/spi3. One task, one PR. Never merge, never deploy, never touch env files
or secrets. Data-pipeline scripts are **deep-review tier** — say so at the top of your PR so the
senior scrutinises it. When blocked or unsure about anything irreversible or data-shaped, stop
and write the question in the PR rather than guessing.

## Your working notes

Per the agreement's notes convention, keep your working notes in
docs/notes/2026-06-29-deepseek.md (your own file — only you edit it). The shared rolling
status index docs/STATUS.md is seeded by the senior; you may append a dated, attributed entry
at the top but never rewrite an existing one.

## Definition of done

See section 7 of the SPI-3 brief. In short: scripts/compute_spi.py plus tests/test_spi.py
plus pytest in requirements-dev.txt, in one PR on feature/spi3, with acceptance tests A–G
passing, ready for senior review. You do not deploy — the senior regenerates the data on the server.
