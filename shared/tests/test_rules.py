"""
Tests for shared/rule_engine.py
Uses TEST FIXTURE data from /tests/fixtures/ via conftest.py.

Run with:  pytest shared/tests/test_rules.py -v
"""

from datetime import date, timedelta

import pytest

from shared.schemas import (
    Category,
    Education,
    EligibilityCriteria,
    Gender,
    ImportantDates,
    MatchStatus,
    Opportunity,
    OpportunityType,
    Person,
    Document,
)
from shared.rule_engine import (
    check_eligibility,
    compute_age,
    generate_deadline_reminders,
    match_household,
    build_why_fit,
    get_immunization_schedule,
    get_anc_schedule,
    get_health_disclaimer,
)


# ── compute_age ───────────────────────────────────────────────────────────────

class TestComputeAge:
    def test_exact_birthday(self):
        dob = date(2000, 1, 1)
        assert compute_age(dob, date(2026, 1, 1)) == 26

    def test_before_birthday_this_year(self):
        dob = date(2000, 12, 31)
        assert compute_age(dob, date(2026, 1, 1)) == 25

    def test_newborn(self):
        today = date.today()
        assert compute_age(today, today) == 0

    def test_infant(self):
        dob = date(2026, 1, 1)
        assert compute_age(dob, date(2026, 6, 1)) == 0


# ── check_eligibility — using YAML fixtures ───────────────────────────────────

class TestEligibilityWithFixtures:
    """All persons here are TEST FIXTURE — is_test_persona=True (set in conftest)."""

    def test_obc_male_secondary_eligible(
        self, tf_person_adult_obc_m, tf_opp_obc_scholarship
    ):
        result = check_eligibility(
            tf_person_adult_obc_m, tf_opp_obc_scholarship, date(2026, 6, 1)
        )
        assert result.status == MatchStatus.eligible

    def test_wrong_gender_for_women_scheme(
        self, tf_person_adult_obc_m, tf_opp_women_training
    ):
        result = check_eligibility(
            tf_person_adult_obc_m, tf_opp_women_training, date(2026, 6, 1)
        )
        assert result.status == MatchStatus.not_eligible

    def test_women_eligible_for_women_scheme(
        self, tf_person_adult_obc_f, tf_opp_women_training
    ):
        result = check_eligibility(
            tf_person_adult_obc_f, tf_opp_women_training, date(2026, 6, 1)
        )
        assert result.status == MatchStatus.eligible

    def test_expired_opportunity(self, tf_person_adult_obc_m, tf_opp_expired):
        result = check_eligibility(
            tf_person_adult_obc_m, tf_opp_expired, date(2026, 6, 1)
        )
        assert result.status == MatchStatus.not_eligible
        assert "passed" in result.reason

    def test_child_too_young(self, tf_person_child, tf_opp_obc_scholarship):
        result = check_eligibility(
            tf_person_child, tf_opp_obc_scholarship, date(2026, 6, 1)
        )
        assert result.status == MatchStatus.not_eligible
        assert "below minimum" in result.reason

    def test_disability_scheme_non_disabled(
        self, tf_person_adult_obc_m, tf_opp_disability
    ):
        result = check_eligibility(
            tf_person_adult_obc_m, tf_opp_disability, date(2026, 6, 1)
        )
        assert result.status == MatchStatus.not_eligible

    def test_disability_scheme_disabled_person(
        self, tf_person_disabled, tf_opp_disability
    ):
        result = check_eligibility(
            tf_person_disabled, tf_opp_disability, date(2026, 6, 1)
        )
        assert result.status == MatchStatus.eligible

    def test_unknown_gender_yields_possible(
        self, tf_person_unknown, tf_opp_women_training
    ):
        # tf_person_unknown has gender=None
        result = check_eligibility(
            tf_person_unknown, tf_opp_women_training, date(2026, 6, 1)
        )
        assert result.status == MatchStatus.possible
        assert result.question is not None

    def test_unknown_category_yields_possible(
        self, tf_person_unknown, tf_opp_obc_scholarship
    ):
        result = check_eligibility(
            tf_person_unknown, tf_opp_obc_scholarship, date(2026, 6, 1)
        )
        assert result.status == MatchStatus.possible

    def test_education_insufficient_for_grad_exam(
        self, tf_person_adult_obc_m, tf_opp_graduate_exam
    ):
        # tf_person_adult_obc_m has education=secondary, exam requires graduate
        result = check_eligibility(
            tf_person_adult_obc_m, tf_opp_graduate_exam, date(2026, 6, 1)
        )
        assert result.status == MatchStatus.not_eligible

    def test_graduate_eligible_for_grad_exam(
        self, tf_person_adult_obc_f, tf_opp_graduate_exam
    ):
        # tf_person_adult_obc_f has education=graduate
        result = check_eligibility(
            tf_person_adult_obc_f, tf_opp_graduate_exam, date(2026, 6, 1)
        )
        assert result.status == MatchStatus.eligible


