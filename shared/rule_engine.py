"""
shared/rule_engine.py
Deterministic eligibility matching, reminder generation, and health rules.

STRICT RULES:
  - No LLM calls ever.
  - No DB queries inside rules — callers pass plain Pydantic objects.
  - Age computed from dob + reference_date; never stored.
  - Health data loaded from /data/real/health/*.yaml — never from model memory.
  - If /data/real/health/ files have placeholder content, health rules return
    a safe "data not loaded" state rather than invented guidance.
"""

from __future__ import annotations

import pathlib
from datetime import date, timedelta
from typing import Optional

try:
    import yaml  # PyYAML — optional; graceful fallback if not installed
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False

from shared.schemas import (
    Category,
    Education,
    EligibilityCriteria,
    Gender,
    MatchResult,
    MatchStatus,
    Opportunity,
    Person,
    Document,
)

# Education ordering for ">= X level" comparisons
_EDUCATION_RANK: dict[str, int] = {
    "none": 0,
    "primary": 1,
    "middle": 2,
    "secondary": 3,
    "senior_sec": 4,
    "graduate": 5,
    "postgrad": 6,
}

# Real data paths (relative to repo root)
_REPO_ROOT = pathlib.Path(__file__).parent.parent
_HEALTH_DIR = _REPO_ROOT / "data" / "real" / "health"
_IMMUNIZATION_FILE = _HEALTH_DIR / "immunization_schedule.yaml"
_RED_FLAGS_FILE = _HEALTH_DIR / "red_flags.yaml"
_PATHWAYS_FILE = _REPO_ROOT / "data" / "real" / "pathways.yaml"


# ── Utility ───────────────────────────────────────────────────────────────────

def compute_age(dob: date, reference_date: Optional[date] = None) -> int:
    """Return age in completed years. Age is never stored — always computed."""
    ref = reference_date or date.today()
    age = ref.year - dob.year - ((ref.month, ref.day) < (dob.month, dob.day))
    return max(0, age)


def education_rank(edu: Optional[str]) -> int:
    if edu is None:
        return -1
    return _EDUCATION_RANK.get(str(edu), -1)


# ── Core eligibility check ────────────────────────────────────────────────────

def check_eligibility(
    person: Person,
    opportunity: Opportunity,
    reference_date: Optional[date] = None,
) -> MatchResult:
    """
    Returns MatchResult with status ELIGIBLE | POSSIBLE | NOT_ELIGIBLE.

    POSSIBLE: a profile field is None/unknown; surfaces ONE question to ask.
    NOT_ELIGIBLE: at least one criterion is definitively not met.
    ELIGIBLE: all known criteria pass.
    """
    ref = reference_date or date.today()
    age = compute_age(person.dob, ref)
    e = opportunity.eligibility

    reasons: list[str] = []
    questions: list[str] = []
    definite_fail = False

    # ── Age ──────────────────────────────────────────────────────────────────
    if e.min_age is not None and age < e.min_age:
        definite_fail = True
        reasons.append(f"Age {age} is below minimum {e.min_age}")

    if e.max_age is not None and age > e.max_age:
        definite_fail = True
        reasons.append(f"Age {age} exceeds maximum {e.max_age}")

    # ── Gender ───────────────────────────────────────────────────────────────
    if e.gender:
        if person.gender is None:
            questions.append("What is this person's gender?")
        elif person.gender not in e.gender:
            definite_fail = True
            reasons.append(
                f"Gender {person.gender} not in allowed {[g.value for g in e.gender]}"
            )

    # ── Category ─────────────────────────────────────────────────────────────
    if e.category:
        if person.category is None:
            questions.append("What is this person's caste category (GEN/OBC/SC/ST/EWS)?")
        elif person.category not in e.category:
            definite_fail = True
            reasons.append(
                f"Category {person.category} not in {[c.value for c in e.category]}"
            )

    # ── Education ─────────────────────────────────────────────────────────────
    if e.education:
        if person.education is None:
            questions.append("What is this person's highest education level?")
        else:
            person_rank = education_rank(person.education.value)
            required_ranks = [education_rank(edu.value) for edu in e.education]
            if person_rank < min(required_ranks):
                definite_fail = True
                reasons.append(
                    f"Education {person.education} does not meet minimum requirement "
                    f"{[edu.value for edu in e.education]}"
                )

    # ── Disability ───────────────────────────────────────────────────────────
    if e.is_disabled is not None:
        if e.is_disabled and not person.is_disabled:
            definite_fail = True
            reasons.append("This opportunity is only for persons with disability")

    # ── Deadline passed ───────────────────────────────────────────────────────
    if opportunity.dates.last_date and opportunity.dates.last_date < ref:
        definite_fail = True
        reasons.append(
            f"Application deadline {opportunity.dates.last_date} has passed"
        )

    # ── Outcome ───────────────────────────────────────────────────────────────
    if definite_fail:
        return MatchResult(
            person_id=person.id,
            opportunity_id=opportunity.id,
            status=MatchStatus.not_eligible,
            reason="; ".join(reasons) if reasons else "Not eligible",
        )

    if questions:
        return MatchResult(
            person_id=person.id,
            opportunity_id=opportunity.id,
            status=MatchStatus.possible,
            question=questions[0],  # surface one at a time
        )

    return MatchResult(
        person_id=person.id,
        opportunity_id=opportunity.id,
        status=MatchStatus.eligible,
        reason="Meets all known criteria",
    )


