"""Current-site trust checks without calling authentication, email or production."""

import base64
import hashlib
import json
import subprocess
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Elements(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.tags = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def test_auth_sdk_is_exact_self_hosted_and_integrity_checked():
    info = json.loads(
        (ROOT / "frontend/static/vendor/supabase-provenance.json").read_text()
    )
    path = "/static/vendor/supabase-" + info["version"] + ".js"
    content = (ROOT / "frontend" / path.lstrip("/")).read_bytes()
    assert hashlib.sha256(content).hexdigest() == info["sha256"]
    assert (
        "sha384-" + base64.b64encode(hashlib.sha384(content).digest()).decode()
        == info["integrity"]
    )
    for name in ("frontend/login.html", "frontend/ghana/hub.html"):
        tags = Elements((ROOT / name).read_text()).tags
        script = next(
            attrs for tag, attrs in tags if tag == "script" and attrs.get("src") == path
        )
        assert script["integrity"] == info["integrity"]
        assert not any(
            "supabase-js@2" in attrs.get("src", "")
            for tag, attrs in tags
            if tag == "script"
        )


def test_contact_payload_fields_are_preserved():
    original = subprocess.check_output(
        ["git", "show", "c7a65e4:frontend/index.html"], cwd=ROOT, text=True
    )
    current = (ROOT / "frontend/index.html").read_text()

    def fields(text):
        start = text.index("    var payload = {")
        return text[start : text.index("    };", start) + 6]

    assert fields(current) == fields(original)


def test_site_trust_does_not_publish_or_link_to_a_privacy_draft():
    assert not (ROOT / "frontend/privacy.html").exists()
    paths = [
        ROOT / "frontend/index.html",
        ROOT / "frontend/login.html",
        ROOT / "frontend/how-it-works.html",
        *ROOT.glob("frontend/_templates/hub*.html"),
        *ROOT.glob("frontend/*/hub.html"),
    ]
    assert all("/privacy.html" not in path.read_text() for path in paths)


def test_share_description_and_archive_claims_are_consistent():
    page = (ROOT / "frontend/index.html").read_text()
    for tag, attrs in Elements(page).tags:
        if tag == "meta" and attrs.get("property") == "og:description":
            assert "South Africa" in attrs["content"] and "Senegal" in attrs["content"]
    assert "Satellite data archive" not in page
    assert "Rainfall archive starts" in page
    assert "100%</span>" not in page
    assert "CHIRPS (UCSB CHC)" in page
    assert 'href="/how-it-works.html#source-terms"' in page


def test_hub_wording_does_not_claim_every_download_needs_a_key():
    text = (ROOT / "frontend/ghana/hub.html").read_text()
    assert "A key is not required for the anonymous recent window." in text
    assert "Free keys: 500 requests/day" in text


def test_all_vendor_assets_match_provenance_and_pages_use_sri():
    for folder in ("leaflet-1.9.4", "chartjs-4.4.2"):
        base = ROOT / "frontend/static/vendor" / folder
        info = json.loads((base / "provenance.json").read_text())
        for name, record in info["files"].items():
            data = (base / name).read_bytes()
            assert hashlib.sha256(data).hexdigest() == record["sha256"]
            assert (
                "sha384-" + base64.b64encode(hashlib.sha384(data).digest()).decode()
                == record["integrity"]
            )
    pages = list((ROOT / "frontend").rglob("*.html"))
    for page in pages:
        text = page.read_text()
        assert "fonts.googleapis.com" not in text
        assert "fonts.gstatic.com" not in text
        assert "all open source" not in text.lower()
        for tag, attrs in Elements(text).tags:
            url = attrs.get("src", attrs.get("href", ""))
            if "leaflet" in url or "chart.umd" in url or "site-fonts.css" in url:
                assert url.startswith("/static/")
                data = (ROOT / "frontend" / url.lstrip("/")).read_bytes()
                assert (
                    attrs["integrity"]
                    == "sha384-"
                    + base64.b64encode(hashlib.sha384(data).digest()).decode()
                )


def test_corrected_source_terms_and_open_data_stat():
    assert ">Open data</span>" in (ROOT / "frontend/index.html").read_text()
    for country in ("ivorycoast", "senegal", "capeverde"):
        text = (ROOT / "frontend" / country / "hub.html").read_text()
        assert "Boundaries: GADM 4.1 (non-commercial licence" in text
        assert "Boundaries: GADM 4.1 &middot; CC BY-NC" not in text


def test_self_hosted_font_files_and_licences_exist():
    folder = ROOT / "frontend/static/fonts"
    css = (folder / "site-fonts.css").read_text()
    import re

    files = re.findall(r"url\(['\"]?([^)'\"]+)", css)
    assert files
    for url in files:
        data = (
            (ROOT / "frontend" / url.lstrip("/"))
            if url.startswith("/")
            else folder / url
        ).read_bytes()
        assert data[:4] == b"wOF2"
    assert (folder / "syne-OFL.txt").exists()
    assert (folder / "dmmono-OFL.txt").exists()
