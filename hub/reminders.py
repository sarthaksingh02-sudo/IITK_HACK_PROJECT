"""
hub/reminders.py
Generates deadline countdowns, document preparation alerts, and stage tracking.
Supports Fast-Forward N days simulation control.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any, Optional

from shared.rule_engine import generate_deadline_reminders
from hub.db import HubOpportunity, HubPerson, HubReminder
from hub.suggestions import convert_db_to_opportunity, convert_db_to_person


def evaluate_household_reminders(
    people: list[HubPerson],
    opportunities: list[HubOpportunity],
    fast_forward_days: int = 0,
) -> list[dict[str, Any]]:
    """
    Evaluates reminders for all household members across all active opportunities
    at reference_date = today + fast_forward_days.
    """
    ref_date = date.today() + timedelta(days=fast_forward_days)
    all_reminders = []

    for p in people:
        person_model = convert_db_to_person(p)
        for o in opportunities:
            opp_model = convert_db_to_opportunity(o)
            reminders = generate_deadline_reminders(person_model, opp_model, ref_date)
            for r in reminders:
                r["person_name"] = p.name
                r["opportunity_title"] = o.title
                r["opportunity_title_hi"] = o.title_hi
                all_reminders.append(r)

    # Sort by due_at ascending
    all_reminders.sort(key=lambda x: x.get("due_at", ""))
    return all_reminders
