from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_super_admin
from app.db.session import get_db
from app.models.reporting import Booking, InsuranceCost, SupplierPayment
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
    expected_booking_cost: Decimal | None,
    supplier_payments_total: Decimal,
) -> tuple[str, Decimal | None, Decimal | None, str | None]:
    if expected_booking_cost is None:
        return "awaiting_supplier_nett", None, None, "Expected supplier nett missing"

    expected = money(expected_booking_cost)
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
    search: str = "",
    source: str = "all",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> SupplierPaymentListResponse:
    search_term = search.strip()
    search_pattern = f"%{search_term}%" if search_term else ""
    source_filter = source.strip().lower()
    if source_filter not in {"all", "taps", "tt"}:
        source_filter = "all"
    payment_filters = []
    booking_filters = []
    if source_filter != "all":
        payment_filters.append(SupplierPayment.payment_source == source_filter)
    total_statement = select(func.count()).select_from(SupplierPayment)
    if source_filter != "all":
        total_statement = total_statement.where(SupplierPayment.payment_source == source_filter)
    total = db.scalar(total_statement) or 0
    if search_term:
        payment_filters.append(
            or_(
                SupplierPayment.booking_ref.ilike(search_pattern),
                SupplierPayment.product_type.ilike(search_pattern),
                SupplierPayment.supplier_name.ilike(search_pattern),
                SupplierPayment.payment_supplier_name.ilike(search_pattern),
                SupplierPayment.supplier_payment_method.ilike(search_pattern),
                SupplierPayment.payment_source.ilike(search_pattern),
            )
        )
        booking_filters.append(
            or_(
                Booking.booking_ref.ilike(search_pattern),
                Booking.customer_last_name.ilike(search_pattern),
                Booking.destination.ilike(search_pattern),
            )
        )

    filtered_total_statement = select(func.count()).select_from(SupplierPayment)
    if payment_filters:
        filtered_total_statement = filtered_total_statement.where(*payment_filters)
    filtered_total = db.scalar(filtered_total_statement) or 0

    payment_statement = (
        select(SupplierPayment)
        .where(*payment_filters)
        .order_by(SupplierPayment.created_at.desc(), SupplierPayment.id.desc())
        .limit(200)
    )
    payments = list(db.scalars(payment_statement))

    totals_by_booking_and_source: dict[tuple[str, str], Decimal] = {
        (booking_ref, payment_source): money(total_paid)
        for booking_ref, payment_source, total_paid in db.execute(
            select(
                SupplierPayment.booking_ref,
                SupplierPayment.payment_source,
                func.sum(SupplierPayment.supplier_payment_amount),
            )
            .where(SupplierPayment.booking_ref.is_not(None))
            .group_by(SupplierPayment.booking_ref, SupplierPayment.payment_source)
        )
    }
    active_insurance_statuses = ("booking", "booked", "confirmed", "live")
    insurance_totals_by_booking: dict[str, Decimal] = {
        booking_ref: money(total_cost)
        for booking_ref, total_cost in db.execute(
            select(InsuranceCost.booking_ref, func.sum(InsuranceCost.insurance_cost_amount))
            .where(InsuranceCost.booking_ref.is_not(None))
            .where(InsuranceCost.insurance_status.in_(active_insurance_statuses))
            .group_by(InsuranceCost.booking_ref)
        )
    }

    booking_refs_from_filtered_payments: set[str] = set()
    if search_term:
        booking_refs_from_filtered_payments = {
            booking_ref
            for booking_ref in db.scalars(
                select(SupplierPayment.booking_ref)
                .where(*payment_filters)
                .where(SupplierPayment.booking_ref.is_not(None))
            )
            if booking_ref
        }

    booking_statement = select(Booking)
    if search_term:
        booking_statement = booking_statement.where(
            or_(
                *booking_filters,
                Booking.booking_ref.in_(booking_refs_from_filtered_payments),
            )
        )
    booking_statement = booking_statement.order_by(Booking.updated_at.desc(), Booking.id.desc()).limit(200)
    reconciliations = []
    for booking in db.scalars(booking_statement):
        supplier_payments_taps_total = totals_by_booking_and_source.get((booking.booking_ref, "taps"), ZERO)
        supplier_payments_tt_total = totals_by_booking_and_source.get((booking.booking_ref, "tt"), ZERO)
        insurance_cost_total = insurance_totals_by_booking.get(booking.booking_ref, ZERO)
        total_expected_booking_cost = None
        if booking.expected_supplier_nett is not None:
            total_expected_booking_cost = money(booking.expected_supplier_nett) + insurance_cost_total
        supplier_payments_total = supplier_payments_taps_total
        supplier_cross_check_variance = money(supplier_payments_taps_total - supplier_payments_tt_total)
        status, balance_due, variance, supplier_exception = get_supplier_status(
            total_expected_booking_cost,
            supplier_payments_total,
        )
        reconciliations.append(
            SupplierBookingReconciliationRead(
                booking_ref=booking.booking_ref,
                customer_last_name=booking.customer_last_name,
                expected_supplier_nett=booking.expected_supplier_nett,
                insurance_cost_total=money(insurance_cost_total),
                total_expected_booking_cost=money(total_expected_booking_cost)
                if total_expected_booking_cost is not None
                else None,
                supplier_payments_total=supplier_payments_total,
                supplier_payments_taps_total=supplier_payments_taps_total,
                supplier_payments_tt_total=supplier_payments_tt_total,
                supplier_cross_check_variance=supplier_cross_check_variance,
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
        filtered_total=filtered_total,
    )
