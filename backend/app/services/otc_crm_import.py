from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.reporting import AuditLog, Booking, OtcCrmBookingRow, UploadBatch
from app.services.agent_allocation_import import comparable_name
from app.services.master_booking_import import (
    clean_text,
    normalise_booking_ref,
    normalise_header,
    parse_date,
    parse_int,
    parse_money,
    read_tabular_rows,
)


COLUMN_ALIASES = {
    "crm_booking_ref": ("booking ref", "crm booking ref"),
    "booking_ref": ("otc reference number", "otc reference", "otc booking reference", "booking reference"),
    "customer_name": ("customer name", "customer", "lead name"),
    "email": ("email", "email address"),
    "destination": ("destination",),
    "gross_amount": ("gross", "gross pound", "gross gbp", "gross amount", "gross l", "gross ps"),
    "net_amount": ("net", "net pound", "net gbp", "net amount", "net l", "net ps"),
    "profit_amount": ("profit", "profit pound", "profit gbp", "profit amount", "profit l", "profit ps"),
    "qc_status": ("qc status", "status"),
    "agent_name": ("agent", "agent name", "sales consultant", "consultant"),
    "commission_amount": ("commission", "commission pound", "commission gbp", "commission amount", "commission l"),
    "passenger_count": ("number of passengers", "passengers", "pax", "passenger count"),
    "departure_date": ("departure date", "depart date", "depart"),
    "return_date": ("return date", "returned date", "return"),
    "created_date": ("created date", "created", "booking created date"),
}

REQUIRED_FIELDS = {"booking_ref", "agent_name"}


@dataclass
class OtcCrmImportResult:
    row_count: int = 0
    accepted_rows: int = 0
    rejected_rows: int = 0
    matched_rows: int = 0
    unmatched_rows: int = 0
    updated_agent_rows: int = 0
    different_rows: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def error_summary(self) -> str | None:
        summary = (
            f"OTC CRM import stored {self.accepted_rows} row(s), "
            f"matched {self.matched_rows}, unmatched {self.unmatched_rows}, "
            f"updated {self.updated_agent_rows} booking agent(s), "
            f"and found {self.different_rows} CRM vs Traveltek difference row(s)."
        )
        if not self.errors:
            return summary
        preview = self.errors[:10]
        remaining = len(self.errors) - len(preview)
        suffix = f" Plus {remaining} more error(s)." if remaining > 0 else ""
        return f"{summary} {' '.join(preview)}{suffix}"


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


def normalise_crm_booking_ref(value: Any) -> str | None:
    text = clean_text(value)
    return text.upper() if text else None


def money_equal(left: Decimal | None, right: Decimal | None) -> bool:
    if left is None or right is None:
        return True
    return left.quantize(Decimal("0.01")) == right.quantize(Decimal("0.01"))


def text_equal(left: str | None, right: str | None) -> bool:
    left_text = " ".join((left or "").strip().split()).casefold()
    right_text = " ".join((right or "").strip().split()).casefold()
    if not left_text or not right_text:
        return True
    return left_text == right_text


def name_equal(left: str | None, right: str | None) -> bool:
    left_text = " ".join((left or "").strip().split()).casefold()
    right_text = " ".join((right or "").strip().split()).casefold()
    if not left_text or not right_text:
        return True
    return left_text == right_text or right_text in left_text or left_text in right_text


