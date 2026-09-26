"""Version the deliberate key correction without changing CSV columns/routes."""
import csv
import io
import json
import os
from pathlib import Path
import sys

os.environ.setdefault('SUPABASE_URL', 'https://fake-project.supabase.co')
os.environ.setdefault('SUPABASE_ANON_KEY', 'fake-anon-key')
os.environ.setdefault('SUPABASE_SERVICE_ROLE_KEY', 'fake-service-key')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
import api.main as main


def test_flood_response_exposes_identifier_version_and_notice():
    with TestClient(main.app) as client:
        response = client.get('/api/flood/layers')
        assert response.status_code == 200
        assert response.headers['X-Administrative-Key-Version'] == '2'
        assert 'admin-hierarchy-v2.html' in response.headers['Link']
        notice = client.get('/admin-hierarchy-v2.html')
        assert notice.status_code == 200
        assert 'Name|Parent' in notice.text


def test_csv_retains_columns_and_emits_canonical_area(tmp_path):
    payload = {'year': 2026, 'month': 4, 'label': 'April 2026', 'zonal_stats': {
        'districts': {'Abidjan': {'mean': 1.2, 'max': 2.3, 'min': 0.1}}}}
    (tmp_path / 'chirps-test.json').write_text(json.dumps(payload))
    content = main._chirps_csv(tmp_path, '*.json', 'districts', country='ivorycoast')
    reader = csv.DictReader(io.StringIO('\n'.join(line for line in content.splitlines() if not line.startswith('#'))))
    rows = list(reader)
    assert reader.fieldnames == ['year', 'month', 'period', 'area', 'level',
                                 'mean_rainfall_mm', 'max_rainfall_mm', 'min_rainfall_mm']
    assert rows[0]['area'] == 'Abidjan'


def test_ghana_routes_keep_existing_redirects():
    with TestClient(main.app) as client:
        assert client.get('/ghana', follow_redirects=False).headers['location'] == '/ghana/hub.html'
        assert client.get('/flood/', follow_redirects=False).headers['location'] == '/ghana/flood/'
