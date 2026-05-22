from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.reporting import AuditLog, Booking, InsuranceCost, UploadBatch
from app.services.master_booking_import import (
    clean_text,
    normalise_booking_ref,
    normalise_header,
    parse_date,
    parse_datetime,
    parse_money,
    read_tabular_rows,
)


COLUMN_ALIASES = {
    "booking_ref": ("booking reference", "booking ref"),
    "external_reference": ("external reference",),
    "trade_code": ("trade code",),
    "trading_name": ("trading name",),
    "lead_name": ("lead name", "customer name"),
    "departure_date": ("departure date",),
    "supplement_type": ("supplement type", "insurance type"),
    "gross_amount": ("gross", "gross amount"),
    "discount_amount": ("discount", "discount amount"),
    "net_amount": ("net", "net amount"),
    "insurance_status": ("status",),
    "created_at_imported": ("created at", "created"),
    "last_update_imported": ("last update", "updated at", "last updated"),
}

REQUIRED_FIELDS = {"gross_amount"}
QUERY_CHUNK_SIZE = 500
ACTIVE_INSURANCE_STATUSES = {"booking", "booked", "confirmed", "live"}


@dataclass
class InsuranceImportResult:
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


def normalise_insurance_status(status: str | None) -> str | None:
    cleaned = " ".join((status or "").strip().lower().split())
    return cleaned or None


def is_active_insurance_status(status: str | None) -> bool:
    return normalise_insurance_status(status) in ACTIVE_INSURANCE_STATUSES


def insurance_cost_amount(gross_amount: Decimal, discount_amount: Decimal | None) -> Decimal:
    return (gross_amount - (discount_amount or Decimal("0.00"))).quantize(Decimal("0.01"))


def parse_insurance_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if text.endswith(" UTC"):
        text = text[:-4].strip()
    return parse_datetime(text) if text else None


def is_total_row(row: dict[str, Any], column_map: dict[str, str]) -> bool:
    booking_ref = clean_text(get_row_value(row, column_map, "booking_ref"))
    gross_amount = clean_text(get_row_value(row, column_map, "gross_amount"))
    return not booking_ref and bool(gross_amount) and gross_amount.strip().startswith("=")


