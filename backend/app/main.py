from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.bookings import router as bookings_router
from app.api.dashboard import router as dashboard_router
from app.api.health import router as health_router
from app.api.uploads import router as uploads_router
from app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.project_name,
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    app.include_router(auth_router)
    app.include_router(bookings_router)
    app.include_router(dashboard_router)
    app.include_router(uploads_router)
    app.include_router(health_router)
    return app


app = create_app()
