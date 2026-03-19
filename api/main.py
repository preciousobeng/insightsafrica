"""
main.py — InsightsAfrica Multi-Country FastAPI backend

Ghana routes:
  /             → Country selector landing page
  /flood/       → FloodWatch Ghana
  /mine/        → MineWatch Ghana
  /crop/        → CropWatch Ghana
  /heat/        → HeatWatch Ghana
  /api/flood/*  → FloodWatch Ghana data
  /api/mine/*   → MineWatch Ghana data
  /api/crop/*   → CropWatch Ghana data
  /api/heat/*   → HeatWatch Ghana data
  /api/boundaries/* → Ghana admin boundaries

Nigeria routes:
  /nigeria/          → Nigeria Intelligence Hub
  /nigeria/flood/    → FloodWatch Nigeria
  /nigeria/mine/     → MineWatch Nigeria
  /nigeria/crop/     → CropWatch Nigeria
  /nigeria/heat/     → HeatWatch Nigeria
  /api/nigeria/flood/*     → FloodWatch Nigeria data
  /api/nigeria/mine/*      → MineWatch Nigeria data
  /api/nigeria/crop/*      → CropWatch Nigeria data
  /api/nigeria/heat/*      → HeatWatch Nigeria data
  /api/nigeria/boundaries/* → Nigeria admin boundaries
  /ng-tiles/         → Nigeria processed PNGs

Run:
    uvicorn api.main:app --reload --port 8001
"""

import csv
import hashlib
import io
import json
import os
import secrets
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Literal

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

# ── Supabase config ───────────────────────────────────────────────────────────

_SUPA_URL     = os.getenv("SUPABASE_URL", "")
_SUPA_ANON    = os.getenv("SUPABASE_ANON_KEY", "")
_SUPA_SERVICE = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

_supa_headers_service = {
    "apikey":        _SUPA_SERVICE,
    "Authorization": f"Bearer {_SUPA_SERVICE}",
    "Content-Type":  "application/json",
    "Prefer":        "return=minimal",
}


async def _get_user(token: str) -> dict | None:
    """Verify a Supabase JWT and return the user dict, or None if invalid."""
    if not token or not _SUPA_URL:
        return None
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            r = await client.get(
                f"{_SUPA_URL}/auth/v1/user",
                headers={"apikey": _SUPA_ANON, "Authorization": f"Bearer {token}"},
            )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


async def _get_tier(user_id: str) -> str:
    """Return 'free' or 'premium' for a user. Defaults to 'free' on any error."""
    if not user_id or not _SUPA_URL:
        return "free"
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            r = await client.get(
                f"{_SUPA_URL}/rest/v1/user_profiles",
                headers=_supa_headers_service,
                params={"id": f"eq.{user_id}", "select": "tier"},
            )
        if r.status_code == 200:
            rows = r.json()
            if rows:
                return rows[0].get("tier", "free")
    except Exception:
        pass
    return "free"


async def _log_download(
    request: Request,
    country: str,
    product: str,
    fmt: str,
    user_id: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
) -> None:
    """Insert a download event into Supabase. Fire-and-forget."""
    if not _SUPA_URL:
        return
    payload = {
        "country":   country,
        "product":   product,
        "format":    fmt,
        "user_id":   user_id,
        "from_date": from_date,
        "to_date":   to_date,
        "ip":        request.client.host if request.client else None,
    }
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            await client.post(
                f"{_SUPA_URL}/rest/v1/download_events",
                headers=_supa_headers_service,
                json=payload,
            )
    except Exception:
        pass  # logging must never break a download


