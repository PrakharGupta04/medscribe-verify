from datetime import datetime, timezone
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.models import Consultation, Patient, QueueEntry, IntakeSession


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def start_or_get_consultation(
    db: Session,
    patient_id: str,
    session_id: Optional[str] = None,
    force_new: bool = False,
) -> Consultation:
    """
    Creates a new real consultation record or retrieves an existing active (in-progress)
    consultation for a patient from Module 1.
    If force_new is True, any existing in-progress consultation for this patient is marked completed
    and a fresh consultation visit is created.
    Also transitions the associated QueueEntry.status to 'in-consultation' while maintaining
    Consultation.status as 'in-progress'.
    """
    # 1. Verify patient exists
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with ID '{patient_id}' not found.",
        )

    # 2. If session_id not provided, try to find latest intake session for this patient (only if not forcing a new visit)
    if not session_id and not force_new:
        latest_session = (
            db.query(IntakeSession)
            .filter(IntakeSession.patient_id == patient_id)
            .order_by(IntakeSession.created_at.desc())
            .first()
        )
        if latest_session:
            session_id = latest_session.id

    # 3. If force_new, mark previous in-progress consultations as completed
    if force_new:
        prev_in_progress = (
            db.query(Consultation)
            .filter(
                Consultation.patient_id == patient_id,
                Consultation.status == "in-progress",
            )
            .all()
        )
        for prev in prev_in_progress:
            prev.status = "completed"
            prev.updated_at = utc_now()
        db.flush()
    else:
        # Check for existing in-progress consultation for this patient (idempotent retrieval)
        consultation_query = db.query(Consultation).filter(
            Consultation.patient_id == patient_id,
            Consultation.status == "in-progress",
        )
        if session_id:
            consultation_query = consultation_query.filter(
                (Consultation.session_id == session_id) | (Consultation.session_id.is_(None))
            )

        existing = consultation_query.order_by(Consultation.created_at.desc()).first()
        if existing:
            # Update queue entry status if needed
            _update_queue_status_in_consultation(db, patient_id=patient_id, session_id=session_id)
            db.commit()
            db.refresh(existing)
            if existing.session and existing.session.intake_data:
                existing.chief_complaint = existing.session.intake_data.chief_complaint
            return existing

    # 4. Create new consultation record
    consultation = Consultation(
        patient_id=patient_id,
        session_id=session_id,
        status="in-progress",
        transcript="",
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(consultation)

    # 5. Update queue entry status to "in-consultation"
    _update_queue_status_in_consultation(db, patient_id=patient_id, session_id=session_id)

    db.commit()
    db.refresh(consultation)
    if consultation.session and consultation.session.intake_data:
        consultation.chief_complaint = consultation.session.intake_data.chief_complaint
    return consultation


def _update_queue_status_in_consultation(
    db: Session,
    patient_id: str,
    session_id: Optional[str] = None,
) -> None:
    """Updates the associated QueueEntry status to 'in-consultation'."""
    queue_query = db.query(QueueEntry).filter(QueueEntry.patient_id == patient_id)
    if session_id:
        queue_entry = queue_query.filter(QueueEntry.session_id == session_id).first()
        if not queue_entry:
            queue_entry = queue_query.order_by(QueueEntry.created_at.desc()).first()
    else:
        queue_entry = queue_query.order_by(QueueEntry.created_at.desc()).first()

    if queue_entry and queue_entry.status == "waiting":
        queue_entry.status = "in-consultation"
        queue_entry.updated_at = utc_now()


def get_consultation_by_id(db: Session, consultation_id: str) -> Consultation:
    """Retrieves a consultation record by its ID."""
    consultation = db.query(Consultation).filter(Consultation.id == consultation_id).first()
    if not consultation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Consultation with ID '{consultation_id}' not found.",
        )
    if consultation.session and consultation.session.intake_data:
        consultation.chief_complaint = consultation.session.intake_data.chief_complaint
    return consultation


def complete_consultation(db: Session, consultation_id: str) -> Consultation:
    """Marks a consultation as completed and completes the associated queue entry."""
    consultation = get_consultation_by_id(db, consultation_id)
    consultation.status = "completed"
    consultation.updated_at = utc_now()
    if consultation.patient_id:
        queue_entry = (
            db.query(QueueEntry)
            .filter(QueueEntry.patient_id == consultation.patient_id)
            .order_by(QueueEntry.created_at.desc())
            .first()
        )
        if queue_entry and queue_entry.status == "in-consultation":
            queue_entry.status = "completed"
            queue_entry.updated_at = utc_now()
    db.commit()
    db.refresh(consultation)
    if consultation.session and consultation.session.intake_data:
        consultation.chief_complaint = consultation.session.intake_data.chief_complaint
    return consultation


