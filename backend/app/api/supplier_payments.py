from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_super_admin
from app.db.session import get_db
from app.models.reporting import Booking, SupplierPayment
from app.models.user import User
from app.schemas.supplier_payment import (
    SupplierBookingReconciliationRead,
    SupplierPaymentListResponse,
)


router = APIRouter(prefix="/api/supplier-payments", tags=["Supplier Payments"])

ZERO = Decimal("0.00")


def money(value: Decimal | None) -> Decimal:
    if value is None:
        return ZERO
    return value.quantize(Decimal("0.01"))


def get_supplier_status(
    expected_supplier_nett: Decimal | None,
    supplier_payments_total: Decimal,
) -> tuple[str, Decimal | None, Decimal | None, str | None]:
    if expected_supplier_nett is None:
        return "awaiting_supplier_nett", None, None, "Expected supplier nett missing"

    expected = money(expected_supplier_nett)
    paid = money(supplier_payments_total)
    balance_due = money(expected - paid)
    variance = money(paid - expected)

    if paid == ZERO:
        return "unpaid", balance_due, variance, "Supplier balance due"
    if balance_due == ZERO:
        return "paid_in_full", balance_due, variance, None
    if balance_due < ZERO:
        return "overpaid", balance_due, variance, "Supplier overpaid"
    return "partially_paid", balance_due, variance, "Supplier balance due"


@router.get("", response_model=SupplierPaymentListResponse)
def list_supplier_payments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> SupplierPaymentListResponse:
    total = db.scalar(select(func.count()).select_from(SupplierPayment)) or 0
    payment_statement = (
        select(SupplierPayment)
        .order_by(SupplierPayment.created_at.desc(), SupplierPayment.id.desc())
        .limit(200)
    )
    payments = list(db.scalars(payment_statement))

    total_by_booking = {
        booking_ref: money(total_paid)
        for booking_ref, total_paid in db.execute(
            select(SupplierPayment.booking_ref, func.sum(SupplierPayment.supplier_payment_amount))
            .where(SupplierPayment.booking_ref.is_not(None))
            .group_by(SupplierPayment.booking_ref)
        )
    }

    booking_statement = select(Booking).order_by(Booking.updated_at.desc(), Booking.id.desc()).limit(200)
    reconciliations = []
    for booking in db.scalars(booking_statement):
        supplier_payments_total = total_by_booking.get(booking.booking_ref, ZERO)
        status, balance_due, variance, supplier_exception = get_supplier_status(
            booking.expected_supplier_nett,
            supplier_payments_total,
        )
        reconciliations.append(
            SupplierBookingReconciliationRead(
                booking_ref=booking.booking_ref,
                customer_last_name=booking.customer_last_name,
                expected_supplier_nett=booking.expected_supplier_nett,
                supplier_payments_total=supplier_payments_total,
                supplier_balance_due=balance_due,
                supplier_variance=variance,
                supplier_reconciliation_status=status,
                supplier_exception=supplier_exception,
                trust_status="Incomplete until SINGs/Singhs customer payment data is imported",
                true_profit_status="Incomplete until SINGs fees and commission data are imported",
            )
        )

    return SupplierPaymentListResponse(
        payments=payments,
        reconciliations=reconciliations,
        total=total,
    )