def extract_booking_ref_from_external_reference(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None

    match = re.search(r"\bOTC[-_\s]?\d+\b|\bOTC\d+\b", text, flags=re.IGNORECASE)
    if not match:
        return None
    return normalise_booking_ref(match.group(0))


def resolve_insurance_booking_ref(row: dict[str, Any], column_map: dict[str, str]) -> str | None:
    external_booking_ref = extract_booking_ref_from_external_reference(
        get_row_value(row, column_map, "external_reference")
    )
    if external_booking_ref:
        return external_booking_ref
    return normalise_booking_ref(get_row_value(row, column_map, "booking_ref"))


def duplicate_text(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())


def duplicate_decimal(value: Decimal | None) -> str:
    if value is None:
        return ""
    return str(value.quantize(Decimal("0.01")))


def build_duplicate_key(values: dict[str, Any]) -> str:
    parts = (
        duplicate_text(values.get("_source_booking_ref") or values.get("booking_ref")),
        duplicate_text(values.get("external_reference")),
        duplicate_text(values.get("supplement_type")),
        values["departure_date"].isoformat() if values.get("departure_date") else "",
        duplicate_decimal(values.get("gross_amount")),
        duplicate_decimal(values.get("discount_amount")),
        duplicate_decimal(values.get("net_amount")),
        duplicate_text(values.get("insurance_status")),
        values["created_at_imported"].isoformat() if values.get("created_at_imported") else "",
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


def fetch_existing_duplicate_records_by_key(db: Session, duplicate_keys: set[str]) -> dict[str, InsuranceCost]:
    existing_duplicate_records_by_key: dict[str, InsuranceCost] = {}
    for duplicate_key_chunk in chunk_values(duplicate_keys):
        for cost in db.scalars(select(InsuranceCost).where(InsuranceCost.duplicate_key.in_(duplicate_key_chunk))).all():
            if cost.duplicate_key:
                existing_duplicate_records_by_key[cost.duplicate_key] = cost
    return existing_duplicate_records_by_key


def insurance_model_values(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if not key.startswith("_")}


def import_insurance_report(
    db: Session,
    upload_batch: UploadBatch,
    filename: str,
    content: bytes,
    actor_user_id: int | None,
) -> InsuranceImportResult:
    headers, rows = read_tabular_rows(filename, content)
    result = InsuranceImportResult(row_count=len(rows))
    column_map = build_column_map(headers)
    missing_fields = sorted(field for field in REQUIRED_FIELDS if field not in column_map)

    if missing_fields:
        result.rejected_rows = len(rows)
        friendly_names = ", ".join(missing_fields).replace("_", " ")
        result.errors.append(f"Required insurance column(s) missing: {friendly_names}.")
        return result

    parsed_costs: list[dict[str, Any]] = []
    booking_refs_to_match: set[str] = set()
    duplicate_keys_to_check: set[str] = set()

    for index, row in enumerate(rows, start=2):
        if is_total_row(row, column_map):
            result.row_count -= 1
            continue

        try:
            source_booking_ref = normalise_booking_ref(get_row_value(row, column_map, "booking_ref"))
            booking_ref = resolve_insurance_booking_ref(row, column_map)
            if not booking_ref:
                raise ValueError("Booking Reference or External Reference is missing.")

            gross_amount = parse_money(get_row_value(row, column_map, "gross_amount"))
            if gross_amount is None:
                raise ValueError("Gross is missing.")

            discount_amount = parse_money(get_row_value(row, column_map, "discount_amount")) or Decimal("0.00")
            net_amount = parse_money(get_row_value(row, column_map, "net_amount"))
            status = normalise_insurance_status(clean_text(get_row_value(row, column_map, "insurance_status")))

            booking_refs_to_match.add(booking_ref)
            values = {
                "upload_batch_id": upload_batch.id,
                "booking_id": None,
                "_source_booking_ref": source_booking_ref,
                "booking_ref": booking_ref,
                "external_reference": clean_text(get_row_value(row, column_map, "external_reference")),
                "trade_code": clean_text(get_row_value(row, column_map, "trade_code")),
                "trading_name": clean_text(get_row_value(row, column_map, "trading_name")),
                "lead_name": clean_text(get_row_value(row, column_map, "lead_name")),
                "departure_date": parse_date(get_row_value(row, column_map, "departure_date")),
                "supplement_type": clean_text(get_row_value(row, column_map, "supplement_type")),
                "gross_amount": gross_amount,
                "discount_amount": discount_amount,
                "net_amount": net_amount,
                "insurance_cost_amount": insurance_cost_amount(gross_amount, discount_amount),
                "insurance_status": status,
                "created_at_imported": parse_insurance_datetime(
                    get_row_value(row, column_map, "created_at_imported")
                ),
                "last_update_imported": parse_insurance_datetime(
                    get_row_value(row, column_map, "last_update_imported")
                ),
                "match_status": "unmatched",
            }
            duplicate_key = build_duplicate_key(values)
            values["duplicate_key"] = duplicate_key
            duplicate_keys_to_check.add(duplicate_key)
            parsed_costs.append(values)
        except ValueError as exc:
            result.rejected_rows += 1
            result.errors.append(f"Row {index}: {exc}")

    booking_ids_by_ref = fetch_booking_ids_by_ref(db, booking_refs_to_match)
    existing_duplicate_records_by_key = fetch_existing_duplicate_records_by_key(db, duplicate_keys_to_check)
    duplicate_keys_in_this_upload: set[str] = set()

    insurance_costs = []
    updated_existing_rows = 0
    for values in parsed_costs:
        booking_id = booking_ids_by_ref.get(values["booking_ref"] or "")
        values["booking_id"] = booking_id
        values["match_status"] = "matched" if booking_id else "unmatched"
        duplicate_key = values["duplicate_key"]
        model_values = insurance_model_values(values)
        existing_cost = existing_duplicate_records_by_key.get(duplicate_key)
        if existing_cost is not None:
            for field_name, value in model_values.items():
                setattr(existing_cost, field_name, value)
            existing_cost.is_duplicate = False
            updated_existing_rows += 1
            duplicate_keys_in_this_upload.add(duplicate_key)
            continue

        model_values["is_duplicate"] = duplicate_key in duplicate_keys_in_this_upload
        duplicate_keys_in_this_upload.add(duplicate_key)
        insurance_costs.append(InsuranceCost(**model_values))

    if insurance_costs:
        db.add_all(insurance_costs)
    result.accepted_rows = len(insurance_costs) + updated_existing_rows

    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action="insurance_import",
            table_name="upload_batches",
            record_id=upload_batch.id,
            description=(
                f"Insurance import accepted {result.accepted_rows} row(s) "
                f"and rejected {result.rejected_rows} row(s)."
            ),
        )
    )
    return result