def get_patient_consultations(db: Session, patient_id: str) -> List[Consultation]:
    """Retrieves all consultations for a given patient strictly isolated by patient_id."""
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with ID '{patient_id}' not found.",
        )
    consultations = (
        db.query(Consultation)
        .filter(Consultation.patient_id == patient_id)
        .order_by(Consultation.created_at.desc())
        .all()
    )
    for c in consultations:
        if c.session and c.session.intake_data:
            c.chief_complaint = c.session.intake_data.chief_complaint
    return consultations


def update_consultation_transcript(
    db: Session,
    consultation_id: str,
    transcript: str,
    allow_clear: bool = False,
) -> Consultation:
    """
    Updates and saves the consultation transcript text for an existing consultation record.
    Preserves the raw or edited transcript.
    Guards against accidental clearing: if an existing transcript is non-empty and the
    incoming transcript is blank/empty, it requires allow_clear=True to prevent accidental loss.
    """
    consultation = db.query(Consultation).filter(Consultation.id == consultation_id).first()
    if not consultation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Consultation with ID '{consultation_id}' not found.",
        )

    cleaned = transcript.strip() if transcript else ""
    if not cleaned and consultation.transcript and consultation.transcript.strip():
        if not allow_clear:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot overwrite existing transcript with an empty transcript without explicit clear confirmation.",
            )

    consultation.transcript = cleaned
    consultation.updated_at = utc_now()
    db.commit()
    db.refresh(consultation)
    return consultation


def extract_and_save_clinical_data(db: Session, consultation_id: str) -> Consultation:
    """
    Extracts structured clinical facts from the saved consultation transcript
    and persists the validated JSON into the Consultation.extracted_clinical_data column.
    Preserves Consultation.transcript completely unaltered.
    If extraction fails or LLM errors, existing extraction and transcript are left intact.
    """
    consultation = db.query(Consultation).filter(Consultation.id == consultation_id).first()
    if not consultation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Consultation with ID '{consultation_id}' not found.",
        )

    if not consultation.transcript or not consultation.transcript.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Consultation transcript is empty. Please enter or record a transcript before extracting clinical information.",
        )

    from backend.app.services.extraction_service import extract_clinical_facts_groq

    try:
        extraction = extract_clinical_facts_groq(consultation.transcript)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve)) from ve
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Clinical information extraction failed: {str(exc)}",
        ) from exc

    consultation.extracted_clinical_data = extraction.model_dump_json()
    consultation.updated_at = utc_now()
    db.commit()
    db.refresh(consultation)
    return consultation


def generate_and_save_soap_draft(db: Session, consultation_id: str) -> Consultation:
    """
    Generates an AI-assisted SOAP draft note from the consultation transcript
    and the existing extracted clinical facts, saving it to Consultation.soap_draft.

    Strict Requirements:
    1. Rejects with 400 if the transcript is empty.
    2. Rejects with 400 if Phase 2.3 clinical extraction is missing (explicit evidence chain).
    3. Preserves all existing consultation data if generation fails.
    4. Marks provenance as unverified draft.
    """
    consultation = db.query(Consultation).filter(Consultation.id == consultation_id).first()
    if not consultation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Consultation with ID '{consultation_id}' not found.",
        )

    if not consultation.transcript or not consultation.transcript.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Consultation transcript is empty. Please enter or record a transcript before generating a SOAP draft.",
        )

    if not consultation.extracted_clinical_data or not consultation.extracted_clinical_data.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Clinical information must be extracted before generating a SOAP draft. Please extract clinical information first.",
        )

    from backend.app.schemas.consultation import ClinicalExtraction
    from backend.app.services.soap_service import generate_soap_draft_groq

    try:
        clinical_data = ClinicalExtraction.model_validate_json(consultation.extracted_clinical_data)
    except Exception as parse_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse existing clinical extraction data: {str(parse_err)}",
        ) from parse_err

    try:
        soap_draft = generate_soap_draft_groq(
            transcript=consultation.transcript,
            clinical_data=clinical_data,
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve)) from ve
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"SOAP draft generation failed: {str(exc)}",
        ) from exc

    consultation.soap_draft = soap_draft.model_dump_json()
    consultation.updated_at = utc_now()
    db.commit()
    db.refresh(consultation)
    return consultation


