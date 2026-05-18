from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.reporting import AuditLog, Booking, UploadBatch


COLUMN_ALIASES = {
    "status": ("status",),
    "customer_last_name": ("last name",),
    "destination": ("destination",),
    "travel_elements_raw": ("elements",),
    "booking_ref": ("booking reference", "booking ref"),
    "departure_date": ("departure date",),
    "return_date": ("returned date", "return date"),
    "booking_date": ("date booked", "booking date"),
    "customer_balance_due_date": ("due date",),
    "imported_customer_outstanding": ("outstanding",),
    "imported_supplier_outstanding": ("outstanding supplier", "outstanding supp"),
    "gross_booking_value": ("total cost",),
    "expected_supplier_nett": ("nett", "net"),
    "non_trusted_total_received": ("total received",),
    "non_trusted_paid_supplier": ("paid supp", "paid supplier"),
    "non_trusted_projected_profit": ("profit projected", "projected profit"),
}

MONEY_FIELDS = {
    "imported_customer_outstanding",
    "imported_supplier_outstanding",
    "gross_booking_value",
    "expected_supplier_nett",
    "non_trusted_total_received",
    "non_trusted_paid_supplier",
    "non_trusted_projected_profit",
}


@dataclass
class MasterBookingImportResult:
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


def normalise_header(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def read_tabular_rows(filename: str, content: bytes) -> tuple[list[str], list[dict[str, Any]]]:
    extension = Path(filename).suffix.lower()
    if extension == ".csv":
        return read_csv_rows(content)
    if extension == ".xlsx":
        return read_xlsx_rows(content)
    raise ValueError("Unsupported file type.")


def read_csv_rows(content: bytes) -> tuple[list[str], list[dict[str, Any]]]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("cp1252")

    reader = csv.DictReader(StringIO(text))
    headers = reader.fieldnames or []
    rows = [row for row in reader if any(str(value or "").strip() for value in row.values())]
    return headers, rows


def read_xlsx_rows(content: bytes) -> tuple[list[str], list[dict[str, Any]]]:
    workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
    try:
        sheet = workbook.active
        rows = sheet.iter_rows(values_only=True)
        headers = [str(value or "") for value in next(rows, [])]
        output = []
        for row in rows:
            row_data = {headers[index]: value for index, value in enumerate(row) if index < len(headers)}
            if any(value is not None and str(value).strip() for value in row_data.values()):
                output.append(row_data)
        return headers, output
    finally:
        workbook.close()


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


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_money(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.01"))
    if isinstance(value, int | float):
        return Decimal(str(value)).quantize(Decimal("0.01"))

    text = str(value).strip()
    if not text or text in {"-", "--"}:
        return None

    is_negative = text.startswith("(") and text.endswith(")")
    cleaned = (
        text.replace("£", "")
        .replace("?", "")
        .replace(",", "")
        .replace("(", "")
        .replace(")", "")
        .replace(" ", "")
    )
    if cleaned in {"", "-"}:
        return None

    try:
        amount = Decimal(cleaned).quantize(Decimal("0.01"))
    except InvalidOperation as exc:
        raise ValueError(f"Invalid money value '{value}'.") from exc

    return -amount if is_negative else amount


def parse_date(value: Any) -> date | None:
    parsed = parse_datetime(value)
    return parsed.date() if parsed else None


def parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time.min)

    text = str(value).strip()
    if not text:
        return None

    formats = (
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    )
    for date_format in formats:
        try:
            return datetime.strptime(text, date_format)
        except ValueError:
            continue
    raise ValueError(f"Invalid date value '{value}'.")


def normalise_booking_status(status: str | None) -> str | None:
    cleaned = (status or "").strip().lower()
    if not cleaned:
        return None
    status_map = {
        "changed": "amended/live",
        "complete": "completed",
        "completed": "completed",
        "cancelled": "cancelled",
        "canceled": "cancelled",
        "open": "open",
    }
    return status_map.get(cleaned, cleaned)


def parse_elements(elements: str | None) -> dict[str, bool]:
    cleaned = (elements or "").lower()
    return {
        "flight_included": any(term in cleaned for term in ("flight", "flights", "airline")),
        "accommodation_included": any(term in cleaned for term in ("accommodation", "accom", "hotel")),
        "cruise_included": "cruise" in cleaned,
        "extras_included": any(term in cleaned for term in ("extra", "extras", "transfer", "car hire", "insurance")),
        "package_included": any(term in cleaned for term in ("package", "packages")),
    }


def determine_atol_review_status(flags: dict[str, bool]) -> str:
    has_flight = flags["flight_included"]
    has_accommodation = flags["accommodation_included"]
    has_cruise = flags["cruise_included"]
    has_extras = flags["extras_included"]
    has_package = flags["package_included"]

    if has_flight and has_accommodation:
        return "ATOL required"
    if has_flight and has_cruise:
        return "ATOL review"
    if has_flight and (has_extras or has_package):
        return "ATOL review / likely required"
    if has_flight:
        return "flight-only review"
    if has_package:
        return "ATOL review"
    return "non-flight / non-ATOL review"


def get_row_value(row: dict[str, Any], column_map: dict[str, str], field_name: str) -> Any:
    header = column_map.get(field_name)
    if header is None:
        return None
    return row.get(header)


def import_master_booking_report(
    db: Session,
    upload_batch: UploadBatch,
    filename: str,
    content: bytes,
    actor_user_id: int | None,
) -> MasterBookingImportResult:
    headers, rows = read_tabular_rows(filename, content)
    result = MasterBookingImportResult(row_count=len(rows))
    column_map = build_column_map(headers)

    if "booking_ref" not in column_map:
        result.rejected_rows = len(rows)
        result.errors.append("Booking Reference column is required for master booking imports.")
        return result

    for index, row in enumerate(rows, start=2):
        try:
            booking_ref = clean_text(get_row_value(row, column_map, "booking_ref"))
            if not booking_ref:
                raise ValueError("Booking Reference is missing.")

            imported_status = clean_text(get_row_value(row, column_map, "status"))
            elements_raw = clean_text(get_row_value(row, column_map, "travel_elements_raw"))
            flags = parse_elements(elements_raw)

            values = {
                "booking_ref": booking_ref,
                "imported_booking_status": imported_status,
                "normalised_status": normalise_booking_status(imported_status),
                "customer_last_name": clean_text(get_row_value(row, column_map, "customer_last_name")),
                "destination": clean_text(get_row_value(row, column_map, "destination")),
                "travel_elements_raw": elements_raw,
                "departure_date": parse_date(get_row_value(row, column_map, "departure_date")),
                "return_date": parse_date(get_row_value(row, column_map, "return_date")),
                "booking_date": parse_datetime(get_row_value(row, column_map, "booking_date")),
                "customer_balance_due_date": parse_date(get_row_value(row, column_map, "customer_balance_due_date")),
                "last_master_upload_batch_id": upload_batch.id,
                **flags,
            }

            for money_field in MONEY_FIELDS:
                values[money_field] = parse_money(get_row_value(row, column_map, money_field))

            values["atol_review_status"] = determine_atol_review_status(flags)

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
            action="master_booking_import",
            table_name="upload_batches",
            record_id=upload_batch.id,
            description=(
                f"Master booking import accepted {result.accepted_rows} row(s) "
                f"and rejected {result.rejected_rows} row(s)."
            ),
        )
    )
    return result