def _extract_token(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    # Also accept cookie set by Supabase JS client
    return request.cookies.get("sb-access-token")


_FREE_MONTHS    = 6    # how far back free users can go
_FREE_RPD       = 500  # free-tier API key requests per day
_KEY_PREFIX     = "ia_"


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


async def _verify_api_key(key: str) -> dict | None:
    """
    Look up an API key by its hash. Enforces rate limit for free keys.
    Returns the key row dict on success, None if invalid/revoked/over-limit.
    Increments requests_today and resets the counter if it's a new day.
    """
    if not key or not _SUPA_URL:
        return None
    key_hash = _hash_key(key)
    today = datetime.now(timezone.utc).date().isoformat()
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            r = await client.get(
                f"{_SUPA_URL}/rest/v1/api_keys",
                headers=_supa_headers_service,
                params={
                    "key_hash": f"eq.{key_hash}",
                    "revoked_at": "is.null",
                    "select": "id,user_id,tier,requests_today,last_reset",
                },
            )
        if r.status_code != 200 or not r.json():
            return None
        row = r.json()[0]

        # Daily reset
        needs_reset = row["last_reset"] != today
        new_count   = 1 if needs_reset else row["requests_today"] + 1

        # Rate limit check (premium = unlimited)
        if row["tier"] == "free" and new_count > _FREE_RPD:
            return None

        # Update counter
        patch = {"requests_today": new_count}
        if needs_reset:
            patch["last_reset"] = today
        async with httpx.AsyncClient(timeout=4.0) as client:
            await client.patch(
                f"{_SUPA_URL}/rest/v1/api_keys",
                headers=_supa_headers_service,
                params={"id": f"eq.{row['id']}"},
                json=patch,
            )
        return row
    except Exception:
        return None

def _clamp_free(from_ym: str | None, to_ym: str | None) -> tuple[str, str | None]:
    """For free-tier users clamp from_date to last 6 months."""
    from datetime import date, timedelta
    cutoff = date.today().replace(day=1) - timedelta(days=_FREE_MONTHS * 30)
    cutoff_ym = f"{cutoff.year:04d}-{cutoff.month:02d}"
    clamped_from = cutoff_ym if (from_ym is None or from_ym < cutoff_ym) else from_ym
    return clamped_from, to_ym

BASE_DIR          = Path(__file__).parent.parent
PROCESSED_DIR     = BASE_DIR / "data" / "processed"
NIGERIA_DIR       = BASE_DIR / "data" / "processed_nigeria"
IVORYCOAST_DIR    = BASE_DIR / "data" / "processed_ivorycoast"
INDICATORS_DIR    = BASE_DIR / "data" / "processed_indicators"
FRONTEND_DIR      = BASE_DIR / "frontend"

app = FastAPI(title="InsightsAfrica API", version="0.4.0")


# ── Contact form ──────────────────────────────────────────────────────────────

class ContactForm(BaseModel):
    name: str
    email: str
    enquiry_type: str
    message: str


@app.post("/api/contact")
async def contact(form: ContactForm):
    smtp_user  = os.getenv("BREVO_SMTP_USER")
    smtp_pass  = os.getenv("BREVO_SMTP_PASS")
    recipient  = os.getenv("CONTACT_RECIPIENT", "info@insightsafrica.org")

    if not smtp_user or not smtp_pass:
        raise HTTPException(status_code=503, detail="Email service not configured")

    if not form.name.strip() or not form.email.strip() or not form.message.strip():
        raise HTTPException(status_code=400, detail="All fields are required")

    if "@" not in form.email or "." not in form.email.split("@")[-1]:
        raise HTTPException(status_code=400, detail="Invalid email address")

    msg = MIMEMultipart("alternative")
    msg["Subject"]  = f"[InsightsAfrica] {form.enquiry_type} enquiry from {form.name}"
    msg["From"]     = "InsightsAfrica <noreply@insightsafrica.org>"
    msg["To"]       = recipient
    msg["Reply-To"] = f"{form.name} <{form.email}>"

    body = (
        f"New enquiry via insightsafrica.org\n\n"
        f"Name:         {form.name}\n"
        f"Email:        {form.email}\n"
        f"Enquiry type: {form.enquiry_type}\n\n"
        f"Message:\n{form.message}\n"
    )
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP("smtp-relay.brevo.com", 587) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail("noreply@insightsafrica.org", recipient, msg.as_string())
    except Exception:
        raise HTTPException(status_code=502, detail="Failed to send message. Please try again later.")

    return {"ok": True}


# ── API routes — must be defined BEFORE static mounts ──

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "InsightsAfrica", "version": "0.4.0"}


# ── API key management ────────────────────────────────────────────────────────

class _KeyCreate(BaseModel):
    name: str = "My API key"


@app.post("/api/keys")
async def create_api_key(body: _KeyCreate, request: Request):
    """Create a new API key. Requires a valid Supabase session token."""
    token = _extract_token(request)
    user  = await _get_user(token) if token else None
    if not user:
        raise HTTPException(status_code=401, detail="Login required to create API keys")

    raw  = _KEY_PREFIX + secrets.token_urlsafe(32)
    tier = await _get_tier(user["id"])

    async with httpx.AsyncClient(timeout=6.0) as client:
        r = await client.post(
            f"{_SUPA_URL}/rest/v1/api_keys",
            headers={**_supa_headers_service, "Prefer": "return=representation"},
            json={
                "user_id":  user["id"],
                "key_hash": _hash_key(raw),
                "name":     body.name,
                "tier":     tier,
            },
        )
    if r.status_code not in (200, 201):
        raise HTTPException(status_code=500, detail="Failed to create key")

    row = r.json()[0]
    return {
        "id":         row["id"],
        "name":       row["name"],
        "tier":       row["tier"],
        "key":        raw,   # returned once — never stored in plaintext
        "created_at": row["created_at"],
    }


@app.get("/api/keys")
async def list_api_keys(request: Request):
    """List API keys for the authenticated user (plaintext key not returned)."""
    token = _extract_token(request)
    user  = await _get_user(token) if token else None
    if not user:
        raise HTTPException(status_code=401, detail="Login required")

    async with httpx.AsyncClient(timeout=4.0) as client:
        r = await client.get(
            f"{_SUPA_URL}/rest/v1/api_keys",
            headers=_supa_headers_service,
            params={
                "user_id":    f"eq.{user['id']}",
                "revoked_at": "is.null",
                "select":     "id,name,tier,requests_today,last_reset,created_at",
                "order":      "created_at.desc",
            },
        )
    if r.status_code != 200:
        raise HTTPException(status_code=500, detail="Failed to fetch keys")
    return r.json()


