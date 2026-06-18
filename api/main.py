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
import logging
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
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded
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
    except Exception as e:
        logger.warning("auth user lookup failed: %s", e)
    return None


async def _get_tier(user_id: str) -> str:
    """Return 'free' or 'premium' for a user. Defaults to 'free' on any error."""
    if not user_id or not _SUPA_URL:
        return "free"
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            r = await client.get(
                f"{_SUPA_URL}/rest/v1/profiles",
                headers=_supa_headers_service,
                params={"id": f"eq.{user_id}", "select": "tier"},
            )
        if r.status_code == 200:
            rows = r.json()
            if rows:
                return rows[0].get("tier", "free")
    except Exception as e:
        logger.warning("tier lookup failed: %s", e)
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
    except Exception as e:
        logger.warning("download log failed: %s", e)


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
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            r = await client.post(
                f"{_SUPA_URL}/rest/v1/rpc/verify_and_consume_api_key",
                headers=_supa_headers_service,
                json={"key_hash_input": key_hash, "free_limit": _FREE_RPD},
            )
        if r.status_code != 200:
            return None
        row = r.json()
        if not row:
            return None
        return row
    except Exception as e:
        logger.warning("API key verification failed: %s", e)
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
SENEGAL_DIR       = BASE_DIR / "data" / "processed_senegal"
CAPEVERDE_DIR     = BASE_DIR / "data" / "processed_capeverde"
SOUTHAFRICA_DIR   = BASE_DIR / "data" / "processed_southafrica"
INDICATORS_DIR    = BASE_DIR / "data" / "processed_indicators"
ARCHIVE_DIR       = BASE_DIR / "data" / "archive"
FRONTEND_DIR      = BASE_DIR / "frontend"

limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
app = FastAPI(title="InsightsAfrica API", version="0.4.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("insightsafrica")


@app.middleware("http")
async def redirect_https(request: Request, call_next):
    if request.headers.get("x-forwarded-proto") == "http":
        url = str(request.url).replace("http://", "https://", 1)
        return RedirectResponse(url)
    return await call_next(request)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://insightsafrica.org", "https://www.insightsafrica.org"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SlowAPIMiddleware)


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
    except Exception as e:
        logging.error("Contact form SMTP send failed: %s: %s", type(e).__name__, e)
        raise HTTPException(status_code=503, detail="We could not send your message right now. Please email info@insightsafrica.org directly.")

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


# ── Country data-route factory ────────────────────────────────────────────────
# Replaces ~30 copy-pasted flood/crop/heat layer + mine/sites + boundaries routes
# (6 countries) with one registry + 3 factory functions. Each generated route is
# byte-identical to the hand-written original it replaces (same dir, glob, sort,
# JSONResponse, and 400/404 messages). Ghana's unique /api/flood/layers/latest and
# /api/mine/changes are NOT part of this pattern and remain hand-written below.
# Adding a country = one COUNTRY_DATA entry instead of ~50 lines.

COUNTRY_DATA = {
    "ghana": {
        "base": "/api", "dir": PROCESSED_DIR,
        "flood": "chirps-*.json", "crop": "ndvi_*.json", "heat": "heat_*.json",
        "mine_file": "galamsey_sites.json",
        "mine_404": "No site data yet. Run fetch_sentinel2.py",
        "b_prefix": "ghana",
        "b_aliases": {"regions": "regions", "districts": "districts"},
        "b_400": "level must be 'regions' or 'districts'",
        "b_404": "{r} not found. Run fetch_boundaries.py",
    },
    "nigeria": {
        "base": "/api/nigeria", "dir": NIGERIA_DIR,
        "flood": "chirps-*_nigeria.json", "crop": "ndvi_*_nigeria.json", "heat": "heat_*.json",
        "mine_file": "nigeria_mining_sites.json",
        "mine_404": "No Nigeria site data yet. Run fetch_sentinel2.py --country nigeria",
        "b_prefix": "nigeria",
        "b_aliases": {"states": "states", "lgas": "lgas"},
        "b_400": "level must be 'states' or 'lgas'",
        "b_404": "{r} not found. Run fetch_boundaries.py --country nigeria",
    },
    "ivorycoast": {
        "base": "/api/ivorycoast", "dir": IVORYCOAST_DIR,
        "flood": "chirps-*_ivorycoast.json", "crop": "ndvi_*_ivorycoast.json", "heat": "heat_*.json",
        "mine_file": "ivorycoast_mining_sites.json",
        "mine_404": "No Ivory Coast site data yet. Run fetch_sentinel2.py --country ivorycoast",
        "b_prefix": "ivorycoast",
        "b_aliases": {"districts": "districts", "regions": "regions"},
        "b_400": "level must be 'districts' or 'regions'",
        "b_404": "{r} not found. Run fetch_boundaries.py --country ivorycoast",
    },
    "senegal": {
        "base": "/api/senegal", "dir": SENEGAL_DIR,
        "flood": "chirps-*_senegal.json", "crop": "ndvi_*_senegal.json", "heat": "heat_*.json",
        "mine_file": "senegal_mining_sites.json",
        "mine_404": "No Senegal site data yet.",
        "b_prefix": "senegal",
        "b_aliases": {"districts": "departments", "departments": "departments", "regions": "regions"},
        "b_400": "level must be 'regions' or 'departments'",
        "b_404": "{r} not found. Run fetch_boundaries.py --country senegal",
    },
    "capeverde": {
        "base": "/api/capeverde", "dir": CAPEVERDE_DIR,
        "flood": "chirps-*_capeverde.json", "crop": "ndvi_*_capeverde.json", "heat": "heat_*.json",
        "mine_file": "capeverde_mining_sites.json",
        "mine_404": "No Cape Verde site data yet. Run fetch_sentinel2.py --country capeverde",
        "b_prefix": "capeverde",
        "b_aliases": {"islands": "islands"},
        "b_400": "level must be 'islands'",
        "b_404": "{r} not found. Run fetch_boundaries.py --country capeverde",
    },
    "southafrica": {
        "base": "/api/southafrica", "dir": SOUTHAFRICA_DIR,
        "flood": "chirps-*_southafrica.json", "crop": "ndvi_*_southafrica.json", "heat": "heat_*.json",
        "mine_file": "southafrica_mining_sites.json",
        "mine_404": "No SA site data yet. Run fetch_sentinel2.py --country southafrica",
        "b_prefix": "southafrica",
        "b_aliases": {"provinces": "provinces", "districts": "districts"},
        "b_400": "level must be 'provinces' or 'districts'",
        "b_404": "Boundary data not yet available",
    },
}


def _make_layers_route(directory, pattern):
    def handler():
        layers = []
        for f in sorted(directory.glob(pattern)):
            with open(f) as fh:
                layers.append(json.load(fh))
        return JSONResponse(content=layers)
    return handler


def _make_sites_route(directory, filename, not_found_detail):
    def handler():
        sites_path = directory / filename
        if not sites_path.exists():
            raise HTTPException(status_code=404, detail=not_found_detail)
        with open(sites_path) as f:
            return JSONResponse(content=json.load(f))
    return handler


def _make_boundaries_route(directory, file_prefix, aliases, bad_level_detail, not_found_tmpl):
    def handler(level: str):
        resolved = aliases.get(level)
        if resolved is None:
            raise HTTPException(status_code=400, detail=bad_level_detail)
        path = directory / f"{file_prefix}_{resolved}.geojson"
        if not path.exists():
            raise HTTPException(status_code=404, detail=not_found_tmpl.format(r=resolved))
        with open(path) as f:
            return JSONResponse(content=json.load(f))
    return handler


for _slug, _cfg in COUNTRY_DATA.items():
    _base = _cfg["base"]
    app.get(f"{_base}/flood/layers")(_make_layers_route(_cfg["dir"], _cfg["flood"]))
    app.get(f"{_base}/crop/layers")(_make_layers_route(_cfg["dir"], _cfg["crop"]))
    app.get(f"{_base}/heat/layers")(_make_layers_route(_cfg["dir"], _cfg["heat"]))
    app.get(f"{_base}/mine/sites")(_make_sites_route(_cfg["dir"], _cfg["mine_file"], _cfg["mine_404"]))
    app.get(f"{_base}/boundaries/{{level}}")(
        _make_boundaries_route(_cfg["dir"], _cfg["b_prefix"], _cfg["b_aliases"], _cfg["b_400"], _cfg["b_404"])
    )


# --- FloodWatch ---

@app.get("/api/flood/layers/latest")
def flood_latest():
    meta_files = sorted(PROCESSED_DIR.glob("chirps-*.json"))
    if not meta_files:
        raise HTTPException(status_code=404, detail="No flood layers available")
    with open(meta_files[-1]) as f:
        return JSONResponse(content=json.load(f))


# --- MineWatch ---

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


# ── Senegal API routes ────────────────────────────────────────────────────────

@app.get("/senegal")
@app.get("/senegal/")
def senegal_hub():
    return RedirectResponse(url="/senegal/hub.html")


# ── Cape Verde API routes ─────────────────────────────────────────────────────

@app.get("/capeverde")
@app.get("/capeverde/")
def capeverde_hub():
    return RedirectResponse(url="/capeverde/hub.html")


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


# ── Download route factory ────────────────────────────────────────────────────
# Generates the uniform crop/heat/mine CSV + geojson download routes for the 4
# countries that have them. Byte-identical to the hand-written originals (same
# helpers: _auth_and_clamp / _log_download / _ndvi_csv / _heat_csv / _mine_csv /
# _geojson_resp / _csv_resp). Flood CSV (per-country Literal `level`) and South
# Africa's geojson downloads (different content-type, no auth/log) stay hand-written.

_DL_COUNTRIES = {
    "ghana":      {"dir": PROCESSED_DIR,  "base": "/api",            "crop_glob": "ndvi_*_ghana.json",      "mine_file": "galamsey_sites.json"},
    "nigeria":    {"dir": NIGERIA_DIR,    "base": "/api/nigeria",    "crop_glob": "ndvi_*_nigeria.json",    "mine_file": "nigeria_mining_sites.json"},
    "ivorycoast": {"dir": IVORYCOAST_DIR, "base": "/api/ivorycoast", "crop_glob": "ndvi_*_ivorycoast.json", "mine_file": "ivorycoast_mining_sites.json"},
    "senegal":    {"dir": SENEGAL_DIR,    "base": "/api/senegal",    "crop_glob": "ndvi_*_senegal.json",    "mine_file": "senegal_mining_sites.json"},
}

# (route_path, file_path, download_filename, country, log_label)
_DL_GEOJSON = [
    ("/api/flood/download/regions.geojson",              PROCESSED_DIR  / "ghana_regions.geojson",        "ghana_regions.geojson",        "ghana",      "regions.geojson"),
    ("/api/flood/download/districts.geojson",            PROCESSED_DIR  / "ghana_districts.geojson",      "ghana_districts.geojson",      "ghana",      "districts.geojson"),
    ("/api/nigeria/flood/download/states.geojson",       NIGERIA_DIR    / "nigeria_states.geojson",       "nigeria_states.geojson",       "nigeria",    "states.geojson"),
    ("/api/nigeria/flood/download/lgas.geojson",         NIGERIA_DIR    / "nigeria_lgas.geojson",         "nigeria_lgas.geojson",         "nigeria",    "lgas.geojson"),
    ("/api/ivorycoast/flood/download/districts.geojson", IVORYCOAST_DIR / "ivorycoast_districts.geojson", "ivorycoast_districts.geojson", "ivorycoast", "districts.geojson"),
    ("/api/senegal/flood/download/districts.geojson",    SENEGAL_DIR    / "senegal_departments.geojson",  "senegal_departments.geojson",  "senegal",    "districts.geojson"),
    ("/api/senegal/flood/download/departments.geojson",  SENEGAL_DIR    / "senegal_departments.geojson",  "senegal_departments.geojson",  "senegal",    "departments.geojson"),
    ("/api/senegal/flood/download/regions.geojson",      SENEGAL_DIR    / "senegal_regions.geojson",      "senegal_regions.geojson",      "senegal",    "regions.geojson"),
]


def _make_crop_csv_dl(directory, glob, filename, country):
    async def handler(request: Request,
                      from_date: str | None = Query(None, alias="from"),
                      to_date: str | None = Query(None, alias="to")):
        user_id, tier, from_date, to_date = await _auth_and_clamp(request, from_date, to_date)
        await _log_download(request, country, "crop", "csv", user_id, from_date, to_date)
        content = _ndvi_csv(directory, glob, from_date, to_date)
        return _csv_resp(content, filename)
    return handler


def _make_heat_csv_dl(directory, filename, country):
    async def handler(request: Request,
                      from_date: str | None = Query(None, alias="from"),
                      to_date: str | None = Query(None, alias="to")):
        user_id, tier, from_date, to_date = await _auth_and_clamp(request, from_date, to_date)
        await _log_download(request, country, "heat", "csv", user_id, from_date, to_date)
        content = _heat_csv(directory, "heat_*.json", from_date, to_date)
        return _csv_resp(content, filename)
    return handler


def _make_mine_csv_dl(sites_path, filename, country):
    async def handler(request: Request):
        token = _extract_token(request)
        user = await _get_user(token) if token else None
        await _log_download(request, country, "mine", "csv", user["id"] if user else None)
        content = _mine_csv(sites_path)
        return _csv_resp(content, filename)
    return handler


def _make_geojson_dl(file_path, filename, country, label):
    async def handler(request: Request):
        token = _extract_token(request)
        user = await _get_user(token) if token else None
        await _log_download(request, country, "flood", label, user["id"] if user else None)
        return _geojson_resp(file_path, filename)
    return handler


for _slug, _d in _DL_COUNTRIES.items():
    _b = _d["base"]
    app.get(f"{_b}/crop/download/csv")(
        _make_crop_csv_dl(_d["dir"], _d["crop_glob"], f"insightsafrica_{_slug}_crop_ndvi.csv", _slug)
    )
    app.get(f"{_b}/heat/download/csv")(
        _make_heat_csv_dl(_d["dir"], f"insightsafrica_{_slug}_heat.csv", _slug)
    )
    app.get(f"{_b}/mine/download/csv")(
        _make_mine_csv_dl(_d["dir"] / _d["mine_file"], f"insightsafrica_{_slug}_mine_sites.csv", _slug)
    )

for _route, _fp, _fn, _ctry, _label in _DL_GEOJSON:
    app.get(_route)(_make_geojson_dl(_fp, _fn, _ctry, _label))


# ── Ghana download endpoints (flood CSV only; crop/heat/mine/geojson via factory) ──

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


# ── Nigeria download endpoints (flood CSV only; rest via factory) ──

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


# ── Ivory Coast download endpoints (flood CSV only; rest via factory) ──

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


# ── Senegal download endpoints (flood CSV only; rest via factory) ──

@app.get("/api/senegal/flood/download/csv")
async def senegal_flood_csv(
    request: Request,
    level: Literal["departments", "districts", "regions"] = Query("departments"),
    from_date: str | None = Query(None, alias="from"),
    to_date:   str | None = Query(None, alias="to"),
):
    resolved_level = "departments" if level == "districts" else level
    user_id, tier, from_date, to_date = await _auth_and_clamp(request, from_date, to_date)
    await _log_download(request, "senegal", "flood", "csv", user_id, from_date, to_date)
    content = _chirps_csv(SENEGAL_DIR, "chirps-*_senegal.json", resolved_level, from_date, to_date, country="senegal")
    return _csv_resp(content, f"insightsafrica_senegal_flood_{resolved_level}.csv")


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


@app.get("/api/indicators/senegal")
def senegal_indicators():
    return _indicators_resp("senegal_indicators.json")

@app.get("/api/indicators/southafrica")
def southafrica_indicators():
    return _indicators_resp("southafrica_indicators.json")


# ── Anomaly + baseline routes ────────────────────────────────────────────────

_ARCHIVE_COUNTRIES = {
    "ghana", "nigeria", "ivorycoast", "senegal", "capeverde", "southafrica"
}


def _validate_country(country: str) -> None:
    if country not in _ARCHIVE_COUNTRIES:
        raise HTTPException(status_code=404, detail=f"Unknown country: {country}")


def _safe_path(path: Path) -> Path:
    """Resolve path and assert it stays within ARCHIVE_DIR."""
    resolved = path.resolve()
    if not resolved.is_relative_to(ARCHIVE_DIR.resolve()):
        raise HTTPException(status_code=400, detail="Invalid path")
    return resolved


@app.get("/api/{country}/flood/baseline")
def flood_baseline(country: str):
    """WMO 1991-2020 LTM baseline for the given country."""
    _validate_country(country)
    path = _safe_path(ARCHIVE_DIR / country / f"{country}_ltm_1991_2020.json")
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Baseline not found for {country}. Run compute_ltm_baseline.py --country {country}",
        )
    return JSONResponse(content=json.loads(path.read_text()))


