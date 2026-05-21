from fastapi import APIRouter, Depends

from app.api.deps import get_current_super_admin
from app.core.config import settings
from app.models.user import User


router = APIRouter(prefix="/api/settings", tags=["Settings"])


@router.get("/status")
def settings_status(current_user: User = Depends(get_current_super_admin)) -> dict:
    return {
        "project_name": settings.project_name,
        "environment": settings.environment,
        "frontend_url_configured": bool(settings.frontend_url.strip()),
        "database_configured": settings.database_configured,
        "max_upload_size_mb": settings.max_upload_size_mb,
        "login_session_minutes": settings.jwt_access_token_expire_minutes,
        "felloh": {
            "configured": settings.felloh_api_configured,
            "base_url_configured": bool(settings.felloh_api_base_url.strip()),
            "public_key_configured": bool(settings.felloh_public_key.strip()),
            "private_key_configured": bool(settings.felloh_private_key.strip()),
            "organisation_id_configured": bool(settings.felloh_organisation_id.strip()),
        },
        "email": {
            "configured": settings.smtp_configured,
            "host_configured": bool(settings.smtp_host.strip()),
            "from_email_configured": bool(settings.smtp_from_email.strip()),
            "username_configured": bool(settings.smtp_username.strip()),
            "password_configured": bool(settings.smtp_password.strip()),
            "use_tls": settings.smtp_use_tls,
            "port": settings.smtp_port,
        },
    }
