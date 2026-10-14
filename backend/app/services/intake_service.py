import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.core.config import settings
from backend.app.db.models import IntakeData, IntakeSession, Patient, QueueEntry
from backend.app.schemas.intake import (
    IntakeDraftData,
    IntakeSessionDetailResponse,
    IntakeSubmitRequest,
    IntakeSubmitResponse,
    IntakeSubmitSummary,
    SessionCreateResponse,
)
from backend.app.services.normalization_service import normalize_to_clinical_english


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_next_mrn(db: Session) -> str:
    count = db.query(func.count(Patient.id)).scalar() or 0
    return f"MRN-2026-{count + 1:04d}"


def create_session(db: Session) -> SessionCreateResponse:
    token = secrets.token_urlsafe(32)
    expires_at = utc_now() + timedelta(hours=settings.SESSION_EXPIRE_HOURS)

    session = IntakeSession(
        session_token=token,
        status="draft",
        expires_at=expires_at,
        draft_data=json.dumps(IntakeDraftData().model_dump()),
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return SessionCreateResponse(
        session_token=session.session_token,
        status=session.status,
        expires_at=session.expires_at,
        created_at=session.created_at,
    )


def get_session_by_token(db: Session, session_token: str) -> IntakeSession:
    session = (
        db.query(IntakeSession)
        .filter(IntakeSession.session_token == session_token)
        .first()
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Intake session not found or invalid token.",
        )

    # Check expiration
    if session.status == "draft":
        now = utc_now()
        # Ensure session.expires_at is timezone-aware for comparison
        expires_at = session.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if now > expires_at:
            session.status = "expired"
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Intake session has expired. Please start a new session.",
            )

    return session


def get_session_detail(db: Session, session_token: str) -> IntakeSessionDetailResponse:
    session = get_session_by_token(db, session_token)

    draft_obj = None
    if session.draft_data:
        try:
            draft_obj = IntakeDraftData(**json.loads(session.draft_data))
        except Exception:
            draft_obj = IntakeDraftData()

    return IntakeSessionDetailResponse(
        session_token=session.session_token,
        status=session.status,
        expires_at=session.expires_at,
        created_at=session.created_at,
        submitted_at=session.submitted_at,
        draft_data=draft_obj,
    )


def save_draft(
    db: Session, session_token: str, draft: IntakeDraftData
) -> IntakeSessionDetailResponse:
    session = get_session_by_token(db, session_token)
    if session.status == "submitted":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session has already been submitted and cannot be modified.",
        )

    session.draft_data = json.dumps(draft.model_dump())
    session.updated_at = utc_now()
    db.commit()
    db.refresh(session)

    return get_session_detail(db, session_token)


def submit_intake(
    db: Session, session_token: str, req: IntakeSubmitRequest
) -> IntakeSubmitResponse:
    session = get_session_by_token(db, session_token)

    # Duplicate submission protection
    if session.status == "submitted":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Intake has already been submitted for this session. Duplicate submissions are not permitted.",
        )

    now = utc_now()

    # Determine Patient record: look up existing patient if returning, or create new
    patient = None
    if req.patient_id:
        patient = db.query(Patient).filter(Patient.id == req.patient_id.strip()).first()
    if not patient and req.mrn:
        patient = db.query(Patient).filter(Patient.mrn == req.mrn.strip()).first()
    if not patient and req.name and req.phone:
        patient = (
            db.query(Patient)
            .filter(
                Patient.name == req.name.strip(),
                Patient.phone == req.phone.strip(),
            )
            .first()
        )

    if not patient:
        mrn = generate_next_mrn(db)
        patient = Patient(
            mrn=mrn,
            name=req.name.strip(),
            dob=req.dob.strip() if req.dob else None,
            phone=req.phone.strip() if req.phone else None,
            gender="Not specified",
            created_at=now,
            updated_at=now,
        )
        db.add(patient)
        db.flush()
    else:
        patient.updated_at = now
        if req.dob and not patient.dob:
            patient.dob = req.dob.strip()
        if req.phone and not patient.phone:
            patient.phone = req.phone.strip()
        db.flush()

    # Link session to patient
    session.patient_id = patient.id

    # Create IntakeData record
    chief_complaint = ", ".join(req.selected_complaints)
    all_symptoms = list(req.selected_complaints) + list(req.additional_symptoms)

    # Normalize patient free-text input to clean clinical English
    clean_medications = normalize_to_clinical_english(req.medications)
    clean_allergies = normalize_to_clinical_english(req.allergies)
    clean_notes = normalize_to_clinical_english(req.additional_notes)

    # Preserve raw adaptive answers and structured condition details in adaptive_responses JSON
    adaptive_payload = dict(req.adaptive_answers)
    if req.condition_details:
        adaptive_payload["__condition_details__"] = req.condition_details

    intake_data = IntakeData(
        session_id=session.id,
        patient_id=patient.id,
        chief_complaint=chief_complaint,
        symptoms=json.dumps(all_symptoms),
        duration=req.duration,
        severity=req.severity,
        adaptive_responses=json.dumps(adaptive_payload),
        conditions=json.dumps(req.conditions),
        medications=clean_medications or "None",
        allergies=clean_allergies or "None reported",
        previous_procedures="",
        additional_notes=clean_notes or "",
        provenance="patient-reported",
        created_at=now,
        submitted_at=now,
    )
    db.add(intake_data)

    # Calculate queue position: number of patients currently waiting + 1
    waiting_count = (
        db.query(func.count(QueueEntry.id))
        .filter(QueueEntry.status == "waiting")
        .scalar()
        or 0
    )
    new_position = waiting_count + 1
    estimated_wait = max(5, (new_position - 1) * 15 + 10)

    queue_entry = QueueEntry(
        patient_id=patient.id,
        session_id=session.id,
        position=new_position,
        wait_time_minutes=estimated_wait,
        status="waiting",
        created_at=now,
        updated_at=now,
    )
    db.add(queue_entry)

    # Mark session as submitted (raw patient inputs preserved in draft_data)
    session.status = "submitted"
    session.submitted_at = now
    session.draft_data = json.dumps(req.model_dump())
    session.updated_at = now

    db.commit()
    db.refresh(queue_entry)
    db.refresh(session)
    db.refresh(patient)

    summary = IntakeSubmitSummary(
        chief_complaint=chief_complaint,
        symptoms=all_symptoms,
        duration=req.duration,
        severity=req.severity,
        conditions=req.conditions,
        condition_details=req.condition_details or {},
        medications=clean_medications or "None",
        allergies=clean_allergies or "None reported",
        additional_notes=clean_notes or "",
        provenance="patient-reported",
    )

    return IntakeSubmitResponse(
        session_token=session.session_token,
        patient_id=patient.id,
        mrn=patient.mrn,
        patient_name=patient.name,
        queue_entry_id=queue_entry.id,
        queue_position=queue_entry.position,
        wait_time_minutes=queue_entry.wait_time_minutes,
        submitted_at=now,
        summary=summary,
    )
