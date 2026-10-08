"""
cloud/publish_sample.py
Publishes approved opportunities from cloud DB as signed packets to packets/ folder.
Can approve drafts with --approve-all flag for automated demo setup.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import sqlalchemy
from cloud.db import CloudOpportunity, SessionLocal, init_db
from cloud.publisher import publish_opportunity_packet


def publish_all(auto_approve: bool = False):
    init_db()
    db = SessionLocal()

    if auto_approve or "--approve-all" in sys.argv:
        drafts = db.query(CloudOpportunity).filter(CloudOpportunity.status == "draft").all()
        for d in drafts:
            d.status = "approved"
        db.commit()
        print(f"[publish_sample] Approved {len(drafts)} draft opportunity/ies for broadcast demo.")

    opps = db.execute(
        sqlalchemy.text("SELECT * FROM opportunities WHERE status = 'approved'")
    ).mappings().all()

    if not opps:
        print(
            "[publish_sample] No approved opportunities found in cloud DB.\n"
            "                 Run `python cloud/seed.py` first, or run with `python cloud/publish_sample.py --approve-all`"
        )
        db.close()
        return

    published = 0
    for row in opps:
        opp_dict = dict(row)
        for key in ("eligibility_json", "dates_json", "documents_json", "apply_steps_json"):
            raw = opp_dict.pop(key, None)
            parsed_key = key.replace("_json", "")
            opp_dict[parsed_key] = json.loads(raw) if raw else None
        opp_dict["geo"] = {
            "state": opp_dict.pop("geo_state", None),
            "district": opp_dict.pop("geo_district", None),
            "block": opp_dict.pop("geo_block", None),
        }
        try:
            publish_opportunity_packet(opp_dict)
            db.execute(
                sqlalchemy.text("UPDATE opportunities SET status = 'published' WHERE id = :id"),
                {"id": opp_dict.get("id")},
            )
            published += 1
        except Exception as e:
            print(f"[publish_sample] Failed for {opp_dict.get('id')}: {e}")

    db.commit()
    db.close()
    print(f"[publish_sample] Successfully signed & published {published} packet(s) to packets/ folder.")


if __name__ == "__main__":
    auto = "--approve-all" in sys.argv
    publish_all(auto_approve=auto)