def value_equal(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return True
    return left == right


def comparison_notes(values: dict[str, Any], booking: Booking | None) -> tuple[str, str | None]:
    if booking is None:
        return "unmatched", "No booking found for the OTC reference in the CRM file."

    differences = []
    if not name_equal(values.get("customer_name"), booking.customer_last_name):
        differences.append("customer / lead name")
    if not text_equal(values.get("destination"), booking.destination):
        differences.append("destination")
    if not money_equal(values.get("gross_amount"), booking.gross_booking_value):
        differences.append("gross")
    if not money_equal(values.get("net_amount"), booking.expected_supplier_nett):
        differences.append("net")
    if not value_equal(values.get("passenger_count"), booking.passenger_count):
        differences.append("passenger count")
    if not value_equal(values.get("departure_date"), booking.departure_date):
        differences.append("departure date")
    if not value_equal(values.get("return_date"), booking.return_date):
        differences.append("return date")

    if not differences:
        return "matched", None
    return "different", "CRM differs from Traveltek/system for: " + ", ".join(differences) + "."


def import_otc_crm_report(
    db: Session,
    upload_batch: UploadBatch,
    filename: str,
    content: bytes,
    actor_user_id: int | None,
) -> OtcCrmImportResult:
    headers, rows = read_tabular_rows(filename, content)
    result = OtcCrmImportResult(row_count=len(rows))
    column_map = build_column_map(headers)

    missing_fields = sorted(field for field in REQUIRED_FIELDS if field not in column_map)
    if missing_fields:
        friendly = ", ".join(field.replace("_", " ") for field in missing_fields)
        result.rejected_rows = len(rows)
        result.errors.append(f"Required OTC CRM column(s) missing: {friendly}.")
        return result

    # Keep only the latest import rows in the comparison screen.
    db.execute(delete(OtcCrmBookingRow))

    bookings_by_ref = {booking.booking_ref: booking for booking in db.scalars(select(Booking))}

    for index, row in enumerate(rows, start=2):
        try:
            booking_ref = normalise_booking_ref(get_row_value(row, column_map, "booking_ref"))
            if not booking_ref:
                raise ValueError("Otc Reference Number is missing.")

            agent_name = clean_text(get_row_value(row, column_map, "agent_name"))
            if not agent_name:
                raise ValueError("Agent is missing.")

            values = {
                "upload_batch_id": upload_batch.id,
                "crm_booking_ref": normalise_crm_booking_ref(get_row_value(row, column_map, "crm_booking_ref")),
                "booking_ref": booking_ref,
                "customer_name": clean_text(get_row_value(row, column_map, "customer_name")),
                "email": clean_text(get_row_value(row, column_map, "email")),
                "destination": clean_text(get_row_value(row, column_map, "destination")),
                "agent_name": agent_name,
                "qc_status": clean_text(get_row_value(row, column_map, "qc_status")),
                "gross_amount": parse_money(get_row_value(row, column_map, "gross_amount")),
                "net_amount": parse_money(get_row_value(row, column_map, "net_amount")),
                "profit_amount": parse_money(get_row_value(row, column_map, "profit_amount")),
                "commission_amount": parse_money(get_row_value(row, column_map, "commission_amount")),
                "passenger_count": parse_int(get_row_value(row, column_map, "passenger_count")),
                "departure_date": parse_date(get_row_value(row, column_map, "departure_date")),
                "return_date": parse_date(get_row_value(row, column_map, "return_date")),
                "created_date": parse_date(get_row_value(row, column_map, "created_date")),
            }

            booking = bookings_by_ref.get(booking_ref)
            previous_agent = clean_text(booking.agent_in_charge) if booking else None
            agent_updated = False
            if booking is not None:
                result.matched_rows += 1
                if comparable_name(previous_agent) != comparable_name(agent_name):
                    booking.agent_in_charge = agent_name
                    db.add(booking)
                    result.updated_agent_rows += 1
                    agent_updated = True
            else:
                result.unmatched_rows += 1

            comparison_status, notes = comparison_notes(values, booking)
            if comparison_status == "different":
                result.different_rows += 1

            db.add(
                OtcCrmBookingRow(
                    **values,
                    booking_id=booking.id if booking else None,
                    previous_agent_name=previous_agent,
                    agent_updated=agent_updated,
                    match_status="matched" if booking else "unmatched",
                    comparison_status=comparison_status,
                    comparison_notes=notes,
                )
            )
            result.accepted_rows += 1
        except ValueError as exc:
            result.rejected_rows += 1
            result.errors.append(f"Row {index}: {exc}")

    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action="otc_crm_import",
            table_name="otc_crm_booking_rows",
            record_id=upload_batch.id,
            description=(
                f"OTC CRM import stored {result.accepted_rows} row(s), matched {result.matched_rows}, "
                f"updated {result.updated_agent_rows} booking agent(s), and rejected {result.rejected_rows} row(s)."
            ),
            after_data={
                "accepted_rows": result.accepted_rows,
                "matched_rows": result.matched_rows,
                "unmatched_rows": result.unmatched_rows,
                "updated_agent_rows": result.updated_agent_rows,
                "different_rows": result.different_rows,
                "rejected_rows": result.rejected_rows,
            },
        )
    )
    return result
