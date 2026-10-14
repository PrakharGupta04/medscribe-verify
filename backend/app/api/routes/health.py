from datetime import datetime, timezone
from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health")
def get_health():
    return {
        "status": "healthy",
        "service": "Medscribe-Verify API",
        "version": "1.0.0",
        "module": "Module 1 - Patient Intake & Pre-Consultation",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
