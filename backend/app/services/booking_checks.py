from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.reporting import Booking, BookingCheckAdjustment, CustomerPayment, InsuranceCost, SupplierPayment
from app.schemas.booking import BookingCheckRow, BookingChecksResponse, BookingChecksSummary


ZERO = Decimal("0.00")
BOOKING_CHECK_ROW_LIMIT = 5000
ADJUSTABLE_FIELDS = {
    "gross_booking_value",
    "expected_supplier_total",
    "supplier_taps_total",
    "supplier_tt_total",
    "customer_sings_total",
    "customer_tt_total",
}


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


def grouped_adjustments(db: Session) -> dict[str, dict[str, BookingCheckAdjustment]]:
    adjustments_by_booking: dict[str, dict[str, BookingCheckAdjustment]] = {}
    for adjustment in db.scalars(select(BookingCheckAdjustment)):
        adjustments_by_booking.setdefault(adjustment.booking_ref, {})[adjustment.field_name] = adjustment
    return adjustments_by_booking


def adjusted_amount(
    adjustments: dict[str, BookingCheckAdjustment],
    field_name: str,
    raw_value: Decimal | None,
) -> Decimal | None:
    adjustment = adjustments.get(field_name)
    if adjustment is not None:
        return money(adjustment.adjusted_amount)
    return money(raw_value) if raw_value is not None else None


def adjustment_values(adjustments: dict[str, BookingCheckAdjustment]) -> dict[str, Decimal]:
    return {field_name: money(adjustment.adjusted_amount) for field_name, adjustment in adjustments.items()}


def adjustment_note(adjustments: dict[str, BookingCheckAdjustment]) -> str | None:
    notes = []
    for adjustment in adjustments.values():
        note = (adjustment.note or "").strip()
        if note and note not in notes:
            notes.append(note)
    return " | ".join(notes) if notes else None