@app.delete("/api/keys/{key_id}")
async def revoke_api_key(key_id: str, request: Request):
    """Revoke an API key. Only the owning user can revoke their own keys."""
    token = _extract_token(request)
    user  = await _get_user(token) if token else None
    if not user:
        raise HTTPException(status_code=401, detail="Login required")

    now = datetime.now(timezone.utc).isoformat()
    async with httpx.AsyncClient(timeout=4.0) as client:
        r = await client.patch(
            f"{_SUPA_URL}/rest/v1/api_keys",
            headers=_supa_headers_service,
            params={"id": f"eq.{key_id}", "user_id": f"eq.{user['id']}"},
            json={"revoked_at": now},
        )
    if r.status_code not in (200, 204):
        raise HTTPException(status_code=500, detail="Failed to revoke key")
    return {"revoked": True}


# --- FloodWatch ---

@app.get("/api/flood/layers")
def flood_layers():
    """All processed CHIRPS rainfall layers."""
    layers = []
    for f in sorted(PROCESSED_DIR.glob("chirps-*.json")):
        with open(f) as fh:
            layers.append(json.load(fh))
    return JSONResponse(content=layers)


@app.get("/api/flood/layers/latest")
def flood_latest():
    meta_files = sorted(PROCESSED_DIR.glob("chirps-*.json"))
    if not meta_files:
        raise HTTPException(status_code=404, detail="No flood layers available")
    with open(meta_files[-1]) as f:
        return JSONResponse(content=json.load(f))


# --- CropWatch ---

@app.get("/api/crop/layers")
def crop_layers():
    """All processed MODIS NDVI layers."""
    layers = []
    for f in sorted(PROCESSED_DIR.glob("ndvi_*.json")):
        with open(f) as fh:
            layers.append(json.load(fh))
    return JSONResponse(content=layers)


# --- MineWatch ---

@app.get("/api/mine/sites")
def mine_sites():
    """Known galamsey hotspot sites with metadata."""
    sites_path = PROCESSED_DIR / "galamsey_sites.json"
    if not sites_path.exists():
        raise HTTPException(status_code=404, detail="No site data yet. Run fetch_sentinel2.py")
    with open(sites_path) as f:
        return JSONResponse(content=json.load(f))


@app.get("/api/mine/changes")
def mine_changes():
    """Processed NDVI/NDWI change layers for all sites."""
    changes = []
    for f in sorted(PROCESSED_DIR.glob("galamsey_*.json")):
        if f.name == "galamsey_sites.json":
            continue
        with open(f) as fh:
            changes.append(json.load(fh))
    return JSONResponse(content=changes)


# --- Shared ---

@app.get("/api/boundaries/{level}")
def get_boundaries(level: str):
    if level not in ("regions", "districts"):
        raise HTTPException(status_code=400, detail="level must be 'regions' or 'districts'")
    path = PROCESSED_DIR / f"ghana_{level}.geojson"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{level} not found. Run fetch_boundaries.py")
    with open(path) as f:
        return JSONResponse(content=json.load(f))


# ── HeatWatch ──

@app.get("/api/heat/layers")
def heat_layers():
    """All processed Landsat LST layers for Ghana cities."""
    layers = []
    for f in sorted(PROCESSED_DIR.glob("heat_*.json")):
        with open(f) as fh:
            layers.append(json.load(fh))
    return JSONResponse(content=layers)


# ── Nigeria hub redirect ──────────────────────────────────────────────────────

@app.get("/nigeria")
@app.get("/nigeria/")
def nigeria_hub():
    return RedirectResponse(url="/nigeria/hub.html")


# ── Ivory Coast hub redirect ──────────────────────────────────────────────────

@app.get("/ivorycoast")
@app.get("/ivorycoast/")
def ivorycoast_hub():
    return RedirectResponse(url="/ivorycoast/hub.html")


# ── Nigeria API routes ────────────────────────────────────────────────────────

@app.get("/api/nigeria/flood/layers")
def nigeria_flood_layers():
    """All processed CHIRPS rainfall layers for Nigeria."""
    layers = []
    for f in sorted(NIGERIA_DIR.glob("chirps-*_nigeria.json")):
        with open(f) as fh:
            layers.append(json.load(fh))
    return JSONResponse(content=layers)


@app.get("/api/nigeria/crop/layers")
def nigeria_crop_layers():
    """All processed MODIS NDVI layers for Nigeria."""
    layers = []
    for f in sorted(NIGERIA_DIR.glob("ndvi_*_nigeria.json")):
        with open(f) as fh:
            layers.append(json.load(fh))
    return JSONResponse(content=layers)


