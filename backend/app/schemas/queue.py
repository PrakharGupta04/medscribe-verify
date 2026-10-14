from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class QueueItemResponse(BaseModel):
    id: str
    position: Optional[int]
    patient_id: str
    patient_name: str
    mrn: str
    wait_time: str
    complaint: str
    intake_status: str  # "complete" | "pending"
    status: str  # "waiting" | "in-consultation" | "completed"
    session_id: str
    submitted_at: Optional[datetime] = None


class QueueListResponse(BaseModel):
    items: List[QueueItemResponse]
    total_waiting: int
    total_in_consultation: int
    total_completed: int
