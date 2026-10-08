"""
hub/suggestions.py
Feature K: Deterministic Eligibility + Embedding/Keyword Fit Ranking + Pathway Guidance for Ineligible Items.

Principles:
  - Ineligible persons NEVER appear as ELIGIBLE.
  - Every suggestion has a "why this fits" explanation citing the notice or pathway rule.
  - For NOT_ELIGIBLE items, attaches concrete "how to become eligible" steps from /data/real/pathways.yaml.
  - Every recommendation carries the visible "suggested, not guaranteed" disclaimer.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any, Optional

from shared.rule_engine import (
    build_why_fit,
    check_eligibility,
    compute_age,
    get_pathway_steps,
)
from shared.schemas import (
    Category,
    Document,
    Education,
    EligibilityCriteria,
    Gender,
    ImportantDates,
    MatchResult,
    MatchStatus,
    Opportunity,
    OpportunityType,
    Person,
    Relation,
)
from hub.db import HubOpportunity, HubPerson


def _parse_date_safe(val: Any) -> Optional[date]:
    if not val:
        return None
    if isinstance(val, date):
        return val
    try:
        return date.fromisoformat(str(val)[:10])
    except Exception:
        return None


def convert_db_to_person(db_person: HubPerson) -> Person:
    """Converts a HubPerson ORM model to a typed Pydantic Person."""
    skills = json.loads(db_person.skills_json) if db_person.skills_json else []
    interests = json.loads(db_person.interests_json) if db_person.interests_json else []
    languages = json.loads(db_person.languages_json) if db_person.languages_json else []
    assets = json.loads(db_person.assets_json) if db_person.assets_json else []

    y, m, d = [int(x) for x in db_person.dob[:10].split("-")]

    rel = None
    if db_person.relation:
        try:
            rel = Relation(db_person.relation)
        except ValueError:
            rel = Relation.other

    edu = None
    if db_person.education:
        try:
            edu = Education(db_person.education)
        except ValueError:
            edu = None

    cat = None
    if db_person.category:
        try:
            cat = Category(db_person.category)
        except ValueError:
            cat = None

    gender = None
    if db_person.gender:
        try:
            gender = Gender(db_person.gender)
        except ValueError:
            gender = None

    return Person(
        id=db_person.id,
        household_id=db_person.household_id,
        name=db_person.name,
        name_hi=None,
        dob=date(y, m, d),
        gender=gender,
        relation=rel,
        education=edu,
        category=cat,
        is_disabled=bool(db_person.is_disabled),
        occupation=db_person.occupation,
        skills=skills,
        interests=interests,
        languages=languages,
        land_acres=db_person.land_acres,
        assets=assets,
        is_test_persona=bool(db_person.is_test_persona),
    )


def convert_db_to_opportunity(db_opp: HubOpportunity) -> Opportunity:
    """Converts a HubOpportunity ORM model to a typed Pydantic Opportunity."""
    elig_dict = json.loads(db_opp.eligibility_json) if db_opp.eligibility_json else {}
    dates_dict = json.loads(db_opp.dates_json) if db_opp.dates_json else {}
    docs_list = json.loads(db_opp.documents_json) if db_opp.documents_json else []
    steps_list = json.loads(db_opp.apply_steps_json) if db_opp.apply_steps_json else []

    elig = EligibilityCriteria(
        min_age=elig_dict.get("min_age"),
        max_age=elig_dict.get("max_age"),
        education=[Education(e) for e in elig_dict["education"] if e in Education.__members__] if elig_dict.get("education") else None,
        category=[Category(c) for c in elig_dict["category"] if c in Category.__members__] if elig_dict.get("category") else None,
        gender=[Gender(g) for g in elig_dict["gender"] if g in Gender.__members__] if elig_dict.get("gender") else None,
        is_disabled=elig_dict.get("is_disabled"),
        max_income_lpa=elig_dict.get("max_income_lpa"),
    )

    dates = ImportantDates(
        opens=_parse_date_safe(dates_dict.get("opens")),
        last_date=_parse_date_safe(dates_dict.get("last_date")),
        exam_date=_parse_date_safe(dates_dict.get("exam_date")),
        result_date=_parse_date_safe(dates_dict.get("result_date")),
    )

    typed_docs = []
    for d in docs_list:
        if isinstance(d, dict):
            typed_docs.append(Document(
                name=d.get("name", "Document"),
                name_hi=d.get("name_hi"),
                typical_lead_time_days=d.get("typical_lead_time_days"),
            ))

    opp_type = OpportunityType.scheme
    if db_opp.type in OpportunityType.__members__:
        opp_type = OpportunityType(db_opp.type)

    return Opportunity(
        id=db_opp.id,
        type=opp_type,
        title=db_opp.title,
        title_hi=db_opp.title_hi,
        org=db_opp.org,
        level=db_opp.level,
        geo={"state": db_opp.geo_state, "district": db_opp.geo_district, "block": db_opp.geo_block},
        eligibility=elig,
        dates=dates,
        documents_required=typed_docs,
        fee=db_opp.fee,
        apply_mode=db_opp.apply_mode,
        apply_steps=steps_list,
        source_url=db_opp.source_url,
        last_verified=_parse_date_safe(db_opp.last_verified),
        priority=db_opp.priority or 5,
        is_sample=bool(db_opp.is_sample),
    )


def compute_fit_score(person: Person, opp: Opportunity, match: MatchResult) -> float:
    """
    Computes a fit ranking score [0.0 - 1.0] combining:
      1. Eligibility status base (Eligible = 0.6, Possible = 0.4, Not Eligible = 0.1)
      2. Skill & Interest keyword alignment vs Opportunity title/org (+0.3 max)
      3. Priority weight (+0.1 max)
    """
    score = 0.0
    if match.status.value == "ELIGIBLE":
        score += 0.6
    elif match.status.value == "POSSIBLE":
        score += 0.4
    else:
        score += 0.1

    # Skill & interest matching
    profile_keywords = set()
    for s in person.skills:
        profile_keywords.update(s.lower().split())
    for i in person.interests:
        profile_keywords.update(i.lower().split())
    if person.occupation:
        profile_keywords.update(person.occupation.lower().split())

    opp_text = f"{opp.title} {opp.title_hi or ''} {opp.org or ''} {opp.type.value}".lower()
    matches_count = sum(1 for kw in profile_keywords if len(kw) > 3 and kw in opp_text)

    if matches_count > 0:
        score += min(0.3, matches_count * 0.1)

    # Opportunity priority bonus
    score += (opp.priority / 10.0) * 0.1

    return min(1.0, round(score, 2))


def generate_person_suggestions(
    db_person: HubPerson,
    db_opportunities: list[HubOpportunity],
    reference_date: Optional[date] = None,
) -> list[dict[str, Any]]:
    """
    Generates ranked suggestions for a person across all stored opportunities.
    """
    ref = reference_date or date.today()
    person = convert_db_to_person(db_person)
    suggestions = []

    for db_opp in db_opportunities:
        opp = convert_db_to_opportunity(db_opp)
        match = check_eligibility(person, opp, ref)
        fit_score = compute_fit_score(person, opp, match)

        why_fit_en = build_why_fit(person, opp, match, ref)
        why_fit_hi = f"{person.name} के लिए: {why_fit_en}"

        pathway_info = None
        if match.status.value == "NOT_ELIGIBLE":
            # Look up next step pathway for this person's education level
            edu_level = person.education.value if person.education else "none"
            steps = get_pathway_steps(edu_level)
            if steps:
                best_step = steps[0]
                pathway_info = {
                    "step_title": best_step.get("title"),
                    "step_title_hi": best_step.get("title_hi"),
                    "description": best_step.get("description"),
                    "source_url": best_step.get("source_url"),
                    "action_required": f"To qualify for opportunities like '{opp.title}', consider completing {best_step.get('title')}.",
                }

        suggestions.append({
            "opportunity_id": opp.id,
            "title": opp.title,
            "title_hi": opp.title_hi,
            "type": opp.type.value,
            "org": opp.org,
            "status": match.status.value,
            "status_reasons": [match.reason] if match.reason else [],
            "question_if_possible": match.question,
            "fit_score": fit_score,
            "why_fit": why_fit_en,
            "why_fit_hi": why_fit_hi,
            "pathway_step": pathway_info,
            "label": "suggested, not guaranteed",
            "source_url": opp.source_url,
            "dates": opp.dates.model_dump(mode="json"),
            "documents_required": [d.model_dump(mode="json") for d in opp.documents_required],
            "fee": opp.fee,
        })

    # Rank by fit score descending
    suggestions.sort(key=lambda s: s["fit_score"], reverse=True)
    return suggestions
