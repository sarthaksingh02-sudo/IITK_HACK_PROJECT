"""
cloud/db.py
SQLAlchemy setup + table definitions for the Cloud Control Center DB.
"""

from __future__ import annotations

import os
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DB_URL = os.getenv("CLOUD_DB_URL", "sqlite:///./cloud/cloud.db")

engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class RawNotice(Base):
    __tablename__ = "raw_notices"

    id = Column(String, primary_key=True)
    source_url = Column(String)
    raw_text = Column(Text, nullable=False)
    language = Column(String, default="en")
    ingested_at = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending")
    # pending | processing | approved | rejected


class CloudOpportunity(Base):
    __tablename__ = "opportunities"

    id = Column(String, primary_key=True)
    raw_notice_id = Column(String)
    type = Column(String, nullable=False)
    title = Column(String, nullable=False)
    title_hi = Column(String)
    org = Column(String)
    level = Column(String)
    geo_state = Column(String)
    geo_district = Column(String)
    geo_block = Column(String)
    language = Column(String, default="en")
    eligibility_json = Column(Text)
    dates_json = Column(Text)
    documents_json = Column(Text)
    fee = Column(Float, default=0.0)
    apply_mode = Column(String)
    apply_steps_json = Column(Text)
    source_url = Column(String)
    last_verified = Column(String)
    priority = Column(Integer, default=5)
    status = Column(String, default="draft")
    # draft | approved | published | expired
    is_sample = Column(Boolean, default=False)
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)


class CloudPacket(Base):
    __tablename__ = "packets"

    id = Column(String, primary_key=True)
    kind = Column(String, nullable=False)
    topic = Column(String)
    geo_state = Column(String)
    geo_district = Column(String)
    language = Column(String)
    priority = Column(Integer, default=5)
    valid_until = Column(String)
    version = Column(Integer, default=1)
    payload_ref = Column(String)
    published_at = Column(String, nullable=False)
    signature = Column(String, nullable=False)


def get_db():
    """FastAPI dependency — yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
