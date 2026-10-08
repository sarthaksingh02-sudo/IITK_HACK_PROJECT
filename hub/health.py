"""
hub/health.py
Village Hub Family Health Module.

STRICT PRINCIPLES:
  - Driven ONLY by verified data files in /data/real/health/.
  - Outputs referral advice, NEVER medical diagnoses.
  - Visible disclaimer and source citation included with every rule.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from shared.rule_engine import (
    compute_age,
    get_health_disclaimer,
    get_immunization_schedule,
    get_red_flags,
)
from hub.db import HubPerson


def get_person_health_summary(db_person: HubPerson, reference_date: Optional[date] = None) -> dict[str, Any]:
    """
    Computes age from DOB and returns appropriate immunization reminders or red-flag guidelines.
    """
    ref = reference_date or date.today()
    y, m, d = [int(x) for x in db_person.dob.split("-")]
    dob = date(y, m, d)
    age_years = compute_age(dob, ref)
    age_months = ((ref.year - dob.year) * 12) + (ref.month - dob.month)

    disclaimer = get_health_disclaimer()
    red_flags = get_red_flags()

    # Determine age category
    is_infant_child = age_years <= 16
    is_adult_female = db_person.gender == "F" and 15 <= age_years <= 49

    immunizations = []
    if is_infant_child:
        all_schedule = get_immunization_schedule(dob)
        # Filter into upcoming / past
        for item in all_schedule:
            due = item["due_date"]
            days_diff = (due - ref).days
            status = "due_now" if -30 <= days_diff <= 30 else ("upcoming" if days_diff > 30 else "passed")
            immunizations.append({
                "vaccine": item["vaccine"],
                "months_from_birth": item["months_from_birth"],
                "due_date": due.isoformat(),
                "status": status,
                "notes": item.get("notes"),
            })

    # Relevant red flags for this person
    relevant_red_flags = []
    for rf in red_flags:
        cat = rf.get("category")
        if (cat == "child" and age_years <= 12) or (cat == "maternal" and is_adult_female) or (cat == "general"):
            relevant_red_flags.append(rf)

    return {
        "person_id": db_person.id,
        "name": db_person.name,
        "age_years": age_years,
        "age_months": age_months,
        "dob": db_person.dob,
        "immunizations": immunizations,
        "relevant_red_flags": relevant_red_flags,
        "disclaimer": disclaimer,
        "source": "National Immunization Schedule (MoHFW) & IMNCI Guidelines",
    }
