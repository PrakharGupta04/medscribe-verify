import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.models import IntakeData, IntakeSession, Patient, QueueEntry
from backend.app.schemas.doctor import DoctorIntakeSummaryResponse
from backend.app.schemas.queue import QueueItemResponse, QueueListResponse
from backend.app.services.summary_service import build_pre_consult_summary


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_queue_list(db: Session) -> QueueListResponse:
    # Query active/non-cancelled entries
    entries = (
        db.query(QueueEntry)
        .join(Patient, QueueEntry.patient_id == Patient.id)
        .filter(QueueEntry.status != "cancelled")
        .order_by(QueueEntry.created_at.asc())
        .all()
    )

    items: List[QueueItemResponse] = []

    # Separate by status to maintain proper consultation flow order
    in_consult_entries = [e for e in entries if e.status == "in-consultation"]
    waiting_entries = [e for e in entries if e.status == "waiting"]
    completed_entries = [e for e in entries if e.status == "completed"]

    waiting_count = len(waiting_entries)
    in_consult_count = len(in_consult_entries)
    completed_count = len(completed_entries)

    # 1. In-consultation entries
    for entry in in_consult_entries:
        patient = entry.patient
        intake = (
            db.query(IntakeData)
            .filter(IntakeData.session_id == entry.session_id)
            .first()
        )
        complaint = intake.chief_complaint if intake else "General Consultation"
        items.append(
            QueueItemResponse(
                id=entry.id,
                position=None,
                patient_id=patient.id,
                patient_name=patient.name,
                mrn=patient.mrn,
                wait_time="In Consultation",
                complaint=complaint,
                intake_status="complete" if intake else "pending",
                status=entry.status,
                session_id=entry.session_id,
                submitted_at=entry.created_at,
            )
        )

    # 2. Waiting entries: deterministic 1-based ordering and wait time derivation
    for idx, entry in enumerate(waiting_entries):
        pos = idx + 1
        est_wait = max(5, (pos - 1) * 15 + 10)
        entry.position = pos
        entry.wait_time_minutes = est_wait

        patient = entry.patient
        intake = (
            db.query(IntakeData)
            .filter(IntakeData.session_id == entry.session_id)
            .first()
        )
        complaint = intake.chief_complaint if intake else "General Consultation"
        items.append(
            QueueItemResponse(
                id=entry.id,
                position=pos,
                patient_id=patient.id,
                patient_name=patient.name,
                mrn=patient.mrn,
                wait_time=f"~{est_wait} min",
                complaint=complaint,
                intake_status="complete" if intake else "pending",
                status=entry.status,
                session_id=entry.session_id,
                submitted_at=entry.created_at,
            )
        )

    # 3. Completed entries
    for entry in completed_entries:
        patient = entry.patient
        intake = (
            db.query(IntakeData)
            .filter(IntakeData.session_id == entry.session_id)
            .first()
        )
        complaint = intake.chief_complaint if intake else "General Consultation"
        items.append(
            QueueItemResponse(
                id=entry.id,
                position=None,
                patient_id=patient.id,
                patient_name=patient.name,
                mrn=patient.mrn,
                wait_time="—",
                complaint=complaint,
                intake_status="complete" if intake else "pending",
                status=entry.status,
                session_id=entry.session_id,
                submitted_at=entry.created_at,
            )
        )

    db.commit()

    return QueueListResponse(
        items=items,
        total_waiting=waiting_count,
        total_in_consultation=in_consult_count,
        total_completed=completed_count,
    )


def remove_from_queue(db: Session, queue_entry_id: str) -> dict:
    """
    Safely removes/cancels a patient from today's active queue.
    Guarantees patient record, MRN, intake data, and history remain intact.
    Only allows removing entries in 'waiting' status.
    """
    entry = db.query(QueueEntry).filter(QueueEntry.id == queue_entry_id).first()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Queue entry not found."
        )

    if entry.status != "waiting":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot remove entry with status '{entry.status}'. Only waiting patients can be removed from the queue."
        )

    entry.status = "cancelled"
    entry.position = 0
    entry.updated_at = utc_now()
    db.commit()

    return {
        "message": "Patient successfully removed from today's active queue. Patient and clinical records preserved.",
        "status": "cancelled",
        "queue_entry_id": queue_entry_id,
    }