@app.get("/api/{country}/flood/anomaly/{year}/{month}")
def flood_anomaly(country: str, year: int, month: int):
    """Pre-computed rainfall anomaly vs WMO LTM baseline for a given month."""
    _validate_country(country)
    if not 1 <= month <= 12:
        raise HTTPException(status_code=400, detail="month must be 1-12")
    path = _safe_path(
        ARCHIVE_DIR / country / "anomaly" / f"chirps-v2.0.{year}.{month:02d}_{country}_anomaly.json"
    )
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Anomaly not found for {country} {year}-{month:02d}. Run precompute_anomalies.py --country {country}",
        )
    return JSONResponse(content=json.loads(path.read_text()))


@app.get("/api/{country}/flood/anomaly")
def flood_anomaly_index(country: str):
    """List all available anomaly months for a country."""
    _validate_country(country)
    anomaly_dir = _safe_path(ARCHIVE_DIR / country / "anomaly")
    if not anomaly_dir.exists():
        raise HTTPException(status_code=404, detail=f"No anomaly data for {country}")
    months = []
    for f in sorted(anomaly_dir.glob(f"chirps-v2.0.*_{country}_anomaly.json")):
        data = json.loads(f.read_text())
        months.append({"year": data["year"], "month": data["month"]})
    return JSONResponse(content={"country": country, "available_months": months})


