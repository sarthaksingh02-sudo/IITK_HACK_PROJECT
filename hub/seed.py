"""
hub/seed.py
Seeds the hub DB with TEST PERSONA households from /data/personas/*.yaml.
Also creates the packets/ directory.

Run directly:  python hub/seed.py

IMPORTANT:
  - Only loads households marked _label: "TEST PERSONA".
  - Sets is_test_persona=True on every person loaded from /data/personas/.
  - These records must NEVER appear in the production demo UI.
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

try:
    import yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False
    print("[hub/seed] WARNING: PyYAML not installed. Cannot load personas.")
    print("           Install with: pip install pyyaml")

from hub.db import (
    HubHousehold,
    HubPerson,
    SessionLocal,
    init_db,
)

PERSONAS_DIR = pathlib.Path(__file__).parent.parent / "data" / "personas"
PACKETS_DIR = pathlib.Path(__file__).parent.parent / "packets"


def seed():
    init_db()
    PACKETS_DIR.mkdir(parents=True, exist_ok=True)

    if not _YAML_AVAILABLE:
        print("[hub/seed] Skipping persona load — PyYAML not installed.")
        return

    db = SessionLocal()
    now = datetime.utcnow().isoformat()
    hh_count = 0
    person_count = 0

    for persona_file in sorted(PERSONAS_DIR.glob("*.yaml")):
        with open(persona_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            continue

        hh_raw = data.get("household")
        people_raw = data.get("people", [])

        if not hh_raw:
            continue

        # Validate TEST PERSONA label
        if hh_raw.get("_label") != "TEST PERSONA":
            print(
                f"[hub/seed] SKIPPED {persona_file.name} — missing _label: 'TEST PERSONA'"
            )
            continue

        hh_id = hh_raw["id"]
        existing_hh = db.get(HubHousehold, hh_id)
        if not existing_hh:
            db.add(HubHousehold(
                id=hh_id,
                village=hh_raw.get("village"),
                district=hh_raw.get("district"),
                state=hh_raw.get("state"),
                created_at=now,
                consent_given_at=None,  # Consent must be given through the UI
            ))
            hh_count += 1

        for p in people_raw:
            p_id = p["id"]
            existing_p = db.get(HubPerson, p_id)
            if not existing_p:
                db.add(HubPerson(
                    id=p_id,
                    household_id=p["household_id"],
                    name=p["name"],
                    dob=p["dob"],
                    gender=p.get("gender"),
                    relation=p.get("relation"),
                    education=p.get("education"),
                    category=p.get("category"),
                    is_disabled=p.get("is_disabled", False),
                    occupation=p.get("occupation"),
                    skills_json=json.dumps(p.get("skills", [])),
                    interests_json=json.dumps(p.get("interests", [])),
                    languages_json=json.dumps(p.get("languages", [])),
                    land_acres=p.get("land_acres"),
                    assets_json=json.dumps(p.get("assets", [])),
                    created_at=now,
                    is_test_persona=True,  # Always true for /data/personas/ data
                ))
                person_count += 1

    db.commit()
    db.close()
    print(f"[hub/seed] Loaded {hh_count} household(s) and {person_count} person(s) from /data/personas/.")
    print("[hub/seed] Note: all loaded personas are TEST PERSONA — is_test_persona=True.")


if __name__ == "__main__":
    seed()
