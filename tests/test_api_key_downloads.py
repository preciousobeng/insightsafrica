"""Regression coverage for table-returning API-key verification RPCs."""
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock

os.environ.setdefault("SUPABASE_URL", "https://fake-project.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "fake-anon-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "fake-service-key")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
import api.main as main

ROW = {"id": "key-id", "user_id": "user-id", "tier": "free",
       "requests_today": 1, "last_reset": "2026-09-15"}


@pytest.mark.parametrize("tier", ["free", "premium"])
def test_valid_key_downloads_full_archive(monkeypatch, tier):
    log = AsyncMock()
    monkeypatch.setattr(main, "_log_download", log)
    seen = []
    def csv_rows(*args, **kwargs):
        seen.append((args, kwargs))
        return "year,month\n1981,1\n"
    monkeypatch.setattr(main, "_chirps_csv", csv_rows)
    with respx.mock as router, TestClient(main.app) as client:
        verify = router.post(f"{main._SUPA_URL}/rest/v1/rpc/verify_and_consume_api_key").mock(
            return_value=httpx.Response(200, json=[{**ROW, "tier": tier}]))
        response = client.get("/api/flood/download/csv?from=1981-01", headers={"X-API-Key": "ia_test"})
    assert response.status_code == 200
    assert "1981,1" in response.text
    assert verify.call_count == 1
    assert seen[0][0][3] == "1981-01"
    assert log.await_args.args[4] == "user-id"


@pytest.mark.parametrize("payload", [[], None, {}, ROW, [ROW, ROW], [None], [{}],
    [{**ROW, "user_id": ""}], [{**ROW, "user_id": None}], [{**ROW, "tier": "admin"}]])
def test_invalid_rpc_shape_fails_closed(payload):
    with respx.mock as router, TestClient(main.app) as client:
        router.post(f"{main._SUPA_URL}/rest/v1/rpc/verify_and_consume_api_key").mock(
            return_value=httpx.Response(200, json=payload))
        response = client.get("/api/flood/download/csv", headers={"X-API-Key": "ia_test"})
    assert response.status_code == 401


def test_provider_error_fails_closed():
    with respx.mock as router, TestClient(main.app) as client:
        router.post(f"{main._SUPA_URL}/rest/v1/rpc/verify_and_consume_api_key").mock(
            return_value=httpx.Response(503))
        response = client.get("/api/flood/download/csv", headers={"X-API-Key": "ia_test"})
    assert response.status_code == 401
