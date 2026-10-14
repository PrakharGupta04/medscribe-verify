from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.services import queue_service

router = APIRouter(prefix="/demo", tags=["Development Demo"])


@router.post("/seed")
def seed_demo_data(db: Session = Depends(get_db)):
    """
    Explicitly populates isolated demo patients for development and testing.
    Never run silently or automatically.
    """
    return queue_service.seed_demo_queue(db)
