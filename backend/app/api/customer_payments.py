from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_super_admin
from app.db.session import get_db
from app.models.reporting import CustomerPayment
from app.models.user import User
from app.schemas.customer_payment import (
    CustomerPaymentListResponse,
    CustomerPaymentSummaryRead,
)


router = APIRouter(prefix="/api/customer-payments", tags=["Customer Payments"])

ZERO = Decimal("0.00")


def money(value: Decimal | None) -> Decimal:
    if value is None:
        return ZERO
    return value.quantize(Decimal("0.01"))


@router.get("", response_model=CustomerPaymentListResponse)
def list_customer_payments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> CustomerPaymentListResponse:
    payment_statement = (
        select(CustomerPayment)
        .order_by(CustomerPayment.created_at.desc(), CustomerPayment.id.desc())
        .limit(200)
    )
    payments = list(db.scalars(payment_statement))
    all_payments = list(db.scalars(select(CustomerPayment)))

    gross_total = sum((money(payment.gross_amount) for payment in all_payments), ZERO)
    fee_total = sum((money(payment.fee_amount) for payment in all_payments), ZERO)
    actual_fee_total = sum(
        (money(payment.fee_amount) for payment in all_payments if not payment.fee_is_estimated),
        ZERO,
    )
    estimated_fee_total = sum(
        (money(payment.fee_amount) for payment in all_payments if payment.fee_is_estimated),
        ZERO,
    )
    net_settled_total = sum((money(payment.net_settled_amount) for payment in all_payments), ZERO)

    summary = CustomerPaymentSummaryRead(
        total_rows=len(all_payments),
        gross_total=money(gross_total),
        fee_total=money(fee_total),
        actual_fee_total=money(actual_fee_total),
        estimated_fee_total=money(estimated_fee_total),
        net_settled_total=money(net_settled_total),
        matched_count=sum(
            1 for payment in all_payments if payment.match_confidence in {"booking_ref", "invoice_ref"}
        ),
        lower_confidence_count=sum(1 for payment in all_payments if payment.match_confidence == "lower_confidence"),
        unmatched_count=sum(1 for payment in all_payments if payment.match_confidence == "unmatched"),
    )

    return CustomerPaymentListResponse(payments=payments, summary=summary)
