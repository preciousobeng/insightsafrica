"""Map atomic database-cap rejection to the existing HTTP quota response."""
import os
from pathlib import Path
import sys

os.environ.setdefault('SUPABASE_URL', 'https://fake-project.supabase.co')
os.environ.setdefault('SUPABASE_ANON_KEY', 'fake-anon-key')
os.environ.setdefault('SUPABASE_SERVICE_ROLE_KEY', 'fake-service-key')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
import api.main as main


@pytest.mark.parametrize('error,status', [
    ({'code': 'P0001', 'message': 'API key limit reached (max 5 active keys).'}, 429),
    ({'code': '23503', 'message': 'Profile required'}, 500),
])
def test_database_insert_failure_response(error, status):
    with respx.mock as router, TestClient(main.app) as client:
        router.get(main._SUPA_URL+'/auth/v1/user').mock(return_value=httpx.Response(200, json={'id': 'user'}))
        router.get(main._SUPA_URL+'/rest/v1/api_keys').mock(return_value=httpx.Response(200, json=[]))
        router.get(main._SUPA_URL+'/rest/v1/profiles').mock(return_value=httpx.Response(200, json=[{'tier': 'free'}]))
        router.post(main._SUPA_URL+'/rest/v1/api_keys').mock(return_value=httpx.Response(400, json=error))
        result = client.post('/api/keys', json={'name': 'Test'}, headers={'Authorization': 'Bearer test'})
    assert result.status_code == status
