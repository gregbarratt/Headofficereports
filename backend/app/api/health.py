from fastapi import APIRouter

from app.core.config import settings


router = APIRouter(tags=["Health"])


def health_payload() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "app": settings.project_name,
        "environment": settings.environment,
        "database_configured": settings.database_configured,
    }


@router.get("/health")
def health_check() -> dict[str, str | bool]:
    return health_payload()


@router.get("/api/health")
def api_health_check() -> dict[str, str | bool]:
    return health_payload()