@app.get("/api/nigeria/mine/sites")
def nigeria_mine_sites():
    """Mining sites for Nigeria (artisanal + oil/gas)."""
    sites_path = NIGERIA_DIR / "nigeria_mining_sites.json"
    if not sites_path.exists():
        raise HTTPException(status_code=404, detail="No Nigeria site data yet. Run fetch_sentinel2.py --country nigeria")
    with open(sites_path) as f:
        return JSONResponse(content=json.load(f))


@app.get("/api/nigeria/heat/layers")
def nigeria_heat_layers():
    """All processed Landsat LST layers for Nigeria cities."""
    layers = []
    for f in sorted(NIGERIA_DIR.glob("heat_*.json")):
        with open(f) as fh:
            layers.append(json.load(fh))
    return JSONResponse(content=layers)


@app.get("/api/nigeria/boundaries/{level}")
def nigeria_boundaries(level: str):
    if level not in ("states", "lgas"):
        raise HTTPException(status_code=400, detail="level must be 'states' or 'lgas'")
    path = NIGERIA_DIR / f"nigeria_{level}.geojson"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{level} not found. Run fetch_boundaries.py --country nigeria")
    with open(path) as f:
        return JSONResponse(content=json.load(f))


# ── Ivory Coast API routes ────────────────────────────────────────────────────

@app.get("/api/ivorycoast/flood/layers")
def ivorycoast_flood_layers():
    """All processed CHIRPS rainfall layers for Ivory Coast."""
    layers = []
    for f in sorted(IVORYCOAST_DIR.glob("chirps-*_ivorycoast.json")):
        with open(f) as fh:
            layers.append(json.load(fh))
    return JSONResponse(content=layers)


@app.get("/api/ivorycoast/crop/layers")
def ivorycoast_crop_layers():
    """All processed MODIS NDVI layers for Ivory Coast."""
    layers = []
    for f in sorted(IVORYCOAST_DIR.glob("ndvi_*_ivorycoast.json")):
        with open(f) as fh:
            layers.append(json.load(fh))
    return JSONResponse(content=layers)


@app.get("/api/ivorycoast/mine/sites")
def ivorycoast_mine_sites():
    """Mining sites for Ivory Coast."""
    sites_path = IVORYCOAST_DIR / "ivorycoast_mining_sites.json"
    if not sites_path.exists():
        raise HTTPException(status_code=404, detail="No Ivory Coast site data yet. Run fetch_sentinel2.py --country ivorycoast")
    with open(sites_path) as f:
        return JSONResponse(content=json.load(f))


@app.get("/api/ivorycoast/heat/layers")
def ivorycoast_heat_layers():
    """All processed Landsat LST layers for Ivory Coast cities."""
    layers = []
    for f in sorted(IVORYCOAST_DIR.glob("heat_*.json")):
        with open(f) as fh:
            layers.append(json.load(fh))
    return JSONResponse(content=layers)


@app.get("/api/ivorycoast/boundaries/{level}")
def ivorycoast_boundaries(level: str):
    if level not in ("districts", "regions"):
        raise HTTPException(status_code=400, detail="level must be 'districts' or 'regions'")
    path = IVORYCOAST_DIR / f"ivorycoast_{level}.geojson"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{level} not found. Run fetch_boundaries.py --country ivorycoast")
    with open(path) as f:
        return JSONResponse(content=json.load(f))


# ── Downloads ────────────────────────────────────────────────────────────────

_ATTRIBUTION = {
    "flood": (
        "# Source: CHIRPS v2.0 (Climate Hazards Group InfraRed Precipitation with Station data)\n"
        "# Provider: Climate Hazards Center, UC Santa Barbara & USGS\n"
        "# Reference: Funk et al. (2015). https://doi.org/10.1038/sdata.2015.66\n"
        "# Processed and distributed by InsightsAfrica (insightsafrica.org)\n"
        "# Units: rainfall in millimetres (mm)\n"
        "#\n"
    ),
    "crop": (
        "# Source: MODIS MOD13Q1 v6.1 — 16-day 250m Vegetation Indices\n"
        "# Provider: NASA EOSDIS Land Processes DAAC, USGS EROS Center\n"
        "# Reference: Didan, K. (2021). https://doi.org/10.5067/MODIS/MOD13Q1.061\n"
        "# Processed and distributed by InsightsAfrica (insightsafrica.org)\n"
        "# Units: NDVI (dimensionless, -1 to 1); stress percentages are % of land area\n"
        "#\n"
    ),
    "heat": (
        "# Source: Landsat 9 Collection 2 Level-2 Surface Temperature (ST_B10)\n"
        "# Provider: NASA / USGS Earthdata (earthdata.nasa.gov)\n"
        "# Processed and distributed by InsightsAfrica (insightsafrica.org)\n"
        "# Units: Land Surface Temperature in degrees Celsius (°C)\n"
        "#\n"
    ),
    "mine": (
        "# Source: Sentinel-2 MSI — Multispectral Instrument, Level-2A\n"
        "# Provider: ESA Copernicus Open Access Hub (scihub.copernicus.eu)\n"
        "# Indices: NDVI (vegetation), NDWI (water body change)\n"
        "# Processed and distributed by InsightsAfrica (insightsafrica.org)\n"
        "#\n"
    ),
}


