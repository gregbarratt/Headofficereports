from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_super_admin
from app.db.session import get_db
from app.models.user import User
from app.services.booking_checks import build_booking_checks_summary


router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/status")
def dashboard_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> dict:
    booking_checks = build_booking_checks_summary(db)
    return {
        "status": "ok",
        "message": "Super Admin access confirmed.",
        "email": current_user.email,
        "booking_checks": {
            "total_bookings": booking_checks.total_bookings,
            "fully_matched": booking_checks.fully_matched,
            "error_count": booking_checks.error_count,
            "awaiting_count": booking_checks.awaiting_count,
            "needs_review": booking_checks.needs_review,
        },
    }
