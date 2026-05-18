from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.reporting import (
    AgentCommission,
    AuditLog,
    Booking,
    CustomerPayment,
    Refund,
    SupplierPayment,
    WeeklySnapshot,
    WeeklySnapshotBooking,
)


ZERO = Decimal("0.00")
COMMISSION_DUE_STATUSES = {"accrued", "due", "withheld"}


@dataclass(frozen=True)
class Movement:
    booking_ref: str
    movement_type: str
    field_name: str
    previous_value: str | None
    current_value: str | None
    description: str


@dataclass(frozen=True)
class MovementSummary:
    movement_count: int
    new_bookings: int
    cancelled_bookings: int
    completed_bookings: int
    changed_booking_value: int
    changed_supplier_cost: int
    changed_payment_position: int
    changed_supplier_payment_position: int
    changed_refund_position: int
    changed_commission_position: int
    changed_atol_status: int


def money(value: Decimal | None) -> Decimal:
    if value is None:
        return ZERO
    return Decimal(value).quantize(Decimal("0.01"))


def current_week_range(reference_date: date | None = None) -> tuple[date, date]:
    today = reference_date or datetime.now(UTC).date()
    week_start = today - timedelta(days=today.weekday())
    return week_start, week_start + timedelta(days=6)


def atol_required_from_status(status: str | None) -> bool:
    cleaned = (status or "").lower()
    if not cleaned or "non-flight" in cleaned or "flight-only" in cleaned:
        return False
    return "atol required" in cleaned or "likely required" in cleaned or cleaned == "atol review"


def add_amount(target: dict[str, Decimal], booking_ref: str | None, amount: Decimal | None) -> None:
    if not booking_ref:
        return
    target[booking_ref] = target.get(booking_ref, ZERO) + money(amount)


def build_current_snapshot_rows(db: Session, snapshot_id: int) -> list[WeeklySnapshotBooking]:
    bookings = list(db.scalars(select(Booking).order_by(Booking.booking_ref)))
    customer_totals: dict[str, Decimal] = {}
    card_fee_totals: dict[str, Decimal] = {}
    supplier_totals: dict[str, Decimal] = {}
    refund_due_totals: dict[str, Decimal] = {}
    refund_paid_totals: dict[str, Decimal] = {}
    commission_due_totals: dict[str, Decimal] = {}

    for payment in db.scalars(select(CustomerPayment)):
        if payment.match_confidence == "unmatched":
            continue
        add_amount(customer_totals, payment.booking_ref, payment.gross_amount)
        add_amount(card_fee_totals, payment.booking_ref, payment.fee_amount)

    for payment in db.scalars(select(SupplierPayment)):
        add_amount(supplier_totals, payment.booking_ref, payment.supplier_payment_amount)

    for refund in db.scalars(select(Refund)):
        add_amount(refund_due_totals, refund.booking_ref, refund.refund_amount_due)
        add_amount(refund_paid_totals, refund.booking_ref, refund.refund_amount_paid)

    for commission in db.scalars(select(AgentCommission)):
        if (commission.commission_status or "").lower() in COMMISSION_DUE_STATUSES:
            add_amount(commission_due_totals, commission.booking_ref, commission.net_commission_due)

    rows = []
    for booking in bookings:
        customer_total = customer_totals.get(booking.booking_ref, ZERO)
        card_fee_total = card_fee_totals.get(booking.booking_ref, ZERO)
        supplier_total = supplier_totals.get(booking.booking_ref, ZERO)
        refund_paid_total = refund_paid_totals.get(booking.booking_ref, ZERO)
        calculated_trust_balance = customer_total - card_fee_total - supplier_total - refund_paid_total

        rows.append(
            WeeklySnapshotBooking(
                weekly_snapshot_id=snapshot_id,
                booking_id=booking.id,
                booking_ref=booking.booking_ref,
                booking_status=booking.normalised_status,
                gross_booking_value=booking.gross_booking_value,
                expected_supplier_nett=booking.expected_supplier_nett,
                customer_payments_total=money(customer_total),
                card_fees_total=money(card_fee_total),
                supplier_payments_total=money(supplier_total),
                refunds_due_total=money(refund_due_totals.get(booking.booking_ref, ZERO)),
                refunds_paid_total=money(refund_paid_total),
                commission_due_total=money(commission_due_totals.get(booking.booking_ref, ZERO)),
                calculated_trust_balance=money(calculated_trust_balance),
                atol_required=atol_required_from_status(booking.atol_review_status),
                atol_certificate_issued=booking.atol_certificate_issued,
            )
        )
    return rows


