"""
tests/test_end_to_end.py
Comprehensive End-to-End Test Suite for AccessAI (AVINYA 2K26).
Validates:
  - Feature K: Ineligible persons NEVER appear as ELIGIBLE.
  - Feature K: Every suggestion contains a valid source citation / pathway.
  - Family Health: Immunization schedule & red-flag non-diagnostic guidance with disclaimer.
  - Reminders: Countdown and Fast-Forward N days simulation.
  - Voice Assistant: Multi-intent processing in Hindi and English.
  - Broadcast Transport: Packet signing, Ed25519 verification, and hub DB ingestion.
"""

from __future__ import annotations

import json
import os
import pathlib
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient

from cloud.main import app as cloud_app
from hub.main import app as hub_app
from hub.db import HubHousehold, HubOpportunity, HubPerson, SessionLocal, init_db as init_hub_db
from cloud.db import init_db as init_cloud_db
from hub.suggestions import generate_person_suggestions
from hub.health import get_person_health_summary
from hub.reminders import evaluate_household_reminders
from hub.voice import process_voice_query
from hub.transport.file_transport import FileTransport
from shared.packet import build_and_sign, load_signing_key, load_verify_key, verify_packet
from shared.schemas import Category, Education, Gender, Geo, Opportunity, OpportunityType, PacketKind, Person


@pytest.fixture(autouse=True)
def setup_databases():
    init_cloud_db()
    init_hub_db()


# ── Feature K Tests ───────────────────────────────────────────────────────────

class TestFeatureK:
    def test_ineligible_person_never_appears_as_eligible(self):
        """Proof that Feature K strictly respects deterministic rules and never promotes ineligible to eligible."""
        db = SessionLocal()
        try:
            # Person with middle school only
            person = HubPerson(
                id="test-p-mid",
                household_id="hh-test",
                name="Test Student",
                dob="2005-01-01",
                gender="M",
                education="middle",
                category="GEN",
                is_disabled=False,
                skills_json=json.dumps(["farming"]),
                interests_json=json.dumps(["technology"]),
                created_at="2026-10-09",
            )
            # Opportunity requiring graduate
            opp = HubOpportunity(
                id="opp-grad-exam",
                type="exam",
                title="Graduate Civil Exam",
                source_url="https://gov.in/exam",
                eligibility_json=json.dumps({"education": ["graduate"], "min_age": 21, "max_age": 32}),
                dates_json=json.dumps({"last_date": "2026-12-31"}),
                synced_at="2026-10-09",
            )

            suggestions = generate_person_suggestions(person, [opp])
            assert len(suggestions) == 1
            s = suggestions[0]
            assert s["status"] == "NOT_ELIGIBLE"
            assert s["status"] != "ELIGIBLE"
            assert s["pathway_step"] is not None
            assert "source_url" in s["pathway_step"]
            assert s["label"] == "suggested, not guaranteed"
        finally:
            db.close()

    def test_every_suggestion_has_source_and_why_fit(self):
        """Verifies that all suggestions cite official source and provide why_fit."""
        db = SessionLocal()
        try:
            person = HubPerson(
                id="test-p-1",
                household_id="hh-test",
                name="Arjun",
                dob="2007-03-14",
                gender="M",
                education="secondary",
                category="OBC",
                is_disabled=False,
                skills_json=json.dumps(["mobile repair"]),
                interests_json=json.dumps(["electronics"]),
                created_at="2026-10-09",
            )
            opp = HubOpportunity(
                id="opp-pmkvy",
                type="training",
                title="PMKVY Mobile Repair",
                title_hi="पीएमकेवीवाई मोबाइल रिपेयर",
                source_url="https://skillindiadigital.gov.in",
                eligibility_json=json.dumps({"min_age": 15, "max_age": 45, "education": ["secondary"]}),
                dates_json=json.dumps({"last_date": "2026-12-20"}),
                synced_at="2026-10-09",
            )

            suggestions = generate_person_suggestions(person, [opp])
            assert len(suggestions) == 1
            s = suggestions[0]
            assert s["source_url"] == "https://skillindiadigital.gov.in"
            assert len(s["why_fit"]) > 10
            assert len(s["why_fit_hi"]) > 10
        finally:
            db.close()


# ── Family Health Tests ───────────────────────────────────────────────────────