def update_soap_draft(
    db: Session,
    consultation_id: str,
    subjective: str,
    objective: str,
    assessment: str,
    plan: str,
) -> Consultation:
    """
    Updates and saves edited SOAP draft sections for an existing consultation record.
    Preserves raw transcript and extracted clinical facts.
    """
    consultation = db.query(Consultation).filter(Consultation.id == consultation_id).first()
    if not consultation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Consultation with ID '{consultation_id}' not found.",
        )

    from backend.app.schemas.consultation import SoapDraft

    now = utc_now()
    # If a draft already exists, preserve its original generated_at
    generated_at = now
    if consultation.soap_draft:
        try:
            existing_draft = SoapDraft.model_validate_json(consultation.soap_draft)
            if existing_draft.generated_at:
                generated_at = existing_draft.generated_at
        except Exception:
            pass

    updated_draft = SoapDraft(
        subjective=subjective.strip() if subjective else "Not documented.",
        objective=objective.strip() if objective else "Not documented.",
        assessment=assessment.strip() if assessment else "Not explicitly documented.",
        plan=plan.strip() if plan else "Not documented.",
        provenance="ai-generated-draft-unverified",
        generated_at=generated_at,
        updated_at=now,
    )

    consultation.soap_draft = updated_draft.model_dump_json()
    consultation.updated_at = now
    db.commit()
    db.refresh(consultation)
    return consultation


def verify_consultation(db: Session, consultation_id: str) -> Consultation:
    """
    Runs the Verification Agent (Agent 3) to verify claims in the SOAP draft
    against the raw consultation transcript and structured clinical facts.
    Persists the claim-level verification results in Consultation.verification_results.
    """
    consultation = db.query(Consultation).filter(Consultation.id == consultation_id).first()
    if not consultation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Consultation with ID '{consultation_id}' not found.",
        )

    if not consultation.transcript or not consultation.transcript.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Consultation transcript is empty. Cannot verify claims without source transcript evidence.",
        )

    if not consultation.soap_draft:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No SOAP draft found for this consultation. Please generate or enter a SOAP draft before running verification.",
        )

    from backend.app.schemas.consultation import ClinicalExtraction, SoapDraft
    from backend.app.services.verification_service import verify_soap_claims

    # Load extraction or default to empty
    clinical_data = ClinicalExtraction()
    if consultation.extracted_clinical_data:
        try:
            clinical_data = ClinicalExtraction.model_validate_json(consultation.extracted_clinical_data)
        except Exception:
            pass

    soap_draft = SoapDraft.model_validate_json(consultation.soap_draft)
    verif_results = verify_soap_claims(
        transcript=consultation.transcript,
        clinical_data=clinical_data,
        soap_draft=soap_draft,
    )

    consultation.verification_results = verif_results.model_dump_json()
    consultation.updated_at = utc_now()
    db.commit()
    db.refresh(consultation)
    return consultation


def compare_consultation(db: Session, consultation_id: str) -> Consultation:
    """
    Runs the Comparison / Conflict Intelligence Agent (Agent 4)
    to compare Module 1 Pre-Consult Intake data with Module 2 Consultation findings.
    Persists the comparison findings in Consultation.comparison_results.
    """
    consultation = db.query(Consultation).filter(Consultation.id == consultation_id).first()
    if not consultation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Consultation with ID '{consultation_id}' not found.",
        )

    from backend.app.db.models import IntakeData
    from backend.app.services.comparison_service import compare_intake_and_consultation

    intake_data = None
    if consultation.session_id:
        intake_data = db.query(IntakeData).filter(IntakeData.session_id == consultation.session_id).first()
    if not intake_data and consultation.patient_id:
        intake_data = (
            db.query(IntakeData)
            .filter(IntakeData.patient_id == consultation.patient_id)
            .order_by(IntakeData.created_at.desc())
            .first()
        )

    comp_results = compare_intake_and_consultation(
        intake_data=intake_data,
        consultation=consultation,
    )

    consultation.comparison_results = comp_results.model_dump_json()
    consultation.updated_at = utc_now()
    db.commit()
    db.refresh(consultation)
    return consultation


