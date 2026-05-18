from fastapi import APIRouter, Depends

from app.api.deps import get_current_super_admin
from app.models.user import User


router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/status")
def dashboard_status(current_user: User = Depends(get_current_super_admin)) -> dict[str, str]:
    return {
        "status": "ok",
        "message": "Super Admin access confirmed.",
        "email": current_user.email,
    }