def generate_weekly_snapshot(
    db: Session,
    actor_user_id: int | None,
    reference_date: date | None = None,
) -> WeeklySnapshot:
    week_start, week_end = current_week_range(reference_date)
    now = datetime.now(UTC)
    snapshot = db.scalar(
        select(WeeklySnapshot).where(
            WeeklySnapshot.week_start_date == week_start,
            WeeklySnapshot.week_end_date == week_end,
        )
    )

    if snapshot is None:
        snapshot = WeeklySnapshot(
            week_start_date=week_start,
            week_end_date=week_end,
            status="generated",
            generated_by_user_id=actor_user_id,
            generated_at=now,
        )
        db.add(snapshot)
        db.flush()
    else:
        db.execute(delete(WeeklySnapshotBooking).where(WeeklySnapshotBooking.weekly_snapshot_id == snapshot.id))
        snapshot.status = "generated"
        snapshot.generated_by_user_id = actor_user_id
        snapshot.generated_at = now
        db.flush()

    for row in build_current_snapshot_rows(db, snapshot.id):
        db.add(row)

    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action="weekly_snapshot_generation",
            table_name="weekly_snapshots",
            record_id=snapshot.id,
            description=f"Weekly snapshot generated for {week_start.isoformat()} to {week_end.isoformat()}.",
        )
    )
    db.flush()
    return snapshot


def previous_snapshot(db: Session, snapshot: WeeklySnapshot) -> WeeklySnapshot | None:
    return db.scalar(
        select(WeeklySnapshot)
        .where(WeeklySnapshot.week_start_date < snapshot.week_start_date)
        .order_by(WeeklySnapshot.week_start_date.desc(), WeeklySnapshot.id.desc())
        .limit(1)
    )


def latest_snapshot(db: Session) -> WeeklySnapshot | None:
    return db.scalar(
        select(WeeklySnapshot)
        .order_by(WeeklySnapshot.week_start_date.desc(), WeeklySnapshot.id.desc())
        .limit(1)
    )


def snapshot_rows(db: Session, snapshot_id: int) -> list[WeeklySnapshotBooking]:
    return list(
        db.scalars(
            select(WeeklySnapshotBooking)
            .where(WeeklySnapshotBooking.weekly_snapshot_id == snapshot_id)
            .order_by(WeeklySnapshotBooking.booking_ref)
        )
    )


def value_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return str(money(value))
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def values_differ(previous: Any, current: Any) -> bool:
    if isinstance(previous, Decimal) or isinstance(current, Decimal):
        return money(previous) != money(current)
    return previous != current


def make_movement(
    row: WeeklySnapshotBooking,
    previous_value: Any,
    current_value: Any,
    movement_type: str,
    field_name: str,
    description: str,
) -> Movement:
    return Movement(
        booking_ref=row.booking_ref,
        movement_type=movement_type,
        field_name=field_name,
        previous_value=value_text(previous_value),
        current_value=value_text(current_value),
        description=description,
    )


def compare_field(
    movements: list[Movement],
    previous_row: WeeklySnapshotBooking,
    current_row: WeeklySnapshotBooking,
    field_name: str,
    movement_type: str,
    description: str,
) -> None:
    previous_value = getattr(previous_row, field_name)
    current_value = getattr(current_row, field_name)
    if values_differ(previous_value, current_value):
        movements.append(
            make_movement(
                current_row,
                previous_value,
                current_value,
                movement_type,
                field_name,
                description,
            )
        )