def get_doctor_intake(db: Session, identifier: str) -> DoctorIntakeSummaryResponse:
    """Look up doctor intake summary by patient_id or session_id or queue_entry_id."""
    queue_entry = None
    patient = None
    intake = None
    session = None

    # Try matching QueueEntry ID
    queue_entry = db.query(QueueEntry).filter(QueueEntry.id == identifier).first()
    if queue_entry:
        patient = queue_entry.patient
        session = queue_entry.session
        intake = (
            db.query(IntakeData)
            .filter(IntakeData.session_id == queue_entry.session_id)
            .first()
        )

    # Try matching Patient ID
    if not patient:
        patient = db.query(Patient).filter(Patient.id == identifier).first()
        if patient:
            intake = (
                db.query(IntakeData)
                .filter(IntakeData.patient_id == patient.id)
                .order_by(IntakeData.created_at.desc())
                .first()
            )
            if intake:
                session = intake.session
                queue_entry = session.queue_entry if session else None

    # Try matching Session ID
    if not intake:
        session = (
            db.query(IntakeSession)
            .filter(
                (IntakeSession.id == identifier)
                | (IntakeSession.session_token == identifier)
            )
            .first()
        )
        if session:
            patient = session.patient
            intake = session.intake_data
            queue_entry = session.queue_entry

    if not patient or not intake:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Clinical intake summary not found for identifier: {identifier}",
        )

    return build_pre_consult_summary(
        patient=patient,
        intake=intake,
        session_id=session.id if session else "",
        queue_id=queue_entry.id if queue_entry else None,
        queue_status=queue_entry.status if queue_entry else None,
    )


def seed_demo_queue(db: Session) -> dict:
    """Explicitly seeds demo patients for development and isolated testing."""
    existing = db.query(Patient).filter(Patient.mrn == "MRN-2026-0091").first()
    if existing:
        return {"message": "Demo data already seeded.", "status": "exists"}

    now = utc_now()

    # 1. Sarah M.
    p1 = Patient(
        id="sarah-demo-id",
        mrn="MRN-2026-0091",
        name="Sarah M.",
        dob="14 March 1998",
        phone="+44 7700 900142",
        gender="Female",
        created_at=now - timedelta(minutes=20),
        updated_at=now,
    )
    db.add(p1)
    db.flush()

    s1 = IntakeSession(
        id="session-sarah-demo",
        session_token="demo-token-sarah",
        patient_id=p1.id,
        status="submitted",
        expires_at=now + timedelta(hours=24),
        submitted_at=now - timedelta(minutes=18),
        created_at=now - timedelta(minutes=25),
    )
    db.add(s1)
    db.flush()

    d1 = IntakeData(
        id="intake-sarah-demo",
        session_id=s1.id,
        patient_id=p1.id,
        chief_complaint="Fever and sore throat",
        symptoms=json.dumps(["Fever", "Sore Throat", "Difficulty Swallowing", "Runny Nose", "Chills"]),
        duration="3–5 days",
        severity=6,
        adaptive_responses=json.dumps({
            "Fever-0": "Gradually",
            "Fever-1": "Yes, above 38°C",
            "Sore Throat-0": "Yes, very painful",
            "Sore Throat-1": "No",
        }),
        conditions=json.dumps(["None of the above"]),
        medications="None",
        allergies="Penicillin — rash",
        additional_notes="Sore throat is getting worse. Had a similar episode last year which resolved on its own after about a week.",
        provenance="patient-reported",
        created_at=now - timedelta(minutes=18),
        submitted_at=now - timedelta(minutes=18),
    )
    db.add(d1)

    q1 = QueueEntry(
        id="queue-sarah-demo",
        patient_id=p1.id,
        session_id=s1.id,
        position=1,
        wait_time_minutes=18,
        status="waiting",
        created_at=now - timedelta(minutes=18),
        updated_at=now,
    )
    db.add(q1)

    # 2. James K.
    p2 = Patient(
        id="james-demo-id",
        mrn="MRN-2026-0092",
        name="James K.",
        dob="05 August 1985",
        phone="+44 7700 900143",
        gender="Male",
        created_at=now - timedelta(minutes=10),
        updated_at=now,
    )
    db.add(p2)
    db.flush()

    s2 = IntakeSession(
        id="session-james-demo",
        session_token="demo-token-james",
        patient_id=p2.id,
        status="submitted",
        expires_at=now + timedelta(hours=24),
        submitted_at=now - timedelta(minutes=6),
        created_at=now - timedelta(minutes=12),
    )
    db.add(s2)
    db.flush()

    d2 = IntakeData(
        id="intake-james-demo",
        session_id=s2.id,
        patient_id=p2.id,
        chief_complaint="Knee pain",
        symptoms=json.dumps(["Knee pain", "Swelling", "Difficulty walking"]),
        duration="1–2 days",
        severity=5,
        adaptive_responses=json.dumps({"Stomach Pain-0": "Upper abdomen"}),
        conditions=json.dumps(["Asthma"]),
        medications="Salbutamol inhaler PRN",
        allergies="None known",
        additional_notes="Twisted knee while jogging yesterday evening.",
        provenance="patient-reported",
        created_at=now - timedelta(minutes=6),
        submitted_at=now - timedelta(minutes=6),
    )
    db.add(d2)

    q2 = QueueEntry(
        id="queue-james-demo",
        patient_id=p2.id,
        session_id=s2.id,
        position=2,
        wait_time_minutes=6,
        status="waiting",
        created_at=now - timedelta(minutes=6),
        updated_at=now,
    )
    db.add(q2)

    db.commit()
    return {"message": "Demo data successfully seeded.", "status": "seeded"}
