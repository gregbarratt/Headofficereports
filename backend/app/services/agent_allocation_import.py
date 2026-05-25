from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.reporting import AuditLog, Booking, UploadBatch
from app.services.master_booking_import import (
    clean_text,
    normalise_booking_ref,
    normalise_header,
    read_tabular_rows,
)


COLUMN_ALIASES = {
    "booking_ref": ("booking reference", "booking ref", "ref", "otc ref", "otc reference"),
    "agent_in_charge": ("agent name", "agent", "agent in charge", "consultant", "consultant name"),
    "customer_last_name": ("customer surname", "last name", "surname", "customer"),
    "allocation_status": ("status",),
}


@dataclass
class AgentAllocationImportResult:
    row_count: int = 0
    accepted_rows: int = 0
    rejected_rows: int = 0
    updated_rows: int = 0
    unchanged_rows: int = 0
    surname_filled_rows: int = 0
    surname_difference_rows: int = 0
    errors: list[str] = field(default_factory=list)
    changed_refs: list[str] = field(default_factory=list)

    @property
    def error_summary(self) -> str | None:
        summary = (
            f"Agent allocation import matched {self.accepted_rows} row(s), "
            f"updated {self.updated_rows} booking agent(s), "
            f"left {self.unchanged_rows} unchanged, "
            f"filled {self.surname_filled_rows} blank surname(s), "
            f"and found {self.surname_difference_rows} surname difference(s)."
        )
        if not self.errors:
            return summary

        preview = self.errors[:10]
        remaining = len(self.errors) - len(preview)
        suffix = f" Plus {remaining} more error(s)." if remaining > 0 else ""
        return summary + " " + " ".join(preview) + suffix


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


def comparable_name(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip().casefold()


def normalise_agent_booking_ref(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None

    direct_ref = normalise_booking_ref(text)
    if direct_ref and direct_ref != text.strip().upper():
        return direct_ref

    upper_text = text.upper()
    tta_match = re.search(r"\b(TTAS?|TTA)[-_\s]?0*(\d{3,})\b", upper_text)
    if tta_match:
        prefix = "TTAS" if tta_match.group(1).startswith("TTAS") else "TTA"
        return f"{prefix}-{int(tta_match.group(2)):07d}"

    otc_match = re.search(r"\b(?:OTC|OCT|OTG)[-_\s]?0*(\d+)\b", upper_text)
    if otc_match:
        digits = otc_match.group(1)
        if digits.startswith("1") and len(digits) >= 7:
            return f"OTC{digits}"
        return f"OTC-{int(digits):05d}"

    return direct_ref


def import_agent_allocation_report(
    db: Session,
    upload_batch: UploadBatch,
    filename: str,
    content: bytes,
    actor_user_id: int | None,
) -> AgentAllocationImportResult:
    headers, rows = read_tabular_rows(filename, content)
    result = AgentAllocationImportResult()
    column_map = build_column_map(headers)

    missing_columns = []
    if "booking_ref" not in column_map:
        missing_columns.append("Booking Reference")
    if "agent_in_charge" not in column_map:
        missing_columns.append("Agent Name")
    if missing_columns:
        result.row_count = len(rows)
        result.rejected_rows = len(rows)
        result.errors.append(f"Required agent allocation column(s) missing: {', '.join(missing_columns)}.")
        return result

    bookings_by_ref = {booking.booking_ref: booking for booking in db.scalars(select(Booking))}

    for index, row in enumerate(rows, start=2):
        result.row_count += 1
        try:
            booking_ref = normalise_agent_booking_ref(get_row_value(row, column_map, "booking_ref"))
            if not booking_ref:
                raise ValueError("Booking Reference is missing.")

            agent_name = clean_text(get_row_value(row, column_map, "agent_in_charge"))
            if not agent_name:
                raise ValueError("Agent Name is missing.")

            booking = bookings_by_ref.get(booking_ref)
            if booking is None:
                raise ValueError(f"Booking {booking_ref} was not found in the Head Office database yet.")

            current_agent = clean_text(booking.agent_in_charge)
            changed_booking = False
            if comparable_name(current_agent) != comparable_name(agent_name):
                booking.agent_in_charge = agent_name
                result.updated_rows += 1
                result.changed_refs.append(booking_ref)
                changed_booking = True
            else:
                result.unchanged_rows += 1

            customer_surname = clean_text(get_row_value(row, column_map, "customer_last_name"))
            current_surname = clean_text(booking.customer_last_name)
            if customer_surname and not current_surname:
                booking.customer_last_name = customer_surname
                result.surname_filled_rows += 1
                changed_booking = True
            elif customer_surname and current_surname and comparable_name(customer_surname) != comparable_name(current_surname):
                result.surname_difference_rows += 1

            if changed_booking:
                db.add(booking)

            result.accepted_rows += 1
        except ValueError as exc:
            result.rejected_rows += 1
            result.errors.append(f"Row {index}: {exc}")

    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action="agent_allocation_import",
            table_name="upload_batches",
            record_id=upload_batch.id,
            description=(
                f"Agent allocation import matched {result.accepted_rows} row(s), "
                f"updated {result.updated_rows} booking agent(s), and rejected {result.rejected_rows} row(s)."
            ),
            after_data={
                "matched_rows": result.accepted_rows,
                "updated_rows": result.updated_rows,
                "unchanged_rows": result.unchanged_rows,
                "surname_filled_rows": result.surname_filled_rows,
                "surname_difference_rows": result.surname_difference_rows,
                "rejected_rows": result.rejected_rows,
                "changed_booking_refs_sample": result.changed_refs[:50],
            },
        )
    )
    return result
