from fastapi import APIRouter, HTTPException, status

router = APIRouter(tags=["Future Modules"])


@router.post("/consultation/transcript")
def upload_consultation_transcript():
    """Extension placeholder for Module 2: Consultation Intelligence & Verification."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Module 2 (Consultation Intelligence & Verification) will implement transcript ingestion and claim verification.",
    )


@router.get("/verification/claims/{consultation_id}")
def get_verification_claims(consultation_id: str):
    """Extension placeholder for Module 2: Claim-level verification."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Module 2 will implement claim extraction and verification results.",
    )


@router.post("/records/{visit_id}/approve")
def approve_visit_record(visit_id: str):
    """Extension placeholder for Module 3: Verified Longitudinal Record."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Module 3 will implement doctor approval workflow and longitudinal record persistence.",
    )
