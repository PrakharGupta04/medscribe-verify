import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import relationship
from backend.app.db.base import Base


def utc_now():
    return datetime.now(timezone.utc)


def generate_uuid():
    return str(uuid.uuid4())


class Patient(Base):
    __tablename__ = "patients"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    mrn = Column(String(32), unique=True, index=True, nullable=False)
    name = Column(String(128), nullable=False)
    dob = Column(String(32), nullable=True)
    phone = Column(String(32), nullable=True)
    gender = Column(String(32), nullable=True, default="Not specified")
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    sessions = relationship("IntakeSession", back_populates="patient", cascade="all, delete-orphan")
    intake_records = relationship("IntakeData", back_populates="patient", cascade="all, delete-orphan")
    queue_entries = relationship("QueueEntry", back_populates="patient", cascade="all, delete-orphan")
    consultations = relationship("Consultation", back_populates="patient", cascade="all, delete-orphan")


class IntakeSession(Base):
    __tablename__ = "intake_sessions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_token = Column(String(64), unique=True, index=True, nullable=False)
    patient_id = Column(String(36), ForeignKey("patients.id"), nullable=True)
    status = Column(String(32), default="draft", nullable=False)  # draft, submitted, expired
    draft_data = Column(Text, nullable=True)  # JSON string for in-progress draft responses
    expires_at = Column(DateTime(timezone=True), nullable=False)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    patient = relationship("Patient", back_populates="sessions")
    intake_data = relationship("IntakeData", back_populates="session", uselist=False, cascade="all, delete-orphan")
    queue_entry = relationship("QueueEntry", back_populates="session", uselist=False, cascade="all, delete-orphan")
    consultations = relationship("Consultation", back_populates="session", cascade="all, delete-orphan")


class IntakeData(Base):
    __tablename__ = "intake_data"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("intake_sessions.id"), unique=True, nullable=False)
    patient_id = Column(String(36), ForeignKey("patients.id"), nullable=False)
    chief_complaint = Column(String(256), nullable=False)
    symptoms = Column(Text, nullable=False, default="[]")  # JSON list
    duration = Column(String(64), nullable=False)
    severity = Column(Integer, nullable=False)  # 1 to 10
    adaptive_responses = Column(Text, nullable=False, default="{}")  # JSON dict
    conditions = Column(Text, nullable=False, default="[]")  # JSON list
    medications = Column(Text, nullable=True, default="")
    allergies = Column(Text, nullable=True, default="")
    previous_procedures = Column(Text, nullable=True, default="")
    additional_notes = Column(Text, nullable=True, default="")
    provenance = Column(String(64), default="patient-reported", nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    submitted_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    session = relationship("IntakeSession", back_populates="intake_data")
    patient = relationship("Patient", back_populates="intake_records")


class QueueEntry(Base):
    __tablename__ = "queue_entries"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    patient_id = Column(String(36), ForeignKey("patients.id"), nullable=False)
    session_id = Column(String(36), ForeignKey("intake_sessions.id"), unique=True, nullable=False)
    position = Column(Integer, nullable=False)
    wait_time_minutes = Column(Integer, nullable=False, default=15)
    status = Column(String(32), default="waiting", nullable=False)  # waiting, in-consultation, completed
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    patient = relationship("Patient", back_populates="queue_entries")
    session = relationship("IntakeSession", back_populates="queue_entry")


class Consultation(Base):
    __tablename__ = "consultations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    patient_id = Column(String(36), ForeignKey("patients.id"), nullable=False, index=True)
    session_id = Column(String(36), ForeignKey("intake_sessions.id"), nullable=True)
    status = Column(String(32), default="in-progress", nullable=False)  # in-progress, completed
    transcript = Column(Text, nullable=True, default="")
    extracted_clinical_data = Column(Text, nullable=True, default=None)  # JSON-serialized ClinicalExtraction
    soap_draft = Column(Text, nullable=True, default=None)  # JSON-serialized SoapDraft
    verification_results = Column(Text, nullable=True, default=None)  # JSON-serialized VerificationResults
    comparison_results = Column(Text, nullable=True, default=None)  # JSON-serialized ComparisonResults
    final_record = Column(Text, nullable=True, default=None)  # JSON-serialized FinalMedicalRecord
    finalized_at = Column(DateTime(timezone=True), nullable=True, default=None)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    patient = relationship("Patient", back_populates="consultations")
    session = relationship("IntakeSession", back_populates="consultations")
