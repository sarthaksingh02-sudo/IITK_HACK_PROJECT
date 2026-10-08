"""
cloud/main.py
FastAPI app for the Cloud Control Center.
Provides complete REST API and rich Admin Control Center UI for:
  - Ingesting official notices (text / file / PDF)
  - Reviewing & editing extracted fields side-by-side with source text & span citations
  - Human review & approval workflow
  - Hindi + English translation & TTS audio bulletins
  - Ed25519 packet signing & publishing to simulated radio broadcast carousel (packets/)
"""

from __future__ import annotations

import json
import os
import pathlib
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import Body, Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

load_dotenv()

from cloud.db import CloudOpportunity, CloudPacket, RawNotice, get_db, init_db
from cloud.extractor import extract_notice_spans
from cloud.llm_client import MOCK_LLM, generate_audio_bulletin, translate_text
from cloud.publisher import publish_opportunity_packet, publish_update_packet
from shared.sarvam_client import SARVAM_LANGUAGES, translate_with_sarvam
from shared.schemas import Opportunity, OpportunityType

NOTICES_DIR = pathlib.Path(__file__).parent.parent / "data" / "real" / "notices"
PACKETS_DIR = pathlib.Path(os.getenv("PACKETS_DIR", "./packets"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    PACKETS_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="AccessAI Cloud Control Center",
    description="Ingest → Extract → Review/Edit → Approve → Sign & Publish packets.",
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


# ── Pydantic Request Models ───────────────────────────────────────────────────

class IngestTextRequest(BaseModel):
    raw_text: str
    source_url: Optional[str] = None
    language: str = "en"


class UpdateOpportunityRequest(BaseModel):
    title: Optional[str] = None
    title_hi: Optional[str] = None
    type: Optional[str] = None
    org: Optional[str] = None
    level: Optional[str] = None
    geo_state: Optional[str] = None
    geo_district: Optional[str] = None
    eligibility: Optional[dict[str, Any]] = None
    dates: Optional[dict[str, Any]] = None
    documents_required: Optional[list[dict[str, Any]]] = None
    fee: Optional[float] = None
    apply_mode: Optional[str] = None
    apply_steps: Optional[list[str]] = None
    priority: Optional[int] = None
    source_url: Optional[str] = None


# ── Health & Stats ────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "cloud",
        "mock_llm": MOCK_LLM,
        "packets_dir": str(PACKETS_DIR),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db)):
    raw_count = db.query(RawNotice).count()
    draft_count = db.query(CloudOpportunity).filter(CloudOpportunity.status == "draft").count()
    approved_count = db.query(CloudOpportunity).filter(CloudOpportunity.status == "approved").count()
    published_count = db.query(CloudOpportunity).filter(CloudOpportunity.status == "published").count()
    packets_on_disk = len(list(PACKETS_DIR.glob("*.packet"))) if PACKETS_DIR.exists() else 0

    return {
        "raw_notices": raw_count,
        "drafts_pending_review": draft_count,
        "approved": approved_count,
        "published": published_count,
        "packets_in_carousel": packets_on_disk,
        "mock_mode": MOCK_LLM,
    }


# ── Notice Ingestion ──────────────────────────────────────────────────────────

@app.get("/api/notices/available-files")
def list_available_notice_files():
    """Lists real notice files available in data/real/notices/ folder."""
    if not NOTICES_DIR.exists():
        return {"files": []}
    files = []
    for f in NOTICES_DIR.iterdir():
        if f.suffix in (".txt", ".pdf", ".md") and f.name != "README.md":
            files.append({
                "name": f.name,
                "size_bytes": f.stat().st_size,
                "path": str(f.name),
            })
    return {"files": files}


@app.post("/api/notices/ingest-text")
def ingest_notice_text(req: IngestTextRequest, db: Session = Depends(get_db)):
    """Ingests pasted notice text, runs extraction, and creates a draft opportunity."""
    now = datetime.now(timezone.utc).isoformat()
    raw_id = f"notice-{uuid.uuid4().hex[:8]}"

    # 1. Store raw notice
    raw_notice = RawNotice(
        id=raw_id,
        source_url=req.source_url,
        raw_text=req.raw_text,
        language=req.language,
        ingested_at=now,
        status="processing",
    )
    db.add(raw_notice)

    # 2. Extract structured fields
    extracted = extract_notice_spans(req.raw_text)
    if req.source_url and not extracted.get("source_url"):
        extracted["source_url"] = req.source_url

    opp_id = f"opp-{uuid.uuid4().hex[:8]}"
    opp = CloudOpportunity(
        id=opp_id,
        raw_notice_id=raw_id,
        type=extracted.get("type", "scheme"),
        title=extracted.get("title", "Untitled Notice"),
        title_hi=extracted.get("title_hi"),
        org=extracted.get("org"),
        level=extracted.get("level", "central"),
        geo_state=extracted.get("geo", {}).get("state"),
        geo_district=extracted.get("geo", {}).get("district"),
        geo_block=extracted.get("geo", {}).get("block"),
        language=req.language,
        eligibility_json=json.dumps(extracted.get("eligibility", {})),
        dates_json=json.dumps(extracted.get("dates", {})),
        documents_json=json.dumps(extracted.get("documents_required", [])),
        fee=extracted.get("fee", 0.0),
        apply_mode=extracted.get("apply_mode", "online"),
        apply_steps_json=json.dumps(extracted.get("apply_steps", [])),
        source_url=extracted.get("source_url") or req.source_url or "https://gov.in",
        last_verified=now,
        priority=extracted.get("priority", 5),
        status="draft",
        is_sample=MOCK_LLM,
        created_at=now,
        updated_at=now,
    )
    db.add(opp)
    raw_notice.status = "extracted"
    db.commit()

    return {
        "success": True,
        "opportunity_id": opp_id,
        "raw_notice_id": raw_id,
        "extracted": extracted,
        "status": "draft",
        "message": "Notice ingested. Please review and approve before publishing.",
    }


