from fastapi import APIRouter, Depends
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_super_admin
from app.db.session import get_db
from app.models.reporting import InsuranceCost
from app.models.user import User
from app.services.booking_checks import build_booking_checks_summary
from app.services.insurance_import import is_active_insurance_status


router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

ZERO = Decimal("0.00")


def money(value: Decimal | None) -> Decimal:
    if value is None:
        return ZERO
    return Decimal(value).quantize(Decimal("0.01"))


@router.get("/status")
def dashboard_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> dict:
    booking_checks = build_booking_checks_summary(db)
    all_insurance_costs = list(db.scalars(select(InsuranceCost)))
    active_insurance_costs = [
        cost for cost in all_insurance_costs if is_active_insurance_status(cost.insurance_status)
    ]
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
        "insurance": {
            "total_rows": len(all_insurance_costs),
            "active_rows": len(active_insurance_costs),
            "active_cost_total": str(
                money(sum((money(cost.insurance_cost_amount) for cost in active_insurance_costs), ZERO))
            ),
            "unmatched_count": sum(1 for cost in all_insurance_costs if cost.match_status == "unmatched"),
        },
    }
