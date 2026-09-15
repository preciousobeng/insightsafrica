"""The generator must fail closed on incomplete or broken output."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import build_pages as build


@pytest.fixture
def tree(tmp_path, monkeypatch):
    frontend = tmp_path / "frontend"
    templates = frontend / "_templates"
    templates.mkdir(parents=True)
    (templates / "flood.html").write_text("{{ c.slug }}\n")
    monkeypatch.setattr(build, "FRONTEND", frontend)
    monkeypatch.setattr(build, "TEMPLATES", templates)
    monkeypatch.setattr(build, "load_config", lambda: {"ghana": {"slug": "ghana"}})
    monkeypatch.setattr(sys, "argv", ["build_pages.py", "--type", "flood", "--verify"])
    output = frontend / "ghana/flood/index.html"
    output.parent.mkdir(parents=True)
    output.write_text("ghana\n")
    return templates, output


def test_matching_output_passes(tree):
    build.main()


@pytest.mark.parametrize("failure", ["render", "template", "output", "different"])
def test_incomplete_or_different_output_fails_without_writing(tree, failure):
    templates, output = tree
    if failure == "render":
        (templates / "flood.html").write_text("{{ missing_variable }}")
    elif failure == "template":
        (templates / "flood.html").unlink()
    elif failure == "output":
        output.unlink()
    else:
        output.write_text("stale")
    before = output.read_bytes() if output.exists() else None
    with pytest.raises(SystemExit) as exc:
        build.main()
    assert exc.value.code == 1
    assert (output.read_bytes() if output.exists() else None) == before


def test_render_error_fails_write_mode(tree, monkeypatch):
    (tree[0] / "flood.html").write_text("{{ missing_variable }}")
    monkeypatch.setattr(sys, "argv", ["build_pages.py", "--type", "flood"])
    with pytest.raises(SystemExit) as exc:
        build.main()
    assert exc.value.code == 1


def test_unknown_page_type_fails(tree, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["build_pages.py", "--type", "flod", "--verify"])
    with pytest.raises(SystemExit) as exc:
        build.main()
    assert exc.value.code == 2
