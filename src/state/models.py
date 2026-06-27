from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from src.state.db import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

class SessionModel(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True, default=generate_uuid)
    type = Column(String, nullable=False)  # BUG, FEATURE, MEETING/PLANNING, UNCERTAIN
    subtype = Column(String, nullable=True)  # e.g., "Performance Investigation"
    raw_input = Column(Text, nullable=False)
    active_mode = Column(String, default="PLAN", nullable=False)  # PLAN, BUILD
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    steps = relationship("StepModel", back_populates="session", cascade="all, delete-orphan", lazy="joined")
    artifacts = relationship("ArtifactModel", back_populates="session", cascade="all, delete-orphan", lazy="joined")


class StepModel(Base):
    __tablename__ = "steps"

    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    name = Column(String, nullable=False)
    status = Column(String, nullable=False, default="PENDING")  # PENDING, COMPLETED, SKIPPED
    reason = Column(Text, nullable=True)  # Reason if skipped
    data = Column(JSON, nullable=True)  # Store step transcript or other key-value pairs

    # Relationships
    session = relationship("SessionModel", back_populates="steps")


class ArtifactModel(Base):
    __tablename__ = "artifacts"

    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)  # BDD_SCENARIO, TEST_SKELETON, MONITORING_PLAN, SUMMARY
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    session = relationship("SessionModel", back_populates="artifacts")
