"""
conftest.py (root) — shared pytest fixtures loaded from /tests/fixtures/
These fixtures are TEST FIXTURE data only; never used in the demo UI.
"""

from __future__ import annotations

import pathlib
from datetime import date, timedelta

import pytest

try:
    import yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False

from shared.schemas import (
    Category,
    Education,
    EligibilityCriteria,
    Gender,
    ImportantDates,
    Opportunity,
    OpportunityType,
    Person,
    Relation,
    Document,
    Geo,
)

FIXTURES_DIR = pathlib.Path(__file__).parent / "tests" / "fixtures"


def _load_yaml(name: str) -> dict:
    if not _YAML_AVAILABLE:
        pytest.skip("PyYAML not installed; skipping YAML-based fixture")
    with open(FIXTURES_DIR / name, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ── Helper builders ───────────────────────────────────────────────────────────

def _build_person(raw: dict) -> Person:
    return Person(
        id=raw["id"],
        household_id=raw["household_id"],
        name=raw["name"],
        dob=date.fromisoformat(raw["dob"]),
        gender=raw.get("gender"),
        relation=raw.get("relation"),
        education=raw.get("education"),
        category=raw.get("category"),
        is_disabled=raw.get("is_disabled", False),
        occupation=raw.get("occupation"),
        skills=raw.get("skills", []),
        interests=raw.get("interests", []),
        languages=raw.get("languages", []),
        land_acres=raw.get("land_acres"),
        assets=raw.get("assets", []),
        is_test_persona=True,
    )


def _build_opportunity(raw: dict) -> Opportunity:
    elig_raw = raw.get("eligibility", {}) or {}
    dates_raw = raw.get("dates", {}) or {}
    docs_raw = raw.get("documents_required", []) or []

    elig = EligibilityCriteria(
        min_age=elig_raw.get("min_age"),
        max_age=elig_raw.get("max_age"),
        education=[Education(e) for e in elig_raw["education"]] if elig_raw.get("education") else None,
        category=[Category(c) for c in elig_raw["category"]] if elig_raw.get("category") else None,
        gender=[Gender(g) for g in elig_raw["gender"]] if elig_raw.get("gender") else None,
        is_disabled=elig_raw.get("is_disabled"),
        max_income_lpa=elig_raw.get("max_income_lpa"),
    )
    dates = ImportantDates(
        opens=date.fromisoformat(dates_raw["opens"]) if dates_raw.get("opens") else None,
        last_date=date.fromisoformat(dates_raw["last_date"]) if dates_raw.get("last_date") else None,
        exam_date=date.fromisoformat(dates_raw["exam_date"]) if dates_raw.get("exam_date") else None,
        result_date=date.fromisoformat(dates_raw["result_date"]) if dates_raw.get("result_date") else None,
    )
    docs = [
        Document(
            name=d["name"],
            typical_lead_time_days=d.get("typical_lead_time_days"),
        )
        for d in docs_raw
    ]
    return Opportunity(
        id=raw["id"],
        type=OpportunityType(raw["type"]),
        title=raw["title"],
        source_url=raw.get("source_url", "https://example.com/test"),
        org=raw.get("org"),
        level=raw.get("level"),
        eligibility=elig,
        dates=dates,
        documents_required=docs,
        priority=raw.get("priority", 5),
        is_sample=True,
    )


@pytest.fixture
def tf_opportunities() -> list[Opportunity]:
    """TEST FIXTURE opportunities from /tests/fixtures/opportunities.yaml"""
    data = _load_yaml("opportunities.yaml")
    return [_build_opportunity(o) for o in data["opportunities"]]


@pytest.fixture
def tf_people() -> list[Person]:
    """TEST FIXTURE people from /tests/fixtures/households.yaml"""
    data = _load_yaml("households.yaml")
    return [_build_person(p) for p in data["people"]]


@pytest.fixture
def tf_opp_obc_scholarship(tf_opportunities) -> Opportunity:
    return next(o for o in tf_opportunities if o.id == "tf-opp-001")


@pytest.fixture
def tf_opp_women_training(tf_opportunities) -> Opportunity:
    return next(o for o in tf_opportunities if o.id == "tf-opp-002")


@pytest.fixture
def tf_opp_expired(tf_opportunities) -> Opportunity:
    return next(o for o in tf_opportunities if o.id == "tf-opp-003")


@pytest.fixture
def tf_opp_disability(tf_opportunities) -> Opportunity:
    return next(o for o in tf_opportunities if o.id == "tf-opp-004")


@pytest.fixture
def tf_opp_graduate_exam(tf_opportunities) -> Opportunity:
    return next(o for o in tf_opportunities if o.id == "tf-opp-005")


@pytest.fixture
def tf_person_adult_obc_m(tf_people) -> Person:
    return next(p for p in tf_people if p.id == "tf-p-adult-obc-m")


@pytest.fixture
def tf_person_adult_obc_f(tf_people) -> Person:
    return next(p for p in tf_people if p.id == "tf-p-adult-obc-f")


@pytest.fixture
def tf_person_child(tf_people) -> Person:
    return next(p for p in tf_people if p.id == "tf-p-child")


@pytest.fixture
def tf_person_unknown(tf_people) -> Person:
    return next(p for p in tf_people if p.id == "tf-p-unknown-fields")


@pytest.fixture
def tf_person_disabled(tf_people) -> Person:
    return next(p for p in tf_people if p.id == "tf-p-disabled")
