from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_notice_is_explicitly_draft_and_lists_verified_providers():
    text = (ROOT / "frontend/privacy.html").read_text()
    for value in (
        "CONFIRM",
        "Esri",
        "Google Fonts",
        "Supabase",
        "Cloudflare",
        "Oracle",
    ):
        assert value in text
    assert "noindex" in text


def test_privacy_links_and_proposed_retention_remain_separate():
    for path in [
        ROOT / "frontend/index.html",
        ROOT / "frontend/login.html",
        *ROOT.glob("frontend/*/hub.html"),
    ]:
        assert "/privacy.html" in path.read_text()
    sql = (
        ROOT / "supabase/migrations/20261116_download_event_retention.sql"
    ).read_text()
    assert "SECURITY INVOKER" in sql
    assert "cron.schedule" not in sql