def resolve_discrepancy(
    db: Session,
    consultation_id: str,
    item_id: str,
    resolution: str,
) -> Consultation:
    """
    Updates the resolution status and doctor note for a specific discrepancy item.
    """
    consultation = db.query(Consultation).filter(Consultation.id == consultation_id).first()
    if not consultation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Consultation with ID '{consultation_id}' not found.",
        )

    if not consultation.comparison_results:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No comparison results exist for this consultation.",
        )

    from backend.app.schemas.consultation import ComparisonResults

    try:
        results = ComparisonResults.model_validate_json(consultation.comparison_results)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse comparison results: {str(exc)}",
        ) from exc

    item_found = False
    for item in results.items:
        if item.id == item_id:
            item.resolution = resolution.strip()
            item.status = "resolved"
            item_found = True
            break

    if not item_found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Discrepancy item '{item_id}' not found in comparison results.",
        )

    consultation.comparison_results = results.model_dump_json()
    consultation.updated_at = utc_now()
    db.commit()
    db.refresh(consultation)
    return consultation


def finalize_consultation(
    db: Session,
    consultation_id: str,
    subjective: Optional[str] = None,
    objective: Optional[str] = None,
    assessment: Optional[str] = None,
    plan: Optional[str] = None,
    doctor_notes: Optional[str] = None,
    doctor_name: Optional[str] = "Dr. J. Patel",
) -> Consultation:
    """
    Finalizes a consultation with doctor review and approval.
    Creates a non-destructible FinalMedicalRecord clearly distinguishing:
    AI Draft != Verified Draft != Doctor-Approved Final Record.
    Transitions Consultation.status to 'finalized' and QueueEntry.status to 'completed'.
    """
    consultation = db.query(Consultation).filter(Consultation.id == consultation_id).first()
    if not consultation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Consultation with ID '{consultation_id}' not found.",
        )

    patient = consultation.patient
    patient_name = patient.name if patient else "Patient"
    patient_mrn = patient.mrn if patient else f"MRN-{consultation.patient_id[:8]}"

    # Guard against accidental repeated approval: preserve existing doctor-approved final record
    if consultation.final_record and consultation.status in ("completed", "finalized"):
        return consultation

    from backend.app.schemas.consultation import FinalMedicalRecord, SoapDraft

    # Resolve final SOAP content (passed explicitly or fallback to existing draft)
    existing_soap = None
    if consultation.soap_draft:
        try:
            existing_soap = SoapDraft.model_validate_json(consultation.soap_draft)
        except Exception:
            pass

    final_sub = (subjective if subjective is not None else (existing_soap.subjective if existing_soap else "Not documented.")).strip()
    final_obj = (objective if objective is not None else (existing_soap.objective if existing_soap else "Not documented.")).strip()
    final_ass = (assessment if assessment is not None else (existing_soap.assessment if existing_soap else "Not explicitly documented.")).strip()
    final_pln = (plan if plan is not None else (existing_soap.plan if existing_soap else "Not documented.")).strip()

    now = utc_now()
    final_soap_obj = SoapDraft(
        subjective=final_sub or "Not documented.",
        objective=final_obj or "Not documented.",
        assessment=final_ass or "Not explicitly documented.",
        plan=final_pln or "Not documented.",
        provenance="doctor-approved-final",
        generated_at=existing_soap.generated_at if existing_soap else now,
        updated_at=now,
    )

    final_record = FinalMedicalRecord(
        patient_id=consultation.patient_id,
        patient_name=patient_name,
        mrn=patient_mrn,
        consultation_id=consultation.id,
        session_id=consultation.session_id,
        visit_date=now.strftime("%d %b %Y"),
        soap=final_soap_obj,
        doctor_notes=doctor_notes.strip() if doctor_notes else None,
        doctor_name=(doctor_name or "Dr. J. Patel").strip(),
        status="doctor-approved",
        approved_at=now,
        provenance="doctor-approved-final-record",
    )

    # Persist final approval state
    consultation.final_record = final_record.model_dump_json()
    consultation.finalized_at = now
    consultation.status = "completed"  # Compatible with completed status
    consultation.updated_at = now

    # Also complete queue entry
    if consultation.patient_id:
        queue_entry = (
            db.query(QueueEntry)
            .filter(QueueEntry.patient_id == consultation.patient_id)
            .order_by(QueueEntry.created_at.desc())
            .first()
        )
        if queue_entry and queue_entry.status in {"waiting", "in-consultation"}:
            queue_entry.status = "completed"
            queue_entry.updated_at = now

    db.commit()
    db.refresh(consultation)
    return consultation