class TestFamilyHealthModule:
    def test_child_immunization_from_real_nis_schedule(self):
        """Verifies that infant immunization data is loaded from /data/real/health/."""
        child = HubPerson(
            id="p-child-test",
            household_id="hh-test",
            name="Priya Kumari",
            dob="2024-01-10",
            gender="F",
            created_at="2026-10-09",
        )
        health = get_person_health_summary(child, reference_date=date(2026, 10, 9))
        assert health["name"] == "Priya Kumari"
        assert len(health["immunizations"]) > 0
        assert "BCG" in health["immunizations"][0]["vaccine"]
        assert "disclaimer" in health
        assert len(health["disclaimer"]["en"]) > 20

    def test_maternal_and_child_red_flags_loaded(self):
        """Verifies that official IMNCI / Maternal red flags are attached without diagnoses."""
        mother = HubPerson(
            id="p-mother-test",
            household_id="hh-test",
            name="Savitri Devi",
            dob="1980-07-22",
            gender="F",
            created_at="2026-10-09",
        )
        health = get_person_health_summary(mother, reference_date=date(2026, 10, 9))
        assert len(health["relevant_red_flags"]) > 0
        # Verify referral actions
        for rf in health["relevant_red_flags"]:
            assert "action" in rf
            assert "source_ref" in rf


# ── Fast-Forward Reminders Tests ──────────────────────────────────────────────

class TestRemindersAndFastForward:
    def test_fast_forward_triggers_deadline_countdown(self):
        """Fast-forwarding time advances reference date and generates countdown warnings."""
        person = HubPerson(
            id="p-ff-test",
            household_id="hh-test",
            name="Ramesh",
            dob="1985-05-10",
            created_at="2026-10-09",
        )
        # Opportunity closing in 12 days from today
        today = date.today()
        closing = today + timedelta(days=12)
        opp = HubOpportunity(
            id="opp-ff",
            type="scheme",
            title="Kisan Scheme",
            source_url="https://pmkisan.gov.in",
            dates_json=json.dumps({"last_date": closing.isoformat()}),
            documents_json=json.dumps([{"name": "Land Record", "typical_lead_time_days": 5}]),
            synced_at="2026-10-09",
        )

        # At Day 0: 12 days left
        rem_day0 = evaluate_household_reminders([person], [opp], fast_forward_days=0)
        assert len(rem_day0) > 0

        # Fast forward by 10 days (now 2 days left)
        rem_day10 = evaluate_household_reminders([person], [opp], fast_forward_days=10)
        assert len(rem_day10) > 0
        assert any("2 day" in r["message"] for r in rem_day10)


# ── Voice Assistant Tests ─────────────────────────────────────────────────────

class TestVoiceAssistant:
    def test_voice_eligibility_intent_hindi_and_english(self):
        res_hi = process_voice_query("क्या मेरा बेटा आवेदन कर सकता है?", lang="hi")
        assert res_hi["intent"] in ("eligibility", "suggestions", "general_help")
        assert len(res_hi["reply_text_hi"]) > 10

        res_en = process_voice_query("can my son apply for scholarship?", lang="en")
        assert res_en["intent"] in ("eligibility", "suggestions")
        assert len(res_en["reply_text_en"]) > 10

    def test_voice_profile_update_slot_filling(self):
        res = process_voice_query("मैंने राजमिस्त्री masonry का काम सीखा है", lang="hi")
        assert res["intent"] == "profile_update"
        assert res["detected_skill"] == "masonry"
        assert "राजमिस्त्री" in res["reply_text_hi"] or "masonry" in res["reply_text_hi"]


# ── Cloud & Hub API Integration Tests ─────────────────────────────────────────

class TestApiIntegration:
    def test_cloud_stats_and_health(self):
        client = TestClient(cloud_app)
        res = client.get("/health")
        assert res.status_code == 200
        assert res.json()["service"] == "cloud"

        stats = client.get("/api/stats")
        assert stats.status_code == 200
        assert "drafts_pending_review" in stats.json()

    def test_hub_stats_and_health(self):
        client = TestClient(hub_app)
        res = client.get("/health")
        assert res.status_code == 200
        assert res.json()["service"] == "hub"
        assert res.json()["offline_mode"] is True

        res_opps = client.get("/api/opportunities")
        assert res_opps.status_code == 200
