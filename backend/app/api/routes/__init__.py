from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.intake import router as intake_router
from backend.app.api.routes.queue import router as queue_router
from backend.app.api.routes.doctor import router as doctor_router
from backend.app.api.routes.demo import router as demo_router
from backend.app.api.routes.stubs import router as stubs_router

__all__ = [
    "health_router",
    "intake_router",
    "queue_router",
    "doctor_router",
    "demo_router",
    "stubs_router",
]
