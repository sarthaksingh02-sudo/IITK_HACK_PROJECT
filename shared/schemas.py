"""
shared/schemas.py
Pydantic v2 models shared between cloud and hub.

STRICT DATA RULES (enforced here and in data_loader.py):
  - Age is NEVER stored — always compute from dob at runtime.
  - source_url is MANDATORY on Opportunity and PathwayEntry.
  - Fields not in the source notice stay None; never default-guess.
  - HealthRule data must come from /data/real/health/ files only.
  - is_test_persona=True blocks a Person from appearing in any production UI.
  - No Aadhaar numbers, anywhere, ever.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


# ── Enums ────────────────────────────────────────────────────────────────────

class OpportunityType(str, Enum):
    exam       = "exam"
    job        = "job"
    scholarship= "scholarship"
    scheme     = "scheme"
    training   = "training"


class Level(str, Enum):
    central  = "central"
    state    = "state"
    district = "district"


class ApplyMode(str, Enum):
    online  = "online"
    offline = "offline"
    CSC     = "CSC"


class MatchStatus(str, Enum):
    eligible     = "ELIGIBLE"
    possible     = "POSSIBLE"
    not_eligible = "NOT_ELIGIBLE"


class TrackingStage(str, Enum):
    seen        = "seen"
    interested  = "interested"
    preparing   = "preparing"
    applied     = "applied"
    admit_card  = "admit_card"
    result      = "result"


class Gender(str, Enum):
    M = "M"
    F = "F"
    O = "O"


class Education(str, Enum):
    none       = "none"
    primary    = "primary"
    middle     = "middle"
    secondary  = "secondary"
    senior_sec = "senior_sec"
    graduate   = "graduate"
    postgrad   = "postgrad"


class Category(str, Enum):
    GEN = "GEN"
    OBC = "OBC"
    SC  = "SC"
    ST  = "ST"
    EWS = "EWS"


class Relation(str, Enum):
    head     = "head"
    spouse   = "spouse"
    son      = "son"
    daughter = "daughter"
    parent   = "parent"
    other    = "other"


class PacketKind(str, Enum):
    opportunity   = "opportunity"
    update        = "update"
    health_tip    = "health_tip"
    alert         = "alert"
    sync_response = "sync_response"


class Topic(str, Enum):
    agriculture = "agriculture"
    health      = "health"
    education   = "education"
    jobs        = "jobs"
    schemes     = "schemes"
    disaster    = "disaster"
    general     = "general"


class HealthRuleCategory(str, Enum):
    immunization = "immunization"
    anc          = "anc"
    red_flag     = "red_flag"
    chronic      = "chronic"


# ── Sub-models ────────────────────────────────────────────────────────────────

class Geo(BaseModel):
    state:    Optional[str] = None
    district: Optional[str] = None
    block:    Optional[str] = None


class EligibilityCriteria(BaseModel):
    """
    All fields default to None = "no restriction stated in the source notice".
    Never infer or fill from model knowledge.
    """
    min_age:        Optional[int]           = None
    max_age:        Optional[int]           = None
    education:      Optional[list[Education]]= None   # any of these qualifies
    category:       Optional[list[Category]]= None   # None = all categories
    gender:         Optional[list[Gender]]  = None   # None = all genders
    is_disabled:    Optional[bool]          = None   # True = PWD-only scheme
    min_income_lpa: Optional[float]         = None
    max_income_lpa: Optional[float]         = None
    geo_state:      Optional[list[str]]     = None   # None = all states
    extra:          dict[str, Any]          = Field(default_factory=dict)


class ImportantDates(BaseModel):
    """All fields None when not stated in source notice."""
    opens:       Optional[date] = None
    last_date:   Optional[date] = None
    exam_date:   Optional[date] = None
    result_date: Optional[date] = None


class Document(BaseModel):
    name:                     str
    name_hi:                  Optional[str] = None
    typical_lead_time_days:   Optional[int] = None   # None when not stated in source


# ── Opportunity ───────────────────────────────────────────────────────────────

class Opportunity(BaseModel):
    id:                 str
    type:               OpportunityType
    title:              str
    title_hi:           Optional[str]       = None
    org:                Optional[str]        = None
    level:              Optional[Level]      = None
    geo:                Geo                  = Field(default_factory=Geo)
    language:           str                  = "en"
    eligibility:        EligibilityCriteria  = Field(default_factory=EligibilityCriteria)
    dates:              ImportantDates        = Field(default_factory=ImportantDates)
    documents_required: list[Document]       = Field(default_factory=list)
    fee:                Optional[float]      = None   # None when not stated
    apply_mode:         Optional[ApplyMode]  = None
    apply_steps:        list[str]            = Field(default_factory=list)
    source_url:         str                           # MANDATORY — never invent
    last_verified:      Optional[date]       = None
    priority:           int                  = Field(default=5, ge=1, le=10)
    is_sample:          bool                 = False  # True for mock / demo data

    @field_validator("priority")
    @classmethod
    def clamp(cls, v: int) -> int:
        return max(1, min(10, v))


# ── Person + Household ────────────────────────────────────────────────────────

class Person(BaseModel):
    """
    Household member.
    Age MUST be computed via compute_age(dob, ref). Never stored.
    No Aadhaar numbers — not in this model, not anywhere.
    is_test_persona=True → must never appear in production UI.
    """
    id:             str
    household_id:   str
    name:           str
    dob:            date                    # YYYY-MM-DD
    gender:         Optional[Gender]    = None
    relation:       Optional[Relation]  = None
    education:      Optional[Education] = None
    category:       Optional[Category]  = None
    is_disabled:    bool                = False
    occupation:     Optional[str]       = None
    skills:         list[str]           = Field(default_factory=list)
    interests:      list[str]           = Field(default_factory=list)
    languages:      list[str]           = Field(default_factory=list)
    land_acres:     Optional[float]     = None
    assets:         list[str]           = Field(default_factory=list)
    is_test_persona: bool               = False
    created_at:     datetime            = Field(default_factory=lambda: datetime.now())


class Household(BaseModel):
    id:               str
    village:          Optional[str]      = None
    district:         Optional[str]      = None
    state:            Optional[str]      = None
    created_at:       datetime           = Field(default_factory=lambda: datetime.now())
    consent_given_at: Optional[datetime] = None   # None = consent not yet given


# ── Packet ────────────────────────────────────────────────────────────────────

class Packet(BaseModel):
    """
    Signed transport envelope.
    Signature covers canonical JSON of all fields except 'signature'.
    Hub MUST reject packets where verify_packet() → False.
    """
    id:          str
    kind:        PacketKind
    topic:       Optional[Topic]    = None
    geo:         Geo                = Field(default_factory=Geo)
    language:    str                = "hi"
    priority:    int                = 5
    valid_until: Optional[datetime] = None
    version:     int                = 1
    payload:     dict[str, Any]
    signature:   Optional[str]      = None  # hex Ed25519; None before signing


# ── PathwayEntry ──────────────────────────────────────────────────────────────

class PathwayEntry(BaseModel):
    """
    One step in a career / education pathway.
    Loaded ONLY from /data/real/pathways.yaml.
    source_url is mandatory — entries without it are rejected by the data loader.
    Never invent pathway text, salaries, cutoffs, or selection odds.
    """
    id:               str
    title:            str
    title_hi:         Optional[str] = None
    type:             str           # exam | job | training | qualification | next_step
    description:      Optional[str] = None
    eligibility_note: Optional[str] = None
    source_url:       str           # MANDATORY
    retrieved_date:   Optional[date]= None


# ── HealthRule ────────────────────────────────────────────────────────────────

class ImmunizationRule(BaseModel):
    """
    One line in the National Immunization Schedule.
    Source: MoHFW NIS — loaded from /data/real/health/immunization_schedule.yaml.
    """
    vaccine:            str
    when:               str           # human-readable, e.g. "At birth", "6 weeks"
    months_from_birth:  float         # numeric; used for due-date arithmetic
    dose:               Optional[str] = None
    route:              Optional[str] = None
    notes:              Optional[str] = None


class RedFlagRule(BaseModel):
    """
    One red-flag symptom → "go to PHC" referral rule.
    Source: ASHA/IMCI — loaded from /data/real/health/red_flags.yaml.
    """
    symptom:     str
    symptom_hi:  Optional[str] = None
    action:      str
    action_hi:   Optional[str] = None
    category:    str            # maternal | child | general
    source_ref:  Optional[str] = None


class HealthRule(BaseModel):
    """
    Union wrapper for all health rule types.
    category determines which concrete rule type is populated.
    """
    category:          HealthRuleCategory
    immunization_rule: Optional[ImmunizationRule] = None
    red_flag_rule:     Optional[RedFlagRule]       = None
    disclaimer_en:     str = (
        "This is a general reminder only. It does NOT replace medical advice. "
        "Consult your ASHA worker or PHC for any health concern."
    )
    disclaimer_hi:     str = (
        "यह केवल एक सामान्य अनुस्मारक है। यह चिकित्सा सलाह का विकल्प नहीं है। "
        "किसी भी स्वास्थ्य समस्या के लिए अपनी ASHA कार्यकर्ता या PHC से संपर्क करें।"
    )


# ── Match + Suggestion results ────────────────────────────────────────────────

class MatchResult(BaseModel):
    person_id:      str
    opportunity_id: str
    status:         MatchStatus
    reason:         Optional[str] = None
    question:       Optional[str] = None   # filled when status == POSSIBLE
    matched_at:     datetime       = Field(default_factory=lambda: datetime.now())


class SuggestionResult(BaseModel):
    """
    Output of the personalized suggestion engine.
    Always carries the label 'suggested, not guaranteed'.
    why_fit is a deterministic template (LLM may rephrase but never changes facts).
    """
    person_id:      str
    opportunity_id: str
    match_status:   MatchStatus
    rank_score:     Optional[float] = None    # embedding cosine sim; None if no model loaded
    why_fit:        Optional[str]   = None    # generated by rule_engine.build_why_fit()
    pathway_step:   Optional[str]   = None    # from pathways.yaml if NOT_ELIGIBLE
    label:          str             = "suggested, not guaranteed"
    created_at:     datetime        = Field(default_factory=lambda: datetime.now())


class TrackingRecord(BaseModel):
    id:             str
    person_id:      str
    opportunity_id: str
    stage:          TrackingStage = TrackingStage.seen
    updated_at:     datetime      = Field(default_factory=lambda: datetime.now())
    notes:          Optional[str] = None


class RegionalUpdate(BaseModel):
    id:          str
    topic:       Topic
    title:       str
    title_hi:    Optional[str]   = None
    body:        Optional[str]   = None
    body_hi:     Optional[str]   = None
    geo:         Geo             = Field(default_factory=Geo)
    priority:    int             = 5
    valid_until: Optional[datetime] = None
    published_at: datetime       = Field(default_factory=lambda: datetime.now())