def _csv_resp(content: str, filename: str) -> Response:
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""},
    )


def _geojson_resp(path: Path, filename: str) -> Response:
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{filename} not found")
    return Response(
        content=path.read_text(),
        media_type="application/geo+json",
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""},
    )


def _ym(year: int, month: int) -> str:
    """Normalise year+month to YYYY-MM for comparison."""
    return f"{year:04d}-{month:02d}"


def _chirps_csv(directory: Path, glob: str, level: str,
                from_ym: str | None = None, to_ym: str | None = None,
                country: str = "") -> str:
    rows = []
    for f in sorted(directory.glob(glob)):
        layer = json.loads(f.read_text())
        key = _ym(layer.get("year", 0), layer.get("month", 0))
        if from_ym and key < from_ym:
            continue
        if to_ym and key > to_ym:
            continue
        for area, stats in layer.get("zonal_stats", {}).get(level, {}).items():
            rows.append({
                "year": layer.get("year"),
                "month": layer.get("month"),
                "period": layer.get("label"),
                "area": area,
                "level": level,
                "mean_rainfall_mm": stats.get("mean"),
                "max_rainfall_mm": stats.get("max"),
                "min_rainfall_mm": stats.get("min"),
            })
    buf = io.StringIO()
    buf.write(_ATTRIBUTION["flood"])
    if country:
        buf.write(f"# Country: {country.title()}\n#\n")
    if rows:
        w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return buf.getvalue()


def _doy_to_ym(year: int, doy: int) -> str:
    """Convert year + day-of-year to YYYY-MM."""
    from datetime import date, timedelta
    d = date(year, 1, 1) + timedelta(days=doy - 1)
    return f"{d.year:04d}-{d.month:02d}"


def _ndvi_csv(directory: Path, glob: str,
              from_ym: str | None = None, to_ym: str | None = None) -> str:
    rows = []
    for f in sorted(directory.glob(glob)):
        layer = json.loads(f.read_text())
        key = _doy_to_ym(layer.get("year", 0), layer.get("doy", 1))
        if from_ym and key < from_ym:
            continue
        if to_ym and key > to_ym:
            continue
        s = layer.get("stress_score", {})
        rows.append({
            "year": layer.get("year"),
            "doy": layer.get("doy"),
            "period": layer.get("label"),
            "source": layer.get("source"),
            "mean_ndvi": s.get("mean_ndvi"),
            "min_ndvi": s.get("min_ndvi"),
            "max_ndvi": s.get("max_ndvi"),
            "healthy_pct": round(s.get("healthy") or 0, 3),
            "fair_pct": round(s.get("fair") or 0, 3),
            "moderate_stress_pct": round(s.get("moderate_stress") or 0, 3),
            "severe_stress_pct": round(s.get("severe_stress") or 0, 3),
        })
    buf = io.StringIO()
    buf.write(_ATTRIBUTION["crop"])
    if rows:
        w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return buf.getvalue()


def _heat_csv(directory: Path, glob: str,
              from_ym: str | None = None, to_ym: str | None = None) -> str:
    rows = []
    for f in sorted(directory.glob(glob)):
        layer = json.loads(f.read_text())
        date_str = layer.get("date", "")
        key = date_str[:7]  # YYYY-MM
        if from_ym and key < from_ym:
            continue
        if to_ym and key > to_ym:
            continue
        s = layer.get("stats", {})
        rows.append({
            "city": layer.get("city_name"),
            "city_id": layer.get("city_id"),
            "region": layer.get("region"),
            "date": date_str,
            "source": layer.get("source"),
            "mean_lst_c": s.get("mean_lst_c"),
            "max_lst_c": s.get("max_lst_c"),
            "min_lst_c": s.get("min_lst_c"),
            "urban_mean_c": s.get("urban_mean_c"),
            "rural_mean_c": s.get("rural_mean_c"),
            "uhi_intensity_c": s.get("uhi_intensity_c"),
        })
    buf = io.StringIO()
    buf.write(_ATTRIBUTION["heat"])
    if rows:
        w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return buf.getvalue()


def _mine_csv(sites_path: Path) -> str:
    if not sites_path.exists():
        return ""
    sites = json.loads(sites_path.read_text())
    rows = []
    for site in sites:
        c = site.get("centre") or []
        rows.append({
            "id": site.get("id"),
            "name": site.get("name"),
            "region": site.get("region"),
            "lat": c[1] if len(c) > 1 else None,
            "lon": c[0] if len(c) > 0 else None,
            "notes": site.get("notes"),
            "ndvi_change": site.get("ndvi_change"),
            "ndwi_change": site.get("ndwi_change"),
            "period": site.get("period"),
        })
    buf = io.StringIO()
    buf.write(_ATTRIBUTION["mine"])
    if rows:
        w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return buf.getvalue()


