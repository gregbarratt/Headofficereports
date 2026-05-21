from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_super_admin
from app.db.session import get_db
from app.models.reporting import InsuranceCost
from app.models.user import User
from app.schemas.insurance import InsuranceListResponse, InsuranceSummaryRead
from app.services.insurance_import import is_active_insurance_status


router = APIRouter(prefix="/api/insurance-costs", tags=["Insurance Costs"])

ZERO = Decimal("0.00")


def money(value: Decimal | None) -> Decimal:
    if value is None:
        return ZERO
    return Decimal(value).quantize(Decimal("0.01"))


@router.get("", response_model=InsuranceListResponse)
def list_insurance_costs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> InsuranceListResponse:
    costs = list(
        db.scalars(
            select(InsuranceCost)
            .order_by(InsuranceCost.created_at.desc(), InsuranceCost.id.desc())
            .limit(200)
        )
    )
    all_costs = list(db.scalars(select(InsuranceCost)))
    active_costs = [cost for cost in all_costs if is_active_insurance_status(cost.insurance_status)]
    summary = InsuranceSummaryRead(
        total_rows=len(all_costs),
        active_rows=len(active_costs),
        active_cost_total=money(sum((money(cost.insurance_cost_amount) for cost in active_costs), ZERO)),
        unmatched_count=sum(1 for cost in all_costs if cost.match_status == "unmatched"),
        duplicate_count=sum(1 for cost in all_costs if cost.is_duplicate),
    )
    return InsuranceListResponse(costs=costs, summary=summary)
