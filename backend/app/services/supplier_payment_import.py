from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.reporting import AuditLog, Booking, SupplierPayment, UploadBatch
from app.services.master_booking_import import (
    clean_text,
    normalise_header,
    parse_date,
    parse_money,
    read_tabular_rows,
)


COLUMN_ALIASES = {
    "supplier_payment_date": ("transaction date", "supplier payment date", "payment date"),
    "booking_ref": ("booking reference", "booking ref"),
    "product_type": ("product", "product type"),
    "supplier_name": ("supplier", "supplier name"),
    "payment_supplier_name": ("payment supplier", "payment supplier name"),
    "booking_date_imported": ("booking date", "date booked"),
    "departure_date_imported": ("departure date",),
    "supplier_payment_method": ("payment method", "supplier payment method"),
    "supplier_payment_amount": ("payment value", "payment amount", "supplier payment amount"),
    "associated_vat": ("associated vat", "vat"),
}

REQUIRED_FIELDS = {"booking_ref", "supplier_payment_amount"}
QUERY_CHUNK_SIZE = 500


@dataclass
class SupplierPaymentImportResult:
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
            original_header = normalised_to_original.get(alias)
            if original_header is not None:
                column_map[target_field] = original_header
                break
    return column_map


def get_row_value(row: dict[str, Any], column_map: dict[str, str], field_name: str) -> Any:
    header = column_map.get(field_name)
    if header is None:
        return None
    return row.get(header)


def duplicate_text(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())


def duplicate_decimal(value: Decimal | None) -> str:
    if value is None:
        return ""
    return str(value.quantize(Decimal("0.01")))


def build_duplicate_key(values: dict[str, Any]) -> str:
    parts = (
        duplicate_text(values.get("booking_ref")),
        duplicate_text(values.get("supplier_name")),
        duplicate_text(values.get("payment_supplier_name")),
        values["supplier_payment_date"].isoformat() if values.get("supplier_payment_date") else "",
        duplicate_text(values.get("supplier_payment_method")),
        duplicate_decimal(values.get("supplier_payment_amount")),
        duplicate_decimal(values.get("associated_vat")),
    )
    return "|".join(parts)


def chunk_values(values: set[str], size: int = QUERY_CHUNK_SIZE) -> list[list[str]]:
    ordered_values = sorted(value for value in values if value)
    return [ordered_values[index : index + size] for index in range(0, len(ordered_values), size)]


def fetch_booking_ids_by_ref(db: Session, booking_refs: set[str]) -> dict[str, int]:
    booking_ids: dict[str, int] = {}
    for booking_ref_chunk in chunk_values(booking_refs):
        rows = db.execute(
            select(Booking.booking_ref, Booking.id).where(Booking.booking_ref.in_(booking_ref_chunk))
        ).all()
        booking_ids.update({booking_ref: booking_id for booking_ref, booking_id in rows})
    return booking_ids


def fetch_existing_duplicate_keys(db: Session, duplicate_keys: set[str]) -> set[str]:
    existing_duplicate_keys: set[str] = set()
    for duplicate_key_chunk in chunk_values(duplicate_keys):
        existing_duplicate_keys.update(
            db.scalars(
                select(SupplierPayment.duplicate_key).where(SupplierPayment.duplicate_key.in_(duplicate_key_chunk))
            ).all()
        )
    return existing_duplicate_keys


def import_supplier_payment_report(
    db: Session,
    upload_batch: UploadBatch,
    filename: str,
    content: bytes,
    actor_user_id: int | None,
) -> SupplierPaymentImportResult:
    headers, rows = read_tabular_rows(filename, content)
    result = SupplierPaymentImportResult(row_count=len(rows))
    column_map = build_column_map(headers)
    missing_fields = sorted(field for field in REQUIRED_FIELDS if field not in column_map)

    if missing_fields:
        result.rejected_rows = len(rows)
        friendly_names = ", ".join(missing_fields).replace("_", " ")
        result.errors.append(f"Required supplier payment column(s) missing: {friendly_names}.")
        return result

    parsed_payments: list[dict[str, Any]] = []
    booking_refs_to_match: set[str] = set()
    duplicate_keys_to_check: set[str] = set()

    for index, row in enumerate(rows, start=2):
        try:
            payment_amount = parse_money(get_row_value(row, column_map, "supplier_payment_amount"))
            if payment_amount is None:
                raise ValueError("Payment Value is missing.")

            booking_ref = clean_text(get_row_value(row, column_map, "booking_ref"))
            if booking_ref:
                booking_refs_to_match.add(booking_ref)

            values = {
                "upload_batch_id": upload_batch.id,
                "booking_id": None,
                "booking_ref": booking_ref,
                "supplier_payment_date": parse_date(get_row_value(row, column_map, "supplier_payment_date")),
                "product_type": clean_text(get_row_value(row, column_map, "product_type")),
                "supplier_name": clean_text(get_row_value(row, column_map, "supplier_name")),
                "payment_supplier_name": clean_text(get_row_value(row, column_map, "payment_supplier_name")),
                "booking_date_imported": parse_date(get_row_value(row, column_map, "booking_date_imported")),
                "departure_date_imported": parse_date(get_row_value(row, column_map, "departure_date_imported")),
                "supplier_payment_method": clean_text(get_row_value(row, column_map, "supplier_payment_method")),
                "supplier_payment_amount": payment_amount,
                "associated_vat": parse_money(get_row_value(row, column_map, "associated_vat")),
                "match_status": "unmatched",
            }
            duplicate_key = build_duplicate_key(values)
            values["duplicate_key"] = duplicate_key
            duplicate_keys_to_check.add(duplicate_key)
            parsed_payments.append(values)
        except ValueError as exc:
            result.rejected_rows += 1
            result.errors.append(f"Row {index}: {exc}")

    booking_ids_by_ref = fetch_booking_ids_by_ref(db, booking_refs_to_match)
    existing_duplicate_keys = fetch_existing_duplicate_keys(db, duplicate_keys_to_check)
    duplicate_keys_in_this_upload: set[str] = set()

    supplier_payments = []
    for values in parsed_payments:
        booking_id = booking_ids_by_ref.get(values["booking_ref"] or "")
        values["booking_id"] = booking_id
        values["match_status"] = "matched" if booking_id else "unmatched"
        duplicate_key = values["duplicate_key"]
        values["is_duplicate"] = duplicate_key in duplicate_keys_in_this_upload or duplicate_key in existing_duplicate_keys
        duplicate_keys_in_this_upload.add(duplicate_key)
        supplier_payments.append(SupplierPayment(**values))

    if supplier_payments:
        db.add_all(supplier_payments)
        result.accepted_rows = len(supplier_payments)

    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action="supplier_payment_import",
            table_name="upload_batches",
            record_id=upload_batch.id,
            description=(
                f"Supplier payment import accepted {result.accepted_rows} row(s) "
                f"and rejected {result.rejected_rows} row(s)."
            ),
        )
    )
    return result
