import base64
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.schemas.intake import (
    IntakeDraftData,
    IntakeSessionDetailResponse,
    IntakeSubmitRequest,
    IntakeSubmitResponse,
    SessionCreateResponse,
    TranscribeAudioRequest,
    TranscribeAudioResponse,
)
from backend.app.services import intake_service
from backend.app.services.normalization_service import transcribe_audio_groq

router = APIRouter(prefix="/intake", tags=["Patient Intake"])


@router.post("/sessions", response_model=SessionCreateResponse, status_code=201)
def create_new_intake_session(db: Session = Depends(get_db)):
    """Creates a new secure temporary intake session for patient check-in."""
    return intake_service.create_session(db)


@router.get("/sessions/{session_token}", response_model=IntakeSessionDetailResponse)
def get_intake_session(session_token: str, db: Session = Depends(get_db)):
    """Retrieves session details and any saved draft intake responses."""
    return intake_service.get_session_detail(db, session_token)


@router.put("/sessions/{session_token}", response_model=IntakeSessionDetailResponse)
def save_intake_draft(
    session_token: str, draft: IntakeDraftData, db: Session = Depends(get_db)
):
    """Saves or updates draft intake responses at form checkpoints."""
    return intake_service.save_draft(db, session_token, draft)


@router.post("/sessions/{session_token}/submit", response_model=IntakeSubmitResponse)
def submit_completed_intake(
    session_token: str, req: IntakeSubmitRequest, db: Session = Depends(get_db)
):
    """Submits completed intake, creates/updates patient record, and assigns queue entry."""
    return intake_service.submit_intake(db, session_token, req)


@router.post("/transcribe", response_model=TranscribeAudioResponse)
def transcribe_patient_voice(req: TranscribeAudioRequest):
    """
    Transcribes patient voice speech (English, Hindi, Hinglish) for free-text fields.
    Returns the transcription without submitting the form, allowing the patient to review and edit.
    """
    try:
        raw_b64 = req.audio_base64
        if "," in raw_b64:
            raw_b64 = raw_b64.split(",", 1)[1]
        audio_bytes = base64.b64decode(raw_b64)
        if not audio_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No audio content received.",
            )
        print(f"[TRANSCRIBE_DEBUG] Received audio: {len(audio_bytes)} bytes, filename={req.filename}, lang={req.language}", flush=True)
        text = transcribe_audio_groq(
            audio_bytes=audio_bytes,
            filename=req.filename or "audio.webm",
            language=req.language,
        )
        print(f"[TRANSCRIBE_DEBUG] Result text: '{text}'", flush=True)
        return TranscribeAudioResponse(text=text)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transcription service error: {str(exc)}",
        )
