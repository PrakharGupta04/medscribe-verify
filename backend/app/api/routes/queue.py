from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.schemas.queue import QueueListResponse
from backend.app.services import queue_service

router = APIRouter(prefix="/queue", tags=["Clinical Queue"])


@router.get("", response_model=QueueListResponse)
def get_clinical_queue(db: Session = Depends(get_db)):
    """Retrieves the active patient consultation queue for doctors."""
    return queue_service.get_queue_list(db)


@router.delete("/{queue_entry_id}")
def remove_patient_from_queue(queue_entry_id: str, db: Session = Depends(get_db)):
    """Removes/cancels a waiting patient from today's active queue while preserving all patient and clinical data."""
    return queue_service.remove_from_queue(db, queue_entry_id)


@router.post("/{queue_entry_id}/remove")
def remove_patient_from_queue_post(queue_entry_id: str, db: Session = Depends(get_db)):
    """Alternative POST endpoint to remove/cancel a waiting patient from today's active queue."""
    return queue_service.remove_from_queue(db, queue_entry_id)

