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


def test_privacy_draft_is_linked_and_requires_owner_input():
    notice = (ROOT / "frontend/privacy.html").read_text()
    assert "owner confirmation required before publication" in notice
    for name in (
        "CONTROLLER_NAME_AND_CONTACT",
        "CONTACT_RETENTION",
        "DOWNLOAD_LOG_RETENTION",
        "PURPOSES_AND_LAWFUL_BASES",
    ):
        assert "OWNER INPUT · " + name in notice
    for path in [
        ROOT / "frontend/index.html",
        ROOT / "frontend/login.html",
        *ROOT.glob("frontend/*/hub.html"),
    ]:
        assert 'href="/privacy.html"' in path.read_text(), path
    assert (
        'aria-describedby="contact-privacy-note"'
        in (ROOT / "frontend/index.html").read_text()
    )


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
