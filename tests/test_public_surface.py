"""Public serving must not expose source files or unused processed artifacts."""

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("SUPABASE_URL", "https://fake-project.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "fake-anon-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "fake-service-key")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from api.public_files import PublicFrontendFiles, PublicMapFiles
import api.main as main


@pytest.mark.parametrize(
    "path",
    [
        "/_templates/flood.html",
        "/_config/countries.yml",
        "/admin-hierarchy-v2.html",
        "/.env",
        "/static/../_config/countries.yml",
    ],
)
def test_private_frontend_paths_are_not_served(path):
    with TestClient(main.app) as client:
        assert client.get(path).status_code == 404


def test_public_pages_and_security_contact_work():
    with TestClient(main.app) as client:
        for path in (
            "/",
            "/login.html",
            "/data-key-version.html",
            "/.well-known/security.txt",
            "/ghana/flood/",
            "/nigeria/hub.html",
        ):
            response = client.get(path)
            assert response.status_code == 200, path
            assert response.headers["X-Frame-Options"] == "DENY"
        assert (
            "mailto:info@insightsafrica.org"
            in client.get("/.well-known/security.txt").text
        )


@pytest.mark.parametrize(
    "metadata",
    [
        "chirps-v2.0.2026.09_nigeria.json",
        "ndvi_2026_nigeria.json",
        "heat_lagos.json",
        "nigeria_mining_sites.json",
    ],
)
def test_only_metadata_referenced_png_is_public(tmp_path, metadata):
    (tmp_path / metadata).write_text(
        json.dumps({"png": "real.png", "nested": [{"ndvi_png": "mine.png"}]})
    )
    for name in (
        "real.png",
        "mine.png",
        "stray.png",
        "nigeria_states.geojson",
        "private.sql",
    ):
        (tmp_path / name).write_text("fixture")
    app = FastAPI()
    app.mount("/tiles", PublicMapFiles(directory=str(tmp_path)))
    with TestClient(app) as client:
        assert client.get("/tiles/real.png").status_code == 200
        assert client.get("/tiles/mine.png").status_code == 200
        for name in ("stray.png", "nigeria_states.geojson", metadata, "private.sql"):
            assert client.get("/tiles/" + name).status_code == 404


def test_manifest_refresh_and_symlink_escape(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    metadata = root / "heat_city.json"
    metadata.write_text(json.dumps({"png": "old.png"}))
    (root / "old.png").write_text("old")
    (root / "new.png").write_text("new")
    (tmp_path / "outside.png").write_text("outside")
    (root / "escape.png").symlink_to(tmp_path / "outside.png")
    app = FastAPI()
    app.mount("/tiles", PublicMapFiles(directory=str(root)))
    with TestClient(app) as client:
        assert client.get("/tiles/old.png").status_code == 200
        metadata.write_text(json.dumps({"png": "new.png", "other": "escape.png"}))
        assert client.get("/tiles/new.png").status_code == 200
        assert client.get("/tiles/old.png").status_code == 404
        assert client.get("/tiles/escape.png").status_code == 404


@pytest.mark.parametrize(
    "path",
    [item[0] for item in main._DL_GEOJSON]
    + [
        "/api/southafrica/flood/download/provinces.geojson",
        "/api/southafrica/flood/download/districts.geojson",
    ],
)
def test_bulk_boundary_downloads_are_paused(path):
    with TestClient(main.app) as client:
        assert client.get(path).status_code == 410


def test_interactive_boundary_route_still_works(tmp_path, monkeypatch):
    # Use synthetic geometry, never copied GADM geometry, for this contract.
    (tmp_path / "test_regions.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": []})
    )
    endpoint = main._make_boundaries_route(
        tmp_path, "test", {"regions": "regions"}, "bad", "missing {r}"
    )
    response = endpoint("regions")
    assert json.loads(response.body)["features"] == []


def test_api_docs_keep_existing_optional_download_auth():
    schema = main.app.openapi()
    assert all(path.startswith("/api/") for path in schema["paths"])
    auth = schema["paths"]["/api/flood/download/csv"]["get"]["security"]
    assert {} in auth and {"APIKey": []} in auth
    assert schema["components"]["securitySchemes"]["APIKey"]["name"] == "X-API-Key"
