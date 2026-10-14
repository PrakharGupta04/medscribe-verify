from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.intake import router as intake_router
from backend.app.api.routes.queue import router as queue_router
from backend.app.api.routes.doctor import router as doctor_router
from backend.app.api.routes.demo import router as demo_router
from backend.app.api.routes.consultations import router as consultations_router
from backend.app.api.routes.stubs import router as stubs_router
from backend.app.core.config import settings
from backend.app.db.base import Base
from backend.app.db.session import engine


# Initialize SQLite database tables
Base.metadata.create_all(bind=engine)


def ensure_schema_migrations():
    """Ensures additive columns exist on existing SQLite databases without requiring full migrations."""
    from sqlalchemy import text
    try:
        with engine.begin() as conn:
            result = conn.execute(text("PRAGMA table_info(consultations)")).fetchall()
            col_names = [row[1] for row in result]
            if col_names and "extracted_clinical_data" not in col_names:
                conn.execute(text("ALTER TABLE consultations ADD COLUMN extracted_clinical_data TEXT"))
            if col_names and "soap_draft" not in col_names:
                conn.execute(text("ALTER TABLE consultations ADD COLUMN soap_draft TEXT"))
            if col_names and "verification_results" not in col_names:
                conn.execute(text("ALTER TABLE consultations ADD COLUMN verification_results TEXT"))
            if col_names and "comparison_results" not in col_names:
                conn.execute(text("ALTER TABLE consultations ADD COLUMN comparison_results TEXT"))
            if col_names and "final_record" not in col_names:
                conn.execute(text("ALTER TABLE consultations ADD COLUMN final_record TEXT"))
            if col_names and "finalized_at" not in col_names:
                conn.execute(text("ALTER TABLE consultations ADD COLUMN finalized_at TIMESTAMP"))
    except Exception:
        pass


ensure_schema_migrations()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_schema_migrations()
    yield



app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description=(
        "Medscribe-Verify: A source-aware, conflict-aware clinical documentation workflow API. "
        "Module 1: Patient Intake & Pre-Consultation."
    ),
    lifespan=lifespan,
)

# CORS middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes under /api
app.include_router(health_router, prefix=settings.API_V1_STR)
app.include_router(intake_router, prefix=settings.API_V1_STR)
app.include_router(queue_router, prefix=settings.API_V1_STR)
app.include_router(doctor_router, prefix=settings.API_V1_STR)
app.include_router(demo_router, prefix=settings.API_V1_STR)
app.include_router(consultations_router, prefix=settings.API_V1_STR)
app.include_router(stubs_router, prefix=settings.API_V1_STR)


@app.get("/")
def root():
    return {
        "message": "Welcome to Medscribe-Verify API",
        "health": "/api/health",
        "docs": "/docs",
    }