def build_booking_checks(db: Session, limit: int = BOOKING_CHECK_ROW_LIMIT) -> BookingChecksResponse:
    bookings = list(
        db.scalars(
            select(Booking)
            .order_by(Booking.departure_date.desc().nullslast(), Booking.updated_at.desc(), Booking.id.desc())
            .limit(limit)
        )
    )
    supplier_totals = grouped_supplier_totals(db)
    customer_totals = grouped_customer_totals(db)
    insurance_totals = grouped_insurance_totals(db)
    adjustments_by_booking = grouped_adjustments(db)

    rows: list[BookingCheckRow] = []
    for booking in bookings:
        raw_supplier_taps_total = supplier_totals.get((booking.booking_ref, "taps"), ZERO)
        raw_supplier_tt_total = supplier_totals.get(
            (booking.booking_ref, "tt"),
            money(booking.non_trusted_paid_supplier) if booking.non_trusted_paid_supplier is not None else ZERO,
        )
        raw_customer_sings_total = customer_totals.get((booking.booking_ref, "sings"), ZERO)
        raw_customer_tt_total = customer_totals.get(
            (booking.booking_ref, "tt"),
            money(booking.non_trusted_total_received) if booking.non_trusted_total_received is not None else ZERO,
        )
        insurance_cost_total = insurance_totals.get(booking.booking_ref, ZERO)

        raw_expected_supplier_total = None
        if booking.expected_supplier_nett is not None:
            raw_expected_supplier_total = money(booking.expected_supplier_nett) + insurance_cost_total

        adjustments = adjustments_by_booking.get(booking.booking_ref, {})
        gross_booking_value = adjusted_amount(adjustments, "gross_booking_value", booking.gross_booking_value)
        expected_supplier_total = adjusted_amount(
            adjustments,
            "expected_supplier_total",
            raw_expected_supplier_total,
        )
        supplier_taps_total = money(adjusted_amount(adjustments, "supplier_taps_total", raw_supplier_taps_total))
        supplier_tt_total = money(adjusted_amount(adjustments, "supplier_tt_total", raw_supplier_tt_total))
        customer_sings_total = money(adjusted_amount(adjustments, "customer_sings_total", raw_customer_sings_total))
        customer_tt_total = money(adjusted_amount(adjustments, "customer_tt_total", raw_customer_tt_total))

        supplier_expected_check = trusted_vs_expected_check(expected_supplier_total, supplier_taps_total)
        supplier_tt_check = trusted_vs_human_check(supplier_taps_total, supplier_tt_total)
        customer_expected_check = trusted_vs_expected_check(gross_booking_value, customer_sings_total)
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
        if gross_booking_value is not None:
            customer_expected_variance = money(customer_sings_total - gross_booking_value)

        rows.append(
            BookingCheckRow(
                booking_ref=booking.booking_ref,
                booking_company=booking.booking_company,
                normalised_status=booking.normalised_status,
                customer_last_name=booking.customer_last_name,
                agent_in_charge=booking.agent_in_charge,
                destination=booking.destination,
                travel_elements_raw=booking.travel_elements_raw,
                departure_date=booking.departure_date,
                return_date=booking.return_date,
                passenger_count=booking.passenger_count,
                gross_booking_value=gross_booking_value,
                expected_supplier_nett=booking.expected_supplier_nett,
                insurance_cost_total=money(insurance_cost_total),
                expected_supplier_total=expected_supplier_total,
                supplier_taps_total=supplier_taps_total,
                supplier_tt_total=supplier_tt_total,
                supplier_expected_variance=supplier_expected_variance,
                supplier_tt_variance=money(supplier_taps_total - supplier_tt_total),
                supplier_expected_check=supplier_expected_check,
                supplier_tt_check=supplier_tt_check,
                customer_sings_total=customer_sings_total,
                customer_tt_total=customer_tt_total,
                customer_expected_variance=customer_expected_variance,
                customer_tt_variance=money(customer_sings_total - customer_tt_total),
                customer_expected_check=customer_expected_check,
                customer_tt_check=customer_tt_check,
                review_status=row_review_status,
                review_note=row_review_note,
                raw_gross_booking_value=booking.gross_booking_value,
                raw_expected_supplier_total=raw_expected_supplier_total,
                raw_supplier_taps_total=money(raw_supplier_taps_total),
                raw_supplier_tt_total=money(raw_supplier_tt_total),
                raw_customer_sings_total=money(raw_customer_sings_total),
                raw_customer_tt_total=money(raw_customer_tt_total),
                traveltek_total_due=booking.non_trusted_total_due,
                traveltek_total_amount_paid=booking.non_trusted_total_received,
                traveltek_customer_outstanding=booking.imported_customer_outstanding,
                traveltek_due_to_suppliers=booking.imported_supplier_outstanding,
                traveltek_paid_to_supplier=booking.non_trusted_paid_supplier,
                traveltek_projected_profit=booking.non_trusted_projected_profit,
                manual_adjustments=adjustment_values(adjustments),
                manual_adjustment_note=adjustment_note(adjustments),
                has_manual_adjustment=bool(adjustments),
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
        error_count=sum(1 for row in rows if row.review_status == "mismatch"),
        awaiting_count=sum(1 for row in rows if row.review_status == "waiting"),
    )
    return BookingChecksResponse(summary=summary, bookings=rows)


def build_booking_checks_summary(db: Session, limit: int = BOOKING_CHECK_ROW_LIMIT) -> BookingChecksSummary:
    bookings = list(
        db.scalars(
            select(Booking)
            .order_by(Booking.departure_date.desc().nullslast(), Booking.updated_at.desc(), Booking.id.desc())
            .limit(limit)
        )
    )
    supplier_totals = grouped_supplier_totals(db)
    customer_totals = grouped_customer_totals(db)
    insurance_totals = grouped_insurance_totals(db)
    adjustments_by_booking = grouped_adjustments(db)

    supplier_expected_matches = 0
    supplier_tt_matches = 0
    customer_expected_matches = 0
    customer_tt_matches = 0
    fully_matched = 0
    error_count = 0
    awaiting_count = 0

    for booking in bookings:
        raw_supplier_taps_total = supplier_totals.get((booking.booking_ref, "taps"), ZERO)
        raw_supplier_tt_total = supplier_totals.get(
            (booking.booking_ref, "tt"),
            money(booking.non_trusted_paid_supplier) if booking.non_trusted_paid_supplier is not None else ZERO,
        )
        raw_customer_sings_total = customer_totals.get((booking.booking_ref, "sings"), ZERO)
        raw_customer_tt_total = customer_totals.get(
            (booking.booking_ref, "tt"),
            money(booking.non_trusted_total_received) if booking.non_trusted_total_received is not None else ZERO,
        )
        insurance_cost_total = insurance_totals.get(booking.booking_ref, ZERO)

        raw_expected_supplier_total = None
        if booking.expected_supplier_nett is not None:
            raw_expected_supplier_total = money(booking.expected_supplier_nett) + insurance_cost_total

        adjustments = adjustments_by_booking.get(booking.booking_ref, {})
        gross_booking_value = adjusted_amount(adjustments, "gross_booking_value", booking.gross_booking_value)
        expected_supplier_total = adjusted_amount(
            adjustments,
            "expected_supplier_total",
            raw_expected_supplier_total,
        )
        supplier_taps_total = money(adjusted_amount(adjustments, "supplier_taps_total", raw_supplier_taps_total))
        supplier_tt_total = money(adjusted_amount(adjustments, "supplier_tt_total", raw_supplier_tt_total))
        customer_sings_total = money(adjusted_amount(adjustments, "customer_sings_total", raw_customer_sings_total))
        customer_tt_total = money(adjusted_amount(adjustments, "customer_tt_total", raw_customer_tt_total))

        checks = (
            trusted_vs_expected_check(expected_supplier_total, supplier_taps_total),
            trusted_vs_human_check(supplier_taps_total, supplier_tt_total),
            trusted_vs_expected_check(gross_booking_value, customer_sings_total),
            trusted_vs_human_check(customer_sings_total, customer_tt_total),
        )

        supplier_expected_matches += checks[0] == "match"
        supplier_tt_matches += checks[1] == "match"
        customer_expected_matches += checks[2] == "match"
        customer_tt_matches += checks[3] == "match"

        row_review_status, _ = review_status(*checks)
        fully_matched += row_review_status == "match"
        error_count += row_review_status == "mismatch"
        awaiting_count += row_review_status == "waiting"

    total_bookings = len(bookings)
    return BookingChecksSummary(
        total_bookings=total_bookings,
        supplier_expected_matches=supplier_expected_matches,
        supplier_tt_matches=supplier_tt_matches,
        customer_expected_matches=customer_expected_matches,
        customer_tt_matches=customer_tt_matches,
        fully_matched=fully_matched,
        needs_review=total_bookings - fully_matched,
        error_count=error_count,
        awaiting_count=awaiting_count,
    )
