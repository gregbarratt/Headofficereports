from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.reporting import (
    Booking,
    BookingCheckAdjustment,
    CustomerPayment,
    InsuranceCost,
    SupplierPayment,
    TraveltekBookingUpdate,
)
from app.schemas.booking import BookingCheckRow, BookingChecksResponse, BookingChecksSummary
from app.services.master_booking_import import parse_date, parse_int, parse_money


ZERO = Decimal("0.00")
BOOKING_CHECK_ROW_LIMIT = 10000
BOOKING_CHECK_FAST_PAGE_LIMIT = 250
TRAVELTEK_AUTO_BOOKING_FIELDS = {
    "return_date",
    "passenger_count",
    "imported_customer_outstanding",
    "imported_supplier_outstanding",
    "non_trusted_total_due",
    "non_trusted_total_received",
    "non_trusted_paid_supplier",
}
ADJUSTABLE_FIELDS = {
    "gross_booking_value",
    "expected_supplier_total",
    "supplier_taps_total",
    "supplier_tt_total",
    "customer_sings_total",
    "customer_tt_total",
}


def parse_traveltek_auto_booking_value(field_name: str, raw_value: str | None):
    if raw_value is None:
        return None
    try:
        if field_name == "return_date":
            try:
                return parse_date(raw_value)
            except ValueError:
                return date.fromisoformat(str(raw_value).strip()[:10])
        if field_name == "passenger_count":
            value = parse_int(raw_value)
            return value if value is not None and 0 < value <= 99 else None
        if field_name == "non_trusted_total_due":
            return parse_money(raw_value)
        if field_name in {
            "imported_customer_outstanding",
            "imported_supplier_outstanding",
            "non_trusted_total_received",
            "non_trusted_paid_supplier",
        }:
            return parse_money(raw_value)
    except (TypeError, ValueError):
        return None
    return None


def values_match(current_value, new_value) -> bool:
    if current_value is None and new_value is None:
        return True
    if isinstance(current_value, Decimal) or isinstance(new_value, Decimal):
        if current_value is None or new_value is None:
            return False
        return money(current_value) == money(new_value)
    if isinstance(current_value, datetime):
        current_value = current_value.date()
    if isinstance(new_value, datetime):
        new_value = new_value.date()
    return current_value == new_value


def apply_pending_traveltek_auto_booking_fields(db: Session) -> None:
    pending_updates = list(
        db.scalars(
            select(TraveltekBookingUpdate)
            .where(TraveltekBookingUpdate.field_name.in_(TRAVELTEK_AUTO_BOOKING_FIELDS))
            .where(TraveltekBookingUpdate.status.in_(("open", "reviewing")))
            .order_by(TraveltekBookingUpdate.detected_at.desc(), TraveltekBookingUpdate.id.desc())
        )
    )
    if not pending_updates:
        return

    changed = False
    bookings_by_id: dict[int, Booking] = {}
    bookings_by_ref: dict[str, Booking] = {}

    for update in pending_updates:
        parsed_value = parse_traveltek_auto_booking_value(update.field_name, update.traveltek_value)
        if parsed_value is None or not hasattr(Booking, update.field_name):
            continue

        booking = None
        if update.booking_id:
            booking = bookings_by_id.get(update.booking_id)
            if booking is None:
                booking = db.get(Booking, update.booking_id)
                if booking is not None:
                    bookings_by_id[update.booking_id] = booking

        if booking is None:
            booking_ref = update.booking_ref.strip().upper()
            booking = bookings_by_ref.get(booking_ref)
            if booking is None:
                booking = db.scalar(select(Booking).where(Booking.booking_ref == booking_ref))
                if booking is not None:
                    bookings_by_ref[booking_ref] = booking

        if booking is None:
            continue

        if not values_match(getattr(booking, update.field_name), parsed_value):
            setattr(booking, update.field_name, parsed_value)
            changed = True

        update.status = "resolved"
        changed = True

    if changed:
        db.commit()


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


