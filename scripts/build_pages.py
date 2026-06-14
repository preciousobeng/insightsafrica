"""
build_pages.py

Generates the InsightsAfrica frontend HTML pages from shared Jinja2 templates
+ per-country config, so the 44 near-identical pages are no longer hand-maintained.

Templates:  frontend/_templates/<page_type>.html
Config:     frontend/_config/countries.yml
Output:     frontend/<slug>/<page_type>/index.html   (or frontend/<page_type>/index.html for Ghana root)
            frontend/<slug>/hub.html

Usage:
    python scripts/build_pages.py --type flood          # one page type, all countries
    python scripts/build_pages.py --all                 # everything
    python scripts/build_pages.py --type flood --verify # generate to temp, diff vs committed, DO NOT write

--verify is the safety gate: it proves the generated output is byte-identical to
the current committed pages (no regression) before any real file is overwritten.
"""

import argparse
import difflib
import sys
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

BASE_DIR    = Path(__file__).parent.parent
FRONTEND    = BASE_DIR / "frontend"
TEMPLATES   = FRONTEND / "_templates"
CONFIG_FILE = FRONTEND / "_config" / "countries.yml"

# Page types that exist per country as <type>/index.html
MODULE_TYPES = ["flood", "crop", "heat", "mine", "human", "profile"]
# hub.html sits at the country root, not under a subfolder


def load_config() -> dict:
    with open(CONFIG_FILE) as f:
        return yaml.safe_load(f)


def output_path(country: dict, page_type: str) -> Path:
    """Where the generated file lands. Ghana is at the frontend root."""
    root = FRONTEND if country.get("is_root") else FRONTEND / country["slug"]
    if page_type == "hub":
        return root / "hub.html"
    return root / page_type / "index.html"


def render(env: Environment, page_type: str, country: dict) -> str:
    # Per-country template variant: <page_type>_<slug>.html takes precedence over
    # the shared <page_type>.html. Used where a country's structure diverges too far
    # to share (e.g. Cape Verde's single-level flood page).
    variant = TEMPLATES / f"{page_type}_{country['slug']}.html"
    name = variant.name if variant.exists() else f"{page_type}.html"
    tmpl = env.get_template(name)
    return tmpl.render(c=country, country=country)


def main():
    ap = argparse.ArgumentParser(description="Generate InsightsAfrica frontend pages")
    ap.add_argument("--type", help="Single page type (flood, crop, heat, mine, human, profile, hub)")
    ap.add_argument("--all", action="store_true", help="All page types")
    ap.add_argument("--verify", action="store_true",
                    help="Diff generated output against committed files; write nothing")
    args = ap.parse_args()

    if not args.type and not args.all:
        ap.error("specify --type <name> or --all")

    config = load_config()
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        undefined=StrictUndefined,   # fail loudly on a missing config key
        keep_trailing_newline=True,
        trim_blocks=True,    # newline after a block tag is stripped — clean HTML output
        lstrip_blocks=True,  # leading whitespace before a block tag is stripped
    )

    types = MODULE_TYPES + ["hub"] if args.all else [args.type]
    available = {p.stem for p in TEMPLATES.glob("*.html")}

    total = clean = diffs = skipped = written = 0
    for page_type in types:
        if page_type not in available:
            print(f"[skip] no template for '{page_type}' yet")
            continue
        for slug, country in config.items():
            country.setdefault("slug", slug)
            # capeverde-only single-level pages may not define coarse/fine; that's per-template
            out = output_path(country, page_type)
            try:
                generated = render(env, page_type, country)
            except Exception as e:
                print(f"[ERROR] {slug}/{page_type}: {e}")
                continue
            total += 1

            if args.verify:
                if not out.exists():
                    print(f"[new]  {out.relative_to(FRONTEND)} (no committed file to diff)")
                    continue
                current = out.read_text()
                if current == generated:
                    clean += 1
                else:
                    diffs += 1
                    d = difflib.unified_diff(
                        current.splitlines(), generated.splitlines(),
                        fromfile=f"committed/{out.relative_to(FRONTEND)}",
                        tofile=f"generated/{out.relative_to(FRONTEND)}",
                        lineterm="", n=1,
                    )
                    print(f"\n===== DIFF {out.relative_to(FRONTEND)} =====")
                    print("\n".join(list(d)[:60]))
            else:
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(generated)
                written += 1
                print(f"[write] {out.relative_to(FRONTEND)}")

    print(f"\nTotal {total} | identical {clean} | differ {diffs} | written {written}")
    if args.verify and diffs:
        sys.exit(1)


if __name__ == "__main__":
    main()