@app.post("/api/notices/ingest-file/{filename}")
def ingest_notice_file(filename: str, db: Session = Depends(get_db)):
    """Ingests a notice file from data/real/notices/."""
    file_path = NOTICES_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found in data/real/notices/")

    raw_text = file_path.read_text(encoding="utf-8", errors="replace")
    req = IngestTextRequest(raw_text=raw_text, source_url=f"file://{filename}")
    return ingest_notice_text(req, db)


# ── Opportunity Review & Editing ──────────────────────────────────────────────

@app.get("/api/opportunities")
def list_opportunities(status: Optional[str] = None, db: Session = Depends(get_db)):
    """Lists opportunities with optional status filtering (draft, approved, published)."""
    query = db.query(CloudOpportunity)
    if status:
        query = query.filter(CloudOpportunity.status == status)
    opps = query.order_by(CloudOpportunity.created_at.desc()).all()

    result = []
    for o in opps:
        result.append({
            "id": o.id,
            "raw_notice_id": o.raw_notice_id,
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
            "status": o.status,
            "is_sample": o.is_sample,
            "created_at": o.created_at,
            "updated_at": o.updated_at,
        })
    return {"items": result, "count": len(result)}


@app.get("/api/opportunities/{opp_id}")
def get_opportunity(opp_id: str, db: Session = Depends(get_db)):
    """Gets single opportunity along with its raw notice source text and text spans for verification."""
    o = db.get(CloudOpportunity, opp_id)
    if not o:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    raw_notice = None
    source_spans = {}
    if o.raw_notice_id:
        raw_obj = db.get(RawNotice, o.raw_notice_id)
        if raw_obj:
            raw_notice = raw_obj.raw_text
            extracted_probe = extract_notice_spans(raw_obj.raw_text)
            source_spans = extracted_probe.get("source_spans", {})

    return {
        "id": o.id,
        "raw_notice_id": o.raw_notice_id,
        "raw_source_text": raw_notice,
        "source_spans": source_spans,
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
        "status": o.status,
        "is_sample": o.is_sample,
        "created_at": o.created_at,
        "updated_at": o.updated_at,
    }


@app.put("/api/opportunities/{opp_id}")
def update_opportunity(opp_id: str, req: UpdateOpportunityRequest, db: Session = Depends(get_db)):
    """Human edits opportunity fields during review."""
    o = db.get(CloudOpportunity, opp_id)
    if not o:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    if req.title is not None:
        o.title = req.title
    if req.title_hi is not None:
        o.title_hi = req.title_hi
    if req.type is not None:
        o.type = req.type
    if req.org is not None:
        o.org = req.org
    if req.level is not None:
        o.level = req.level
    if req.geo_state is not None:
        o.geo_state = req.geo_state
    if req.geo_district is not None:
        o.geo_district = req.geo_district
    if req.eligibility is not None:
        o.eligibility_json = json.dumps(req.eligibility)
    if req.dates is not None:
        o.dates_json = json.dumps(req.dates)
    if req.documents_required is not None:
        o.documents_json = json.dumps(req.documents_required)
    if req.fee is not None:
        o.fee = req.fee
    if req.apply_mode is not None:
        o.apply_mode = req.apply_mode
    if req.apply_steps is not None:
        o.apply_steps_json = json.dumps(req.apply_steps)
    if req.priority is not None:
        o.priority = req.priority
    if req.source_url is not None:
        o.source_url = req.source_url

    o.updated_at = datetime.now(timezone.utc).isoformat()
    db.commit()
    return {"success": True, "id": o.id, "status": o.status, "message": "Opportunity updated."}


@app.post("/api/opportunities/{opp_id}/approve")
def approve_opportunity(opp_id: str, db: Session = Depends(get_db)):
    """Human approves the opportunity for publication."""
    o = db.get(CloudOpportunity, opp_id)
    if not o:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    o.status = "approved"
    o.updated_at = datetime.now(timezone.utc).isoformat()
    db.commit()
    return {"success": True, "id": o.id, "status": "approved", "message": "Approved for broadcast packet publishing."}


# ── Packet Publishing ─────────────────────────────────────────────────────────

