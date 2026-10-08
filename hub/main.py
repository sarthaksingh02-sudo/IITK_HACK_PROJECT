"""
hub/main.py
FastAPI app for the Village Hub.
Serves the complete offline-first API and rich PWA interface for rural households.
Features:
  - Sarvam AI 9 Indian Languages + English full-flow translation dropdown
  - Deterministic eligibility evaluator
  - Feature K suggestions with pathway guidance
  - Family health module (NIS immunization & NHM red flags)
  - Reminders scheduler with Fast-Forward simulation control
  - Ed25519 verified Tier 0 broadcast packet ingestion
"""

from __future__ import annotations

import json
import os
import pathlib
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import Body, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

load_dotenv()

from shared.rule_engine import check_eligibility, compute_age, match_household
from shared.sarvam_client import SARVAM_LANGUAGES, translate_with_sarvam
from hub.db import (
    HubHealthRecord,
    HubHousehold,
    HubMatchResult,
    HubOpportunity,
    HubOutbox,
    HubPerson,
    HubReminder,
    HubSuggestion,
    HubTracking,
    HubUpdate,
    PacketLedger,
    get_db,
    init_db,
)
from hub.health import get_person_health_summary
from hub.reminders import evaluate_household_reminders
from hub.suggestions import convert_db_to_opportunity, convert_db_to_person, generate_person_suggestions
from hub.transport.file_transport import FileTransport
from hub.voice import process_voice_query

transport = FileTransport()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    count = transport.scan_and_ingest_all()
    if count > 0:
        print(f"[hub/startup] Ingested {count} broadcast packet(s).")
    yield


app = FastAPI(
    title="AccessAI Village Hub",
    description="Offline-First Village Hub for Rural Households (AVINYA 2K26) with Sarvam AI Indian Languages.",
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic Schemas ──────────────────────────────────────────────────────────

class CreateHouseholdRequest(BaseModel):
    village: str
    district: str
    state: str = "Uttar Pradesh"
    consent_given: bool = True


class CreatePersonRequest(BaseModel):
    name: str
    dob: str  # YYYY-MM-DD
    gender: str  # M, F, other
    relation: str = "member"
    education: str = "none"
    category: str = "GEN"
    is_disabled: bool = False
    occupation: Optional[str] = None
    skills: list[str] = []
    interests: list[str] = []
    languages: list[str] = ["Hindi"]
    land_acres: Optional[float] = None
    assets: list[str] = []


class TranslateRequest(BaseModel):
    text: str
    target_lang: str
    source_lang: str = "en"


# ── Health, Transport & Sarvam Languages ──────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "hub",
        "transport": os.getenv("HUB_TRANSPORT", "file"),
        "offline_mode": True,
        "sarvam_languages_count": len(SARVAM_LANGUAGES),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/languages")
def get_languages():
    """Returns the 9 Indian languages + English supported by Sarvam AI."""
    return {"languages": SARVAM_LANGUAGES}


@app.post("/api/translate")
def translate_api(req: TranslateRequest):
    """Translates text to any of the 9 Indian languages or English via Sarvam AI."""
    translated = translate_with_sarvam(req.text, req.target_lang, req.source_lang)
    return {
        "original": req.text,
        "translated": translated,
        "target_lang": req.target_lang,
        "engine": "sarvam-ai",
    }


@app.post("/api/transport/scan")
def trigger_transport_scan():
    """Forces immediate check of packets/ folder for new broadcast packets."""
    new_count = transport.scan_and_ingest_all()
    return {"status": "success", "new_packets_ingested": new_count}


@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db)):
    opp_count = db.query(HubOpportunity).count()
    hh_count = db.query(HubHousehold).count()
    person_count = db.query(HubPerson).count()
    verified_packets = db.query(PacketLedger).filter(PacketLedger.verified == 1).count()

    return {
        "active_opportunities": opp_count,
        "registered_households": hh_count,
        "village_residents": person_count,
        "verified_broadcast_packets": verified_packets,
        "connectivity_tier": "Tier 1 (Offline Village Hub)",
    }


# ── Opportunities ─────────────────────────────────────────────────────────────

@app.get("/api/opportunities")
def list_opportunities(
    type: Optional[str] = None,
    lang: Optional[str] = "hi",
    db: Session = Depends(get_db),
):
    query = db.query(HubOpportunity)
    if type:
        query = query.filter(HubOpportunity.type == type)
    opps = query.order_by(HubOpportunity.priority.desc()).all()

    items = []
    for o in opps:
        # Localized title
        localized_title = o.title_hi if lang == "hi" and o.title_hi else o.title
        if lang and lang not in ("en", "hi"):
            localized_title = translate_with_sarvam(o.title, target_lang=lang)

        items.append({
            "id": o.id,
            "type": o.type,
            "title": o.title,
            "title_hi": o.title_hi,
            "title_localized": localized_title,
            "org": o.org,
            "level": o.level,
            "geo_state": o.geo_state,
            "geo_district": o.geo_district,
            "eligibility": json.loads(o.eligibility_json) if o.eligibility_json else {},
            "dates": json.loads(o.dates_json) if o.dates_json else {},
            "documents_required": json.loads(o.documents_json) if o.documents_json else [],
            "fee": o.fee,
            "apply_mode": o.apply_mode,
            "apply_steps": json.loads(o.apply_steps_json) if o.apply_steps_json else [],
            "source_url": o.source_url,
            "priority": o.priority,
            "synced_at": o.synced_at,
        })
    return {"items": items, "count": len(items)}


@app.get("/api/opportunities/{opp_id}")
def get_opportunity(opp_id: str, db: Session = Depends(get_db)):
    o = db.get(HubOpportunity, opp_id)
    if not o:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    return {
        "id": o.id,
        "type": o.type,
        "title": o.title,
        "title_hi": o.title_hi,
        "org": o.org,
        "level": o.level,
        "geo": {"state": o.geo_state, "district": o.geo_district, "block": o.geo_block},
        "eligibility": json.loads(o.eligibility_json) if o.eligibility_json else {},
        "dates": json.loads(o.dates_json) if o.dates_json else {},
        "documents_required": json.loads(o.documents_json) if o.documents_json else [],
        "fee": o.fee,
        "apply_mode": o.apply_mode,
        "apply_steps": json.loads(o.apply_steps_json) if o.apply_steps_json else [],
        "source_url": o.source_url,
        "priority": o.priority,
        "synced_at": o.synced_at,
    }


# ── Households & Profiles ─────────────────────────────────────────────────────

@app.get("/api/households")
def list_households(db: Session = Depends(get_db)):
    hhs = db.query(HubHousehold).all()
    res = []
    for h in hhs:
        members = db.query(HubPerson).filter(HubPerson.household_id == h.id).all()
        res.append({
            "id": h.id,
            "village": h.village,
            "district": h.district,
            "state": h.state,
            "consent_given_at": h.consent_given_at,
            "member_count": len(members),
            "members": [
                {
                    "id": m.id,
                    "name": m.name,
                    "dob": m.dob,
                    "gender": m.gender,
                    "relation": m.relation,
                    "education": m.education,
                    "category": m.category,
                    "occupation": m.occupation,
                    "skills": json.loads(m.skills_json) if m.skills_json else [],
                    "interests": json.loads(m.interests_json) if m.interests_json else [],
                    "land_acres": m.land_acres,
                    "is_test_persona": m.is_test_persona,
                }
                for m in members
            ],
        })
    return {"items": res}


@app.post("/api/households")
def create_household(req: CreateHouseholdRequest, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc).isoformat()
    hh_id = f"hh-{uuid.uuid4().hex[:8]}"
    hh = HubHousehold(
        id=hh_id,
        village=req.village,
        district=req.district,
        state=req.state,
        created_at=now,
        consent_given_at=now if req.consent_given else None,
    )
    db.add(hh)
    db.commit()
    return {"success": True, "household_id": hh_id}


@app.post("/api/households/{hh_id}/people")
def add_person(hh_id: str, req: CreatePersonRequest, db: Session = Depends(get_db)):
    hh = db.get(HubHousehold, hh_id)
    if not hh:
        raise HTTPException(status_code=404, detail="Household not found")

    now = datetime.now(timezone.utc).isoformat()
    p_id = f"p-{uuid.uuid4().hex[:8]}"
    person = HubPerson(
        id=p_id,
        household_id=hh_id,
        name=req.name,
        dob=req.dob,
        gender=req.gender,
        relation=req.relation,
        education=req.education,
        category=req.category,
        is_disabled=req.is_disabled,
        occupation=req.occupation,
        skills_json=json.dumps(req.skills),
        interests_json=json.dumps(req.interests),
        languages_json=json.dumps(req.languages),
        land_acres=req.land_acres,
        assets_json=json.dumps(req.assets),
        created_at=now,
        is_test_persona=False,
    )
    db.add(person)
    db.commit()
    return {"success": True, "person_id": p_id}


# ── Deterministic Matching & Suggestions (Feature K) ──────────────────────────

@app.get("/api/match/household/{hh_id}")
def match_household_route(hh_id: str, db: Session = Depends(get_db)):
    """Runs deterministic eligibility matrix for all family members against all opportunities."""
    hh = db.get(HubHousehold, hh_id)
    if not hh:
        raise HTTPException(status_code=404, detail="Household not found")

    members = db.query(HubPerson).filter(HubPerson.household_id == hh_id).all()
    opps = db.query(HubOpportunity).all()

    person_models = [convert_db_to_person(m) for m in members]
    opp_models = [convert_db_to_opportunity(o) for o in opps]

    results_matrix = match_household(person_models, opp_models)

    formatted = []
    for r in results_matrix:
        p_obj = next((m for m in members if m.id == r.person_id), None)
        o_obj = next((o for o in opps if o.id == r.opportunity_id), None)
        formatted.append({
            "person_id": r.person_id,
            "person_name": p_obj.name if p_obj else r.person_id,
            "opportunity_id": r.opportunity_id,
            "opportunity_title": o_obj.title if o_obj else r.opportunity_id,
            "opportunity_title_hi": o_obj.title_hi if o_obj else None,
            "status": r.status.value,
            "reasons": [r.reason] if r.reason else [],
            "question": r.question,
        })

    return {"household_id": hh_id, "matches": formatted}