# ── South Africa downloads (layers/sites/boundaries handled by the factory above) ──
@app.get("/api/southafrica/flood/download/provinces.geojson")
def sa_flood_provinces():
    path = SOUTHAFRICA_DIR / "southafrica_provinces.geojson"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Not available")
    return JSONResponse(content=json.loads(path.read_text()))

@app.get("/api/southafrica/flood/download/districts.geojson")
def sa_flood_districts():
    path = SOUTHAFRICA_DIR / "southafrica_districts.geojson"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Not available")
    return JSONResponse(content=json.loads(path.read_text()))


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
app.mount("/sn-tiles",              StaticFiles(directory=str(SENEGAL_DIR)),                                       name="sn-tiles")
app.mount("/senegal/flood",         StaticFiles(directory=str(FRONTEND_DIR / "senegal" / "flood"),    html=True), name="sn-flood")
app.mount("/senegal/mine",          StaticFiles(directory=str(FRONTEND_DIR / "senegal" / "mine"),     html=True), name="sn-mine")
app.mount("/senegal/crop",          StaticFiles(directory=str(FRONTEND_DIR / "senegal" / "crop"),     html=True), name="sn-crop")
app.mount("/senegal/heat",          StaticFiles(directory=str(FRONTEND_DIR / "senegal" / "heat"),     html=True), name="sn-heat")
app.mount("/senegal/human",         StaticFiles(directory=str(FRONTEND_DIR / "senegal" / "human"),    html=True), name="sn-human")
app.mount("/senegal/profile",       StaticFiles(directory=str(FRONTEND_DIR / "senegal" / "profile"),  html=True), name="sn-profile")
app.mount("/senegal",               StaticFiles(directory=str(FRONTEND_DIR / "senegal"),              html=True), name="senegal")
app.mount("/za-tiles",              StaticFiles(directory=str(SOUTHAFRICA_DIR)),                                       name="za-tiles")
app.mount("/southafrica/flood",     StaticFiles(directory=str(FRONTEND_DIR / "southafrica" / "flood"),   html=True), name="za-flood")
app.mount("/southafrica/mine",      StaticFiles(directory=str(FRONTEND_DIR / "southafrica" / "mine"),    html=True), name="za-mine")
app.mount("/southafrica/crop",      StaticFiles(directory=str(FRONTEND_DIR / "southafrica" / "crop"),    html=True), name="za-crop")
app.mount("/southafrica/heat",      StaticFiles(directory=str(FRONTEND_DIR / "southafrica" / "heat"),    html=True), name="za-heat")
app.mount("/southafrica/human",     StaticFiles(directory=str(FRONTEND_DIR / "southafrica" / "human"),   html=True), name="za-human")
app.mount("/southafrica/profile",   StaticFiles(directory=str(FRONTEND_DIR / "southafrica" / "profile"), html=True), name="za-profile")
app.mount("/southafrica",           StaticFiles(directory=str(FRONTEND_DIR / "southafrica"),              html=True), name="southafrica")
app.mount("/cv-tiles",              StaticFiles(directory=str(CAPEVERDE_DIR)),                                      name="cv-tiles")
app.mount("/capeverde/flood",      StaticFiles(directory=str(FRONTEND_DIR / "capeverde" / "flood"),  html=True), name="cv-flood")
app.mount("/capeverde/mine",       StaticFiles(directory=str(FRONTEND_DIR / "capeverde" / "mine"),   html=True), name="cv-mine")
app.mount("/capeverde/crop",       StaticFiles(directory=str(FRONTEND_DIR / "capeverde" / "crop"),   html=True), name="cv-crop")
app.mount("/capeverde/heat",       StaticFiles(directory=str(FRONTEND_DIR / "capeverde" / "heat"),   html=True), name="cv-heat")
app.mount("/capeverde/human",      StaticFiles(directory=str(FRONTEND_DIR / "capeverde" / "human"),  html=True), name="cv-human")
app.mount("/capeverde/profile",    StaticFiles(directory=str(FRONTEND_DIR / "capeverde" / "profile"),html=True), name="cv-profile")
app.mount("/capeverde",            StaticFiles(directory=str(FRONTEND_DIR / "capeverde"),             html=True), name="capeverde")
app.mount("/tiles",                 StaticFiles(directory=str(PROCESSED_DIR)),                                    name="tiles")
app.mount("/flood",                 StaticFiles(directory=str(FRONTEND_DIR / "flood"),                html=True), name="flood")
app.mount("/mine",                  StaticFiles(directory=str(FRONTEND_DIR / "mine"),                 html=True), name="mine")
app.mount("/crop",                  StaticFiles(directory=str(FRONTEND_DIR / "crop"),                 html=True), name="crop")
app.mount("/heat",                  StaticFiles(directory=str(FRONTEND_DIR / "heat"),                 html=True), name="heat")
app.mount("/human",                 StaticFiles(directory=str(FRONTEND_DIR / "human"),                html=True), name="human")
app.mount("/profile",               StaticFiles(directory=str(FRONTEND_DIR / "profile"),              html=True), name="profile")
app.mount("/",                      StaticFiles(directory=str(FRONTEND_DIR),                          html=True), name="home")