# ── match_household ───────────────────────────────────────────────────────────

class TestMatchHousehold:
    def test_returns_n_times_m_results(self, tf_people, tf_opportunities):
        results = match_household(tf_people, tf_opportunities, date(2026, 6, 1))
        assert len(results) == len(tf_people) * len(tf_opportunities)

    def test_all_results_have_person_and_opp_ids(self, tf_people, tf_opportunities):
        results = match_household(tf_people, tf_opportunities, date(2026, 6, 1))
        for r in results:
            assert r.person_id
            assert r.opportunity_id


# ── build_why_fit ─────────────────────────────────────────────────────────────

class TestBuildWhyFit:
    def test_eligible_message(
        self, tf_person_adult_obc_m, tf_opp_obc_scholarship
    ):
        match = check_eligibility(
            tf_person_adult_obc_m, tf_opp_obc_scholarship, date(2026, 6, 1)
        )
        msg = build_why_fit(
            tf_person_adult_obc_m, tf_opp_obc_scholarship, match, date(2026, 6, 1)
        )
        assert tf_person_adult_obc_m.name in msg
        assert "meets all" in msg.lower()

    def test_not_eligible_includes_reason(
        self, tf_person_adult_obc_m, tf_opp_expired
    ):
        match = check_eligibility(
            tf_person_adult_obc_m, tf_opp_expired, date(2026, 6, 1)
        )
        msg = build_why_fit(
            tf_person_adult_obc_m, tf_opp_expired, match, date(2026, 6, 1)
        )
        assert len(msg) > 0


# ── Deadline reminders ────────────────────────────────────────────────────────

class TestDeadlineReminders:
    def test_reminders_for_future_deadline(
        self, tf_person_adult_obc_m, tf_opp_graduate_exam
    ):
        reminders = generate_deadline_reminders(
            tf_person_adult_obc_m, tf_opp_graduate_exam, date(2026, 10, 1)
        )
        assert any(r["kind"] == "deadline" for r in reminders)

    def test_no_reminders_for_past_deadline(
        self, tf_person_adult_obc_m, tf_opp_expired
    ):
        reminders = generate_deadline_reminders(
            tf_person_adult_obc_m, tf_opp_expired, date(2026, 6, 1)
        )
        deadline = [r for r in reminders if r["kind"] == "deadline"]
        assert len(deadline) == 0

    def test_document_reminder_generated(
        self, tf_person_adult_obc_m, tf_opp_graduate_exam
    ):
        # tf-opp-005 has doc with typical_lead_time_days=30, deadline 2026-11-30
        reminders = generate_deadline_reminders(
            tf_person_adult_obc_m, tf_opp_graduate_exam, date(2026, 10, 1)
        )
        doc_reminders = [r for r in reminders if r["kind"] == "document"]
        assert len(doc_reminders) >= 1

    def test_today_reminder(self, tf_person_adult_obc_m):
        opp = tf_person_adult_obc_m  # just borrowing person; build temp opp
        from shared.schemas import Geo
        today_opp = Opportunity(
            id="tf-today",
            type=OpportunityType.scheme,
            title="[TEST] Today Deadline",
            source_url="https://example.com/test",
            dates=ImportantDates(last_date=date.today()),
        )
        reminders = generate_deadline_reminders(opp, today_opp, date.today())
        today_r = [r for r in reminders if r["kind"] == "deadline" and "TODAY" in r["message"]]
        assert len(today_r) == 1


# ── Health data (safe fallback when YAML not populated) ───────────────────────

class TestHealthDataLoaders:
    def test_immunization_returns_list(self):
        """Should return list (possibly empty if real data not loaded)."""
        result = get_immunization_schedule(date(2026, 1, 1))
        assert isinstance(result, list)

    def test_anc_returns_list(self):
        result = get_anc_schedule(date(2026, 1, 1))
        assert isinstance(result, list)

    def test_disclaimer_always_present(self):
        d = get_health_disclaimer()
        assert "en" in d
        assert "hi" in d
        assert len(d["en"]) > 0
        assert len(d["hi"]) > 0
