"""
hub/db.py
SQLAlchemy models for the Village Hub SQLite database.
"""

from __future__ import annotations

import os

from sqlalchemy import (
    Boolean,
    Column,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DB_URL = os.getenv("HUB_DB_URL", "sqlite:///./hub/hub.db")
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class HubOpportunity(Base):
    __tablename__ = "opportunities"

    id = Column(String, primary_key=True)
    type = Column(String, nullable=False)
    title = Column(String, nullable=False)
    title_hi = Column(String)
    org = Column(String)
    level = Column(String)
    geo_state = Column(String)
    geo_district = Column(String)
    geo_block = Column(String)
    eligibility_json = Column(Text)
    dates_json = Column(Text)
    documents_json = Column(Text)
    fee = Column(Float)          # None if not stated in source
    apply_mode = Column(String)
    apply_steps_json = Column(Text)
    source_url = Column(String, nullable=False)  # mandatory
    last_verified = Column(String)
    priority = Column(Integer, default=5)
    valid_until = Column(String)
    synced_at = Column(String, nullable=False)
    is_sample = Column(Boolean, default=False)


class HubHousehold(Base):
    __tablename__ = "households"

    id = Column(String, primary_key=True)
    village = Column(String)
    district = Column(String)
    state = Column(String)
    created_at = Column(String, nullable=False)
    consent_given_at = Column(String)  # None = not consented yet


class HubPerson(Base):
    __tablename__ = "people"

    id = Column(String, primary_key=True)
    household_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    dob = Column(String, nullable=False)    # YYYY-MM-DD; age always computed
    gender = Column(String)
    relation = Column(String)
    education = Column(String)
    category = Column(String)
    is_disabled = Column(Boolean, default=False)
    occupation = Column(String)
    skills_json = Column(Text)
    interests_json = Column(Text)
    languages_json = Column(Text)
    land_acres = Column(Float)
    assets_json = Column(Text)
    created_at = Column(String, nullable=False)
    # Safeguard: test personas must never appear in production UI
    is_test_persona = Column(Boolean, default=False)


class HubMatchResult(Base):
    __tablename__ = "match_results"

    id = Column(String, primary_key=True)
    person_id = Column(String, nullable=False)
    opportunity_id = Column(String, nullable=False)
    status = Column(String, nullable=False)
    reason = Column(String)
    question = Column(String)
    matched_at = Column(String, nullable=False)

    __table_args__ = (UniqueConstraint("person_id", "opportunity_id"),)


class HubSuggestion(Base):
    __tablename__ = "suggestions"

    id = Column(String, primary_key=True)
    person_id = Column(String, nullable=False)
    opportunity_id = Column(String, nullable=False)
    match_status = Column(String, nullable=False)
    rank_score = Column(Float)
    why_fit = Column(Text)
    pathway_step = Column(Text)
    label = Column(String, default="suggested, not guaranteed")
    created_at = Column(String, nullable=False)

    __table_args__ = (UniqueConstraint("person_id", "opportunity_id"),)


class HubTracking(Base):
    __tablename__ = "tracking"

    id = Column(String, primary_key=True)
    person_id = Column(String, nullable=False)
    opportunity_id = Column(String, nullable=False)
    stage = Column(String, nullable=False, default="seen")
    updated_at = Column(String, nullable=False)
    notes = Column(Text)

    __table_args__ = (UniqueConstraint("person_id", "opportunity_id"),)


class HubReminder(Base):
    __tablename__ = "reminders"

    id = Column(String, primary_key=True)
    person_id = Column(String)
    household_id = Column(String)
    opportunity_id = Column(String)
    kind = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    message_hi = Column(Text)
    due_at = Column(String, nullable=False)
    fired_at = Column(String)
    dismissed_at = Column(String)


class HubHealthRecord(Base):
    __tablename__ = "health_records"

    id = Column(String, primary_key=True)
    person_id = Column(String, nullable=False)
    record_type = Column(String, nullable=False)
    detail_json = Column(Text)
    date = Column(String, nullable=False)
    notes = Column(Text)
    created_at = Column(String, nullable=False)


class HubUpdate(Base):
    __tablename__ = "updates"

    id = Column(String, primary_key=True)
    topic = Column(String, nullable=False)
    title = Column(String, nullable=False)
    title_hi = Column(String)
    body = Column(Text)
    body_hi = Column(Text)
    geo_state = Column(String)
    geo_district = Column(String)
    priority = Column(Integer, default=5)
    valid_until = Column(String)
    published_at = Column(String, nullable=False)


class HubOutbox(Base):
    __tablename__ = "outbox"

    id = Column(String, primary_key=True)
    kind = Column(String, nullable=False)
    payload_json = Column(Text, nullable=False)
    created_at = Column(String, nullable=False)
    sent_at = Column(String)


class PacketLedger(Base):
    __tablename__ = "packet_ledger"

    packet_id = Column(String, primary_key=True)
    received_at = Column(String, nullable=False)
    verified = Column(Integer, nullable=False, default=0)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
