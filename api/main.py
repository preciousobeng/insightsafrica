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

import json
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

load_dotenv()

BASE_DIR      = Path(__file__).parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"
NIGERIA_DIR   = BASE_DIR / "data" / "processed_nigeria"
FRONTEND_DIR  = BASE_DIR / "frontend"

app = FastAPI(title="InsightsAfrica API", version="0.3.0")


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
    return {"status": "ok", "service": "InsightsAfrica", "version": "0.3.0"}


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


# ── Static mounts — AFTER all API routes ──
# Nigeria mounts MUST come before /nigeria root and before Ghana / root

app.mount("/ng-tiles",      StaticFiles(directory=str(NIGERIA_DIR)),                              name="ng-tiles")
app.mount("/nigeria/flood", StaticFiles(directory=str(FRONTEND_DIR / "nigeria" / "flood"), html=True), name="ng-flood")
app.mount("/nigeria/mine",  StaticFiles(directory=str(FRONTEND_DIR / "nigeria" / "mine"),  html=True), name="ng-mine")
app.mount("/nigeria/crop",  StaticFiles(directory=str(FRONTEND_DIR / "nigeria" / "crop"),  html=True), name="ng-crop")
app.mount("/nigeria/heat",  StaticFiles(directory=str(FRONTEND_DIR / "nigeria" / "heat"),  html=True), name="ng-heat")
app.mount("/nigeria",       StaticFiles(directory=str(FRONTEND_DIR / "nigeria"),           html=True), name="nigeria")
app.mount("/tiles",         StaticFiles(directory=str(PROCESSED_DIR)),                             name="tiles")
app.mount("/flood",         StaticFiles(directory=str(FRONTEND_DIR / "flood"), html=True),         name="flood")
app.mount("/mine",          StaticFiles(directory=str(FRONTEND_DIR / "mine"),  html=True),         name="mine")
app.mount("/crop",          StaticFiles(directory=str(FRONTEND_DIR / "crop"),  html=True),         name="crop")
app.mount("/heat",          StaticFiles(directory=str(FRONTEND_DIR / "heat"),  html=True),         name="heat")
app.mount("/",              StaticFiles(directory=str(FRONTEND_DIR),           html=True),         name="home")