# ── Shared auth handler for CSV downloads ──────────────────────────────────────

async def _auth_and_clamp(request, from_date, to_date):
    """
    Resolve identity from either X-API-Key or Supabase Bearer token.
    Any authenticated user (registered account or valid API key) gets full archive access.
    Anonymous users are clamped to the last 6 months.
    Returns (user_id, tier, from_date, to_date).
    """
    # 1. API key path
    api_key = request.headers.get("X-API-Key", "")
    if api_key:
        key_row = await _verify_api_key(api_key)
        if key_row is None:
            raise HTTPException(status_code=401, detail="Invalid or rate-limited API key")
        user_id = key_row["user_id"]
        tier    = key_row["tier"]
    else:
        # 2. Supabase session token path
        token   = _extract_token(request)
        user    = await _get_user(token) if token else None
        user_id = user["id"] if user else None
        tier    = "registered" if user_id else "anonymous"

    # Only clamp anonymous users — any registered account gets full archive
    if user_id is None:
        from_date, to_date = _clamp_free(from_date, to_date)
    return user_id, tier, from_date, to_date


# ── Ghana download endpoints ──

@app.get("/api/flood/download/csv")
async def ghana_flood_csv(
    request: Request,
    level: Literal["regions", "districts"] = Query("districts"),
    from_date: str | None = Query(None, alias="from"),
    to_date:   str | None = Query(None, alias="to"),
):
    user_id, tier, from_date, to_date = await _auth_and_clamp(request, from_date, to_date)
    await _log_download(request, "ghana", "flood", "csv", user_id, from_date, to_date)
    content = _chirps_csv(PROCESSED_DIR, "chirps-*.json", level, from_date, to_date, country="ghana")
    return _csv_resp(content, f"insightsafrica_ghana_flood_{level}.csv")


@app.get("/api/flood/download/regions.geojson")
async def ghana_flood_regions_geojson(request: Request):
    token = _extract_token(request)
    user  = await _get_user(token) if token else None
    await _log_download(request, "ghana", "flood", "regions.geojson", user["id"] if user else None)
    return _geojson_resp(PROCESSED_DIR / "ghana_regions.geojson", "ghana_regions.geojson")


@app.get("/api/flood/download/districts.geojson")
async def ghana_flood_districts_geojson(request: Request):
    token = _extract_token(request)
    user  = await _get_user(token) if token else None
    await _log_download(request, "ghana", "flood", "districts.geojson", user["id"] if user else None)
    return _geojson_resp(PROCESSED_DIR / "ghana_districts.geojson", "ghana_districts.geojson")


@app.get("/api/crop/download/csv")
async def ghana_crop_csv(
    request: Request,
    from_date: str | None = Query(None, alias="from"),
    to_date:   str | None = Query(None, alias="to"),
):
    user_id, tier, from_date, to_date = await _auth_and_clamp(request, from_date, to_date)
    await _log_download(request, "ghana", "crop", "csv", user_id, from_date, to_date)
    content = _ndvi_csv(PROCESSED_DIR, "ndvi_*_ghana.json", from_date, to_date)
    return _csv_resp(content, "insightsafrica_ghana_crop_ndvi.csv")


@app.get("/api/heat/download/csv")
async def ghana_heat_csv(
    request: Request,
    from_date: str | None = Query(None, alias="from"),
    to_date:   str | None = Query(None, alias="to"),
):
    user_id, tier, from_date, to_date = await _auth_and_clamp(request, from_date, to_date)
    await _log_download(request, "ghana", "heat", "csv", user_id, from_date, to_date)
    content = _heat_csv(PROCESSED_DIR, "heat_*.json", from_date, to_date)
    return _csv_resp(content, "insightsafrica_ghana_heat.csv")


@app.get("/api/mine/download/csv")
async def ghana_mine_csv(request: Request):
    token = _extract_token(request)
    user  = await _get_user(token) if token else None
    await _log_download(request, "ghana", "mine", "csv", user["id"] if user else None)
    content = _mine_csv(PROCESSED_DIR / "galamsey_sites.json")
    return _csv_resp(content, "insightsafrica_ghana_mine_sites.csv")


# ── Nigeria download endpoints ──

@app.get("/api/nigeria/flood/download/csv")
async def nigeria_flood_csv(
    request: Request,
    level: Literal["states", "lgas"] = Query("states"),
    from_date: str | None = Query(None, alias="from"),
    to_date:   str | None = Query(None, alias="to"),
):
    user_id, tier, from_date, to_date = await _auth_and_clamp(request, from_date, to_date)
    await _log_download(request, "nigeria", "flood", "csv", user_id, from_date, to_date)
    content = _chirps_csv(NIGERIA_DIR, "chirps-*_nigeria.json", level, from_date, to_date, country="nigeria")
    return _csv_resp(content, f"insightsafrica_nigeria_flood_{level}.csv")