def compare_snapshots(
    previous_rows: list[WeeklySnapshotBooking],
    current_rows: list[WeeklySnapshotBooking],
) -> list[Movement]:
    previous_by_ref = {row.booking_ref: row for row in previous_rows}
    current_by_ref = {row.booking_ref: row for row in current_rows}
    movements: list[Movement] = []

    for booking_ref, current_row in current_by_ref.items():
        previous_row = previous_by_ref.get(booking_ref)
        if previous_row is None:
            movements.append(
                Movement(
                    booking_ref=booking_ref,
                    movement_type="new_booking",
                    field_name="booking_ref",
                    previous_value=None,
                    current_value=booking_ref,
                    description="Booking appears in this snapshot for the first time.",
                )
            )
            continue

        if values_differ(previous_row.booking_status, current_row.booking_status):
            current_status = (current_row.booking_status or "").lower()
            if current_status == "cancelled":
                movement_type = "cancelled_booking"
                description = "Booking changed to cancelled."
            elif current_status == "completed":
                movement_type = "completed_booking"
                description = "Booking changed to completed."
            else:
                movement_type = "status_changed"
                description = "Booking status changed."
            movements.append(
                make_movement(
                    current_row,
                    previous_row.booking_status,
                    current_row.booking_status,
                    movement_type,
                    "booking_status",
                    description,
                )
            )

        compare_field(
            movements,
            previous_row,
            current_row,
            "gross_booking_value",
            "changed_booking_value",
            "Gross booking value changed.",
        )
        compare_field(
            movements,
            previous_row,
            current_row,
            "expected_supplier_nett",
            "changed_supplier_cost",
            "Expected supplier nett changed.",
        )
        compare_field(
            movements,
            previous_row,
            current_row,
            "customer_payments_total",
            "changed_payment_position",
            "Customer payment total changed.",
        )
        compare_field(
            movements,
            previous_row,
            current_row,
            "card_fees_total",
            "changed_payment_position",
            "Card fee total changed.",
        )
        compare_field(
            movements,
            previous_row,
            current_row,
            "supplier_payments_total",
            "changed_supplier_payment_position",
            "Supplier payment total changed.",
        )
        compare_field(
            movements,
            previous_row,
            current_row,
            "refunds_due_total",
            "changed_refund_position",
            "Refund amount due changed.",
        )
        compare_field(
            movements,
            previous_row,
            current_row,
            "refunds_paid_total",
            "changed_refund_position",
            "Refund amount paid changed.",
        )
        compare_field(
            movements,
            previous_row,
            current_row,
            "commission_due_total",
            "changed_commission_position",
            "Commission due total changed.",
        )
        compare_field(
            movements,
            previous_row,
            current_row,
            "atol_required",
            "changed_atol_status",
            "ATOL required flag changed.",
        )
        compare_field(
            movements,
            previous_row,
            current_row,
            "atol_certificate_issued",
            "changed_atol_status",
            "ATOL certificate issued flag changed.",
        )

    for booking_ref, previous_row in previous_by_ref.items():
        if booking_ref not in current_by_ref:
            movements.append(
                Movement(
                    booking_ref=booking_ref,
                    movement_type="removed_booking",
                    field_name="booking_ref",
                    previous_value=booking_ref,
                    current_value=None,
                    description="Booking was present in the previous snapshot but is not present now.",
                )
            )

    return movements


def movement_summary(movements: list[Movement]) -> MovementSummary:
    def count(movement_type: str) -> int:
        return len({movement.booking_ref for movement in movements if movement.movement_type == movement_type})

    return MovementSummary(
        movement_count=len(movements),
        new_bookings=count("new_booking"),
        cancelled_bookings=count("cancelled_booking"),
        completed_bookings=count("completed_booking"),
        changed_booking_value=count("changed_booking_value"),
        changed_supplier_cost=count("changed_supplier_cost"),
        changed_payment_position=count("changed_payment_position"),
        changed_supplier_payment_position=count("changed_supplier_payment_position"),
        changed_refund_position=count("changed_refund_position"),
        changed_commission_position=count("changed_commission_position"),
        changed_atol_status=count("changed_atol_status"),
    )