# ── Batch matching ────────────────────────────────────────────────────────────

def match_household(
    people: list[Person],
    opportunities: list[Opportunity],
    reference_date: Optional[date] = None,
) -> list[MatchResult]:
    """Run check_eligibility for every (person, opportunity) pair."""
    results = []
    for person in people:
        for opp in opportunities:
            results.append(check_eligibility(person, opp, reference_date))
    return results


# ── Why-fit explanation (deterministic template) ──────────────────────────────

def build_why_fit(
    person: Person,
    opportunity: Opportunity,
    match: MatchResult,
    reference_date: Optional[date] = None,
) -> str:
    """
    Returns a deterministic explanation string.
    The LLM may rephrase this, but the underlying facts come only from here.
    Never invents criteria not present in the opportunity schema.
    """
    ref = reference_date or date.today()
    age = compute_age(person.dob, ref)
    parts: list[str] = []

    if match.status == MatchStatus.eligible:
        parts.append(f"{person.name} meets all known criteria.")
        if opportunity.eligibility.min_age or opportunity.eligibility.max_age:
            parts.append(f"Age {age} is within the required range.")
        if opportunity.eligibility.category:
            cats = [c.value for c in opportunity.eligibility.category]
            parts.append(f"Category {person.category.value if person.category else '?'} is accepted.")
        if opportunity.eligibility.education:
            parts.append(f"Education level qualifies.")
        if opportunity.dates.last_date:
            days_left = (opportunity.dates.last_date - ref).days
            if days_left >= 0:
                parts.append(f"{days_left} day(s) left to apply.")
    elif match.status == MatchStatus.possible:
        parts.append(f"{person.name} may qualify — more information needed.")
        if match.question:
            parts.append(f"Missing: {match.question}")
    else:
        parts.append(f"{person.name} does not currently meet the criteria.")
        if match.reason:
            parts.append(match.reason)

    return " ".join(parts)


# ── Reminder generation ───────────────────────────────────────────────────────

REMINDER_DAYS = [15, 7, 2, 0]  # days before deadline


def generate_deadline_reminders(
    person: Person,
    opportunity: Opportunity,
    reference_date: Optional[date] = None,
) -> list[dict]:
    """
    Returns reminder dicts for deadline countdown and document readiness.
    Keys: kind, person_id, opportunity_id, due_at (date str), message, message_hi.
    """
    ref = reference_date or date.today()
    reminders: list[dict] = []
    last = opportunity.dates.last_date
    if not last:
        return reminders

    for days_before in REMINDER_DAYS:
        fire_on = last - timedelta(days=days_before)
        if fire_on < ref:
            continue
        days_left = (last - ref).days
        if days_before == 0:
            msg_en = f"TODAY is the last day to apply for '{opportunity.title}'."
            msg_hi = (
                f"आज '{opportunity.title_hi or opportunity.title}' "
                f"आवेदन की अंतिम तिथि है।"
            )
        else:
            msg_en = (
                f"Only {days_left} day(s) left to apply for '{opportunity.title}'."
            )
            msg_hi = (
                f"'{opportunity.title_hi or opportunity.title}' के लिए "
                f"आवेदन में {days_left} दिन शेष।"
            )
        reminders.append({
            "kind": "deadline",
            "person_id": person.id,
            "opportunity_id": opportunity.id,
            "due_at": fire_on.isoformat(),
            "message": msg_en,
            "message_hi": msg_hi,
        })

    # ── Document readiness ────────────────────────────────────────────────────
    for doc in opportunity.documents_required:
        lead = doc.typical_lead_time_days
        if lead and lead > 0 and last:
            start_by = last - timedelta(days=lead)
            if start_by >= ref:
                reminders.append({
                    "kind": "document",
                    "person_id": person.id,
                    "opportunity_id": opportunity.id,
                    "due_at": start_by.isoformat(),
                    "message": (
                        f"Start getting '{doc.name}' now — it can take up to "
                        f"{lead} days and is needed for '{opportunity.title}'."
                    ),
                    "message_hi": (
                        f"'{doc.name_hi or doc.name}' प्राप्त करना शुरू करें — "
                        f"इसमें {lead} दिन तक लग सकते हैं।"
                    ),
                })

    return reminders