@app.get("/api/nigeria/flood/download/states.geojson")
async def nigeria_states_geojson(request: Request):
    token = _extract_token(request)
    user  = await _get_user(token) if token else None
    await _log_download(request, "nigeria", "flood", "states.geojson", user["id"] if user else None)
    return _geojson_resp(NIGERIA_DIR / "nigeria_states.geojson", "nigeria_states.geojson")


@app.get("/api/nigeria/flood/download/lgas.geojson")
async def nigeria_lgas_geojson(request: Request):
    token = _extract_token(request)
    user  = await _get_user(token) if token else None
    await _log_download(request, "nigeria", "flood", "lgas.geojson", user["id"] if user else None)
    return _geojson_resp(NIGERIA_DIR / "nigeria_lgas.geojson", "nigeria_lgas.geojson")


@app.get("/api/nigeria/crop/download/csv")
async def nigeria_crop_csv(
    request: Request,
    from_date: str | None = Query(None, alias="from"),
    to_date:   str | None = Query(None, alias="to"),
):
    user_id, tier, from_date, to_date = await _auth_and_clamp(request, from_date, to_date)
    await _log_download(request, "nigeria", "crop", "csv", user_id, from_date, to_date)
    content = _ndvi_csv(NIGERIA_DIR, "ndvi_*_nigeria.json", from_date, to_date)
    return _csv_resp(content, "insightsafrica_nigeria_crop_ndvi.csv")


@app.get("/api/nigeria/heat/download/csv")
async def nigeria_heat_csv(
    request: Request,
    from_date: str | None = Query(None, alias="from"),
    to_date:   str | None = Query(None, alias="to"),
):
    user_id, tier, from_date, to_date = await _auth_and_clamp(request, from_date, to_date)
    await _log_download(request, "nigeria", "heat", "csv", user_id, from_date, to_date)
    content = _heat_csv(NIGERIA_DIR, "heat_*.json", from_date, to_date)
    return _csv_resp(content, "insightsafrica_nigeria_heat.csv")


@app.get("/api/nigeria/mine/download/csv")
async def nigeria_mine_csv(request: Request):
    token = _extract_token(request)
    user  = await _get_user(token) if token else None
    await _log_download(request, "nigeria", "mine", "csv", user["id"] if user else None)
    content = _mine_csv(NIGERIA_DIR / "nigeria_mining_sites.json")
    return _csv_resp(content, "insightsafrica_nigeria_mine_sites.csv")


# ── Ivory Coast download endpoints ──

@app.get("/api/ivorycoast/flood/download/csv")
async def ivorycoast_flood_csv(
    request: Request,
    level: Literal["districts", "regions"] = Query("districts"),
    from_date: str | None = Query(None, alias="from"),
    to_date:   str | None = Query(None, alias="to"),
):
    user_id, tier, from_date, to_date = await _auth_and_clamp(request, from_date, to_date)
    await _log_download(request, "ivorycoast", "flood", "csv", user_id, from_date, to_date)
    content = _chirps_csv(IVORYCOAST_DIR, "chirps-*_ivorycoast.json", level, from_date, to_date, country="ivory coast")
    return _csv_resp(content, f"insightsafrica_ivorycoast_flood_{level}.csv")


@app.get("/api/ivorycoast/flood/download/districts.geojson")
async def ivorycoast_districts_geojson(request: Request):
    token = _extract_token(request)
    user  = await _get_user(token) if token else None
    await _log_download(request, "ivorycoast", "flood", "districts.geojson", user["id"] if user else None)
    return _geojson_resp(IVORYCOAST_DIR / "ivorycoast_districts.geojson", "ivorycoast_districts.geojson")


@app.get("/api/ivorycoast/crop/download/csv")
async def ivorycoast_crop_csv(
    request: Request,
    from_date: str | None = Query(None, alias="from"),
    to_date:   str | None = Query(None, alias="to"),
):
    user_id, tier, from_date, to_date = await _auth_and_clamp(request, from_date, to_date)
    await _log_download(request, "ivorycoast", "crop", "csv", user_id, from_date, to_date)
    content = _ndvi_csv(IVORYCOAST_DIR, "ndvi_*_ivorycoast.json", from_date, to_date)
    return _csv_resp(content, "insightsafrica_ivorycoast_crop_ndvi.csv")


@app.get("/api/ivorycoast/heat/download/csv")
async def ivorycoast_heat_csv(
    request: Request,
    from_date: str | None = Query(None, alias="from"),
    to_date:   str | None = Query(None, alias="to"),
):
    user_id, tier, from_date, to_date = await _auth_and_clamp(request, from_date, to_date)
    await _log_download(request, "ivorycoast", "heat", "csv", user_id, from_date, to_date)
    content = _heat_csv(IVORYCOAST_DIR, "heat_*.json", from_date, to_date)
    return _csv_resp(content, "insightsafrica_ivorycoast_heat.csv")


