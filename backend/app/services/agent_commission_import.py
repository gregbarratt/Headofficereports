from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.reporting import AgentCommission, AuditLog, Booking, UploadBatch
from app.services.master_booking_import import (
    clean_text,
    normalise_header,
    parse_date,
    parse_money,
    read_tabular_rows,
)


COLUMN_ALIASES = {
    "booking_ref": ("booking ref", "booking reference", "booking_ref"),
    "agent_name": ("agent name", "agent", "consultant", "consultant name"),
    "commission_basis": ("commission basis", "basis", "commission_basis"),
    "gross_commission": ("gross commission", "commission gross", "gross_commission"),
    "deductions": ("deductions", "commission deductions", "deduction"),
    "net_commission_due": ("net commission due", "net commission", "commission due", "net_commission_due"),
    "commission_status": ("commission status", "status", "commission_status"),
    "due_date": ("due date", "commission due date", "due_date"),
    "paid_date": ("paid date", "commission paid date", "paid_date"),
}

COMMISSION_STATUSES = {
    "accrued",
    "due",
    "paid",
    "withheld",
    "clawed_back",
    "cancelled",
}


@dataclass
class AgentCommissionImportResult:
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


def normalise_commission_status(status: str | None, net_commission_due: Decimal, paid_date_present: bool) -> str:
    cleaned = normalise_header(status or "").replace(" ", "_")
    if cleaned in {"clawed_back", "clawback", "clawed"}:
        return "clawed_back"
    if cleaned in {"cancelled", "canceled"}:
        return "cancelled"
    if cleaned in COMMISSION_STATUSES:
        return cleaned
    if paid_date_present or net_commission_due == Decimal("0.00"):
        return "paid"
    return "due"


def import_agent_commission_report(
    db: Session,
    upload_batch: UploadBatch,
    filename: str,
    content: bytes,
    actor_user_id: int | None,
) -> AgentCommissionImportResult:
    headers, rows = read_tabular_rows(filename, content)
    result = AgentCommissionImportResult(row_count=len(rows))
    column_map = build_column_map(headers)

    if "booking_ref" not in column_map:
        result.rejected_rows = len(rows)
        result.errors.append("Booking Ref column is required for agent commission imports.")
        return result

    for index, row in enumerate(rows, start=2):
        try:
            booking_ref = clean_text(get_row_value(row, column_map, "booking_ref"))
            if not booking_ref:
                raise ValueError("Booking Ref is missing.")

            gross_commission = parse_money(get_row_value(row, column_map, "gross_commission"))
            deductions = parse_money(get_row_value(row, column_map, "deductions")) or Decimal("0.00")
            net_commission_due = parse_money(get_row_value(row, column_map, "net_commission_due"))
            if gross_commission is None and net_commission_due is None:
                raise ValueError("Gross Commission or Net Commission Due is required.")
            if gross_commission is None:
                gross_commission = net_commission_due
            if net_commission_due is None and gross_commission is not None:
                net_commission_due = gross_commission - deductions

            paid_date = parse_date(get_row_value(row, column_map, "paid_date"))
            status = normalise_commission_status(
                clean_text(get_row_value(row, column_map, "commission_status")),
                net_commission_due or Decimal("0.00"),
                paid_date is not None,
            )
            booking = db.scalar(select(Booking).where(Booking.booking_ref == booking_ref))

            db.add(
                AgentCommission(
                    upload_batch_id=upload_batch.id,
                    booking_id=booking.id if booking else None,
                    booking_ref=booking_ref,
                    agent_name=clean_text(get_row_value(row, column_map, "agent_name")),
                    commission_basis=clean_text(get_row_value(row, column_map, "commission_basis")),
                    gross_commission=gross_commission,
                    deductions=deductions,
                    net_commission_due=net_commission_due,
                    commission_status=status,
                    due_date=parse_date(get_row_value(row, column_map, "due_date")),
                    paid_date=paid_date,
                )
            )
            result.accepted_rows += 1
        except ValueError as exc:
            result.rejected_rows += 1
            result.errors.append(f"Row {index}: {exc}")

    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action="agent_commission_import",
            table_name="upload_batches",
            record_id=upload_batch.id,
            description=(
                f"Agent commission import accepted {result.accepted_rows} row(s) "
                f"and rejected {result.rejected_rows} row(s)."
            ),
        )
    )
    return result