# ── Health data loaders ───────────────────────────────────────────────────────

def _load_yaml_safe(path: pathlib.Path) -> Optional[dict]:
    """Load a YAML file. Returns None if file missing, YAML unavailable, or placeholder."""
    if not _YAML_AVAILABLE:
        return None
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if isinstance(data, dict) and data.get("_status", "").startswith("PLACEHOLDER"):
        return None   # Real data not yet loaded; return None rather than invent
    return data


def get_immunization_schedule(dob: date) -> list[dict]:
    """
    Return expected immunization dates for a child from their DOB.
    Data loaded from /data/real/health/immunization_schedule.yaml.
    Returns empty list if real data not yet loaded (placeholder detected).

    ⚠ Disclaimer must always be shown alongside immunization data.
    """
    data = _load_yaml_safe(_IMMUNIZATION_FILE)
    if not data:
        return []   # Placeholder content — do not invent schedule

    schedule = []
    for item in data.get("schedule", []):
        months = item.get("months_from_birth", 0)
        due = dob + timedelta(days=int(months * 30.44))
        schedule.append({
            "vaccine": item["vaccine"],
            "months_from_birth": months,
            "due_date": due,
            "notes": item.get("notes"),
        })
    return schedule


def get_anc_schedule(lmp_date: date) -> list[dict]:
    """
    Antenatal care visit schedule.
    NOTE: Real ANC schedule should be loaded from /data/real/health/anc_schedule.yaml
    when that file is populated from official MoHFW sources.
    Returns empty list until real data is loaded.
    """
    # Structural placeholder — returns empty until real data file is added
    return []


def get_red_flags() -> list[dict]:
    """
    Load red-flag symptom rules from /data/real/health/red_flags.yaml.
    Returns empty list if real data not yet loaded.
    """
    data = _load_yaml_safe(_RED_FLAGS_FILE)
    if not data:
        return []
    return data.get("red_flags", [])


def get_health_disclaimer() -> dict:
    """Return the health disclaimer from red_flags.yaml, or a safe default."""
    data = _load_yaml_safe(_RED_FLAGS_FILE)
    if data:
        return {
            "en": data.get("disclaimer_en", ""),
            "hi": data.get("disclaimer_hi", ""),
        }
    return {
        "en": (
            "This information is a general reminder only. "
            "It does NOT replace medical advice. "
            "Consult your ASHA worker or PHC for any health concern."
        ),
        "hi": (
            "यह जानकारी केवल एक सामान्य अनुस्मारक है। "
            "यह चिकित्सा सलाह का विकल्प नहीं है। "
            "किसी भी स्वास्थ्य समस्या के लिए अपनी ASHA कार्यकर्ता या PHC से संपर्क करें।"
        ),
    }


# ── Pathway loader ────────────────────────────────────────────────────────────

def get_pathway_steps(education_level: Optional[str]) -> list[dict]:
    """
    Load pathway steps for a given education level from /data/real/pathways.yaml.
    Returns empty list if real data not yet loaded or level not found.
    Never invents pathway entries.
    """
    if not education_level:
        return []
    data = _load_yaml_safe(_PATHWAYS_FILE)
    if not data:
        return []
    pathways = data.get("pathways", {})
    steps = pathways.get(education_level, [])
    # Filter out any remaining placeholder entries
    return [
        s for s in steps
        if s.get("source_url") and s["source_url"] != "REQUIRED"
    ]