@app.get("/api/ivorycoast/mine/download/csv")
async def ivorycoast_mine_csv(request: Request):
    token = _extract_token(request)
    user  = await _get_user(token) if token else None
    await _log_download(request, "ivorycoast", "mine", "csv", user["id"] if user else None)
    content = _mine_csv(IVORYCOAST_DIR / "ivorycoast_mining_sites.json")
    return _csv_resp(content, "insightsafrica_ivorycoast_mine_sites.csv")


# ── Human Development indicators ─────────────────────────────────────────────

def _indicators_resp(filename: str) -> JSONResponse:
    path = INDICATORS_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Indicators not found. Run scripts/fetch_indicators.py")
    return JSONResponse(content=json.loads(path.read_text()))


@app.get("/api/indicators/ghana")
def ghana_indicators():
    return _indicators_resp("ghana_indicators.json")


@app.get("/api/indicators/nigeria")
def nigeria_indicators():
    return _indicators_resp("nigeria_indicators.json")


@app.get("/api/indicators/ivorycoast")
def ivorycoast_indicators():
    return _indicators_resp("ivorycoast_indicators.json")


# ── Static mounts — AFTER all API routes ──
# Nigeria mounts MUST come before /nigeria root and before Ghana / root

app.mount("/ng-tiles",              StaticFiles(directory=str(NIGERIA_DIR)),                                      name="ng-tiles")
app.mount("/nigeria/flood",         StaticFiles(directory=str(FRONTEND_DIR / "nigeria" / "flood"),    html=True), name="ng-flood")
app.mount("/nigeria/mine",          StaticFiles(directory=str(FRONTEND_DIR / "nigeria" / "mine"),     html=True), name="ng-mine")
app.mount("/nigeria/crop",          StaticFiles(directory=str(FRONTEND_DIR / "nigeria" / "crop"),     html=True), name="ng-crop")
app.mount("/nigeria/heat",          StaticFiles(directory=str(FRONTEND_DIR / "nigeria" / "heat"),     html=True), name="ng-heat")
app.mount("/nigeria/human",         StaticFiles(directory=str(FRONTEND_DIR / "nigeria" / "human"),    html=True), name="ng-human")
app.mount("/nigeria/profile",       StaticFiles(directory=str(FRONTEND_DIR / "nigeria" / "profile"),  html=True), name="ng-profile")
app.mount("/nigeria",               StaticFiles(directory=str(FRONTEND_DIR / "nigeria"),              html=True), name="nigeria")
app.mount("/ic-tiles",              StaticFiles(directory=str(IVORYCOAST_DIR)),                                   name="ic-tiles")
app.mount("/ivorycoast/flood",      StaticFiles(directory=str(FRONTEND_DIR / "ivorycoast" / "flood"), html=True), name="ic-flood")
app.mount("/ivorycoast/mine",       StaticFiles(directory=str(FRONTEND_DIR / "ivorycoast" / "mine"),  html=True), name="ic-mine")
app.mount("/ivorycoast/crop",       StaticFiles(directory=str(FRONTEND_DIR / "ivorycoast" / "crop"),  html=True), name="ic-crop")
app.mount("/ivorycoast/heat",       StaticFiles(directory=str(FRONTEND_DIR / "ivorycoast" / "heat"),  html=True), name="ic-heat")
app.mount("/ivorycoast/human",      StaticFiles(directory=str(FRONTEND_DIR / "ivorycoast" / "human"), html=True), name="ic-human")
app.mount("/ivorycoast/profile",    StaticFiles(directory=str(FRONTEND_DIR / "ivorycoast" / "profile"),html=True),name="ic-profile")
app.mount("/ivorycoast",            StaticFiles(directory=str(FRONTEND_DIR / "ivorycoast"),           html=True), name="ivorycoast")
app.mount("/tiles",                 StaticFiles(directory=str(PROCESSED_DIR)),                                    name="tiles")
app.mount("/flood",                 StaticFiles(directory=str(FRONTEND_DIR / "flood"),                html=True), name="flood")
app.mount("/mine",                  StaticFiles(directory=str(FRONTEND_DIR / "mine"),                 html=True), name="mine")
app.mount("/crop",                  StaticFiles(directory=str(FRONTEND_DIR / "crop"),                 html=True), name="crop")
app.mount("/heat",                  StaticFiles(directory=str(FRONTEND_DIR / "heat"),                 html=True), name="heat")
app.mount("/human",                 StaticFiles(directory=str(FRONTEND_DIR / "human"),                html=True), name="human")
app.mount("/profile",               StaticFiles(directory=str(FRONTEND_DIR / "profile"),              html=True), name="profile")
app.mount("/",                      StaticFiles(directory=str(FRONTEND_DIR),                          html=True), name="home")
