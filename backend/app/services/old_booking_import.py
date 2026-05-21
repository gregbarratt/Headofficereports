from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.reporting import AuditLog, Booking, UploadBatch
from app.services.master_booking_import import (
    clean_text,
    determine_booking_company,
    normalise_booking_ref,
    normalise_header,
    parse_date,
    parse_datetime,
    parse_money,
    read_tabular_rows,
)


COLUMN_ALIASES = {
    "booking_ref": ("otc ref", "otc reference", "booking reference", "booking ref", "ref"),
    "first_name": ("first name",),
    "customer_last_name": ("last name", "surname", "customer"),
    "supplier_ref": ("supplier ref", "supplier reference"),
    "provider": ("provider atol holder", "provider", "atol holder"),
    "expected_supplier_nett": ("net rates", "nett", "net"),
    "gross_booking_value": ("price sold by otc", "price sold", "gross", "total cost", "total sell"),
    "booking_date": ("deposit date", "booking date", "date booked", "booked"),
    "departure_date": ("departure date", "depart"),
    "return_date": ("return date", "returned date"),
}

MONEY_FIELDS = {"expected_supplier_nett", "gross_booking_value"}


@dataclass
class OldBookingImportResult:
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


def build_old_booking_notes(row: dict[str, Any], column_map: dict[str, str]) -> str | None:
    supplier_ref = clean_text(get_row_value(row, column_map, "supplier_ref"))
    provider = clean_text(get_row_value(row, column_map, "provider"))
    parts = []
    if provider:
        parts.append(f"Provider / ATOL holder: {provider}")
    if supplier_ref:
        parts.append(f"Supplier ref: {supplier_ref}")
    return " | ".join(parts) if parts else "Old booking import"


def import_old_booking_report(
    db: Session,
    upload_batch: UploadBatch,
    filename: str,
    content: bytes,
    actor_user_id: int | None,
) -> OldBookingImportResult:
    headers, rows = read_tabular_rows(filename, content)
    result = OldBookingImportResult()
    column_map = build_column_map(headers)

    if "booking_ref" not in column_map:
        result.rejected_rows = len(rows)
        result.row_count = len(rows)
        result.errors.append("OTC Ref column is required for old booking imports.")
        return result

    for index, row in enumerate(rows, start=2):
        result.row_count += 1

        try:
            booking_ref = normalise_booking_ref(get_row_value(row, column_map, "booking_ref"))
            if not booking_ref:
                raise ValueError("OTC Ref is missing.")

            provider = clean_text(get_row_value(row, column_map, "provider"))
            notes = build_old_booking_notes(row, column_map)
            values = {
                "booking_ref": booking_ref,
                "booking_company": determine_booking_company(booking_ref),
                "imported_booking_status": "old booking",
                "normalised_status": "completed",
                "customer_last_name": clean_text(get_row_value(row, column_map, "customer_last_name")),
                "destination": provider,
                "travel_elements_raw": notes,
                "departure_date": parse_date(get_row_value(row, column_map, "departure_date")),
                "return_date": parse_date(get_row_value(row, column_map, "return_date")),
                "booking_date": parse_datetime(get_row_value(row, column_map, "booking_date")),
                "customer_balance_due_date": None,
                "imported_customer_outstanding": None,
                "imported_supplier_outstanding": None,
                "non_trusted_total_received": None,
                "non_trusted_paid_supplier": None,
                "non_trusted_projected_profit": None,
                "flight_included": False,
                "accommodation_included": False,
                "cruise_included": False,
                "extras_included": False,
                "package_included": False,
                "atol_review_status": "old booking review",
                "last_master_upload_batch_id": upload_batch.id,
            }

            for money_field in MONEY_FIELDS:
                values[money_field] = parse_money(get_row_value(row, column_map, money_field))

            booking = db.scalar(select(Booking).where(Booking.booking_ref == booking_ref))
            if booking is None:
                booking = Booking(**values)
                db.add(booking)
            else:
                for field_name, value in values.items():
                    setattr(booking, field_name, value)

            result.accepted_rows += 1
        except ValueError as exc:
            result.rejected_rows += 1
            result.errors.append(f"Row {index}: {exc}")

    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action="old_booking_import",
            table_name="upload_batches",
            record_id=upload_batch.id,
            description=(
                f"Old booking import accepted {result.accepted_rows} row(s) "
                f"and rejected {result.rejected_rows} row(s)."
            ),
        )
    )
    return result
