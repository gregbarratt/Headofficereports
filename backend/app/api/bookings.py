from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_super_admin
from app.db.session import get_db
from decimal import Decimal

from app.models.reporting import Booking, CustomerPayment, InsuranceCost, SupplierPayment
from app.models.user import User
from app.schemas.booking import BookingChecksResponse, BookingChecksSummary, BookingCheckRow, BookingListResponse


router = APIRouter(prefix="/api/bookings", tags=["Bookings"])
ZERO = Decimal("0.00")


def money(value: Decimal | None) -> Decimal:
    if value is None:
        return ZERO
    return Decimal(value).quantize(Decimal("0.01"))


def trusted_vs_expected_check(expected: Decimal | None, actual: Decimal) -> str:
    if expected is None:
        return "waiting_master"

    expected_money = money(expected)
    actual_money = money(actual)
    if actual_money == expected_money:
        return "match"
    if actual_money == ZERO:
        return "waiting_actual"
    return "mismatch"


def trusted_vs_human_check(actual: Decimal, human_input: Decimal) -> str:
    actual_money = money(actual)
    human_money = money(human_input)
    if actual_money == ZERO and human_money == ZERO:
        return "waiting_both"
    if actual_money == human_money:
        return "match"
    if actual_money == ZERO:
        return "waiting_actual"
    if human_money == ZERO:
        return "waiting_human"
    return "mismatch"


def review_status(*checks: str) -> tuple[str, str]:
    if all(check == "match" for check in checks):
        return "match", "All imported values match."
    if any(check == "mismatch" for check in checks):
        return "mismatch", "One or more values do not match."
    return "waiting", "One or more imports are still missing."


def grouped_supplier_totals(db: Session) -> dict[tuple[str, str], Decimal]:
    return {
        (booking_ref, payment_source): money(total)
        for booking_ref, payment_source, total in db.execute(
            select(
                SupplierPayment.booking_ref,
                SupplierPayment.payment_source,
                func.sum(SupplierPayment.supplier_payment_amount),
            )
            .where(SupplierPayment.booking_ref.is_not(None))
            .group_by(SupplierPayment.booking_ref, SupplierPayment.payment_source)
        )
        if booking_ref and payment_source
    }


def grouped_customer_totals(db: Session) -> dict[tuple[str, str], Decimal]:
    return {
        (booking_ref, payment_source): money(total)
        for booking_ref, payment_source, total in db.execute(
            select(
                CustomerPayment.booking_ref,
                CustomerPayment.payment_source,
                func.sum(CustomerPayment.gross_amount),
            )
            .where(CustomerPayment.booking_ref.is_not(None))
            .group_by(CustomerPayment.booking_ref, CustomerPayment.payment_source)
        )
        if booking_ref and payment_source
    }


def grouped_insurance_totals(db: Session) -> dict[str, Decimal]:
    active_statuses = ("booking", "booked", "confirmed", "live")
    return {
        booking_ref: money(total)
        for booking_ref, total in db.execute(
            select(InsuranceCost.booking_ref, func.sum(InsuranceCost.insurance_cost_amount))
            .where(InsuranceCost.booking_ref.is_not(None))
            .where(InsuranceCost.insurance_status.in_(active_statuses))
            .group_by(InsuranceCost.booking_ref)
        )
        if booking_ref
    }


@router.get("", response_model=BookingListResponse)
def list_bookings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> BookingListResponse:
    total = db.scalar(select(func.count()).select_from(Booking)) or 0
    statement = select(Booking).order_by(Booking.updated_at.desc(), Booking.id.desc()).limit(200)
    bookings = list(db.scalars(statement))
    return BookingListResponse(bookings=bookings, total=total)


@router.get("/checks", response_model=BookingChecksResponse)
def list_booking_checks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> BookingChecksResponse:
    bookings = list(db.scalars(select(Booking).order_by(Booking.updated_at.desc(), Booking.id.desc()).limit(500)))
    supplier_totals = grouped_supplier_totals(db)
    customer_totals = grouped_customer_totals(db)
    insurance_totals = grouped_insurance_totals(db)

    rows: list[BookingCheckRow] = []
    for booking in bookings:
        supplier_taps_total = supplier_totals.get((booking.booking_ref, "taps"), ZERO)
        supplier_tt_total = supplier_totals.get((booking.booking_ref, "tt"), ZERO)
        customer_sings_total = customer_totals.get((booking.booking_ref, "sings"), ZERO)
        customer_tt_total = customer_totals.get((booking.booking_ref, "tt"), ZERO)
        insurance_cost_total = insurance_totals.get(booking.booking_ref, ZERO)

        expected_supplier_total = None
        if booking.expected_supplier_nett is not None:
            expected_supplier_total = money(booking.expected_supplier_nett) + insurance_cost_total

        supplier_expected_check = trusted_vs_expected_check(expected_supplier_total, supplier_taps_total)
        supplier_tt_check = trusted_vs_human_check(supplier_taps_total, supplier_tt_total)
        customer_expected_check = trusted_vs_expected_check(booking.gross_booking_value, customer_sings_total)
        customer_tt_check = trusted_vs_human_check(customer_sings_total, customer_tt_total)
        row_review_status, row_review_note = review_status(
            supplier_expected_check,
            supplier_tt_check,
            customer_expected_check,
            customer_tt_check,
        )

        supplier_expected_variance = None
        if expected_supplier_total is not None:
            supplier_expected_variance = money(supplier_taps_total - expected_supplier_total)

        customer_expected_variance = None
        if booking.gross_booking_value is not None:
            customer_expected_variance = money(customer_sings_total - money(booking.gross_booking_value))

        rows.append(
            BookingCheckRow(
                booking_ref=booking.booking_ref,
                booking_company=booking.booking_company,
                normalised_status=booking.normalised_status,
                customer_last_name=booking.customer_last_name,
                destination=booking.destination,
                departure_date=booking.departure_date,
                gross_booking_value=booking.gross_booking_value,
                expected_supplier_nett=booking.expected_supplier_nett,
                insurance_cost_total=money(insurance_cost_total),
                expected_supplier_total=expected_supplier_total,
                supplier_taps_total=money(supplier_taps_total),
                supplier_tt_total=money(supplier_tt_total),
                supplier_expected_variance=supplier_expected_variance,
                supplier_tt_variance=money(supplier_taps_total - supplier_tt_total),
                supplier_expected_check=supplier_expected_check,
                supplier_tt_check=supplier_tt_check,
                customer_sings_total=money(customer_sings_total),
                customer_tt_total=money(customer_tt_total),
                customer_expected_variance=customer_expected_variance,
                customer_tt_variance=money(customer_sings_total - customer_tt_total),
                customer_expected_check=customer_expected_check,
                customer_tt_check=customer_tt_check,
                review_status=row_review_status,
                review_note=row_review_note,
            )
        )

    summary = BookingChecksSummary(
        total_bookings=len(rows),
        supplier_expected_matches=sum(1 for row in rows if row.supplier_expected_check == "match"),
        supplier_tt_matches=sum(1 for row in rows if row.supplier_tt_check == "match"),
        customer_expected_matches=sum(1 for row in rows if row.customer_expected_check == "match"),
        customer_tt_matches=sum(1 for row in rows if row.customer_tt_check == "match"),
        fully_matched=sum(1 for row in rows if row.review_status == "match"),
        needs_review=sum(1 for row in rows if row.review_status != "match"),
    )
    return BookingChecksResponse(summary=summary, bookings=rows)