@app.get("/api/suggestions/{person_id}")
def get_suggestions_route(
    person_id: str,
    lang: Optional[str] = "hi",
    db: Session = Depends(get_db),
):
    """Feature K: Returns ranked recommendations with 'Why this fits', pathways, and citations."""
    person = db.get(HubPerson, person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    opps = db.query(HubOpportunity).all()
    suggestions = generate_person_suggestions(person, opps)

    # If non-English/non-Hindi language requested, translate dynamically
    if lang and lang not in ("en", "hi"):
        for s in suggestions:
            s["title_localized"] = translate_with_sarvam(s["title"], target_lang=lang)
            if s.get("why_fit"):
                s["why_fit_localized"] = translate_with_sarvam(s["why_fit"], target_lang=lang)

    return {
        "person_id": person.id,
        "person_name": person.name,
        "suggestions": suggestions,
        "total": len(suggestions),
    }


# ── Health Module ─────────────────────────────────────────────────────────────

@app.get("/api/health/{person_id}")
def get_health_route(person_id: str, db: Session = Depends(get_db)):
    """Returns NIS child immunization schedule and NHM red-flag referral advice."""
    person = db.get(HubPerson, person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    summary = get_person_health_summary(person)
    return summary


# ── Reminders & Fast-Forward Simulator ────────────────────────────────────────

@app.get("/api/reminders")
def get_reminders_route(
    fast_forward_days: int = Query(0, ge=0, le=365),
    db: Session = Depends(get_db),
):
    """Generates countdown alerts for deadlines and document lead times."""
    people = db.query(HubPerson).all()
    opps = db.query(HubOpportunity).all()

    reminders = evaluate_household_reminders(people, opps, fast_forward_days=fast_forward_days)
    simulated_date = (date.today() + timedelta(days=fast_forward_days)).isoformat()

    return {
        "reference_date": simulated_date,
        "fast_forward_days": fast_forward_days,
        "active_reminders": reminders,
        "count": len(reminders),
    }


# ── PWA Frontend UI ───────────────────────────────────────────────────────────

from fastapi.staticfiles import StaticFiles

REACT_DIST_DIR = pathlib.Path(__file__).parent.parent / "frontend" / "dist"
if (REACT_DIST_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(REACT_DIST_DIR / "assets")), name="assets")


@app.get("/", response_class=HTMLResponse)
def pwa_ui():
    """Serves the rich React PWA interface with Sarvam 9 Indian Languages + English dropdown."""
    if (REACT_DIST_DIR / "index.html").exists():
        return HTMLResponse(content=(REACT_DIST_DIR / "index.html").read_text(encoding="utf-8"))
    return HTMLResponse(content=_HUB_PWA_HTML)


_HUB_PWA_HTML = """<!DOCTYPE html>
<html lang="hi">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
  <title>AccessAI Village Hub | ग्रामीण जन सेवा केंद्र</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #090d16;
      --card: rgba(20, 29, 48, 0.85);
      --card-border: rgba(255, 255, 255, 0.08);
      --primary: #3b82f6;
      --primary-glow: rgba(59, 130, 246, 0.35);
      --accent-green: #10b981;
      --accent-amber: #f59e0b;
      --accent-red: #ef4444;
      --text: #f3f4f6;
      --text-muted: #94a3b8;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
    body {
      background: radial-gradient(circle at 15% 15%, rgba(37, 99, 235, 0.15) 0%, transparent 45%),
                  radial-gradient(circle at 85% 85%, rgba(16, 185, 129, 0.1) 0%, transparent 45%),
                  var(--bg);
      color: var(--text);
      font-family: 'Plus Jakarta Sans', sans-serif;
      min-height: 100vh;
      padding-bottom: 40px;
    }
    
    /* Top Header */
    .header {
      background: rgba(11, 15, 25, 0.92);
      backdrop-filter: blur(16px);
      position: sticky;
      top: 0;
      z-index: 50;
      padding: 16px 20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid var(--card-border);
    }
    .brand { display: flex; align-items: center; gap: 12px; }
    .brand-icon {
      width: 42px; height: 42px; border-radius: 12px;
      background: linear-gradient(135deg, #2563eb, #10b981);
      display: flex; align-items: center; justify-content: center;
      font-size: 22px; box-shadow: 0 4px 16px var(--primary-glow);
    }
    .brand-title { font-family: 'Outfit', sans-serif; font-size: 20px; font-weight: 800; letter-spacing: -0.5px; }
    .brand-sub { font-size: 11px; color: var(--text-muted); }
    
    /* Right Corner Language Dropdown */
    .lang-dropdown-container {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .lang-select {
      background: rgba(22, 30, 49, 0.95);
      border: 1px solid rgba(59, 130, 246, 0.4);
      color: #fff;
      font-family: 'Plus Jakarta Sans', sans-serif;
      font-weight: 700;
      font-size: 13px;
      padding: 8px 14px;
      border-radius: 14px;
      outline: none;
      cursor: pointer;
      box-shadow: 0 2px 10px rgba(0,0,0,0.3);
      transition: all 0.2s ease;
    }
    .lang-select:focus, .lang-select:hover {
      border-color: var(--primary);
      box-shadow: 0 0 12px var(--primary-glow);
    }
    
    .container { max-width: 920px; margin: 0 auto; padding: 20px; }
    
    /* Tier Status Banner */
    .tier-banner {
      background: linear-gradient(135deg, rgba(37, 99, 235, 0.15), rgba(16, 185, 129, 0.15));
      border: 1px solid rgba(59, 130, 246, 0.3);
      border-radius: 16px;
      padding: 14px 18px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 20px;
    }
    
    /* Grid Navigation Icons */
    .nav-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 12px;
      margin-bottom: 24px;
    }
    @media (max-width: 600px) { .nav-grid { grid-template-columns: repeat(2, 1fr); } }
    
    .nav-card {
      background: var(--card);
      border: 1px solid var(--card-border);
      border-radius: 18px;
      padding: 18px 14px;
      display: flex;
      flex-direction: column;
      align-items: center;
      text-align: center;
      cursor: pointer;
      transition: all 0.2s;
    }
    .nav-card:hover, .nav-card.active {
      transform: translateY(-2px);
      border-color: var(--primary);
      background: rgba(37, 99, 235, 0.12);
      box-shadow: 0 6px 20px rgba(59, 130, 246, 0.2);
    }
    .nav-emoji { font-size: 32px; margin-bottom: 8px; }
    .nav-label { font-family: 'Outfit', sans-serif; font-size: 14px; font-weight: 700; color: #fff; }
    .nav-sub { font-size: 11px; color: var(--text-muted); margin-top: 2px; }
    
    /* Content Sections */
    .section { display: none; }
    .section.active { display: block; animation: fadeIn 0.3s ease; }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
    
    /* Cards */
    .card {
      background: var(--card);
      backdrop-filter: blur(16px);
      border: 1px solid var(--card-border);
      border-radius: 20px;
      padding: 20px;
      margin-bottom: 16px;
      box-shadow: 0 4px 24px rgba(0,0,0,0.25);
    }
    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 12px;
    }
    .card-title { font-family: 'Outfit', sans-serif; font-size: 17px; font-weight: 700; color: #fff; line-height: 1.3; }
    .card-org { font-size: 12px; color: var(--text-muted); margin-top: 4px; }
    
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 4px 10px;
      border-radius: 9999px;
      font-size: 11px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .badge-eligible { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); }
    .badge-possible { background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.4); }
    .badge-not { background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4); }
    
    .why-fit-box {
      background: rgba(59, 130, 246, 0.1);
      border-left: 3px solid var(--primary);
      padding: 10px 14px;
      border-radius: 0 10px 10px 0;
      font-size: 13px;
      margin: 10px 0;
      line-height: 1.4;
    }
    .pathway-box {
      background: rgba(245, 158, 11, 0.1);
      border-left: 3px solid var(--accent-amber);
      padding: 10px 14px;
      border-radius: 0 10px 10px 0;
      font-size: 12px;
      margin: 10px 0;
    }
    
    .disclaimer-alert {
      background: rgba(239, 68, 68, 0.1);
      border: 1px solid rgba(239, 68, 68, 0.3);
      color: #fca5a5;
      padding: 12px 16px;
      border-radius: 12px;
      font-size: 12px;
      margin-bottom: 16px;
      line-height: 1.4;
    }
  </style>
</head>
<body>

  <!-- Top Header with Right Corner Language Dropdown -->
  <div class="header">
    <div class="brand">
      <div class="brand-icon">🏛️</div>
      <div>
        <div class="brand-title">AccessAI Village Hub</div>
        <div class="brand-sub" id="lbl-sub">ग्रामीण जन सुविधा एवं अवसर केंद्र</div>
      </div>
    </div>
    
    <!-- Right-most Sarvam AI 9 Indian Languages + English Selector -->
    <div class="lang-dropdown-container">
      <span style="font-size: 16px;">🌐</span>
      <select id="global-lang-select" class="lang-select" onchange="setGlobalLang(this.value)">
        <option value="hi" selected>🇮🇳 हिन्दी (Hindi)</option>
        <option value="bn">🇮🇳 বাংলা (Bengali)</option>
        <option value="te">🇮🇳 తెలుగు (Telugu)</option>
        <option value="mr">🇮🇳 मराठी (Marathi)</option>
        <option value="ta">🇮🇳 தமிழ் (Tamil)</option>
        <option value="gu">🇮🇳 ગુજરાતી (Gujarati)</option>
        <option value="kn">🇮🇳 ಕನ್ನಡ (Kannada)</option>
        <option value="ml">🇮🇳 മലയാളം (Malayalam)</option>
        <option value="pa">🇮🇳 ਪੰਜਾਬੀ (Punjabi)</option>
        <option value="od">🇮🇳 ଓଡ଼ିଆ (Odia)</option>
        <option value="en">🌐 English (EN)</option>
      </select>
    </div>
  </div>

  <div class="container">
    
    <!-- Tier Status -->
    <div class="tier-banner">
      <div style="display: flex; align-items: center; gap: 10px;">
        <span style="font-size: 20px;">📡</span>
        <div>
          <div style="font-weight: 700; font-size: 13px;" id="lbl-tier">TIER 1 — गाँव का स्थानीय हब (ऑफलाइन सक्षम)</div>
          <div style="font-size: 11px; color: var(--text-muted);" id="lbl-sync">Sarvam AI बहुभाषी अनुवाद एवं रेडियो ब्रॉडकास्ट सुरक्षित</div>
        </div>
      </div>
      <button onclick="scanBroadcast()" id="btn-radio-sync" style="background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); color: #fff; padding: 6px 12px; border-radius: 12px; font-size: 12px; cursor: pointer;">🔄 रेडियो सिंक</button>
    </div>

    <!-- Navigation Grid -->
    <div class="nav-grid">
      <div class="nav-card active" onclick="showSection('opportunities', this)">
        <div class="nav-emoji">📢</div>
        <div class="nav-label" id="tab-opps">योजनाएं एवं अवसर</div>
        <div class="nav-sub" id="tab-opps-sub">सरकारी सूचनाएं</div>
      </div>
      <div class="nav-card" onclick="showSection('suggestions', this)">
        <div class="nav-emoji">🎯</div>
        <div class="nav-label" id="tab-sugg">आपके लिए सुझाव</div>
        <div class="nav-sub" id="tab-sugg-sub">योग्यता अनुसार</div>
      </div>
      <div class="nav-card" onclick="showSection('family', this)">
        <div class="nav-emoji">👨‍👩‍👧</div>
        <div class="nav-label" id="tab-fam">मेरा परिवार</div>
        <div class="nav-sub" id="tab-fam-sub">प्रोफाइल व पात्रता</div>
      </div>
      <div class="nav-card" onclick="showSection('health', this)">
        <div class="nav-emoji">🩺</div>
        <div class="nav-label" id="tab-health">परिवार स्वास्थ्य</div>
        <div class="nav-sub" id="tab-health-sub">टीकाकरण व सलाह</div>
      </div>
      <div class="nav-card" onclick="showSection('reminders', this)">
        <div class="nav-emoji">⏱️</div>
        <div class="nav-label" id="tab-rem">स्मरण व अलर्ट</div>
        <div class="nav-sub" id="tab-rem-sub">अंतिम तिथियां</div>
      </div>
      <div class="nav-card" onclick="showSection('dashboard', this)">
        <div class="nav-emoji">📊</div>
        <div class="nav-label" id="tab-dash">ग्राम डैशबोर्ड</div>
        <div class="nav-sub" id="tab-dash-sub">हब स्थिति</div>
      </div>
    </div>

    <!-- Section 1: Opportunities -->
    <div id="sec-opportunities" class="section active">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
        <h2 style="font-family: 'Outfit'; font-size: 20px;" id="hdr-opps">उपलब्ध सरकारी योजनाएं एवं नौकरियां</h2>
      </div>
      <div id="opps-list">लोड हो रहा है...</div>
    </div>

    <!-- Section 2: Suggestions (Feature K) -->
    <div id="sec-suggestions" class="section">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
        <h2 style="font-family: 'Outfit'; font-size: 20px;" id="hdr-sugg">व्यक्तिगत सुझाव (Feature K)</h2>
        <select id="person-select-sugg" onchange="loadSuggestions(this.value)" style="background: var(--card); border: 1px solid var(--card-border); color: #fff; padding: 6px 12px; border-radius: 12px; font-size: 13px;"></select>
      </div>
      <div style="background: rgba(59, 130, 246, 0.12); padding: 12px 16px; border-radius: 12px; font-size: 12px; margin-bottom: 16px; border: 1px solid rgba(59, 130, 246, 0.3);" id="lbl-sugg-disclaimer">
        ℹ️ <strong>सुझाव, कोई गारंटी नहीं</strong>: यह सुझाव आपके कौशल और शिक्षा के आधार पर नियम अनुसार तैयार किए गए हैं।
      </div>
      <div id="suggestions-list">लोड हो रहा है...</div>
    </div>

    <!-- Section 3: Family Profiles -->
    <div id="sec-family" class="section">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
        <h2 style="font-family: 'Outfit'; font-size: 20px;" id="hdr-fam">परिवार के सदस्य एवं प्रोफाइल</h2>
      </div>
      <div id="family-list">लोड हो रहा है...</div>
    </div>

    <!-- Section 4: Health Module -->
    <div id="sec-health" class="section">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
        <h2 style="font-family: 'Outfit'; font-size: 20px;" id="hdr-health">परिवार स्वास्थ्य व टीकाकरण</h2>
        <select id="person-select-health" onchange="loadHealth(this.value)" style="background: var(--card); border: 1px solid var(--card-border); color: #fff; padding: 6px 12px; border-radius: 12px; font-size: 13px;"></select>
      </div>
      <div class="disclaimer-alert" id="health-disclaimer">
        ⚠️ <strong>आवश्यक सूचना</strong>: यह केवल एक सामान्य अनुस्मारक और मार्गदर्शन है। यह चिकित्सीय सलाह या निदान का विकल्प नहीं है। किसी भी स्वास्थ्य समस्या के लिए अपनी ASHA कार्यकर्ता या प्राथमिक स्वास्थ्य केंद्र (PHC) से संपर्क करें।
      </div>
      <div id="health-content">लोड हो रहा है...</div>
    </div>

    <!-- Section 5: Reminders & Fast-Forward Simulator -->
    <div id="sec-reminders" class="section">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
        <h2 style="font-family: 'Outfit'; font-size: 20px;" id="hdr-rem">समय यात्रा व स्मरण अलर्ट</h2>
      </div>
      
      <!-- Fast forward control -->
      <div class="card" style="border-color: rgba(245, 158, 11, 0.4); background: rgba(245, 158, 11, 0.05);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
          <span style="font-weight: 700; font-size: 14px;" id="lbl-ff-title">⏩ समय यात्रा सिम्युलेटर (Fast-Forward)</span>
          <span id="ff-val" style="color: #fbbf24; font-weight: 800; font-size: 15px;">+0 दिन</span>
        </div>
        <p style="font-size: 12px; color: var(--text-muted); margin-bottom: 12px;" id="lbl-ff-desc">भविष्य की अंतिम तिथियों और दस्तावेज़ तैयारी अलर्ट को तुरंत जांचने के लिए आगे बढ़ाएं:</p>
        <div style="display: flex; gap: 8px; flex-wrap: wrap;">
          <button onclick="setFastForward(0)" id="btn-ff-0" style="background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.15); color: #fff; padding: 6px 12px; border-radius: 12px; font-size: 12px; cursor: pointer;">आज (0 दिन)</button>
          <button onclick="setFastForward(10)" id="btn-ff-10" style="background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.15); color: #fff; padding: 6px 12px; border-radius: 12px; font-size: 12px; cursor: pointer;">+10 दिन आगे</button>
          <button onclick="setFastForward(30)" id="btn-ff-30" style="background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.15); color: #fff; padding: 6px 12px; border-radius: 12px; font-size: 12px; cursor: pointer;">+30 दिन आगे</button>
          <button onclick="setFastForward(60)" id="btn-ff-60" style="background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.15); color: #fff; padding: 6px 12px; border-radius: 12px; font-size: 12px; cursor: pointer;">+60 दिन आगे</button>
        </div>
      </div>

      <div id="reminders-list">लोड हो रहा है...</div>
    </div>

    <!-- Section 6: Village Dashboard -->
    <div id="sec-dashboard" class="section">
      <h2 style="font-family: 'Outfit'; font-size: 20px; margin-bottom: 16px;" id="hdr-dash">ग्राम हब स्थिति व रेडियो पैकेट बहीखाता</h2>
      <div id="dashboard-content">लोड हो रहा है...</div>
    </div>

  </div>

  <script>
    let currentLang = 'hi';
    let fastForwardDays = 0;
    let households = [];
    let allOpportunities = [];

    // Multilingual UI Dictionary for Sarvam AI 9 Indian Languages + English
    const I18N = {
      sub_title: {
        hi: "ग्रामीण जन सुविधा एवं अवसर केंद्र",
        bn: "গ্রামীণ কল্যাণ ও সুযোগ কেন্দ্র",
        te: "గ్రామీణ సంక్షేమం మరియు అవకాశాల కేంద్రం",
        mr: "ग्रामीण कल्याण व संधी केंद्र",
        ta: "கிராமப்புற நலன் மற்றும் வாய்ப்புகள் மையம்",
        gu: "ગ્રામીણ કલ્યાણ અને તકો કેન્દ્ર",
        kn: "ಗ್ರಾಮೀಣ ಕಲ್ಯಾಣ ಮತ್ತು ಅವಕಾಶಗಳ ಕೇಂದ್ರ",
        ml: "ഗ്രാമീണ ക്ഷേമവും അവസരങ്ങളും കേന്ദ്രം",
        pa: "ਪੇਂਡੂ ਭਲਾਈ ਅਤੇ ਮੌਕੇ ਕੇਂਦਰ",
        od: "ଗ୍ରାମୀଣ କଲ୍ୟାଣ ଏବଂ ସୁଯୋଗ କେନ୍ଦ୍ର",
        en: "Rural Welfare & Opportunities Hub"
      },
      tier: {
        hi: "TIER 1 — गाँव का स्थानीय हब (ऑफलाइन सक्षम)",
        bn: "TIER 1 — গ্রামের স্থানীয় হাব (অফলাইন সক্ষম)",
        te: "TIER 1 — గ్రామ స్థానిక హబ్ (ఆఫ్‌లైన్ సదుపాయం)",
        mr: "TIER 1 — गावाचे स्थानिक हब (ऑफलाइन सक्षम)",
        ta: "TIER 1 — கிராமப்புற உள்ளூர் மையம் (ஆஃப்லைன் வசதி)",
        gu: "TIER 1 — ગામનું સ્થાનિક હબ (ઑફલાઇન સક્ષમ)",
        kn: "TIER 1 — ಗ್ರಾಮದ ಸ್ಥಳೀಯ ಹಬ್ (ಆಫ್‌ಲೈನ್ ಸಕ್ರಿಯ)",
        ml: "TIER 1 — ഗ്രാമീണ ലോക്കൽ ഹബ്ബ് (ഓഫ്‌ലൈൻ സവിശേഷത)",
        pa: "TIER 1 — ਪਿੰਡ ਦਾ ਸਥਾਨਕ ਹੱਬ (ਆਫਲਾਈਨ ਸਮਰੱਥ)",
        od: "TIER 1 — ଗ୍ରାମୀଣ ସ୍ଥାନୀୟ ହବ୍ (ଅଫଲାଇନ୍ ସକ୍ଷମ)",
        en: "TIER 1 — Village Hub (Offline Capable)"
      },
      sync_lbl: {
        hi: "Sarvam AI बहुभाषी अनुवाद एवं रेडियो ब्रॉडकास्ट सुरक्षित",
        bn: "Sarvam AI বহুভাষিক অনুবাদ এবং রেডিও সম্প্রচার সুরক্ষিত",
        te: "Sarvam AI బహుభాషా అనువాదం మరియు రేడియో ప్రసారం సురక్షితం",
        mr: "Sarvam AI बहुभाषिक भाषांतर व रेडिओ प्रसारण सुरक्षित",
        ta: "Sarvam AI பன்மொழி மொழிபெயர்ப்பு மற்றும் வானொலி ஒளிபரப்பு பாதுகாப்பானது",
        gu: "Sarvam AI બહુભાષી અનુવાદ અને રેડિયો પ્રસારણ સુરક્ષિત",
        kn: "Sarvam AI ಬಹುಭಾಷಾ ಅನುವಾದ ಮತ್ತು ರೇಡಿಯೋ ಪ್ರಸಾರ ಸುರಕ್ಷಿತ",
        ml: "Sarvam AI ബഹുഭാഷാ വിവർത്തനവും റേഡിയോ പ്രക്ഷേപണവും സുരക്ഷിതമാണ്",
        pa: "Sarvam AI ਬਹੁਭਾਸ਼ਾਈ ਅਨੁਵਾਦ ਅਤੇ ਰੇਡੀਓ ਪ੍ਰਸਾਰਣ ਸੁਰੱਖਿਅਤ",
        od: "Sarvam AI ବହୁଭାଷୀ ଅନୁବାଦ ଏବଂ ରେଡିଓ ପ୍ରସାରଣ ସୁରକ୍ଷିତ",
        en: "Sarvam AI Multilingual Translation & Radio Verified"
      },
      tab_opps: {
        hi: "योजनाएं एवं अवसर", bn: "পরিকল্পনা ও সুযোগ", te: "పథకాలు మరియు అవకాశాలు", mr: "योजना व संधी",
        ta: "திட்டங்கள் மற்றும் வாய்ப்புகள்", gu: "યોજનાઓ અને તકો", kn: "ಯೋಜನೆಗಳು ಮತ್ತು ಅವಕಾಶಗಳು",
        ml: "പദ്ധതികളും അവസരങ്ങളും", pa: "ਸਕੀਮਾਂ ਅਤੇ ਮੌਕੇ", od: "ଯୋଜନା ଏବଂ ସୁଯୋଗ", en: "Opportunities"
      },
      tab_opps_sub: {
        hi: "सरकारी सूचनाएं", bn: "সরকারি বিজ্ঞপ্তি", te: "ప్రభుత్వ నోటీసులు", mr: "शासकीय सूचना",
        ta: "அரசு அறிவிப்புகள்", gu: "સરકારી નોટિસો", kn: "ಸರ್ಕಾರಿ ಪ್ರಕಟಣೆಗಳು", ml: "സർക്കാർ വിജ്ഞാപനങ്ങൾ",
        pa: "ਸਰਕਾਰੀ ਨੋਟਿਸ", od: "ସରକାରୀ ବିଜ୍ଞପ୍ତି", en: "Government Notices"
      },
      tab_sugg: {
        hi: "आपके लिए सुझाव", bn: "আপনার জন্য পরামর্শ", te: "మీ కోసం సూచనలు", mr: "तुमच्यासाठी शिफारसी",
        ta: "உங்களுக்கான பரிந்துரைகள்", gu: "તમારા માટે સૂચનો", kn: "ನಿಮಗಾಗಿ ಶಿಫಾರಸುಗಳು",
        ml: "നിങ്ങൾക്കുള്ള നിർദ്ദേശങ്ങൾ", pa: "ਤੁਹਾਡੇ ਲਈ ਸੁਝਾਅ", od: "ଆପଣଙ୍କ ପାଇଁ ପରାମର୍ଶ", en: "Suggested for You"
      },
      tab_sugg_sub: {
        hi: "योग्यता अनुसार", bn: "যোগ্যতা অনুযায়ী", te: "అర్హత ప్రకారం", mr: "पात्रतेनुसार",
        ta: "தகுதிப்படி", gu: "લાયકાત મુજબ", kn: "ಅರ್ಹತೆಯಂತೆ", ml: "യോഗ്യതയനുസരിച്ച്",
        pa: "ਯੋਗਤਾ ਅਨੁਸਾਰ", od: "ଯୋଗ୍ୟତା ଅନୁଯାୟୀ", en: "By Profile Fit"
      },
      tab_fam: {
        hi: "मेरा परिवार", bn: "আমার পরিবার", te: "నా కుటుంబం", mr: "माझे कुटुंब",
        ta: "என் குடும்பம்", gu: "મારો પરિવાર", kn: "ನನ್ನ ಕುಟುಂಬ", ml: "എന്റെ കുടുംബം",
        pa: "ਮੇਰਾ ਪਰਿਵਾਰ", od: "ମୋର ପରିବାର", en: "My Family"
      },
      tab_fam_sub: {
        hi: "प्रोफाइल व पात्रता", bn: "প্রোফাইল ও যোগ্যতা", te: "ప్రొఫైల్ మరియు అర్హత", mr: "प्रोफाइल व पात्रता",
        ta: "சுயவிவரம் மற்றும் தகுதி", gu: "પ્રોફાઇલ અને લાયકાત", kn: "ಪ್ರೊಫೈಲ್ ಮತ್ತು ಅರ್ಹತೆ", ml: "പ്രൊഫൈലും യോഗ്യതയും",
        pa: "ਪ੍ਰੋਫਾਈਲ ਅਤੇ ਯੋਗਤਾ", od: "ପ୍ରୋଫାଇଲ୍ ଏବଂ ଯୋଗ୍ୟତା", en: "Profiles & Eligibility"
      },
      tab_health: {
        hi: "परिवार स्वास्थ्य", bn: "পারিবারিক স্বাস্থ্য", te: "కుటుంబ ఆరోగ్యం", mr: "कुटुंब आरोग्य",
        ta: "குடும்ப சுகாதாரம்", gu: "પરિવાર સ્વાસ્થ્ય", kn: "ಕುಟುಂಬ ಆರೋಗ್ಯ", ml: "കുടുംബ ആരോഗ്യം",
        pa: "ਪਰਿਵਾਰਕ ਸਿਹਤ", od: "ପରିବାର ସ୍ୱାସ୍ଥ୍ୟ", en: "Family Health"
      },
      tab_health_sub: {
        hi: "टीकाकरण व सलाह", bn: "টিকাকরণ ও পরামর্শ", te: "టీకాలు మరియు సలహాలు", mr: "लसीकरण व सल्ला",
        ta: "தடுப்பூசி மற்றும் ஆலோசனை", gu: "રસીકરણ અને સલાહ", kn: "ಲಸಿಕೆ ಮತ್ತು ಸಲಹೆ", ml: "പ്രതിരോധ കുത്തിവയ്പ്പും ഉപദേശവും",
        pa: "ਟੀਕਾਕਰਨ ਅਤੇ ਸਲਾਹ", od: "ଟିକାକରଣ ଏବଂ ପରାମର୍ଶ", en: "Immunization & Guidance"
      },
      tab_rem: {
        hi: "स्मरण व अलर्ट", bn: "অনুস্মারক ও সতর্কতা", te: "రిమైండర్లు మరియు హెచ్చరికలు", mr: "स्मरणपत्रे व सूचना",
        ta: "நினைவூட்டல்கள் மற்றும் எச்சரிக்கைகள்", gu: "રીમાઇન્ડર અને ચેતવણીઓ", kn: "ಜ್ಞಾಪನೆಗಳು ಮತ್ತು ಎಚ್ಚರಿಕೆಗಳು",
        ml: "ഓർമ്മപ്പെടുത്തലുകളും അലേർട്ടുകളും", pa: "ਯਾਦ-ਦਹਾਨੀਆਂ ਅਤੇ ਚਿਤਾਵਨੀਆਂ", od: "ସ୍ମାରକପତ୍ର ଏବଂ ସତର୍କତା", en: "Reminders & Alerts"
      },
      tab_rem_sub: {
        hi: "अंतिम तिथियां", bn: "শেষ তারিখসমূহ", te: "గడువు తేదీలు", mr: "अंतिम तारखा",
        ta: "கடைசி தேதிகள்", gu: "છેલ્લી તારીખો", kn: "ಕೊನೆಯ ದಿನಾಂಕಗಳು", ml: "അവസാന തീയതികൾ",
        pa: "ਆਖਰੀ ਮਿਤੀਆਂ", od: "ଶେଷ ତାରିଖ", en: "Deadlines"
      },
      tab_dash: {
        hi: "ग्राम डैशबोर्ड", bn: "গ্রাম ড্যাশবোর্ড", te: "గ్రామ డ్యాష్‌బోర్డ్", mr: "ग्राम डॅशबोर्ड",
        ta: "கிராம டாஷ்போர்டு", gu: "ગ્રામ ડેશબોર્ડ", kn: "ಗ್ರಾಮ ಡ್ಯಾಶ್‌ಬೋರ್ಡ್", ml: "ഗ്രാമ ഡാഷ്‌ബോർഡ്",
        pa: "ਪਿੰਡ ਡੈਸ਼ਬੋਰਡ", od: "ଗ୍ରାମ ଡ୍ୟାସବୋର୍ଡ", en: "Village Hub"
      },
      tab_dash_sub: {
        hi: "हब स्थिति", bn: "হাব স্থিতি", te: "హబ్ స్థితి", mr: "हब स्थिती",
        ta: "மைய நிலை", gu: "હબ સ્થિતિ", kn: "ಹಬ್ ಸ್ಥಿತಿ", ml: "ഹബ്ബ് അവസ്ഥ",
        pa: "ਹੱਬ ਸਥਿਤੀ", od: "ହବ୍ ସ୍ଥିତି", en: "Status & Ledger"
      },
      hdr_opps: {
        hi: "उपलब्ध सरकारी योजनाएं एवं नौकरियां", bn: "উপলব্ধ সরকারি প্রকল্প ও চাকরি", te: "అందుబాటులో ఉన్న ప్రభుత్వ పథకాలు మరియు ఉద్యోగాలు",
        mr: "उपलब्ध शासकीय योजना व नोकऱ्या", ta: "கிடைக்கும் அரசு திட்டங்கள் மற்றும் வேலைகள்", gu: "ઉપલબ્ધ સરકારી યોજનાઓ અને નોકરીઓ",
        kn: "ಲಭ್ಯವಿರುವ ಸರ್ಕಾರಿ ಯೋಜನೆಗಳು ಮತ್ತು ಉದ್ಯೋಗಗಳು", ml: "ലഭ്യമായ സർക്കാർ പദ്ധതികളും ജോലികളും", pa: "ਉਪਲਬਧ ਸਰਕਾਰੀ ਸਕੀਮਾਂ ਅਤੇ ਨੌਕਰੀਆਂ",
        od: "ଉପଲବ୍ଧ ସରକାରୀ ଯୋଜନା ଏବଂ ଚାକିରି", en: "Available Schemes, Scholarships & Jobs"
      },
      hdr_sugg: {
        hi: "व्यक्तिगत सुझाव (Feature K)", bn: "ব্যক্তিগত পরামর্শ (Feature K)", te: "వ్యక్తిగత సూచనలు (Feature K)", mr: "वैयक्तिक शिफारसी (Feature K)",
        ta: "தனிப்பயனாக்கப்பட்ட பரிந்துரைகள் (Feature K)", gu: "વ્યક્તિગત સૂચનો (Feature K)", kn: "ವೈಯಕ್ತಿಕ ಶಿಫಾರಸುಗಳು (Feature K)",
        ml: "വ്യക്തിഗത നിർദ്ദേശങ്ങൾ (Feature K)", pa: "ਨਿੱਜੀ ਸੁਝਾਅ (Feature K)", od: "ବ୍ୟକ୍ତିଗତ ପରାମର୍ଶ (Feature K)", en: "Personalized Suggestions (Feature K)"
      },
      hdr_fam: {
        hi: "परिवार के सदस्य एवं प्रोफाइल", bn: "পরিবারের সদস্য ও প্রোফাইল", te: "కుటుంబ సభ్యులు మరియు ప్రొఫైల్", mr: "कुटुंबातील सदस्य व प्रोफाइल",
        ta: "குடும்ப உறுப்பினர்கள் மற்றும் சுயவிவரம்", gu: "પરિવારના સભ્યો અને પ્રોફાઇલ", kn: "ಕುಟುಂಬದ ಸದಸ್ಯರು ಮತ್ತು ಪ್ರೊಫೈಲ್",
        ml: "കുടുംബാംഗങ്ങളും പ്രൊഫൈലും", pa: "ਪਰਿਵਾਰਕ ਮੈਂਬਰ ਅਤੇ ਪ੍ਰੋਫਾਈਲ", od: "ପରିବାର ସଦସ୍ୟ ଏବଂ ପ୍ରୋଫାଇଲ୍", en: "Household Members & Profiles"
      },
      hdr_health: {
        hi: "परिवार स्वास्थ्य व टीकाकरण", bn: "পারিবারিক স্বাস্থ্য ও টিকাকরণ", te: "కుటుంబ ఆరోగ్యం మరియు టీకాలు", mr: "कुटुंब आरोग्य व लसीकरण",
        ta: "குடும்ப சுகாதாரம் மற்றும் தடுப்பூசி", gu: "પરિવાર સ્વાસ્થ્ય અને રસીકરણ", kn: "ಕುಟುಂಬ ಆರೋಗ್ಯ ಮತ್ತು ಲಸಿಕೆ",
        ml: "കുടുംബ ആരോഗ്യവും കുത്തിവയ്പ്പും", pa: "ਪਰਿਵਾਰਕ ਸਿਹਤ ਅਤੇ ਟੀਕਾਕਰਨ", od: "ପରିବାର ସ୍ୱାସ୍ଥ୍ୟ ଏବଂ ଟିକାକରଣ", en: "Family Health & Immunization"
      },
      hdr_rem: {
        hi: "समय यात्रा व स्मरण अलर्ट", bn: "সময় যাত্রা ও অনুস্মারক সতর্কতা", te: "సమయ ప్రయాణం మరియు రిమైండర్ హెచ్చరికలు", mr: "वेळ प्रवास व स्मरणपत्रे",
        ta: "நேரப் பயணம் மற்றும் நினைவூட்டல் எச்சரிக்கைகள்", gu: "સમય યાત્રા અને રીમાઇન્ડર ચેતવણીઓ", kn: "ಸಮಯ ಪ್ರಯಾಣ ಮತ್ತು ಜ್ಞಾಪನೆ ಎಚ್ಚರಿಕೆಗಳು",
        ml: "സമയ യാത്രയും റിമൈൻഡർ അലേർട്ടുകളും", pa: "ਸਮਾਂ ਯਾਤਰਾ ਅਤੇ ਯਾਦ-ਦਹਾਨੀ ਚਿਤਾਵਨੀਆਂ", od: "ସମୟ ଯାତ୍ରା ଏବଂ ସ୍ମାରକପତ୍ର ସତର୍କତା", en: "Time Travel & Reminders"
      },
      hdr_dash: {
        hi: "ग्राम हब स्थिति व रेडियो पैकेट बहीखाता", bn: "গ্রাম হাব স্থিতি ও রেডিও প্যাকেট খতিয়ান", te: "గ్రామ హబ్ స్థితి మరియు రేడియో ప్యాకెట్ లెడ్జర్",
        mr: "ग्राम हब स्थिती व रेडिओ पॅकेट खतावणी", ta: "கிராம மைய நிலை மற்றும் வானொலி பாக்கெட் லெட்ஜர்", gu: "ગ્રામ હબ સ્થિતિ અને રેડિયો પેકેટ ખાતાવહી",
        kn: "ಗ್ರಾಮ ಹಬ್ ಸ್ಥಿತಿ ಮತ್ತು ರೇಡಿಯೋ ಪ್ಯಾಕೆಟ್ ಲೆಡ್ಜರ್", ml: "ഗ്രാമ ഹബ്ബ് അവസ്ഥയും റേഡിയോ പാക്കറ്റ് ലെഡ്ജറും", pa: "ਪਿੰਡ ਹੱਬ ਸਥਿਤੀ ਅਤੇ ਰੇਡੀਓ ਪੈਕੇਟ ਖਾਤਾ",
        od: "ଗ୍ରାମ ହବ୍ ସ୍ଥିତି ଏବଂ ରେଡିଓ ପ୍ୟାକେଟ୍ ଲେଜର", en: "Village Hub Status & Radio Packet Ledger"
      },
      sugg_disclaimer: {
        hi: "ℹ️ <strong>सुझाव, कोई गारंटी नहीं</strong>: यह सुझाव आपके कौशल और शिक्षा के आधार पर नियम अनुसार तैयार किए गए हैं।",
        bn: "ℹ️ <strong>পরামর্শ, কোনো গ্যারান্টি নয়</strong>: আপনার দক্ষতা ও শিক্ষার ভিত্তিতে প্রস্তুত।",
        te: "ℹ️ <strong>సూచన మాత్రమే, గ్యారెంటీ లేదు</strong>: మీ నైపుణ్యాలు మరియు విద్య ఆధారంగా రూపొందించబడింది.",
        mr: "ℹ️ <strong>शिफारस, हमी नाही</strong>: आपल्या कौशल्य आणि शिक्षणावर आधारित.",
        ta: "ℹ️ <strong>பரிந்துரை மட்டுமே, உத்தரவாதம் இல்லை</strong>: உங்கள் திறன் மற்றும் கல்வி அடிப்படையில்.",
        gu: "ℹ️ <strong>માત્ર સૂચન, ગેરંટી નથી</strong>: તમારા કૌશલ્ય અને શિક્ષણ પર આધારિત.",
        kn: "ℹ️ <strong>ಶಿಫಾರಸು ಮಾತ್ರ, ಖಾತರಿಯಿಲ್ಲ</strong>: ನಿಮ್ಮ ಕೌಶಲ್ಯ ಮತ್ತು ಶಿಕ್ಷಣದ ಆಧಾರದ ಮೇಲೆ.",
        ml: "ℹ️ <strong>നിർദ്ദേശം മാത്രം, ഗ്യാരണ്ടിയില്ല</strong>: നിങ്ങളുടെ കഴിവുകളെ അടിസ്ഥാനമാക്കി.",
        pa: "ℹ️ <strong>ਸਿਰਫ ਸੁਝਾਅ, ਗਾਰੰਟੀ ਨਹੀਂ</strong>: ਤੁਹਾਡੇ ਹੁਨਰ ਅਤੇ ਸਿੱਖਿਆ 'ਤੇ ਆਧਾਰਿਤ।",
        od: "ℹ️ <strong>କେବଳ ପରାମର୍ଶ, କୌଣସି ଗ୍ୟାରେଣ୍ଟି ନାହିଁ</strong>: ଆପଣଙ୍କ ଦକ୍ଷତା ଓ ଶିକ୍ଷା ଉପରେ ଆଧାରିତ।",
        en: "ℹ️ <strong>Suggested, not guaranteed</strong>: Generated strictly by deterministic matching rules."
      },
      health_disclaimer: {
        hi: "⚠️ <strong>आवश्यक सूचना</strong>: यह केवल एक सामान्य अनुस्मारक और मार्गदर्शन है। यह चिकित्सीय सलाह या निदान का विकल्प नहीं है। किसी भी स्वास्थ्य समस्या के लिए अपनी ASHA कार्यकर्ता या प्राथमिक स्वास्थ्य केंद्र (PHC) से संपर्क करें।",
        bn: "⚠️ <strong>প্রয়োজনীয় বিজ্ঞপ্তি</strong>: এটি কেবল একটি সাধারণ অনুস্মারক ও পরামর্শ। এটি চিকিৎসকের পরামর্শের বিকল্প নয়। ASHA কর্মী বা PHC-তে যোগাযোগ করুন।",
        te: "⚠️ <strong>ముఖ్య గమనిక</strong>: ఇది సాధారణ రిమైండర్ మరియు మార్గదర్శకత్వం మాత్రమే. ఇది వైద్య సలహా లేదా నిర్ధారణకు ప్రత్యామ్నాయం కాదు. ASHA లేదా PHCని సంప్రదించండి.",
        mr: "⚠️ <strong>महत्त्वाची सूचना</strong>: हे केवळ सामान्य स्मरणपत्र आणि मार्गदर्शन आहे. हा वैद्यकीय सल्ल्याचा पर्याय नाही. ASHA कार्यकर्ता किंवा PHC शी संपर्क साधा.",
        ta: "⚠️ <strong>முக்கிய அறிவிப்பு</strong>: இது ஒரு பொதுவான நினைவூட்டல் மட்டுமே. இது மருத்துவ ஆலோசனை அல்ல. ASHA அல்லது PHC-ஐ தொடர்பு கொள்ளவும்.",
        gu: "⚠️ <strong>મહત્વપૂર્ણ સૂચના</strong>: આ માત્ર સામાન્ય રીમાઇન્ડર અને માર્ગદર્શન છે. તે તબીબી સલાહનો વિકલ્પ નથી. ASHA કાર્યકર અથવા PHC નો સંપર્ક કરો.",
        kn: "⚠️ <strong>ಮುಖ್ಯ ಸೂಚನೆ</strong>: ಇದು ಸಾಮಾನ್ಯ ಜ್ಞಾಪನೆ ಮಾತ್ರ. ಇದು ವೈದ್ಯಕೀಯ ಸಲಹೆಯ ಬದಲಿಯಲ್ಲ. ASHA ಅಥವಾ PHC ಅನ್ನು ಸಂಪರ್ಕಿಸಿ.",
        ml: "⚠️ <strong>പ്രധാന അറിയിപ്പ്</strong>: ഇതൊരു പൊതുവായ ഓർമ്മപ്പെടുത്തൽ മാത്രമാണ്. ഇത് വൈദ്യോപദേശത്തിന് പകരമല്ല. ആശാ പ്രവർത്തകയുമായോ PHC യുമായോ ബന്ധപ്പെടുക.",
        pa: "⚠️ <strong>ਜ਼ਰੂਰੀ ਸੂਚਨਾ</strong>: ਇਹ ਸਿਰਫ ਇੱਕ ਆਮ ਯਾਦ-ਦਹਾਨੀ ਹੈ। ਇਹ ਡਾਕਟਰੀ ਸਲਾਹ ਦਾ ਬਦਲ ਨਹੀਂ ਹੈ। ASHA ਵਰਕਰ ਜਾਂ PHC ਨਾਲ ਸੰਪਰਕ ਕਰੋ।",
        od: "⚠️ <strong>ଗୁରୁତ୍ୱପୂର୍ଣ୍ଣ ସୂଚନା</strong>: ଏହା କେବଳ ଏକ ସାଧାରଣ ସ୍ମାରକପତ୍ର ଓ ମାର୍ଗଦର୍ଶନ। ଏହା ଡାକ୍ତରୀ ପରାମର୍ଶର ବିକଳ୍ପ ନୁହେଁ। ASHA କିମ୍ବା PHC ସହିତ ଯୋଗାଯୋଗ କରନ୍ତୁ।",
        en: "⚠️ <strong>Notice</strong>: This is a general reminder and referral guide only. It does NOT replace medical advice or diagnosis. Consult your ASHA worker or PHC."
      },
      ff_title: {
        hi: "⏩ समय यात्रा सिम्युलेटर (Fast-Forward)", bn: "⏩ সময় যাত্রা সিমুলেটর (Fast-Forward)", te: "⏩ సమయ ప్రయాణం సిమ్యులేటర్ (Fast-Forward)",
        mr: "⏩ वेळ प्रवास सिम्युलेटर (Fast-Forward)", ta: "⏩ நேரப் பயண சிமுலேட்டர் (Fast-Forward)", gu: "⏩ સમય યાત્રા સિમ્યુલેટર (Fast-Forward)",
        kn: "⏩ ಸಮಯ ಪ್ರಯಾಣ ಸಿಮ್ಯುಲೇಟರ್ (Fast-Forward)", ml: "⏩ സമയ യാത്ര സിമുലേറ്റർ (Fast-Forward)", pa: "⏩ ਸਮਾਂ ਯਾਤਰਾ ਸਿਮੂਲੇਟਰ (Fast-Forward)",
        od: "⏩ ସମୟ ଯାତ୍ରା ସିମ୍ୟୁଲେଟର (Fast-Forward)", en: "⏩ Time Travel Simulator (Fast-Forward)"
      },
      ff_desc: {
        hi: "भविष्य की अंतिम तिथियों और दस्तावेज़ तैयारी अलर्ट को तुरंत जांचने के लिए आगे बढ़ाएं:",
        bn: "ভবিষ্যতের শেষ তারিখ ও নথি প্রস্তুতির সতর্কতা দেখতে সময় এগিয়ে নিন:",
        te: "భవిష్యత్ గడువు తేదీలు మరియు పత్రాల తయారీ హెచ్చరికలను తనిఖీ చేయడానికి సమయాన్ని ముందుకు జరపండి:",
        mr: "भविष्यातील अंतिम तारखा आणि कागदपत्रे पूर्वतयारी सूचना तपासण्यासाठी वेळ पुढे करा:",
        ta: "எதிர்கால கடைசி தேதிகள் மற்றும் ஆவண தயாரிப்பு எச்சரிக்கைகளை சரிபார்க்க நேரத்தை முன்னெடுக்கவும்:",
        gu: "ભવિષ્યની છેલ્લી તારીખો અને દસ્તાવેજ તૈયારી ચેતવણીઓ તપાસવા માટે સમય આગળ ધપાવો:",
        kn: "ಭವಿಷ್ಯದ ಕೊನೆಯ ದಿನಾಂಕಗಳು ಮತ್ತು ದಾಖಲೆ ಸಿದ್ಧತೆ ಎಚ್ಚರಿಕೆಗಳನ್ನು ಪರೀಕ್ಷಿಸಲು ಸಮಯವನ್ನು ಮುನ್ನಡೆಸಿ:",
        ml: "ഭാവിയിലെ അവസാന തീയതികളും രേഖാ തയ്യാറെടുപ്പ് അലേർട്ടുകളും പരിശോധിക്കാൻ സമയം മുന്നോട്ട് വയ്ക്കുക:",
        pa: "ਭਵਿੱਖ ਦੀਆਂ ਆਖਰੀ ਮਿਤੀਆਂ ਅਤੇ ਦਸਤਾਵੇਜ਼ ਤਿਆਰੀ ਚਿਤਾਵਨੀਆਂ ਦੇਖਣ ਲਈ ਸਮਾਂ ਅੱਗੇ ਵਧਾਓ:",
        od: "ଭବିଷ୍ୟତର ଶେଷ ତାରିଖ ଏବଂ ଦସ୍ତାବିଜ୍ ପ୍ରସ୍ତୁତି ସତର୍କତା ଦେଖିବା ପାଇଁ ସମୟ ଆଗକୁ ନିଅନ୍ତୁ:",
        en: "Advance simulated time to test future deadlines and document lead-time alerts:"
      },
      lbl_last_date: {
        hi: "अंतिम तिथि", bn: "শেষ তারিখ", te: "గడువు తేదీ", mr: "अंतिम तारीख",
        ta: "கடைசி தேதி", gu: "છેલ્લી તારીખ", kn: "ಕೊನೆಯ ದಿನಾಂಕ", ml: "അവസാന തീയതി",
        pa: "ਆਖਰੀ ਮਿਤੀ", od: "ଶେଷ ତାରିଖ", en: "Last Date"
      },
      lbl_fee: {
        hi: "शुल्क", bn: "ফি", te: "ఫీజు", mr: "शुल्क",
        ta: "கட்டணம்", gu: "ફી", kn: "ಶುಲ್ಕ", ml: "ഫീസ്",
        pa: "ਫੀਸ", od: "ଫିସ୍", en: "Fee"
      },
      lbl_docs: {
        hi: "आवश्यक दस्तावेज़", bn: "প্রয়োজনীয় নথি", te: "అవసరమైన పత్రాలు", mr: "आवश्यक कागदपत्रे",
        ta: "தேவையான ஆவணங்கள்", gu: "જરૂરી દસ્તાવેજો", kn: "ಅಗತ್ಯ ದಾಖಲೆಗಳು", ml: "ആവശ്യമായ രേഖകൾ",
        pa: "ਲੋੜੀਂਦੇ ਦਸਤਾਵੇਜ਼", od: "ଆବଶ୍ୟକୀୟ ଦଲିଲ", en: "Documents Required"
      },
      lbl_source: {
        hi: "🔗 आधिकारिक स्रोत", bn: "🔗 অফিসিয়াল সূত্র", te: "🔗 అధికారిక లింక్", mr: "🔗 अधिकृत स्रोत",
        ta: "🔗 அதிகாரப்பூர்வ இணைப்பு", gu: "🔗 સત્તાવાર સ્ત્રોત", kn: "🔗 ಅಧಿಕೃತ ಮೂಲ", ml: "🔗 ഔദ്യോഗിക ലിങ്ക്",
        pa: "🔗 ਅਧਿਕਾਰਤ ਸਰੋਤ", od: "🔗 ସରକାରୀ ଉତ୍ସ", en: "🔗 Official Source"
      },
      lbl_check_elig: {
        hi: "👨‍👩‍👧 परिवार पात्रता जांचें", bn: "👨‍👩‍👧 পরিবারের যোগ্যতা দেখুন", te: "👨‍👩‍👧 కుటుంబ అర్హతను తనిఖీ చేయండి", mr: "👨‍👩‍👧 कुटुंब पात्रता तपासा",
        ta: "👨‍👩‍👧 குடும்பத் தகுதியை சரிபார்க்கவும்", gu: "👨‍👩‍👧 પરિવારની પાત્રતા તપાસો", kn: "👨‍👩‍👧 ಕುಟುಂಬದ ಅರ್ಹತೆಯನ್ನು ಪರಿಶೀಲಿಸಿ", ml: "👨‍👩‍👧 കുടുംബ യോഗ്യത പരിശോധിക്കുക",
        pa: "👨‍👩‍👧 ਪਰਿਵਾਰਕ ਯੋਗਤਾ ਜਾਂਚੋ", od: "👨‍👩‍👧 ପରିବାର ଯୋଗ୍ୟତା ଯାଞ୍ଚ କରନ୍ତୁ", en: "👨‍👩‍👧 Check Family Eligibility"
      },
      why_fit_hdr: {
        hi: "💡 यह आपके लिए क्यों उपयुक्त है:", bn: "💡 এটি আপনার জন্য কেন উপযুক্ত:", te: "💡 ఇది మీకు ఎందుకు సరిపోతుంది:", mr: "💡 हे तुमच्यासाठी का योग्य आहे:",
        ta: "💡 இது உங்களுக்கு ஏன் பொருத்தமானது:", gu: "💡 આ તમારા માટે શા માટે યોગ્ય છે:", kn: "💡 ಇದು ನಿಮಗೆ ಏಕೆ ಸೂಕ್ತವಾಗಿದೆ:", ml: "💡 ഇത് നിങ്ങൾക്ക് അനുയോജ്യമാകുന്നത് എന്തുകൊണ്ട്:",
        pa: "💡 ਇਹ ਤੁਹਾਡੇ ਲਈ ਕਿਉਂ ਢੁਕਵਾਂ ਹੈ:", od: "💡 ଏହା ଆପଣଙ୍କ ପାଇଁ କାହିଁକି ଉପଯୁକ୍ତ:", en: "💡 Why this fits you:"
      },
      pathway_hdr: {
        hi: "🚀 पात्र बनने के लिए अगला कदम:", bn: "🚀 যোগ্য হওয়ার জন্য পরবর্তী পদক্ষেপ:", te: "🚀 అర్హత సాధించడానికి తదుపరి దశ:", mr: "🚀 पात्र होण्यासाठी पुढील पाऊल:",
        ta: "🚀 தகுதி பெறுவதற்கான அடுத்த படி:", gu: "🚀 પાત્ર બનવા માટેનું આગલું પગલું:", kn: "🚀 ಅರ್ಹತೆ ಪಡೆಯಲು ಮುಂದಿನ ಹಂತ:", ml: "🚀 അർഹത നേടാനുള്ള അടുത്ത ഘട്ടം:",
        pa: "🚀 ਯੋਗ ਬਣਨ ਲਈ ਅਗਲਾ ਕਦਮ:", od: "🚀 ଯୋଗ୍ୟ ହେବା ପାଇଁ ପରବର୍ତ୍ତୀ ପଦକ୍ଷେପ:", en: "🚀 How to become eligible:"
      },
      fit_score_lbl: {
        hi: "🎯 उपयुक्तता स्कोर", bn: "🎯 উপযুক্ততা স্কোর", te: "🎯 ఫిట్ స్కోరు", mr: "🎯 योग्यता गुण",
        ta: "🎯 பொருத்தம் மதிப்பெண்", gu: "🎯 યોગ્યતા સ્કોર", kn: "🎯 ಸೂಕ್ತತೆಯ ಅಂಕ", ml: "🎯 ഫിറ്റ് സ്കോർ",
        pa: "🎯 ਅਨੁਕੂਲਤਾ ਸਕੋਰ", od: "🎯 ଫିଟ୍ ସ୍କୋର", en: "🎯 Fit Score"
      }
    };

    async function init() {
      await loadHouseholds();
      await loadOpportunities();
      await loadReminders();
      await loadDashboard();
    }

    function setGlobalLang(lang) {
      currentLang = lang;
      
      // Update UI Header & Tabs from I18N dictionary
      document.getElementById('lbl-sub').innerText = I18N.sub_title[lang] || I18N.sub_title.en;
      document.getElementById('lbl-tier').innerText = I18N.tier[lang] || I18N.tier.en;
      document.getElementById('lbl-sync').innerText = I18N.sync_lbl[lang] || I18N.sync_lbl.en;
      
      document.getElementById('tab-opps').innerText = I18N.tab_opps[lang] || I18N.tab_opps.en;
      document.getElementById('tab-opps-sub').innerText = I18N.tab_opps_sub[lang] || I18N.tab_opps_sub.en;
      document.getElementById('tab-sugg').innerText = I18N.tab_sugg[lang] || I18N.tab_sugg.en;
      document.getElementById('tab-sugg-sub').innerText = I18N.tab_sugg_sub[lang] || I18N.tab_sugg_sub.en;
      document.getElementById('tab-fam').innerText = I18N.tab_fam[lang] || I18N.tab_fam.en;
      document.getElementById('tab-fam-sub').innerText = I18N.tab_fam_sub[lang] || I18N.tab_fam_sub.en;
      document.getElementById('tab-health').innerText = I18N.tab_health[lang] || I18N.tab_health.en;
      document.getElementById('tab-health-sub').innerText = I18N.tab_health_sub[lang] || I18N.tab_health_sub.en;
      document.getElementById('tab-rem').innerText = I18N.tab_rem[lang] || I18N.tab_rem.en;
      document.getElementById('tab-rem-sub').innerText = I18N.tab_rem_sub[lang] || I18N.tab_rem_sub.en;
      document.getElementById('tab-dash').innerText = I18N.tab_dash[lang] || I18N.tab_dash.en;
      document.getElementById('tab-dash-sub').innerText = I18N.tab_dash_sub[lang] || I18N.tab_dash_sub.en;

      document.getElementById('hdr-opps').innerText = I18N.hdr_opps[lang] || I18N.hdr_opps.en;
      document.getElementById('hdr-sugg').innerText = I18N.hdr_sugg[lang] || I18N.hdr_sugg.en;
      document.getElementById('hdr-fam').innerText = I18N.hdr_fam[lang] || I18N.hdr_fam.en;
      document.getElementById('hdr-health').innerText = I18N.hdr_health[lang] || I18N.hdr_health.en;
      document.getElementById('hdr-rem').innerText = I18N.hdr_rem[lang] || I18N.hdr_rem.en;
      document.getElementById('hdr-dash').innerText = I18N.hdr_dash[lang] || I18N.hdr_dash.en;

      document.getElementById('lbl-sugg-disclaimer').innerHTML = I18N.sugg_disclaimer[lang] || I18N.sugg_disclaimer.en;
      document.getElementById('health-disclaimer').innerHTML = I18N.health_disclaimer[lang] || I18N.health_disclaimer.en;
      document.getElementById('lbl-ff-title').innerText = I18N.ff_title[lang] || I18N.ff_title.en;
      document.getElementById('lbl-ff-desc').innerText = I18N.ff_desc[lang] || I18N.ff_desc.en;

      loadOpportunities();
      const pSelSugg = document.getElementById('person-select-sugg');
      if (pSelSugg && pSelSugg.value) loadSuggestions(pSelSugg.value);
      const pSelH = document.getElementById('person-select-health');
      if (pSelH && pSelH.value) loadHealth(pSelH.value);
      loadReminders();
    }

    function showSection(name, tabEl) {
      document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
      document.querySelectorAll('.nav-card').forEach(c => c.classList.remove('active'));
      document.getElementById(`sec-${name}`).classList.add('active');
      if (tabEl) tabEl.classList.add('active');
    }

    async function loadOpportunities() {
      const res = await fetch(`/api/opportunities?lang=${currentLang}`);
      const data = await res.json();
      allOpportunities = data.items;
      renderOpportunities();
    }

    function renderOpportunities() {
      const container = document.getElementById('opps-list');
      if (allOpportunities.length === 0) {
        container.innerHTML = `<div class="card">No opportunities available.</div>`;
        return;
      }
      container.innerHTML = allOpportunities.map(o => {
        const title = o.title_localized || (currentLang === 'hi' && o.title_hi ? o.title_hi : o.title);
        const lastDate = o.dates?.last_date || 'Soon';
        const docs = o.documents_required || [];
        const lblLast = I18N.lbl_last_date[currentLang] || 'Last Date';
        const lblFee = I18N.lbl_fee[currentLang] || 'Fee';
        const lblDocs = I18N.lbl_docs[currentLang] || 'Documents';
        const lblSrc = I18N.lbl_source[currentLang] || '🔗 Official Source';
        const lblCheck = I18N.lbl_check_elig[currentLang] || '👨‍👩‍👧 Check Family Eligibility';

        return `
          <div class="card">
            <div class="card-header">
              <div>
                <div class="card-title">${title}</div>
                <div class="card-org">${o.org || ''} • <span style="text-transform: uppercase;">${o.type}</span></div>
              </div>
              <span class="badge badge-eligible">ACTIVE</span>
            </div>
            <div style="font-size: 13px; color: var(--text-muted); margin-bottom: 8px;">
              🗓️ ${lblLast}: <strong>${lastDate}</strong> | 💰 ${lblFee}: <strong>₹${o.fee || 0}</strong>
            </div>
            ${docs.length > 0 ? `
              <div style="font-size: 12px; margin: 8px 0; background: rgba(0,0,0,0.2); padding: 8px 12px; border-radius: 8px;">
                📑 <strong>${lblDocs}:</strong>
                ${docs.map(d => `${d.name_hi || d.name} (${d.typical_lead_time_days || 0} days)`).join(', ')}
              </div>` : ''}
            <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 12px;">
              <a href="${o.source_url}" target="_blank" style="font-size: 12px; color: var(--primary); text-decoration: none;">${lblSrc}</a>
              <button onclick="checkFamilyEligibility('${o.id}')" style="background: rgba(59, 130, 246, 0.2); border: 1px solid var(--primary); color: #fff; padding: 6px 12px; border-radius: 12px; font-size: 12px; cursor: pointer;">
                ${lblCheck}
              </button>
            </div>
          </div>
        `;
      }).join('');
    }

    async function loadHouseholds() {
      const res = await fetch('/api/households');
      const data = await res.json();
      households = data.items;

      const pSelSugg = document.getElementById('person-select-sugg');
      const pSelH = document.getElementById('person-select-health');
      pSelSugg.innerHTML = '';
      pSelH.innerHTML = '';

      const famContainer = document.getElementById('family-list');
      let famHtml = '';

      households.forEach(hh => {
        famHtml += `
          <div class="card" style="border-left: 4px solid var(--primary);">
            <div style="font-weight: 800; font-size: 16px; margin-bottom: 4px;">🏡 ${hh.village}, ${hh.district}</div>
            <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 12px;">Members: ${hh.member_count} | Consent: ✓</div>
            <div style="display: flex; flex-direction: column; gap: 10px;">
              ${hh.members.map(m => {
                const opt1 = document.createElement('option');
                opt1.value = m.id;
                opt1.innerText = `${m.name} (${m.relation})`;
                pSelSugg.appendChild(opt1);

                const opt2 = document.createElement('option');
                opt2.value = m.id;
                opt2.innerText = `${m.name} (${m.relation})`;
                pSelH.appendChild(opt2);

                return `
                  <div style="background: rgba(0,0,0,0.3); padding: 12px; border-radius: 12px; display: flex; justify-content: space-between; align-items: center;">
                    <div>
                      <div style="font-weight: 700; font-size: 14px;">${m.name} <span style="font-size: 11px; color: var(--text-muted);">(${m.relation})</span></div>
                      <div style="font-size: 12px; color: var(--text-muted); margin-top: 2px;">
                        🎂 ${m.dob} | 🎓 ${m.education} | 🏷️ ${m.category}
                      </div>
                      ${m.skills && m.skills.length > 0 ? `<div style="font-size: 11px; color: #60a5fa; margin-top: 4px;">🛠️ Skills: ${m.skills.join(', ')}</div>` : ''}
                    </div>
                    <button onclick="viewPersonDetails('${m.id}')" style="background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.15); color: #fff; padding: 6px 10px; border-radius: 10px; font-size: 11px; cursor: pointer;">View Suggestions</button>
                  </div>
                `;
              }).join('')}
            </div>
          </div>
        `;
      });

      famContainer.innerHTML = famHtml || 'No household registered.';
      if (pSelSugg.value) loadSuggestions(pSelSugg.value);
      if (pSelH.value) loadHealth(pSelH.value);
    }

    function viewPersonDetails(personId) {
      document.getElementById('person-select-sugg').value = personId;
      showSection('suggestions', document.querySelectorAll('.nav-card')[1]);
      loadSuggestions(personId);
    }

    async function checkFamilyEligibility(oppId) {
      if (households.length === 0) return;
      const hhId = households[0].id;
      const res = await fetch(`/api/match/household/${hhId}`);
      const data = await res.json();
      const matches = data.matches.filter(m => m.opportunity_id === oppId);

      let msg = `Family Eligibility Results:\n\n`;
      matches.forEach(m => {
        msg += `• ${m.person_name}: ${m.status}\n  ${m.reasons.join(', ') || m.question || 'Eligible'}\n\n`;
      });
      alert(msg);
    }

    async function loadSuggestions(personId) {
      if (!personId) return;
      const res = await fetch(`/api/suggestions/${personId}?lang=${currentLang}`);
      const data = await res.json();
      const container = document.getElementById('suggestions-list');

      if (!data.suggestions || data.suggestions.length === 0) {
        container.innerHTML = '<div class="card">No suggestions found.</div>';
        return;
      }

      const whyHdr = I18N.why_fit_hdr[currentLang] || '💡 Why this fits you:';
      const pathHdr = I18N.pathway_hdr[currentLang] || '🚀 How to become eligible:';
      const fitLbl = I18N.fit_score_lbl[currentLang] || '🎯 Fit Score:';
      const srcLbl = I18N.lbl_source[currentLang] || '🔗 Official Notice';

      container.innerHTML = data.suggestions.map(s => {
        const title = s.title_localized || (currentLang === 'hi' && s.title_hi ? s.title_hi : s.title);
        const whyFit = s.why_fit_localized || (currentLang === 'hi' ? s.why_fit_hi : s.why_fit);
        const statusBadge = s.status === 'ELIGIBLE' ? 'badge-eligible' : (s.status === 'POSSIBLE' ? 'badge-possible' : 'badge-not');
        const statusText = s.status === 'ELIGIBLE' ? '✓ ELIGIBLE' : (s.status === 'POSSIBLE' ? '? POSSIBLE' : '✗ NOT ELIGIBLE');

        return `
          <div class="card" style="border-left: 4px solid ${s.status === 'ELIGIBLE' ? '#10b981' : (s.status === 'POSSIBLE' ? '#f59e0b' : '#ef4444')};">
            <div class="card-header">
              <div>
                <div class="card-title">${title}</div>
                <div class="card-org">${s.org || ''} • <span style="text-transform: uppercase;">${s.type}</span></div>
              </div>
              <span class="badge ${statusBadge}">${statusText}</span>
            </div>

            <div class="why-fit-box">
              <strong>${whyHdr}</strong><br>
              ${whyFit}
            </div>

            ${s.pathway_step ? `
              <div class="pathway-box">
                <strong>${pathHdr}</strong><br>
                ${s.pathway_step.action_required}<br>
                <a href="${s.pathway_step.source_url}" target="_blank" style="color: #fbbf24; text-decoration: none; font-weight: 600;">🔗 ${s.pathway_step.step_title} (View Details)</a>
              </div>` : ''}

            <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 10px; font-size: 11px; color: var(--text-muted);">
              <span>${fitLbl} ${Math.round(s.fit_score * 100)}%</span>
              <a href="${s.source_url}" target="_blank" style="color: var(--primary); text-decoration: none;">${srcLbl}</a>
            </div>
          </div>
        `;
      }).join('');
    }

    async function loadHealth(personId) {
      if (!personId) return;
      const res = await fetch(`/api/health/${personId}`);
      const data = await res.json();
      const container = document.getElementById('health-content');

      const imms = data.immunizations || [];
      const redFlags = data.relevant_red_flags || [];

      container.innerHTML = `
        <div class="card">
          <div style="font-weight: 800; font-size: 16px; margin-bottom: 8px;">
            👶 ${data.name} (Age: ${data.age_years} yrs ${data.age_months % 12} mos)
          </div>
          <div style="font-size: 13px; color: var(--text-muted); margin-bottom: 16px;">
            Source: ${data.source}
          </div>

          ${imms.length > 0 ? `
            <div style="font-weight: 700; font-size: 14px; margin-bottom: 8px;">💉 Universal Immunization Schedule (NIS):</div>
            <div style="display: flex; flex-direction: column; gap: 8px; margin-bottom: 16px;">
              ${imms.map(i => `
                <div style="background: rgba(0,0,0,0.3); padding: 10px 14px; border-radius: 10px; display: flex; justify-content: space-between; align-items: center;">
                  <div>
                    <div style="font-weight: 600; font-size: 13px;">${i.vaccine}</div>
                    <div style="font-size: 11px; color: var(--text-muted);">${i.notes || ''}</div>
                  </div>
                  <span class="badge ${i.status === 'due_now' ? 'badge-possible' : (i.status === 'upcoming' ? 'badge-eligible' : 'badge-not')}">
                    ${i.status === 'due_now' ? 'DUE' : (i.status === 'upcoming' ? 'UPCOMING' : 'PASSED')}
                  </span>
                </div>
              `).join('')}
            </div>` : ''}

          <div style="font-weight: 700; font-size: 14px; margin-bottom: 8px; color: #fca5a5;">🚨 Danger Signs & Community Referral (NHM):</div>
          <div style="display: flex; flex-direction: column; gap: 8px;">
            ${redFlags.map(rf => `
              <div style="background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.2); padding: 10px 14px; border-radius: 10px;">
                <div style="font-weight: 700; font-size: 13px; color: #fecaca;">⚠️ ${rf.symptom}</div>
                <div style="font-size: 12px; color: #fff; margin-top: 4px;">🏥 <strong>Action:</strong> ${rf.action}</div>
                <div style="font-size: 10px; color: var(--text-muted); margin-top: 4px;">Reference: ${rf.source_ref}</div>
              </div>
            `).join('')}
          </div>
        </div>
      `;
    }

    async function setFastForward(days) {
      fastForwardDays = days;
      document.getElementById('ff-val').innerText = `+${days} days`;
      await loadReminders();
    }

    async function loadReminders() {
      const res = await fetch(`/api/reminders?fast_forward_days=${fastForwardDays}`);
      const data = await res.json();
      renderReminders(data);
    }

    function renderReminders(data) {
      const container = document.getElementById('reminders-list');
      if (!data || !data.active_reminders || data.active_reminders.length === 0) {
        container.innerHTML = `<div class="card" style="text-align: center; color: var(--text-muted);">No reminders for this date.</div>`;
        return;
      }
      container.innerHTML = data.active_reminders.map(r => {
        const msg = currentLang === 'hi' && r.message_hi ? r.message_hi : r.message;
        const oppTitle = currentLang === 'hi' && r.opportunity_title_hi ? r.opportunity_title_hi : r.opportunity_title;
        return `
          <div class="card" style="border-left: 4px solid var(--accent-amber);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
              <span style="font-weight: 700; font-size: 14px; color: #fbbf24;">⏰ ${r.person_name}</span>
              <span class="badge badge-possible">${r.kind.toUpperCase()}</span>
            </div>
            <div style="font-size: 13px; color: #fff; margin-bottom: 6px;">${msg}</div>
            <div style="font-size: 11px; color: var(--text-muted);">
              Opportunity: <strong>${oppTitle}</strong> | Due Date: <strong>${r.due_at}</strong>
            </div>
          </div>
        `;
      }).join('');
    }

    async function loadDashboard() {
      const resStats = await fetch('/api/stats');
      const stats = await resStats.json();
      const container = document.getElementById('dashboard-content');
      container.innerHTML = `
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 16px;">
          <div class="card" style="padding: 14px;"><div style="font-size: 11px; color: var(--text-muted);">Active Opportunities</div><div style="font-size: 24px; font-weight: 800;">${stats.active_opportunities}</div></div>
          <div class="card" style="padding: 14px;"><div style="font-size: 11px; color: var(--text-muted);">Households</div><div style="font-size: 24px; font-weight: 800;">${stats.registered_households}</div></div>
          <div class="card" style="padding: 14px;"><div style="font-size: 11px; color: var(--text-muted);">Residents</div><div style="font-size: 24px; font-weight: 800;">${stats.village_residents}</div></div>
          <div class="card" style="padding: 14px;"><div style="font-size: 11px; color: var(--text-muted);">Verified Packets</div><div style="font-size: 24px; font-weight: 800; color: #34d399;">${stats.verified_broadcast_packets}</div></div>
        </div>
        <div class="card">
          <div style="font-weight: 700; margin-bottom: 8px;">📡 Sarvam AI & Ed25519 Security</div>
          <p style="font-size: 12px; color: var(--text-muted); line-height: 1.5;">
            The village hub operates offline and supports 9 Indian languages (Hindi, Bengali, Telugu, Marathi, Tamil, Gujarati, Kannada, Malayalam, Punjabi, Odia) and English via Sarvam AI.
          </p>
        </div>
      `;
    }

    async function scanBroadcast() {
      const res = await fetch('/api/transport/scan', { method: 'POST' });
      const data = await res.json();
      alert(`Radio Sync complete. ${data.new_packets_ingested} new verified packets received.`);
      await init();
    }

    window.onload = init;
  </script>
</body>
</html>
"""
