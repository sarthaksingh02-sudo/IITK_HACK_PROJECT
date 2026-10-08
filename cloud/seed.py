"""
cloud/seed.py
Seeds the cloud DB from /data/real/notices/ files (processed through LLM extractor).

DATA RULE: Only loads opportunities from /data/real/notices/.
  - If MOCK_LLM=true, uses canned LLM output (flagged in logs as [MOCK-LLM]).
  - If /data/real/notices/ is empty, prints a clear message and exits.
  - NEVER invents scheme details from model memory.

Run directly:  python cloud/seed.py
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import uuid
from datetime import datetime

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from cloud.db import SessionLocal, init_db, CloudOpportunity
from cloud.llm_client import extract_opportunity_from_text, MOCK_LLM

NOTICES_DIR = pathlib.Path(__file__).parent.parent / "data" / "real" / "notices"


def seed():
    init_db()
    db = SessionLocal()
    now = datetime.utcnow().isoformat()

    notice_files = [
        f for f in NOTICES_DIR.iterdir()
        if f.suffix in (".txt", ".pdf") and f.name != "README.md"
    ]

    if not notice_files:
        print(
            "[cloud/seed] No notice files found in /data/real/notices/.\n"
            "            Add official government notices there before running seed.\n"
            "            See /data/real/notices/README.md for instructions."
        )
        if MOCK_LLM:
            print(
                "[cloud/seed] MOCK_LLM=true — loading one canned mock opportunity "
                "for development. This will be flagged as [MOCK-LLM] and must NOT "
                "be presented as real data in the demo."
            )
            _seed_mock(db, now)
        db.close()
        return

    count = 0
    for notice_file in notice_files:
        raw_text = notice_file.read_text(encoding="utf-8", errors="replace")
        if MOCK_LLM:
            print(f"[MOCK-LLM] Extracting from {notice_file.name} using mock LLM.")
        else:
            print(f"[cloud/seed] Extracting from {notice_file.name} using live LLM.")

        try:
            extracted = extract_opportunity_from_text(raw_text)
        except Exception as e:
            print(f"[cloud/seed] ERROR extracting {notice_file.name}: {e}")
            continue

        opp_id = f"opp-{uuid.uuid4().hex[:8]}"
        # source_url must come from the notice file itself or be set explicitly
        source_url = extracted.get("source_url") or f"file://{notice_file.name}"

        existing = db.execute(
            __import__("sqlalchemy").text(
                "SELECT id FROM opportunities WHERE source_url = :url LIMIT 1"
            ),
            {"url": source_url}
        ).first()
        if existing:
            print(f"[cloud/seed] Already loaded: {source_url}")
            continue

        db.add(CloudOpportunity(
            id=opp_id,
            type=extracted.get("type", "scheme"),
            title=extracted.get("title", "Untitled"),
            title_hi=extracted.get("title_hi"),
            org=extracted.get("org"),
            level=extracted.get("level"),
            geo_state=extracted.get("geo", {}).get("state") if extracted.get("geo") else None,
            geo_district=extracted.get("geo", {}).get("district") if extracted.get("geo") else None,
            eligibility_json=json.dumps(extracted.get("eligibility", {})),
            dates_json=json.dumps(extracted.get("dates", {})),
            documents_json=json.dumps(extracted.get("documents_required", [])),
            fee=extracted.get("fee"),
            apply_mode=extracted.get("apply_mode"),
            apply_steps_json=json.dumps(extracted.get("apply_steps", [])),
            source_url=source_url,
            priority=extracted.get("priority", 5),
            status="draft",     # Requires human review and approval
            is_sample=MOCK_LLM,  # Mark as sample if mock LLM used
            created_at=now,
            updated_at=now,
        ))
        count += 1
        print(f"[cloud/seed] Loaded '{extracted.get('title', opp_id)}' — status=draft (needs review)")

    db.commit()
    db.close()
    print(f"\n[cloud/seed] Done. {count} opportunity/ies loaded with status=draft.")
    print("[cloud/seed] Approve them in the Control Center UI before publishing.")


def _seed_mock(db, now: str):
    """One canned mock opportunity for dev/demo. Clearly flagged."""
    from cloud.llm_client import _MOCK_EXTRACT
    mock_id = "opp-mock-dev-001"
    if db.get(CloudOpportunity, mock_id):
        print("[MOCK-LLM] Mock opportunity already seeded.")
        return
    extracted = dict(_MOCK_EXTRACT)
    db.add(CloudOpportunity(
        id=mock_id,
        type=extracted.get("type", "scheme"),
        title=f"[MOCK-LLM — NOT REAL] {extracted.get('title', 'Mock Opportunity')}",
        title_hi=extracted.get("title_hi"),
        org=extracted.get("org"),
        level=extracted.get("level"),
        eligibility_json=json.dumps(extracted.get("eligibility", {})),
        dates_json=json.dumps(extracted.get("dates", {})),
        documents_json=json.dumps(extracted.get("documents_required", [])),
        fee=extracted.get("fee"),
        apply_mode=extracted.get("apply_mode"),
        apply_steps_json=json.dumps(extracted.get("apply_steps", [])),
        source_url=extracted.get("source_url", "https://example.com/mock"),
        priority=extracted.get("priority", 5),
        status="draft",
        is_sample=True,
        created_at=now,
        updated_at=now,
    ))
    db.commit()
    print("[MOCK-LLM] One mock opportunity seeded with status=draft (title prefixed [MOCK-LLM — NOT REAL]).")


if __name__ == "__main__":
    seed()
