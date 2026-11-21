from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.db.session import get_db

router = APIRouter(tags=["Health"])


@router.get("/health")
def get_health(db: Session = Depends(get_db)):
    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    groq_configured = bool(settings.GROQ_API_KEY)

    if db_status == "error":
        overall_status = "unhealthy"
    elif not groq_configured:
        overall_status = "degraded"
    else:
        overall_status = "healthy"

    return {
        "status": overall_status,
        "service": "Medscribe-Verify API",
        "version": "1.0.0",
        "module": "Medscribe-Verify — Modules 1-3",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "db": db_status,
        "groq_key_configured": groq_configured,
    }
