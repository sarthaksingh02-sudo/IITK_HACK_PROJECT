"""
hub/main.py
FastAPI app for the Village Hub.
Serves the complete offline-first API and rich PWA interface for rural households.
Features:
  - Deterministic eligibility evaluator
  - Feature K suggestions with pathway guidance
  - Family health module (NIS immunization & NHM red flags)
  - Reminders scheduler with Fast-Forward simulation control
  - Voice query assistant (Hindi & English)
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
    # Ingest any existing signed broadcast packets on startup
    count = transport.scan_and_ingest_all()
    if count > 0:
        print(f"[hub/startup] Ingested {count} broadcast packet(s).")
    yield


app = FastAPI(
    title="AccessAI Village Hub",
    description="Offline-First Village Hub for Rural Households (AVINYA 2K26).",
    version="1.0.0",
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


class VoiceQueryRequest(BaseModel):
    query: str
    household_id: Optional[str] = None
    person_id: Optional[str] = None
    lang: str = "hi"


# ── Health & Transport ────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "hub",
        "transport": os.getenv("HUB_TRANSPORT", "file"),
        "offline_mode": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
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
    db: Session = Depends(get_db),
):
    query = db.query(HubOpportunity)
    if type:
        query = query.filter(HubOpportunity.type == type)
    opps = query.order_by(HubOpportunity.priority.desc()).all()

    items = []
    for o in opps:
        items.append({
            "id": o.id,
            "type": o.type,
            "title": o.title,
            "title_hi": o.title_hi,
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

    # Format result
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
def get_suggestions_route(person_id: str, db: Session = Depends(get_db)):
    """Feature K: Returns ranked recommendations with 'Why this fits', pathways, and citations."""
    person = db.get(HubPerson, person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    opps = db.query(HubOpportunity).all()
    suggestions = generate_person_suggestions(person, opps)

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


# ── Voice Assistant ───────────────────────────────────────────────────────────

@app.post("/api/voice/query")
def api_voice_query(req: VoiceQueryRequest):
    """Processes spoken or typed query in Hindi/English with deterministic routing and synthesis."""
    res = process_voice_query(
        query_text=req.query,
        household_id=req.household_id,
        person_id=req.person_id,
        lang=req.lang,
    )
    return res


# ── PWA Frontend UI ───────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def pwa_ui():
    """Serves the rich PWA interface for the Village Hub."""
    return HTMLResponse(content=_HUB_PWA_HTML)


_HUB_PWA_HTML = """<!DOCTYPE html>
<html lang="hi">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
  <title>AccessAI Village Hub | ग्रामीण जन सेवा केंद्र</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Rozha+One&family=Outfit:wght@400;500;600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
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
      padding-bottom: 90px;
    }
    
    /* Top Header */
    .header {
      background: rgba(11, 15, 25, 0.9);
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
      width: 40px; height: 40px; border-radius: 12px;
      background: linear-gradient(135deg, #2563eb, #10b981);
      display: flex; align-items: center; justify-content: center;
      font-size: 20px; box-shadow: 0 4px 16px var(--primary-glow);
    }
    .brand-title { font-family: 'Outfit', sans-serif; font-size: 19px; font-weight: 800; letter-spacing: -0.5px; }
    .brand-sub { font-size: 11px; color: var(--text-muted); }
    
    .lang-toggle {
      background: rgba(255, 255, 255, 0.08);
      border: 1px solid rgba(255, 255, 255, 0.15);
      border-radius: 20px;
      padding: 4px;
      display: flex;
      gap: 4px;
    }
    .lang-btn {
      background: transparent;
      border: none;
      color: var(--text-muted);
      padding: 4px 10px;
      border-radius: 16px;
      font-size: 12px;
      font-weight: 700;
      cursor: pointer;
      transition: all 0.2s;
    }
    .lang-btn.active {
      background: var(--primary);
      color: #fff;
      box-shadow: 0 2px 8px var(--primary-glow);
    }
    
    .container { max-width: 900px; margin: 0 auto; padding: 20px; }
    
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
    
    /* Voice Assistant Bar */
    .voice-bar {
      background: rgba(11, 15, 25, 0.95);
      backdrop-filter: blur(20px);
      position: fixed;
      bottom: 0;
      left: 0;
      right: 0;
      padding: 12px 20px;
      border-top: 1px solid var(--card-border);
      display: flex;
      align-items: center;
      gap: 12px;
      max-width: 900px;
      margin: 0 auto;
      z-index: 100;
    }
    .mic-btn {
      background: linear-gradient(135deg, #ef4444, #dc2626);
      color: white;
      border: none;
      width: 48px;
      height: 48px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 22px;
      cursor: pointer;
      box-shadow: 0 4px 16px rgba(239, 68, 68, 0.4);
      transition: all 0.2s;
    }
    .mic-btn.recording {
      animation: pulse 1.2s infinite;
      background: #10b981;
    }
    .voice-input {
      flex: 1;
      background: rgba(255, 255, 255, 0.08);
      border: 1px solid rgba(255, 255, 255, 0.12);
      border-radius: 24px;
      padding: 12px 18px;
      color: #fff;
      font-size: 14px;
      outline: none;
    }
    .send-btn {
      background: var(--primary);
      color: #fff;
      border: none;
      padding: 10px 18px;
      border-radius: 20px;
      font-weight: 700;
      cursor: pointer;
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

  <!-- Top Header -->
  <div class="header">
    <div class="brand">
      <div class="brand-icon">🏛️</div>
      <div>
        <div class="brand-title">AccessAI Village Hub</div>
        <div class="brand-sub" id="lbl-sub">ग्रामीण जन सुविधा एवं अवसर केंद्र</div>
      </div>
    </div>
    <div class="lang-toggle">
      <button class="lang-btn active" id="btn-hi" onclick="setLang('hi')">हिंदी</button>
      <button class="lang-btn" id="btn-en" onclick="setLang('en')">EN</button>
    </div>
  </div>

  <div class="container">
    
    <!-- Tier Status -->
    <div class="tier-banner">
      <div style="display: flex; align-items: center; gap: 10px;">
        <span style="font-size: 20px;">📡</span>
        <div>
          <div style="font-weight: 700; font-size: 13px;" id="lbl-tier">TIER 1 — गाँव का स्थानीय हब (ऑफलाइन सक्षम)</div>
          <div style="font-size: 11px; color: var(--text-muted);" id="lbl-sync">रेडियो ब्रॉडकास्ट द्वारा सत्यापित पैकेट प्राप्त</div>
        </div>
      </div>
      <button onclick="scanBroadcast()" style="background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); color: #fff; padding: 6px 12px; border-radius: 12px; font-size: 12px; cursor: pointer;">🔄 रेडियो सिंक</button>
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
          <button onclick="setFastForward(0)" class="lang-btn" style="background: rgba(255,255,255,0.1); color: #fff;">आज (0 दिन)</button>
          <button onclick="setFastForward(10)" class="lang-btn" style="background: rgba(255,255,255,0.1); color: #fff;">+10 दिन आगे</button>
          <button onclick="setFastForward(30)" class="lang-btn" style="background: rgba(255,255,255,0.1); color: #fff;">+30 दिन आगे</button>
          <button onclick="setFastForward(60)" class="lang-btn" style="background: rgba(255,255,255,0.1); color: #fff;">+60 दिन आगे</button>
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

  <!-- Bottom Voice Assistant Bar -->
  <div class="voice-bar">
    <button class="mic-btn" id="mic-button" onclick="toggleMic()" title="बोलकर पूछें">🎙️</button>
    <input type="text" id="voice-text" class="voice-input" placeholder="बोलें या टाइप करें: 'क्या मेरा बेटा आवेदन कर सकता है?'" onkeydown="if(event.key==='Enter') sendVoiceQuery()" />
    <button class="send-btn" onclick="sendVoiceQuery()" id="btn-ask">पूछें</button>
  </div>

  <!-- Voice Response Modal -->
  <div id="voice-modal" style="display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.7); backdrop-filter: blur(10px); z-index: 200; align-items: center; justify-content: center; padding: 20px;">
    <div class="card" style="max-width: 500px; width: 100%; border-color: var(--primary);">
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <span style="font-weight: 700; font-size: 16px;">🎙️ AccessAI Voice Assistant</span>
        <button onclick="closeVoiceModal()" style="background: transparent; border: none; color: #fff; font-size: 18px; cursor: pointer;">✕</button>
      </div>
      <div id="voice-modal-content" style="font-size: 14px; line-height: 1.5; color: #fff; margin: 12px 0;"></div>
      <button onclick="playVoiceReply()" style="background: var(--primary); color: #fff; border: none; padding: 10px; border-radius: 12px; font-weight: 700; cursor: pointer;">🔊 दोबारा सुनें</button>
    </div>
  </div>

  <script>
    let currentLang = 'hi';
    let fastForwardDays = 0;
    let households = [];
    let allOpportunities = [];
    let lastVoiceReplyText = '';
    let recognition = null;
    let isRecording = false;

    // Initialize Web Speech Recognition if available
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
      const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
      recognition = new SpeechRec();
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.lang = 'hi-IN';

      recognition.onstart = () => {
        isRecording = true;
        document.getElementById('mic-button').classList.add('recording');
        document.getElementById('voice-text').placeholder = 'सुन रहे हैं... कृपया बोलें...';
      };

      recognition.onresult = (e) => {
        const transcript = e.results[0][0].transcript;
        document.getElementById('voice-text').value = transcript;
        sendVoiceQuery();
      };

      recognition.onend = () => {
        isRecording = false;
        document.getElementById('mic-button').classList.remove('recording');
        document.getElementById('voice-text').placeholder = currentLang === 'hi' ? 'बोलें या टाइप करें: क्या मेरा बेटा आवेदन कर सकता है?' : 'Ask: can my son apply?';
      };
    }

    function toggleMic() {
      if (!recognition) {
        alert(currentLang === 'hi' ? 'आपके ब्राउज़र में माइक्रोफ़ोन पहचान उपलब्ध नहीं है। कृपया लिखकर पूछें।' : 'Speech recognition not supported in this browser. Please type.');
        return;
      }
      if (isRecording) {
        recognition.stop();
      } else {
        recognition.lang = currentLang === 'hi' ? 'hi-IN' : 'en-IN';
        recognition.start();
      }
    }

    async function init() {
      await loadHouseholds();
      await loadOpportunities();
      await loadReminders();
      await loadDashboard();
    }

    function setLang(lang) {
      currentLang = lang;
      document.getElementById('btn-hi').className = 'lang-btn ' + (lang === 'hi' ? 'active' : '');
      document.getElementById('btn-en').className = 'lang-btn ' + (lang === 'en' ? 'active' : '');
      
      // Update UI Labels
      document.getElementById('lbl-sub').innerText = lang === 'hi' ? 'ग्रामीण जन सुविधा एवं अवसर केंद्र' : 'Rural Welfare & Opportunities Center';
      document.getElementById('lbl-tier').innerText = lang === 'hi' ? 'TIER 1 — गाँव का स्थानीय हब (ऑफलाइन सक्षम)' : 'TIER 1 — Village Hub (Offline Capable)';
      document.getElementById('tab-opps').innerText = lang === 'hi' ? 'योजनाएं एवं अवसर' : 'Opportunities';
      document.getElementById('tab-sugg').innerText = lang === 'hi' ? 'आपके लिए सुझाव' : 'Suggested for You';
      document.getElementById('tab-fam').innerText = lang === 'hi' ? 'मेरा परिवार' : 'My Family';
      document.getElementById('tab-health').innerText = lang === 'hi' ? 'परिवार स्वास्थ्य' : 'Family Health';
      document.getElementById('tab-rem').innerText = lang === 'hi' ? 'स्मरण व अलर्ट' : 'Reminders';
      document.getElementById('tab-dash').innerText = lang === 'hi' ? 'ग्राम डैशबोर्ड' : 'Village Hub';
      document.getElementById('btn-ask').innerText = lang === 'hi' ? 'पूछें' : 'Ask';
      document.getElementById('voice-text').placeholder = lang === 'hi' ? 'बोलें या टाइप करें: क्या मेरा बेटा आवेदन कर सकता है?' : 'Ask: can my son apply?';

      renderOpportunities();
      const pSelSugg = document.getElementById('person-select-sugg');
      if (pSelSugg && pSelSugg.value) loadSuggestions(pSelSugg.value);
      const pSelH = document.getElementById('person-select-health');
      if (pSelH && pSelH.value) loadHealth(pSelH.value);
      renderReminders();
    }

    function showSection(name, tabEl) {
      document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
      document.querySelectorAll('.nav-card').forEach(c => c.classList.remove('active'));
      document.getElementById(`sec-${name}`).classList.add('active');
      if (tabEl) tabEl.classList.add('active');
    }

    async function loadOpportunities() {
      const res = await fetch('/api/opportunities');
      const data = await res.json();
      allOpportunities = data.items;
      renderOpportunities();
    }

    function renderOpportunities() {
      const container = document.getElementById('opps-list');
      if (allOpportunities.length === 0) {
        container.innerHTML = `<div class="card">${currentLang === 'hi' ? 'वर्तमान में कोई योजना उपलब्ध नहीं है।' : 'No opportunities available yet.'}</div>`;
        return;
      }
      container.innerHTML = allOpportunities.map(o => {
        const title = currentLang === 'hi' && o.title_hi ? o.title_hi : o.title;
        const lastDate = o.dates?.last_date || (currentLang === 'hi' ? 'शीघ्र' : 'Soon');
        const docs = o.documents_required || [];
        return `
          <div class="card">
            <div class="card-header">
              <div>
                <div class="card-title">${title}</div>
                <div class="card-org">${o.org || ''} • <span style="text-transform: uppercase;">${o.type}</span></div>
              </div>
              <span class="badge badge-eligible">सक्रिय ACTIVE</span>
            </div>
            <div style="font-size: 13px; color: var(--text-muted); margin-bottom: 8px;">
              🗓️ ${currentLang === 'hi' ? 'अंतिम तिथि' : 'Last Date'}: <strong>${lastDate}</strong> | 💰 ${currentLang === 'hi' ? 'शुल्क' : 'Fee'}: <strong>₹${o.fee || 0}</strong>
            </div>
            ${docs.length > 0 ? `
              <div style="font-size: 12px; margin: 8px 0; background: rgba(0,0,0,0.2); padding: 8px 12px; border-radius: 8px;">
                📑 <strong>${currentLang === 'hi' ? 'आवश्यक दस्तावेज़' : 'Documents'}:</strong>
                ${docs.map(d => `${d.name_hi || d.name} (${d.typical_lead_time_days || 0} ${currentLang === 'hi' ? 'दिन' : 'days'})`).join(', ')}
              </div>` : ''}
            <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 12px;">
              <a href="${o.source_url}" target="_blank" style="font-size: 12px; color: var(--primary); text-decoration: none;">🔗 ${currentLang === 'hi' ? 'आधिकारिक स्रोत' : 'Source'}</a>
              <button onclick="checkFamilyEligibility('${o.id}')" style="background: rgba(59, 130, 246, 0.2); border: 1px solid var(--primary); color: #fff; padding: 6px 12px; border-radius: 12px; font-size: 12px; cursor: pointer;">
                👨‍👩‍👧 ${currentLang === 'hi' ? 'परिवार की पात्रता जांचें' : 'Check Family Eligibility'}
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
            <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 12px;">सदस्य संख्या: ${hh.member_count} | सहमति प्राप्त: ✓</div>
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
                      ${m.skills && m.skills.length > 0 ? `<div style="font-size: 11px; color: #60a5fa; margin-top: 4px;">🛠️ हुनर: ${m.skills.join(', ')}</div>` : ''}
                    </div>
                    <button onclick="viewPersonDetails('${m.id}')" style="background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.15); color: #fff; padding: 6px 10px; border-radius: 10px; font-size: 11px; cursor: pointer;">सुझाव देखें</button>
                  </div>
                `;
              }).join('')}
            </div>
          </div>
        `;
      });

      famContainer.innerHTML = famHtml || 'कोई परिवार पंजीकृत नहीं है।';
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

      let msg = `${currentLang === 'hi' ? 'परिवार पात्रता परिणाम' : 'Family Eligibility Results'}:\n\n`;
      matches.forEach(m => {
        msg += `• ${m.person_name}: ${m.status}\n  ${m.reasons.join(', ') || m.question || 'पूर्णतः पात्र'}\n\n`;
      });
      alert(msg);
    }

    async function loadSuggestions(personId) {
      if (!personId) return;
      const res = await fetch(`/api/suggestions/${personId}`);
      const data = await res.json();
      const container = document.getElementById('suggestions-list');

      if (!data.suggestions || data.suggestions.length === 0) {
        container.innerHTML = '<div class="card">कोई सुझाव उपलब्ध नहीं है।</div>';
        return;
      }

      container.innerHTML = data.suggestions.map(s => {
        const title = currentLang === 'hi' && s.title_hi ? s.title_hi : s.title;
        const whyFit = currentLang === 'hi' ? s.why_fit_hi : s.why_fit;
        const statusBadge = s.status === 'ELIGIBLE' ? 'badge-eligible' : (s.status === 'POSSIBLE' ? 'badge-possible' : 'badge-not');
        const statusText = s.status === 'ELIGIBLE' ? (currentLang === 'hi' ? '✓ पात्र (ELIGIBLE)' : '✓ ELIGIBLE') : (s.status === 'POSSIBLE' ? (currentLang === 'hi' ? '? संभावित (POSSIBLE)' : '? POSSIBLE') : (currentLang === 'hi' ? '✗ अपात्र (NOT ELIGIBLE)' : '✗ NOT ELIGIBLE'));

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
              💡 <strong>${currentLang === 'hi' ? 'यह आपके लिए क्यों उपयुक्त है' : 'Why this fits you'}:</strong><br>
              ${whyFit}
            </div>

            ${s.pathway_step ? `
              <div class="pathway-box">
                🚀 <strong>${currentLang === 'hi' ? 'पात्र बनने के लिए कदम (Next Step)' : 'How to become eligible'}:</strong><br>
                ${s.pathway_step.action_required}<br>
                <a href="${s.pathway_step.source_url}" target="_blank" style="color: #fbbf24; text-decoration: none; font-weight: 600;">🔗 ${s.pathway_step.step_title} (${currentLang === 'hi' ? 'विवरण देखें' : 'View Details'})</a>
              </div>` : ''}

            <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 10px; font-size: 11px; color: var(--text-muted);">
              <span>🎯 Fit Score: ${Math.round(s.fit_score * 100)}%</span>
              <a href="${s.source_url}" target="_blank" style="color: var(--primary); text-decoration: none;">🔗 ${currentLang === 'hi' ? 'आधिकारिक सूचना' : 'Official Notice'}</a>
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
            👶 ${data.name} (आयु: ${data.age_years} वर्ष ${data.age_months % 12} माह)
          </div>
          <div style="font-size: 13px; color: var(--text-muted); margin-bottom: 16px;">
            स्रोत: ${data.source}
          </div>

          ${imms.length > 0 ? `
            <div style="font-weight: 700; font-size: 14px; margin-bottom: 8px;">💉 राष्ट्रीय टीकाकरण सारणी (NIS):</div>
            <div style="display: flex; flex-direction: column; gap: 8px; margin-bottom: 16px;">
              ${imms.map(i => `
                <div style="background: rgba(0,0,0,0.3); padding: 10px 14px; border-radius: 10px; display: flex; justify-content: space-between; align-items: center;">
                  <div>
                    <div style="font-weight: 600; font-size: 13px;">${i.vaccine}</div>
                    <div style="font-size: 11px; color: var(--text-muted);">${i.notes || ''}</div>
                  </div>
                  <span class="badge ${i.status === 'due_now' ? 'badge-possible' : (i.status === 'upcoming' ? 'badge-eligible' : 'badge-not')}">
                    ${i.status === 'due_now' ? 'अपेक्षित DUE' : (i.status === 'upcoming' ? 'आगामी' : 'समय पूर्ण')}
                  </span>
                </div>
              `).join('')}
            </div>` : ''}

          <div style="font-weight: 700; font-size: 14px; margin-bottom: 8px; color: #fca5a5;">🚨 स्वास्थ्य खतरे के लक्षण व रेफरल दिशानिर्देश (NHM):</div>
          <div style="display: flex; flex-direction: column; gap: 8px;">
            ${redFlags.map(rf => `
              <div style="background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.2); padding: 10px 14px; border-radius: 10px;">
                <div style="font-weight: 700; font-size: 13px; color: #fecaca;">⚠️ ${currentLang === 'hi' && rf.symptom_hi ? rf.symptom_hi : rf.symptom}</div>
                <div style="font-size: 12px; color: #fff; margin-top: 4px;">🏥 <strong>कार्यवाही:</strong> ${currentLang === 'hi' && rf.action_hi ? rf.action_hi : rf.action}</div>
                <div style="font-size: 10px; color: var(--text-muted); margin-top: 4px;">संदर्भ: ${rf.source_ref}</div>
              </div>
            `).join('')}
          </div>
        </div>
      `;
    }

    async function setFastForward(days) {
      fastForwardDays = days;
      document.getElementById('ff-val').innerText = `+${days} दिन`;
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
        container.innerHTML = `<div class="card" style="text-align: center; color: var(--text-muted);">${currentLang === 'hi' ? 'इस तिथि पर कोई स्मरण अलर्ट नहीं है।' : 'No reminders for this date.'}</div>`;
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
              योजना: <strong>${oppTitle}</strong> | नियत तिथि: <strong>${r.due_at}</strong>
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
          <div class="card" style="padding: 14px;"><div style="font-size: 11px; color: var(--text-muted);">सक्रिय योजनाएं</div><div style="font-size: 24px; font-weight: 800;">${stats.active_opportunities}</div></div>
          <div class="card" style="padding: 14px;"><div style="font-size: 11px; color: var(--text-muted);">पंजीकृत परिवार</div><div style="font-size: 24px; font-weight: 800;">${stats.registered_households}</div></div>
          <div class="card" style="padding: 14px;"><div style="font-size: 11px; color: var(--text-muted);">गाँव के निवासी</div><div style="font-size: 24px; font-weight: 800;">${stats.village_residents}</div></div>
          <div class="card" style="padding: 14px;"><div style="font-size: 11px; color: var(--text-muted);">सत्यापित रेडियो पैकेट</div><div style="font-size: 24px; font-weight: 800; color: #34d399;">${stats.verified_broadcast_packets}</div></div>
        </div>
        <div class="card">
          <div style="font-weight: 700; margin-bottom: 8px;">📡 रेडियो ब्रॉडकास्ट एवं सुरक्षा (Ed25519)</div>
          <p style="font-size: 12px; color: var(--text-muted); line-height: 1.5;">
            गाँव का हब ऑफलाइन रहते हुए केवल Ed25519 डिजिटल हस्ताक्षर द्वारा सत्यापित आधिकारिक पैकेट स्वीकार करता है। छेड़छाड़ किया गया कोई भी पैकेट स्वतः अस्वीकार हो जाता है।
          </p>
        </div>
      `;
    }

    async function scanBroadcast() {
      const res = await fetch('/api/transport/scan', { method: 'POST' });
      const data = await res.json();
      alert(`रेडियो सिंक पूर्ण। ${data.new_packets_ingested} नए पैकेट प्राप्त हुए।`);
      await init();
    }

    async function sendVoiceQuery() {
      const input = document.getElementById('voice-text');
      const query = input.value.trim();
      if (!query) return;

      const pSel = document.getElementById('person-select-sugg');
      const personId = pSel ? pSel.value : null;

      const res = await fetch('/api/voice/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: query,
          person_id: personId,
          lang: currentLang
        })
      });
      const data = await res.json();
      lastVoiceReplyText = currentLang === 'hi' ? data.reply_text_hi : data.reply_text_en;

      document.getElementById('voice-modal-content').innerText = lastVoiceReplyText;
      document.getElementById('voice-modal').style.display = 'flex';
      playVoiceReply();
      input.value = '';
    }

    function playVoiceReply() {
      if ('speechSynthesis' in window && lastVoiceReplyText) {
        const u = new SpeechSynthesisUtterance(lastVoiceReplyText);
        u.lang = currentLang === 'hi' ? 'hi-IN' : 'en-IN';
        window.speechSynthesis.speak(u);
      }
    }

    function closeVoiceModal() {
      document.getElementById('voice-modal').style.display = 'none';
      if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    }

    window.onload = init;
  </script>
</body>
</html>
"""
