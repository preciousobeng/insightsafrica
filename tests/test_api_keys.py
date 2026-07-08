"""Acceptance tests for the per-user API key cap — FROZEN by the senior.

TDD: the junior edits api/main.py (specifically create_api_key) to satisfy these;
it must NOT edit this file. See docs/brief-api-key-cap-2026-07-08.md.

Context: /api/keys (POST) currently lets any authenticated user create unlimited
API keys with no server-side limit. This test suite requires a MAX_API_KEYS_PER_USER
cap (import it from api.main so the test and the implementation share one constant)
enforced in create_api_key: once a user has that many non-revoked keys, further
POST /api/keys calls must fail with HTTP 429 and must NOT insert a new row.

Run: ./venv/bin/python -m pytest tests/test_api_keys.py -v
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

os.environ.setdefault("SUPABASE_URL", "https://fake-project.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "fake-anon-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "fake-service-key")

import pytest
import respx
from httpx import Response
from fastapi.testclient import TestClient

import api.main as main  # type: ignore[import-not-found]

client = TestClient(main.app)

_SUPA = main._SUPA_URL
_AUTH_HEADERS = {"Authorization": "Bearer faketoken"}
_USER_ID = "11111111-1111-1111-1111-111111111111"


def _mock_user(respx_mock):
    respx_mock.get(f"{_SUPA}/auth/v1/user").mock(
        return_value=Response(200, json={"id": _USER_ID, "email": "user@example.com"})
    )


def _mock_tier(respx_mock, tier="free"):
    respx_mock.get(f"{_SUPA}/rest/v1/profiles").mock(
        return_value=Response(200, json=[{"tier": tier}])
    )


def _existing_keys_response(respx_mock, count: int):
    rows = [
        {
            "id": f"key-{i}",
            "name": f"key {i}",
            "tier": "free",
            "requests_today": 0,
            "last_reset": "2026-07-08",
            "created_at": "2026-07-01T00:00:00Z",
        }
        for i in range(count)
    ]
    return respx_mock.get(f"{_SUPA}/rest/v1/api_keys").mock(return_value=Response(200, json=rows))


def test_max_api_keys_per_user_constant_exists():
    """The cap must be a named constant on api.main, not a magic number, so both
    create_api_key and any future admin/UI code reference the same value."""
    assert hasattr(main, "MAX_API_KEYS_PER_USER")
    assert isinstance(main.MAX_API_KEYS_PER_USER, int)
    assert main.MAX_API_KEYS_PER_USER > 0


@respx.mock
def test_create_api_key_succeeds_under_cap():
    _mock_user(respx.mock)
    _mock_tier(respx.mock)
    _existing_keys_response(respx.mock, count=main.MAX_API_KEYS_PER_USER - 1)
    respx.mock.post(f"{_SUPA}/rest/v1/api_keys").mock(
        return_value=Response(
            201,
            json=[
                {
                    "id": "new-key-id",
                    "name": "My API key",
                    "tier": "free",
                    "created_at": "2026-07-08T00:00:00Z",
                }
            ],
        )
    )

    r = client.post("/api/keys", json={"name": "My API key"}, headers=_AUTH_HEADERS)

    assert r.status_code == 200
    body = r.json()
    assert body["key"].startswith(main._KEY_PREFIX)


@respx.mock
def test_create_api_key_blocked_at_cap():
    _mock_user(respx.mock)
    _mock_tier(respx.mock)
    _existing_keys_response(respx.mock, count=main.MAX_API_KEYS_PER_USER)
    insert_route = respx.mock.post(f"{_SUPA}/rest/v1/api_keys").mock(
        return_value=Response(201, json=[{"id": "should-not-be-created"}])
    )

    r = client.post("/api/keys", json={"name": "One too many"}, headers=_AUTH_HEADERS)

    assert r.status_code == 429
    assert not insert_route.called, "must not insert a new key once the user is at the cap"


@respx.mock
def test_create_api_key_blocked_only_counts_active_keys():
    """A user who has revoked old keys down to zero active ones must still be able
    to create a new one, even if their total (incl. revoked) row count is >= cap.
    The count query filters revoked_at=is.null — assert it stays that way."""
    _mock_user(respx.mock)
    _mock_tier(respx.mock)
    list_route = _existing_keys_response(respx.mock, count=0)
    respx.mock.post(f"{_SUPA}/rest/v1/api_keys").mock(
        return_value=Response(201, json=[{"id": "new-key-id", "name": "n", "tier": "free", "created_at": "2026-07-08T00:00:00Z"}])
    )

    r = client.post("/api/keys", json={"name": "Fresh key"}, headers=_AUTH_HEADERS)

    assert r.status_code == 200
    called_request = list_route.calls.last.request
    assert "revoked_at=is.null" in str(called_request.url)


def test_create_api_key_requires_auth_unaffected():
    """Sanity: the cap change must not weaken the existing 401 for anonymous callers."""
    r = client.post("/api/keys", json={"name": "no auth"})
    assert r.status_code == 401
