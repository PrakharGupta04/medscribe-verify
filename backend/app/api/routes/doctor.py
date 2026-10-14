from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.schemas.doctor import DoctorIntakeSummaryResponse
from backend.app.services import queue_service

router = APIRouter(prefix="/doctor", tags=["Doctor Clinical Workspace"])


@router.get("/intake/{identifier}", response_model=DoctorIntakeSummaryResponse)
def get_patient_intake_summary(identifier: str, db: Session = Depends(get_db)):
    """
    Retrieves the deterministic pre-consultation summary for a patient.
    Identifier can be a queue_entry_id, patient_id, or session_id.
    """
    return queue_service.get_doctor_intake(db, identifier)