@app.post("/api/opportunities/{opp_id}/publish")
def publish_opportunity(opp_id: str, db: Session = Depends(get_db)):
    """Signs opportunity with Ed25519 and outputs signed .packet file into packets/ broadcast carousel."""
    o = db.get(CloudOpportunity, opp_id)
    if not o:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    if o.status != "approved":
        raise HTTPException(
            status_code=400,
            detail=f"Opportunity status is '{o.status}'. It must be reviewed and 'approved' before publishing.",
        )

    # Construct Opportunity dict matching schema
    opp_dict = {
        "id": o.id,
        "type": o.type,
        "title": o.title,
        "title_hi": o.title_hi,
        "org": o.org,
        "level": o.level,
        "geo": {
            "state": o.geo_state,
            "district": o.geo_district,
            "block": o.geo_block,
        },
        "language": o.language or "hi",
        "eligibility": json.loads(o.eligibility_json) if o.eligibility_json else {},
        "dates": json.loads(o.dates_json) if o.dates_json else {},
        "documents_required": json.loads(o.documents_json) if o.documents_json else [],
        "fee": o.fee,
        "apply_mode": o.apply_mode,
        "apply_steps": json.loads(o.apply_steps_json) if o.apply_steps_json else [],
        "source_url": o.source_url,
        "last_verified": o.last_verified or datetime.now(timezone.utc).date().isoformat(),
        "priority": o.priority or 5,
        "is_sample": o.is_sample,
    }

    try:
        packet_path = publish_opportunity_packet(opp_dict)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Signing/publishing failed: {e}")

    o.status = "published"
    o.updated_at = datetime.now(timezone.utc).isoformat()
    db.commit()

    return {
        "success": True,
        "opportunity_id": o.id,
        "packet_file": packet_path.name,
        "status": "published",
        "broadcast_channel": "simulated-radio-carousel",
        "message": f"Packet signed with Ed25519 and broadcast to {packet_path.name}",
    }


@app.post("/api/publish-chain")
def run_publish_chain(req: IngestTextRequest, db: Session = Depends(get_db)):
    """One-click ingest -> extract -> auto-approve (if requested) -> sign -> publish chain."""
    ingest_res = ingest_notice_text(req, db)
    opp_id = ingest_res["opportunity_id"]
    approve_opportunity(opp_id, db)
    pub_res = publish_opportunity(opp_id, db)
    return {
        "success": True,
        "opportunity_id": opp_id,
        "packet_file": pub_res["packet_file"],
        "message": "Full publish chain completed successfully.",
    }


# ── Translation & Sarvam Languages ──────────────────────────────────────────

class TranslateRequest(BaseModel):
    text: str
    target_lang: str = "hi"
    source_lang: str = "en"


@app.get("/api/languages")
def get_languages():
    """Returns the 9 Indian languages + English supported by Sarvam AI."""
    return {"languages": SARVAM_LANGUAGES}


@app.post("/api/translate")
def api_translate(req: TranslateRequest):
    """Translates text using Sarvam AI Indian language translation API with offline fallback."""
    result = translate_with_sarvam(req.text, req.target_lang, req.source_lang)
    return {
        "original": req.text,
        "translated": result,
        "target_lang": req.target_lang,
        "engine": "sarvam-ai",
    }


class TTSRequest(BaseModel):
    text: str
    lang: str = "hi"


@app.post("/api/tts")
def api_tts(req: TTSRequest):
    result = generate_audio_bulletin(req.text, req.lang)
    return result


# ── Web UI Control Center ─────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def admin_ui():
    """Returns the Cloud Control Center web UI."""
    return HTMLResponse(content=_ADMIN_HTML)


_ADMIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>AccessAI Cloud Control Center</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #0b0f19;
      --card-bg: rgba(22, 30, 49, 0.75);
      --card-border: rgba(255, 255, 255, 0.08);
      --primary: #3b82f6;
      --primary-glow: rgba(59, 130, 246, 0.35);
      --accent: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
      --text: #f3f4f6;
      --text-muted: #9ca3af;
      --font-heading: 'Outfit', sans-serif;
      --font-body: 'Plus Jakarta Sans', sans-serif;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: radial-gradient(circle at 10% 20%, rgba(37, 99, 235, 0.12) 0%, transparent 40%),
                  radial-gradient(circle at 90% 80%, rgba(16, 185, 129, 0.08) 0%, transparent 40%),
                  var(--bg);
      color: var(--text);
      font-family: var(--font-body);
      min-height: 100vh;
      padding: 24px;
    }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--card-border);
    }
    .logo {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .logo-badge {
      background: linear-gradient(135deg, #2563eb, #3b82f6);
      width: 42px;
      height: 42px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 22px;
      box-shadow: 0 4px 20px var(--primary-glow);
    }
    h1 { font-family: var(--font-heading); font-size: 26px; font-weight: 700; letter-spacing: -0.5px; }
    .status-badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 6px 14px;
      border-radius: 9999px;
      font-size: 13px;
      font-weight: 600;
      background: rgba(16, 185, 129, 0.15);
      color: #34d399;
      border: 1px solid rgba(16, 185, 129, 0.3);
    }
    .pulse-dot {
      width: 8px;
      height: 8px;
      background: #10b981;
      border-radius: 50%;
      box-shadow: 0 0 10px #10b981;
      animation: pulse 2s infinite;
    }
    @keyframes pulse { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.4; transform: scale(0.85); } }
    
    .stats-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }
    .stat-card {
      background: var(--card-bg);
      backdrop-filter: blur(12px);
      border: 1px solid var(--card-border);
      border-radius: 16px;
      padding: 18px;
      transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .stat-card:hover { transform: translateY(-2px); border-color: rgba(255,255,255,0.18); }
    .stat-val { font-family: var(--font-heading); font-size: 28px; font-weight: 800; color: #fff; margin-top: 4px; }
    .stat-lbl { font-size: 13px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600; }
    
    .main-grid {
      display: grid;
      grid-template-columns: 1fr 1.2fr;
      gap: 24px;
    }
    @media (max-width: 1024px) { .main-grid { grid-template-columns: 1fr; } }
    
    .card {
      background: var(--card-bg);
      backdrop-filter: blur(16px);
      border: 1px solid var(--card-border);
      border-radius: 20px;
      padding: 24px;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
      display: flex;
      flex-direction: column;
      gap: 18px;
    }
    .card-title {
      font-family: var(--font-heading);
      font-size: 18px;
      font-weight: 700;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    
    textarea, input, select {
      width: 100%;
      background: rgba(11, 15, 25, 0.85);
      border: 1px solid rgba(255, 255, 255, 0.12);
      border-radius: 12px;
      padding: 12px 16px;
      color: #fff;
      font-family: var(--font-body);
      font-size: 14px;
      outline: none;
      transition: border-color 0.2s;
    }
    textarea:focus, input:focus, select:focus {
      border-color: var(--primary);
      box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.25);
    }
    textarea { resize: vertical; min-height: 140px; }
    
    button {
      background: linear-gradient(135deg, #2563eb, #1d4ed8);
      color: white;
      border: none;
      padding: 12px 20px;
      border-radius: 12px;
      font-family: var(--font-heading);
      font-weight: 600;
      font-size: 14px;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      transition: all 0.2s;
    }
    button:hover {
      background: linear-gradient(135deg, #3b82f6, #2563eb);
      box-shadow: 0 4px 16px var(--primary-glow);
      transform: translateY(-1px);
    }
    .btn-secondary {
      background: rgba(255, 255, 255, 0.08);
      border: 1px solid rgba(255, 255, 255, 0.15);
    }
    .btn-secondary:hover { background: rgba(255, 255, 255, 0.14); }
    .btn-success {
      background: linear-gradient(135deg, #059669, #10b981);
    }
    .btn-success:hover {
      background: linear-gradient(135deg, #10b981, #34d399);
      box-shadow: 0 4px 16px rgba(16, 185, 129, 0.35);
    }
    
    .table-container {
      overflow-x: auto;
      border-radius: 12px;
      border: 1px solid var(--card-border);
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }
    th, td {
      padding: 12px 14px;
      text-align: left;
      border-bottom: 1px solid var(--card-border);
    }
    th {
      background: rgba(11, 15, 25, 0.6);
      color: var(--text-muted);
      font-weight: 600;
      text-transform: uppercase;
      font-size: 11px;
      letter-spacing: 0.5px;
    }
    tr:hover td { background: rgba(255, 255, 255, 0.03); }
    
    .badge {
      display: inline-block;
      padding: 4px 8px;
      border-radius: 6px;
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
    }
    .badge-draft { background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }
    .badge-approved { background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); }
    .badge-published { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }
    
    .editor-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }
    .field-group { display: flex; flex-direction: column; gap: 4px; }
    .field-lbl { font-size: 12px; color: var(--text-muted); font-weight: 600; }
    
    .source-box {
      background: rgba(0, 0, 0, 0.35);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 12px;
      padding: 12px;
      font-family: monospace;
      font-size: 12px;
      line-height: 1.5;
      max-height: 200px;
      overflow-y: auto;
      white-space: pre-wrap;
      color: #93c5fd;
    }
    .audio-player {
      background: rgba(0,0,0,0.3);
      padding: 12px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      gap: 12px;
      margin-top: 8px;
    }
    .lang-dropdown-container {
      display: flex;
      align-items: center;
      gap: 8px;
      background: rgba(30, 41, 59, 0.85);
      border: 1px solid rgba(255, 255, 255, 0.15);
      border-radius: 12px;
      padding: 4px 10px;
    }
    .lang-select {
      background: transparent;
      border: none;
      color: #fff;
      font-weight: 600;
      font-size: 13px;
      cursor: pointer;
      outline: none;
      padding: 4px 6px;
    }
    .lang-select option {
      background: #0f172a;
      color: #fff;
    }
  </style>
</head>
<body>

  <div class="header">
    <div class="logo">
      <div class="logo-badge">📡</div>
      <div>
        <h1 id="lbl-cloud-title">AccessAI Cloud Control Center</h1>
        <div style="font-size: 13px; color: var(--text-muted);" id="lbl-cloud-sub">Tier 0 Broadcast & Packet Signing Station (AVINYA 2K26)</div>
      </div>
    </div>
    <div style="display: flex; gap: 12px; align-items: center;">
      <!-- Right-most Sarvam AI 9 Indian Languages + English Selector -->
      <div class="lang-dropdown-container">
        <span style="font-size: 16px;">🌐</span>
        <select id="global-lang-select" class="lang-select" onchange="setGlobalLang(this.value)">
          <option value="en" selected>🌐 English (EN)</option>
          <option value="hi">🇮🇳 हिन्दी (Hindi)</option>
          <option value="bn">🇮🇳 বাংলা (Bengali)</option>
          <option value="te">🇮🇳 తెలుగు (Telugu)</option>
          <option value="mr">🇮🇳 मराठी (Marathi)</option>
          <option value="ta">🇮🇳 தமிழ் (Tamil)</option>
          <option value="gu">🇮🇳 ગુજરાતી (Gujarati)</option>
          <option value="kn">🇮🇳 ಕನ್ನಡ (Kannada)</option>
          <option value="ml">🇮🇳 മലയാളം (Malayalam)</option>
          <option value="pa">🇮🇳 ਪੰਜਾਬੀ (Punjabi)</option>
          <option value="od">🇮🇳 ଓଡ଼ିଆ (Odia)</option>
        </select>
      </div>
      <span class="status-badge"><span class="pulse-dot"></span> <span id="lbl-status-badge">BROADCAST ACTIVE</span></span>
      <button onclick="refreshData()" class="btn-secondary" id="btn-refresh">🔄 Refresh</button>
    </div>
  </div>

  <div class="stats-grid">
    <div class="stat-card">
      <div class="stat-lbl" id="lbl-stat-notices">Notices Ingested</div>
      <div class="stat-val" id="stat-notices">0</div>
    </div>
    <div class="stat-card">
      <div class="stat-lbl" id="lbl-stat-drafts">Drafts Pending Review</div>
      <div class="stat-val" id="stat-drafts" style="color: #fbbf24;">0</div>
    </div>
    <div class="stat-card">
      <div class="stat-lbl" id="lbl-stat-approved">Approved Opportunities</div>
      <div class="stat-val" id="stat-approved" style="color: #60a5fa;">0</div>
    </div>
    <div class="stat-card">
      <div class="stat-lbl" id="lbl-stat-packets">Signed Packets (Carousel)</div>
      <div class="stat-val" id="stat-packets" style="color: #34d399;">0</div>
    </div>
  </div>

  <div class="main-grid">
    <!-- Left Column: Ingest & Queue -->
    <div style="display: flex; flex-direction: column; gap: 24px;">
      
      <!-- Ingest Card -->
      <div class="card">
        <div class="card-title">
          <span>📥 Ingest Government Notice</span>
          <select id="file-select" onchange="loadFileContent(this.value)" style="width: auto; padding: 6px 12px; font-size: 12px;">
            <option value="">-- Load from /data/real/notices/ --</option>
          </select>
        </div>
        <textarea id="notice-text" placeholder="Paste official notice text or select a file above..."></textarea>
        <div style="display: flex; gap: 12px;">
          <button onclick="ingestNotice()" style="flex: 1;">⚡ Ingest & Extract Fields</button>
          <button onclick="publishChain()" class="btn-success" style="flex: 1;">🚀 1-Click Publish</button>
        </div>
      </div>

      <!-- Opportunities Table -->
      <div class="card">
        <div class="card-title">
          <span>📋 Opportunities Repository</span>
        </div>
        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th>Title</th>
                <th>Type</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody id="opp-table-body">
              <tr><td colspan="4" style="text-align: center; color: var(--text-muted);">Loading opportunities...</td></tr>
            </tbody>
          </table>
        </div>
      </div>

    </div>

    <!-- Right Column: Interactive Review & Broadcast Card -->
    <div class="card" id="review-card">
      <div class="card-title">
        <span>🔍 Review & Packet Signing Studio</span>
        <span id="selected-badge" class="badge badge-draft">SELECT AN ITEM</span>
      </div>

      <div style="display: flex; flex-direction: column; gap: 12px;">
        <div class="field-group">
          <div class="field-lbl">Opportunity Title (English)</div>
          <input type="text" id="edit-title" placeholder="Select an opportunity to edit..." />
        </div>
        <div class="field-group">
          <div class="field-lbl">Opportunity Title (Hindi Translation)</div>
          <input type="text" id="edit-title-hi" placeholder="हिंदी शीर्षक..." />
        </div>

        <div class="editor-grid">
          <div class="field-group">
            <div class="field-lbl">Category / Scheme Type</div>
            <select id="edit-type">
              <option value="scheme">Scheme (योजना)</option>
              <option value="scholarship">Scholarship (छात्रवृत्ति)</option>
              <option value="job">Job / Recruitment (भर्ती)</option>
              <option value="training">Skill Training (प्रशिक्षण)</option>
              <option value="exam">Competitive Exam (परीक्षा)</option>
            </select>
          </div>
          <div class="field-group">
            <div class="field-lbl">Organization / Ministry</div>
            <input type="text" id="edit-org" />
          </div>
        </div>

        <div class="editor-grid">
          <div class="field-group">
            <div class="field-lbl">Min Age</div>
            <input type="number" id="edit-min-age" />
          </div>
          <div class="field-group">
            <div class="field-lbl">Max Age</div>
            <input type="number" id="edit-max-age" />
          </div>
        </div>

        <div class="editor-grid">
          <div class="field-group">
            <div class="field-lbl">Last Date (YYYY-MM-DD)</div>
            <input type="date" id="edit-last-date" />
          </div>
          <div class="field-group">
            <div class="field-lbl">Application Fee (Rs.)</div>
            <input type="number" id="edit-fee" />
          </div>
        </div>

        <div class="field-group">
          <div class="field-lbl">Source URL (Mandatory Verification Link)</div>
          <input type="text" id="edit-source-url" />
        </div>

        <div class="field-group">
          <div class="field-lbl">Source Notice Snippet (Span Citation)</div>
          <div class="source-box" id="source-snippet">No opportunity selected.</div>
        </div>

        <div class="field-group">
          <div class="field-lbl">Radio Audio Bulletin Preview (TTS Tier 0)</div>
          <div class="audio-player">
            <button onclick="playTTSPreview()" class="btn-secondary" style="padding: 6px 12px; font-size: 12px;">🔊 Play Voice Bulletin</button>
            <span id="tts-status" style="font-size: 12px; color: var(--text-muted);">Voice synthesizer ready</span>
          </div>
        </div>

        <div style="display: flex; gap: 12px; margin-top: 12px;">
          <button onclick="saveChanges()" class="btn-secondary" style="flex: 1;">💾 Save Edits</button>
          <button onclick="approveSelected()" class="btn-secondary" style="flex: 1; border-color: #3b82f6; color: #60a5fa;">✓ Approve</button>
          <button onclick="publishSelected()" class="btn-success" style="flex: 1.2;">📡 Sign & Publish Packet</button>
        </div>
      </div>
    </div>
  </div>

  <script>
    let currentOppId = null;
    let currentOppData = null;
    let currentLang = 'en';

    const CLOUD_I18N = {
      app_title: {
        hi: "AccessAI क्लाउड कंट्रोल सेंटर",
        bn: "AccessAI ক্লাউড কন্ট্রোল সেন্টার",
        te: "AccessAI క్లౌడ్ కంట్రోల్ సెంటర్",
        mr: "AccessAI क्लाउड नियंत्रण केंद्र",
        ta: "AccessAI கிளவுட் கட்டுப்பாட்டு மையம்",
        gu: "AccessAI ક્લાઉડ કંટ્રોલ સેન્ટર",
        kn: "AccessAI ಕ್ಲೌಡ್ ನಿಯಂತ್ರಣ ಕೇಂದ್ರ",
        ml: "AccessAI ക്ലൗഡ് കൺട്രോൾ സെന്റർ",
        pa: "AccessAI ਕਲਾਊਡ ਕੰਟਰੋਲ ਸੈਂਟਰ",
        od: "AccessAI କ୍ଲାଉଡ଼ କଣ୍ଟ୍ରୋଲ ସେଣ୍ଟର",
        en: "AccessAI Cloud Control Center"
      },
      cloud_sub: {
        hi: "टीयर 0 ब्रॉडकास्ट एवं पैकेट हस्ताक्षर स्टेशन (AVINYA 2K26)",
        bn: "টিয়ার ০ সম্প্রচার এবং প্যাকেট সাইনিং স্টেশন (AVINYA 2K26)",
        te: "టైర్ 0 ప్రసారం మరియు ప్యాకెట్ సంతకం స్టేషన్ (AVINYA 2K26)",
        mr: "टियर ० प्रसारण आणि पॅकेट स्वाक्षरी स्टेशन (AVINYA 2K26)",
        ta: "அடுக்கு 0 ஒளிபரப்பு மற்றும் பாக்கெட் கையொப்ப நிலையம் (AVINYA 2K26)",
        gu: "ટાયર 0 પ્રસારણ અને પેકેટ હસ્તાક્ષર સ્ટેશન (AVINYA 2K26)",
        kn: "ಶ್ರೇಣಿ 0 ಪ್ರಸಾರ ಮತ್ತು ಪ್ಯಾಕೆಟ್ ಸಹಿ ಕೇಂದ್ರ (AVINYA 2K26)",
        ml: "ടയർ 0 പ്രക്ഷേപണവും പാക്കറ്റ് ഒപ്പിടൽ സ്റ്റേഷനും (AVINYA 2K26)",
        pa: "ਟੀਅਰ 0 ਪ੍ਰਸਾਰਣ ਅਤੇ ਪੈਕੇਟ ਦਸਤਖਤ ਸਟੇਸ਼ਨ (AVINYA 2K26)",
        od: "ଟିୟର ୦ ପ୍ରସାରଣ ଏବଂ ପ୍ୟାକେଟ ସ୍ୱାକ୍ଷର ଷ୍ଟେସନ (AVINYA 2K26)",
        en: "Tier 0 Broadcast & Packet Signing Station (AVINYA 2K26)"
      },
      status_active: {
        hi: "ब्रॉडकास्ट सक्रिय",
        bn: "সম্প্রচার সক্রিয়",
        te: "ప్రసారం సక్రియం",
        mr: "प्रसारण सक्रिय",
        ta: "ஒளிபரப்பு செயலில் உள்ளது",
        gu: "પ્રસારણ સક્રિય",
        kn: "ಪ್ರಸಾರ ಸಕ್ರಿಯವಾಗಿದೆ",
        ml: "പ്രക്ഷേപണം സജീവം",
        pa: "ਪ੍ਰਸਾਰਣ ਚਾਲੂ ਹੈ",
        od: "ପ୍ରସାରଣ ସକ୍ରିୟ",
        en: "BROADCAST ACTIVE"
      },
      btn_refresh: {
        hi: "🔄 ताज़ा करें",
        bn: "🔄 রিফ্রেশ",
        te: "🔄 రిఫ్రెష్",
        mr: "🔄 रिफ्रेश",
        ta: "🔄 புதுப்பி",
        gu: "🔄 તાજું કરો",
        kn: "🔄 ನವೀಕರಿಸಿ",
        ml: "🔄 പുതുക്കുക",
        pa: "🔄 ਰਿਫ੍ਰੈਸ਼",
        od: "🔄 ରିଫ୍ରେଶ",
        en: "🔄 Refresh"
      },
      stat_notices: {
        hi: "प्राप्त सरकारी सूचनाएं",
        bn: "প্রাপ্ত সরকারি বিজ্ঞপ্তি",
        te: "స్వీకరించిన నోటీసులు",
        mr: "प्राप्त शासकीय सूचना",
        ta: "பெறப்பட்ட அறிவிப்புகள்",
        gu: "મેળવેલ સૂચનાઓ",
        kn: "ಸ್ವೀಕರಿಸಿದ ಪ್ರಕಟಣೆಗಳು",
        ml: "ലഭിച്ച അറിയിപ്പുകൾ",
        pa: "ਪ੍ਰਾਪਤ ਨੋਟਿਸ",
        od: "ପ୍ରାପ୍ତ ବିଜ୍ଞପ୍ତି",
        en: "Notices Ingested"
      },
      stat_drafts: {
        hi: "समीक्षा हेतु लंबित ड्राफ्ट",
        bn: "পর্যালোচনার অপেক্ষায় ড্রাফ্ট",
        te: "పరిశీలనలో ఉన్న డ్రాఫ్ట్‌లు",
        mr: "पुನरावलोकनासाठी प्रलंबित मसुदा",
        ta: "மதிப்பாய்வு நிலுவையில் உள்ள வரைவுகள்",
        gu: "સમીક્ષા માટે પેન્ડિંગ ડ્રાફ્ટ",
        kn: "ಪರಿಶೀಲನೆಗೆ ಬಾಕಿ ಇರುವ ಕರಡುಗಳು",
        ml: "പരിശോധനയിലുള്ള ഡ്രാഫ്റ്റുകൾ",
        pa: "ਸਮੀਖਿਆ ਲਈ ਬਕਾਇਆ ਡਰਾਫਟ",
        od: "ସମୀକ୍ଷା ପାଇଁ ବକେୟା ଡ୍ରାଫ୍ଟ",
        en: "Drafts Pending Review"
      },
      stat_approved: {
        hi: "स्वीकृत योजनाएं",
        bn: "অনুমোদিত সুযোগসমূহ",
        te: "ఆమోదించబడిన అవకాశాలు",
        mr: "मंजूर झालेल्या योजना",
        ta: "ஒப்புதல் அளிக்கப்பட்ட வாய்ப்புகள்",
        gu: "મંજૂર થયેલી તકો",
        kn: "ಅನುಮೋದಿತ ಅವಕಾಶಗಳು",
        ml: "അംഗീകരിച്ച അവസരങ്ങൾ",
        pa: "ਪ੍ਰਵਾਨਿਤ ਮੌਕੇ",
        od: "ଅନୁମୋଦିତ ସୁଯୋଗ",
        en: "Approved Opportunities"
      },
      stat_packets: {
        hi: "हस्ताक्षरित पैकेट (रेडियो)",
        bn: "স্বাক্ষরিত প্যাকেট (রেডিও)",
        te: "సంతకం చేసిన ప్యాకెట్లు (రేడియో)",
        mr: "स्वाक्षरित पॅकेट्स (रेडिओ)",
        ta: "கையொப்பமிடப்பட்ட பாக்கெட்டுகள்",
        gu: "સહી કરેલા પેકેટ્સ (રેડિયો)",
        kn: "ಸಹಿ ಮಾಡಿದ ಪ್ಯಾಕೆಟ್‌ಗಳು",
        ml: "ഒപ്പിട്ട പാക്കറ്റുകൾ (റേഡിയോ)",
        pa: "ਦਸਤਖਤ ਕੀਤੇ ਪੈਕੇਟ (ਰੇਡੀਓ)",
        od: "ସ୍ୱାକ୍ଷରିତ ପ୍ୟାକେଟ୍ (ରେଡିଓ)",
        en: "Signed Packets (Carousel)"
      }
    };

    function setGlobalLang(lang) {
      currentLang = lang;
      const dict = CLOUD_I18N;
      
      const titleEl = document.getElementById('lbl-cloud-title');
      if (titleEl && dict.app_title[lang]) titleEl.innerText = dict.app_title[lang];

      const subEl = document.getElementById('lbl-cloud-sub');
      if (subEl && dict.cloud_sub[lang]) subEl.innerText = dict.cloud_sub[lang];

      const statActEl = document.getElementById('lbl-status-badge');
      if (statActEl && dict.status_active[lang]) statActEl.innerText = dict.status_active[lang];

      const refEl = document.getElementById('btn-refresh');
      if (refEl && dict.btn_refresh[lang]) refEl.innerText = dict.btn_refresh[lang];

      const nEl = document.getElementById('lbl-stat-notices');
      if (nEl && dict.stat_notices[lang]) nEl.innerText = dict.stat_notices[lang];

      const dEl = document.getElementById('lbl-stat-drafts');
      if (dEl && dict.stat_drafts[lang]) dEl.innerText = dict.stat_drafts[lang];

      const aEl = document.getElementById('lbl-stat-approved');
      if (aEl && dict.stat_approved[lang]) aEl.innerText = dict.stat_approved[lang];

      const pEl = document.getElementById('lbl-stat-packets');
      if (pEl && dict.stat_packets[lang]) pEl.innerText = dict.stat_packets[lang];

      refreshData();
    }

    async function init() {
      await loadFiles();
      await refreshData();
    }

    async function refreshData() {
      const resStats = await fetch('/api/stats');
      const stats = await resStats.json();
      document.getElementById('stat-notices').innerText = stats.raw_notices;
      document.getElementById('stat-drafts').innerText = stats.drafts_pending_review;
      document.getElementById('stat-approved').innerText = stats.approved;
      document.getElementById('stat-packets').innerText = stats.packets_in_carousel;

      const resOpps = await fetch('/api/opportunities');
      const data = await resOpps.json();
      renderTable(data.items);
    }

    async function loadFiles() {
      const res = await fetch('/api/notices/available-files');
      const data = await res.json();
      const sel = document.getElementById('file-select');
      sel.innerHTML = '<option value="">-- Load from /data/real/notices/ --</option>';
      data.files.forEach(f => {
        const opt = document.createElement('option');
        opt.value = f.name;
        opt.innerText = f.name;
        sel.appendChild(opt);
      });
    }

    async function loadFileContent(filename) {
      if (!filename) return;
      const res = await fetch(`/api/notices/ingest-file/${filename}`, { method: 'POST' });
      const data = await res.json();
      await refreshData();
      selectOpportunity(data.opportunity_id);
    }

    function renderTable(items) {
      const tbody = document.getElementById('opp-table-body');
      tbody.innerHTML = '';
      if (items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: var(--text-muted);">No opportunities yet. Ingest a notice above.</td></tr>';
        return;
      }
      items.forEach(item => {
        const tr = document.createElement('tr');
        tr.style.cursor = 'pointer';
        tr.onclick = () => selectOpportunity(item.id);
        const badgeClass = item.status === 'published' ? 'badge-published' : (item.status === 'approved' ? 'badge-approved' : 'badge-draft');
        const displayTitle = (currentLang === 'hi' && item.title_hi) ? item.title_hi : item.title;
        tr.innerHTML = `
          <td style="font-weight: 600;">${displayTitle}</td>
          <td><span style="color: var(--text-muted); font-size: 12px;">${item.type}</span></td>
          <td><span class="badge ${badgeClass}">${item.status}</span></td>
          <td><button class="btn-secondary" style="padding: 4px 8px; font-size: 11px;" onclick="event.stopPropagation(); selectOpportunity('${item.id}')">Inspect</button></td>
        `;
        tbody.appendChild(tr);
      });
    }

    async function selectOpportunity(id) {
      currentOppId = id;
      const res = await fetch(`/api/opportunities/${id}`);
      currentOppData = await res.json();

      document.getElementById('edit-title').value = currentOppData.title || '';
      document.getElementById('edit-title-hi').value = currentOppData.title_hi || '';
      document.getElementById('edit-type').value = currentOppData.type || 'scheme';
      document.getElementById('edit-org').value = currentOppData.org || '';
      document.getElementById('edit-min-age').value = currentOppData.eligibility?.min_age || '';
      document.getElementById('edit-max-age').value = currentOppData.eligibility?.max_age || '';
      document.getElementById('edit-last-date').value = currentOppData.dates?.last_date || '';
      document.getElementById('edit-fee').value = currentOppData.fee || 0;
      document.getElementById('edit-source-url').value = currentOppData.source_url || '';

      const badge = document.getElementById('selected-badge');
      badge.className = 'badge ' + (currentOppData.status === 'published' ? 'badge-published' : (currentOppData.status === 'approved' ? 'badge-approved' : 'badge-draft'));
      badge.innerText = currentOppData.status.toUpperCase();

      document.getElementById('source-snippet').innerText = currentOppData.raw_source_text || 'Source text from raw notice.';
    }

    async function ingestNotice() {
      const text = document.getElementById('notice-text').value;
      if (!text.trim()) { alert('Please paste notice text first.'); return; }
      const res = await fetch('/api/notices/ingest-text', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ raw_text: text })
      });
      const data = await res.json();
      await refreshData();
      selectOpportunity(data.opportunity_id);
    }

    async function publishChain() {
      const text = document.getElementById('notice-text').value;
      if (!text.trim()) { alert('Please paste notice text first.'); return; }
      const res = await fetch('/api/publish-chain', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ raw_text: text })
      });
      const data = await res.json();
      alert(`Packet signed and published: ${data.packet_file}`);
      await refreshData();
      selectOpportunity(data.opportunity_id);
    }

    async function saveChanges() {
      if (!currentOppId) return;
      const payload = {
        title: document.getElementById('edit-title').value,
        title_hi: document.getElementById('edit-title-hi').value,
        type: document.getElementById('edit-type').value,
        org: document.getElementById('edit-org').value,
        source_url: document.getElementById('edit-source-url').value,
        fee: parseFloat(document.getElementById('edit-fee').value) || 0,
        eligibility: {
          ...currentOppData.eligibility,
          min_age: parseInt(document.getElementById('edit-min-age').value) || null,
          max_age: parseInt(document.getElementById('edit-max-age').value) || null,
        },
        dates: {
          ...currentOppData.dates,
          last_date: document.getElementById('edit-last-date').value || null,
        }
      };
      await fetch(`/api/opportunities/${currentOppId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      await refreshData();
      selectOpportunity(currentOppId);
      alert('Changes saved.');
    }

    async function approveSelected() {
      if (!currentOppId) return;
      await fetch(`/api/opportunities/${currentOppId}/approve`, { method: 'POST' });
      await refreshData();
      selectOpportunity(currentOppId);
    }

    async function publishSelected() {
      if (!currentOppId) return;
      const res = await fetch(`/api/opportunities/${currentOppId}/publish`, { method: 'POST' });
      const data = await res.json();
      if (res.ok) {
        alert(`Signed packet broadcast: ${data.packet_file}`);
      } else {
        alert(`Error: ${data.detail}`);
      }
      await refreshData();
      selectOpportunity(currentOppId);
    }

    function playTTSPreview() {
      const text = document.getElementById('edit-title-hi').value || document.getElementById('edit-title').value;
      if (!text) return;
      if ('speechSynthesis' in window) {
        const u = new SpeechSynthesisUtterance(text);
        u.lang = 'hi-IN';
        window.speechSynthesis.speak(u);
        document.getElementById('tts-status').innerText = 'Playing Hindi voice broadcast...';
        u.onend = () => { document.getElementById('tts-status').innerText = 'Voice broadcast complete'; };
      } else {
        alert('Web Speech Synthesis not supported in this browser.');
      }
    }

    window.onload = init;
  </script>
</body>
</html>
"""
