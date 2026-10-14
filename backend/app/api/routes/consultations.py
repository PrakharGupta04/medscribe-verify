from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.schemas.consultation import (
    ConsultationCreateRequest,
    ConsultationResponse,
    ConsultationTranscriptUpdateRequest,
    SoapDraftUpdateRequest,
    FinalizeConsultationRequest,
    ResolveDiscrepancyRequest,
)
from backend.app.services import consultation_service

router = APIRouter(prefix="/consultations", tags=["Consultations"])


@router.post("", response_model=ConsultationResponse, status_code=status.HTTP_201_CREATED)
def start_consultation(
    payload: ConsultationCreateRequest,
    db: Session = Depends(get_db),
):
    """
    Creates or retrieves an active in-progress consultation for a Module 1 patient,
    and updates the queue entry status to 'in-consultation'.
    """
    return consultation_service.start_or_get_consultation(
        db=db,
        patient_id=payload.patient_id,
        session_id=payload.session_id,
        force_new=bool(payload.force_new),
    )


@router.post("/{consultation_id}/complete", response_model=ConsultationResponse)
def complete_consultation(
    consultation_id: str,
    db: Session = Depends(get_db),
):
    """Marks a consultation visit as completed."""
    return consultation_service.complete_consultation(
        db=db,
        consultation_id=consultation_id,
    )


@router.get("/{consultation_id}", response_model=ConsultationResponse)
def get_consultation(
    consultation_id: str,
    db: Session = Depends(get_db),
):
    """Retrieves a consultation record by its ID."""
    return consultation_service.get_consultation_by_id(
        db=db,
        consultation_id=consultation_id,
    )


@router.get("/patient/{patient_id}", response_model=List[ConsultationResponse])
def get_patient_consultations(
    patient_id: str,
    db: Session = Depends(get_db),
):
    """Retrieves all consultations for a given patient."""
    return consultation_service.get_patient_consultations(
        db=db,
        patient_id=patient_id,
    )


@router.put("/{consultation_id}/transcript", response_model=ConsultationResponse)
def update_consultation_transcript(
    consultation_id: str,
    payload: ConsultationTranscriptUpdateRequest,
    db: Session = Depends(get_db),
):
    """
    Saves and updates the consultation transcript text for an existing consultation.
    Preserves raw or edited text in the database.
    """
    return consultation_service.update_consultation_transcript(
        db=db,
        consultation_id=consultation_id,
        transcript=payload.transcript,
        allow_clear=payload.allow_clear or False,
    )


@router.post("/{consultation_id}/extract", response_model=ConsultationResponse)
def extract_clinical_information(
    consultation_id: str,
    db: Session = Depends(get_db),
):
    """
    Extracts structured clinical facts from the saved consultation transcript using Groq LLM
    and stores the validated extraction in the consultation record.
    """
    return consultation_service.extract_and_save_clinical_data(
        db=db,
        consultation_id=consultation_id,
    )


@router.post("/{consultation_id}/soap-draft", response_model=ConsultationResponse)
def generate_soap_draft(
    consultation_id: str,
    db: Session = Depends(get_db),
):
    """
    Generates an AI-assisted SOAP draft note from the saved consultation transcript
    and the validated clinical extraction data, and stores it in the consultation record.
    Requires that clinical extraction has already been run.
    """
    return consultation_service.generate_and_save_soap_draft(
        db=db,
        consultation_id=consultation_id,
    )


@router.put("/{consultation_id}/soap-draft", response_model=ConsultationResponse)
def update_soap_draft(
    consultation_id: str,
    payload: SoapDraftUpdateRequest,
    db: Session = Depends(get_db),
):
    """
    Updates and saves the editable SOAP draft note sections for an existing consultation.
    """
    return consultation_service.update_soap_draft(
        db=db,
        consultation_id=consultation_id,
        subjective=payload.subjective,
        objective=payload.objective,
        assessment=payload.assessment,
        plan=payload.plan,
    )


@router.post("/{consultation_id}/verify", response_model=ConsultationResponse)
def verify_consultation(
    consultation_id: str,
    db: Session = Depends(get_db),
):
    """
    Runs the Verification Agent (Agent 3) to verify claims in the SOAP draft against
    the raw consultation transcript and structured clinical facts.
    """
    return consultation_service.verify_consultation(
        db=db,
        consultation_id=consultation_id,
    )


@router.post("/{consultation_id}/compare", response_model=ConsultationResponse)
def compare_consultation(
    consultation_id: str,
    db: Session = Depends(get_db),
):
    """
    Runs the Comparison / Conflict Intelligence Agent (Agent 4) to detect confirmed,
    new, unmentioned, or conflicting findings between Module 1 intake and Module 2 consultation.
    """
    return consultation_service.compare_consultation(
        db=db,
        consultation_id=consultation_id,
    )


@router.put("/{consultation_id}/discrepancies/{item_id}/resolve", response_model=ConsultationResponse)
def resolve_discrepancy(
    consultation_id: str,
    item_id: str,
    payload: ResolveDiscrepancyRequest,
    db: Session = Depends(get_db),
):
    """
    Records doctor resolution for a specific Module 1 vs Module 2 discrepancy.
    """
    return consultation_service.resolve_discrepancy(
        db=db,
        consultation_id=consultation_id,
        item_id=item_id,
        resolution=payload.resolution,
    )


@router.post("/{consultation_id}/finalize", response_model=ConsultationResponse)
def finalize_consultation(
    consultation_id: str,
    payload: FinalizeConsultationRequest,
    db: Session = Depends(get_db),
):
    """
    Finalizes the consultation record with doctor approval.
    Persists the final medical record and marks consultation status as finalized.
    """
    return consultation_service.finalize_consultation(
        db=db,
        consultation_id=consultation_id,
        subjective=payload.subjective,
        objective=payload.objective,
        assessment=payload.assessment,
        plan=payload.plan,
        doctor_notes=payload.doctor_notes,
        doctor_name=payload.doctor_name,
    )