def grouped_check_status(row: BookingCheckRow, check_group: str) -> str:
    checks = (
        (row.supplier_expected_check, row.supplier_tt_check)
        if check_group == "supplier"
        else (row.customer_expected_check, row.customer_tt_check)
    )
    if any(check == "mismatch" for check in checks):
        return "mismatch"
    if all(check == "match" or check == "not_checked" for check in checks):
        return "match"
    return "waiting"


def build_booking_check_row(
    booking: Booking,
    supplier_totals: dict[tuple[str, str], Decimal],
    customer_totals: dict[tuple[str, str], Decimal],
    insurance_totals: dict[str, Decimal],
    adjustments_by_booking: dict[str, dict[str, BookingCheckAdjustment]],
) -> BookingCheckRow:
    raw_supplier_taps_total = supplier_totals.get((booking.booking_ref, "taps"), ZERO)
    raw_supplier_tt_total = (
        money(booking.non_trusted_paid_supplier)
        if booking.non_trusted_paid_supplier is not None
        else supplier_totals.get((booking.booking_ref, "tt"), ZERO)
    )
    raw_customer_sings_total = customer_totals.get((booking.booking_ref, "sings"), ZERO)
    raw_customer_tt_total = (
        money(booking.non_trusted_total_received)
        if booking.non_trusted_total_received is not None
        else customer_totals.get((booking.booking_ref, "tt"), ZERO)
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
    customer_expected_check = "not_checked"
    customer_tt_check = trusted_vs_human_check(customer_sings_total, customer_tt_total)
    row_review_status, row_review_note = review_status(
        supplier_tt_check,
        customer_tt_check,
    )

    supplier_expected_variance = None
    if expected_supplier_total is not None:
        supplier_expected_variance = money(supplier_taps_total - expected_supplier_total)

    return BookingCheckRow(
        booking_ref=booking.booking_ref,
        traveltek_booking_id=booking.traveltek_booking_id,
        booking_company=booking.booking_company,
        normalised_status=booking.normalised_status,
        customer_last_name=booking.customer_last_name,
        agent_in_charge=booking.agent_in_charge,
        destination=booking.destination,
        travel_elements_raw=booking.travel_elements_raw,
        supplier_references_raw=booking.supplier_references_raw,
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
        customer_expected_variance=None,
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
        is_archived=booking.is_archived,
        archived_at=booking.archived_at,
        archive_note=booking.archive_note,
        agent_commission_review_required=booking.agent_commission_review_required,
        agent_commission_review_note=booking.agent_commission_review_note,
        manual_adjustments=adjustment_values(adjustments),
        manual_adjustment_note=adjustment_note(adjustments),
        has_manual_adjustment=bool(adjustments),
        updated_at=booking.updated_at,
    )


def booking_search_statement(search: str, company_filter: str):
    statement = select(Booking).order_by(Booking.departure_date.desc().nullslast(), Booking.updated_at.desc(), Booking.id.desc())
    if company_filter != "all":
        statement = statement.where(Booking.booking_company == company_filter)

    search_value = search.strip()
    if search_value:
        pattern = f"%{search_value}%"
        statement = statement.where(
            or_(
                Booking.booking_ref.ilike(pattern),
                Booking.customer_last_name.ilike(pattern),
                Booking.agent_in_charge.ilike(pattern),
                Booking.destination.ilike(pattern),
                Booking.travel_elements_raw.ilike(pattern),
                Booking.normalised_status.ilike(pattern),
            )
        )
    return statement


def parse_filter_date(value: str | None) -> date | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def filtered_booking_statement(
    search: str = "",
    company_filter: str = "all",
    archive_filter: str = "active",
    commission_review_filter: str = "all",
    departure_from: str = "",
    departure_to: str = "",
):
    statement = booking_search_statement(search, company_filter)

    if archive_filter == "archived":
        statement = statement.where(Booking.is_archived.is_(True))
    elif archive_filter != "all":
        statement = statement.where(Booking.is_archived.is_(False))

    if commission_review_filter == "flagged":
        statement = statement.where(Booking.agent_commission_review_required.is_(True))
    elif commission_review_filter == "not_flagged":
        statement = statement.where(Booking.agent_commission_review_required.is_(False))

    start_date = parse_filter_date(departure_from)
    end_date = parse_filter_date(departure_to)
    if start_date:
        statement = statement.where(Booking.departure_date >= start_date)
    if end_date:
        statement = statement.where(Booking.departure_date <= end_date)

    return statement


def row_matches_filters(row: BookingCheckRow, review_filter: str, supplier_filter: str, customer_filter: str) -> bool:
    if review_filter != "all" and row.review_status != review_filter:
        return False
    if supplier_filter != "all" and grouped_check_status(row, "supplier") != supplier_filter:
        return False
    if customer_filter != "all" and grouped_check_status(row, "customer") != customer_filter:
        return False
    return True


def build_booking_checks(
    db: Session,
    limit: int = BOOKING_CHECK_FAST_PAGE_LIMIT,
    search: str = "",
    review_filter: str = "all",
    company_filter: str = "all",
    supplier_filter: str = "all",
    customer_filter: str = "all",
    archive_filter: str = "active",
    commission_review_filter: str = "all",
    departure_from: str = "",
    departure_to: str = "",
) -> BookingChecksResponse:
    apply_pending_traveltek_auto_booking_fields(db)
    safe_limit = max(1, min(limit, BOOKING_CHECK_ROW_LIMIT))
    bookings = list(
        db.scalars(
            filtered_booking_statement(
                search=search,
                company_filter=company_filter,
                archive_filter=archive_filter,
                commission_review_filter=commission_review_filter,
                departure_from=departure_from,
                departure_to=departure_to,
            )
        )
    )
    supplier_totals = grouped_supplier_totals(db)
    customer_totals = grouped_customer_totals(db)
    insurance_totals = grouped_insurance_totals(db)
    adjustments_by_booking = grouped_adjustments(db)

    rows: list[BookingCheckRow] = []
    total_matching = 0
    for booking in bookings:
        row = build_booking_check_row(
            booking,
            supplier_totals,
            customer_totals,
            insurance_totals,
            adjustments_by_booking,
        )
        if not row_matches_filters(row, review_filter, supplier_filter, customer_filter):
            continue
        total_matching += 1
        if len(rows) < safe_limit:
            rows.append(row)

    summary = build_booking_checks_summary(
        db,
        search=search,
        company_filter=company_filter,
        archive_filter=archive_filter,
        commission_review_filter=commission_review_filter,
        departure_from=departure_from,
        departure_to=departure_to,
    )
    return BookingChecksResponse(
        summary=summary,
        bookings=rows,
        total_matching=total_matching,
        returned_count=len(rows),
        limit=safe_limit,
    )


def build_booking_checks_summary(
    db: Session,
    limit: int = BOOKING_CHECK_ROW_LIMIT,
    search: str = "",
    company_filter: str = "all",
    archive_filter: str = "active",
    commission_review_filter: str = "all",
    departure_from: str = "",
    departure_to: str = "",
) -> BookingChecksSummary:
    apply_pending_traveltek_auto_booking_fields(db)
    bookings = list(
        db.scalars(
            filtered_booking_statement(
                search=search,
                company_filter=company_filter,
                archive_filter=archive_filter,
                commission_review_filter=commission_review_filter,
                departure_from=departure_from,
                departure_to=departure_to,
            ).limit(limit)
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
        row = build_booking_check_row(
            booking,
            supplier_totals,
            customer_totals,
            insurance_totals,
            adjustments_by_booking,
        )

        supplier_expected_matches += row.supplier_expected_check == "match"
        supplier_tt_matches += row.supplier_tt_check == "match"
        customer_tt_matches += row.customer_tt_check == "match"
        fully_matched += row.review_status == "match"
        error_count += row.review_status == "mismatch"
        awaiting_count += row.review_status == "waiting"

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
