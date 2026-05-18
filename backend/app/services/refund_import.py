from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.reporting import AuditLog, Booking, ExceptionRecord, Refund, UploadBatch
from app.services.master_booking_import import (
    clean_text,
    normalise_header,
    parse_date,
    parse_money,
    read_tabular_rows,
)


COLUMN_ALIASES = {
    "booking_ref": ("booking ref", "booking reference", "booking_ref"),
    "customer_name": ("customer name", "customer", "passenger name"),
    "refund_reason": ("refund reason", "reason", "refund_reason"),
    "refund_amount_due": ("refund amount due", "amount due", "refund due", "refund_amount_due"),
    "refund_amount_paid": ("refund amount paid", "amount paid", "refund paid", "refund_amount_paid"),
    "refund_status": ("refund status", "status", "refund_status"),
    "supplier_refund_expected": (
        "supplier refund expected",
        "supplier expected",
        "supplier_refund_expected",
    ),
    "supplier_refund_received": (
        "supplier refund received",
        "supplier received",
        "supplier_refund_received",
    ),
    "due_date": ("due date", "refund due date", "due_date"),
    "paid_date": ("paid date", "refund paid date", "paid_date"),
}

REQUIRED_FIELDS = {"refund_amount_due"}
PAID_STATUSES = {"paid", "refunded", "complete", "completed", "settled"}
CANCELLED_STATUSES = {"cancelled", "canceled", "void"}


@dataclass
class RefundImportResult:
    row_count: int = 0
    accepted_rows: int = 0
    rejected_rows: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def error_summary(self) -> str | None:
        if not self.errors:
            return None
        preview = self.errors[:10]
        remaining = len(self.errors) - len(preview)
        suffix = f" Plus {remaining} more error(s)." if remaining > 0 else ""
        return " ".join(preview) + suffix


def build_column_map(headers: list[str]) -> dict[str, str]:
    normalised_to_original = {normalise_header(header): header for header in headers}
    column_map = {}
    for target_field, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            original_header = normalised_to_original.get(normalise_header(alias))
            if original_header is not None:
                column_map[target_field] = original_header
                break
    return column_map


def get_row_value(row: dict[str, Any], column_map: dict[str, str], field_name: str) -> Any:
    header = column_map.get(field_name)
    if header is None:
        return None
    return row.get(header)


def normalise_refund_status(status: str | None, refund_due: Decimal, refund_paid: Decimal) -> str:
    cleaned = normalise_header(status or "")
    if cleaned in PAID_STATUSES or refund_paid >= refund_due:
        return "paid"
    if cleaned in CANCELLED_STATUSES:
        return "cancelled"
    if cleaned in {"part paid", "partially paid", "partial"}:
        return "partially_paid"
    if cleaned in {"awaiting supplier refund", "supplier refund pending"}:
        return "awaiting_supplier_refund"
    if refund_paid > Decimal("0.00"):
        return "partially_paid"
    return cleaned.replace(" ", "_") if cleaned else "due"


def unpaid_amount(refund_due: Decimal, refund_paid: Decimal) -> Decimal:
    amount = refund_due - refund_paid
    return amount if amount > Decimal("0.00") else Decimal("0.00")


def create_overdue_exception(db: Session, refund: Refund, unpaid: Decimal) -> None:
    db.add(
        ExceptionRecord(
            exception_type="refund_overdue",
            severity="high",
            status="open",
            title="Refund overdue",
            detail=(
                f"Refund for {refund.booking_ref or refund.customer_name or 'unmatched customer'} "
                f"is overdue with {unpaid} still unpaid."
            ),
            booking_id=refund.booking_id,
            booking_ref=refund.booking_ref,
            related_table="refunds",
            related_record_id=refund.id,
        )
    )


def import_refund_report(
    db: Session,
    upload_batch: UploadBatch,
    filename: str,
    content: bytes,
    actor_user_id: int | None,
) -> RefundImportResult:
    headers, rows = read_tabular_rows(filename, content)
    result = RefundImportResult(row_count=len(rows))
    column_map = build_column_map(headers)
    missing_fields = sorted(field for field in REQUIRED_FIELDS if field not in column_map)

    if missing_fields:
        result.rejected_rows = len(rows)
        friendly_names = ", ".join(missing_fields).replace("_", " ")
        result.errors.append(f"Required refund column(s) missing: {friendly_names}.")
        return result

    today = datetime.now(UTC).date()
    for index, row in enumerate(rows, start=2):
        try:
            refund_amount_due = parse_money(get_row_value(row, column_map, "refund_amount_due"))
            if refund_amount_due is None:
                raise ValueError("Refund Amount Due is missing.")

            refund_amount_paid = parse_money(get_row_value(row, column_map, "refund_amount_paid")) or Decimal("0.00")
            booking_ref = clean_text(get_row_value(row, column_map, "booking_ref"))
            booking = None
            if booking_ref:
                booking = db.scalar(select(Booking).where(Booking.booking_ref == booking_ref))

            due_date = parse_date(get_row_value(row, column_map, "due_date"))
            status = normalise_refund_status(
                clean_text(get_row_value(row, column_map, "refund_status")),
                refund_amount_due,
                refund_amount_paid,
            )
            unpaid = unpaid_amount(refund_amount_due, refund_amount_paid)
            if due_date and due_date < today and unpaid > Decimal("0.00") and status != "cancelled":
                status = "overdue"

            refund = Refund(
                upload_batch_id=upload_batch.id,
                booking_id=booking.id if booking else None,
                booking_ref=booking_ref,
                customer_name=clean_text(get_row_value(row, column_map, "customer_name")),
                refund_reason=clean_text(get_row_value(row, column_map, "refund_reason")),
                refund_amount_due=refund_amount_due,
                refund_amount_paid=refund_amount_paid,
                refund_status=status,
                supplier_refund_expected=parse_money(get_row_value(row, column_map, "supplier_refund_expected")),
                supplier_refund_received=parse_money(get_row_value(row, column_map, "supplier_refund_received")),
                due_date=due_date,
                paid_date=parse_date(get_row_value(row, column_map, "paid_date")),
            )
            db.add(refund)
            db.flush()

            if status == "overdue":
                create_overdue_exception(db, refund, unpaid)

            result.accepted_rows += 1
        except ValueError as exc:
            result.rejected_rows += 1
            result.errors.append(f"Row {index}: {exc}")

    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action="refund_import",
            table_name="upload_batches",
            record_id=upload_batch.id,
            description=(
                f"Refund import accepted {result.accepted_rows} row(s) "
                f"and rejected {result.rejected_rows} row(s)."
            ),
        )
    )
    return result
