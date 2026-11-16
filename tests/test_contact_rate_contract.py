"""Origin contact abuse controls survive runtime dependency patch updates."""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault("SUPABASE_URL", "https://fake-project.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "fake-anon-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "fake-service-key")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
import api.main as main


def test_contact_limit_rejects_fourth_hourly_request_before_smtp(monkeypatch):
    monkeypatch.setenv("BREVO_SMTP_USER", "fixture")
    monkeypatch.setenv("BREVO_SMTP_PASS", "fixture")
    smtp = MagicMock()
    monkeypatch.setattr(main.smtplib, "SMTP", smtp)
    payload = {
        "name": "Fixture",
        "email": "fixture@example.invalid",
        "enquiry_type": "General",
        "message": "Local test only",
    }
    with TestClient(main.app) as client:
        responses = [
            client.post(
                "/api/contact",
                json=payload,
                headers={"CF-Connecting-IP": "198.51.100.7"},
            )
            for _ in range(4)
        ]
    assert [response.status_code for response in responses] == [200, 200, 200, 429]
    assert smtp.return_value.__enter__.return_value.sendmail.call_count == 3


def test_contact_size_bound_rejects_before_smtp(monkeypatch):
    smtp = MagicMock()
    monkeypatch.setattr(main.smtplib, "SMTP", smtp)
    with TestClient(main.app) as client:
        response = client.post(
            "/api/contact",
            json={
                "name": "x" * 101,
                "email": "fixture@example.invalid",
                "enquiry_type": "General",
                "message": "fixture",
            },
            headers={"CF-Connecting-IP": "198.51.100.8"},
        )
    assert response.status_code == 422
    smtp.assert_not_called()
