from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_super_admin
from app.db.session import get_db
from app.models.reporting import Refund
from app.models.user import User
from app.schemas.refund import RefundListResponse, RefundRead, RefundSummaryRead


router = APIRouter(prefix="/api/refunds", tags=["Refunds"])

ZERO = Decimal("0.00")


def money(value: Decimal | None) -> Decimal:
    if value is None:
        return ZERO
    return Decimal(value).quantize(Decimal("0.01"))


def positive(value: Decimal) -> Decimal:
    return value if value > ZERO else ZERO


def refund_unpaid(refund: Refund) -> Decimal:
    return positive(money(refund.refund_amount_due) - money(refund.refund_amount_paid))


def supplier_refund_outstanding(refund: Refund) -> Decimal:
    return positive(money(refund.supplier_refund_expected) - money(refund.supplier_refund_received))


def to_refund_read(refund: Refund) -> RefundRead:
    return RefundRead(
        id=refund.id,
        upload_batch_id=refund.upload_batch_id,
        booking_ref=refund.booking_ref,
        customer_name=refund.customer_name,
        refund_reason=refund.refund_reason,
        refund_amount_due=money(refund.refund_amount_due),
        refund_amount_paid=money(refund.refund_amount_paid),
        refund_unpaid=refund_unpaid(refund),
        refund_status=refund.refund_status,
        supplier_refund_expected=refund.supplier_refund_expected,
        supplier_refund_received=refund.supplier_refund_received,
        supplier_refund_outstanding=supplier_refund_outstanding(refund),
        due_date=refund.due_date,
        paid_date=refund.paid_date,
        match_status="matched" if refund.booking_id else "unmatched",
        created_at=refund.created_at,
    )


@router.get("", response_model=RefundListResponse)
def list_refunds(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> RefundListResponse:
    refunds = list(
        db.scalars(
            select(Refund)
            .order_by(Refund.created_at.desc(), Refund.id.desc())
            .limit(200)
        )
    )
    all_refunds = list(db.scalars(select(Refund)))

    summary = RefundSummaryRead(
        total_rows=len(all_refunds),
        refund_amount_due_total=money(sum((money(refund.refund_amount_due) for refund in all_refunds), ZERO)),
        refund_amount_paid_total=money(sum((money(refund.refund_amount_paid) for refund in all_refunds), ZERO)),
        refund_unpaid_total=money(sum((refund_unpaid(refund) for refund in all_refunds), ZERO)),
        supplier_refund_expected_total=money(
            sum((money(refund.supplier_refund_expected) for refund in all_refunds), ZERO)
        ),
        supplier_refund_received_total=money(
            sum((money(refund.supplier_refund_received) for refund in all_refunds), ZERO)
        ),
        supplier_refund_outstanding_total=money(
            sum((supplier_refund_outstanding(refund) for refund in all_refunds), ZERO)
        ),
        overdue_count=sum(1 for refund in all_refunds if refund.refund_status == "overdue"),
        unmatched_count=sum(1 for refund in all_refunds if refund.booking_id is None),
    )

    return RefundListResponse(
        refunds=[to_refund_read(refund) for refund in refunds],
        summary=summary,
    )
