from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.reporting import AuditLog, BankTransaction, Booking, ExceptionRecord, UploadBatch
from app.services.master_booking_import import (
    clean_text,
    normalise_booking_ref,
    normalise_header,
    parse_date,
    parse_money,
    read_tabular_rows,
)


COLUMN_ALIASES = {
    "transaction_date": ("transaction date", "date", "posted date", "bank date"),
    "description": ("description", "details", "narrative", "transaction description", "narrative 1"),
    "money_in": ("money in", "paid in", "credit", "deposit", "amount in"),
    "money_out": ("money out", "paid out", "debit", "withdrawal", "amount out"),
    "balance": ("balance", "running balance", "closing balance"),
    "account_type": ("account type", "account", "account name"),
    "transaction_reference": ("transaction reference", "reference", "bank reference", "transaction id"),
}

REQUIRED_FIELDS = {"transaction_date"}


@dataclass
class BankStatementImportResult:
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


def duplicate_text(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())


def duplicate_decimal(value: Decimal | None) -> str:
    if value is None:
        return ""
    return str(value.quantize(Decimal("0.01")))


def build_duplicate_key(values: dict[str, Any]) -> str:
    transaction_date = values["transaction_date"].isoformat() if values.get("transaction_date") else ""
    parts = (
        transaction_date,
        duplicate_text(values.get("description")),
        duplicate_decimal(values.get("money_in")),
        duplicate_decimal(values.get("money_out")),
        duplicate_decimal(values.get("balance")),
        duplicate_text(values.get("account_type")),
        duplicate_text(values.get("transaction_reference")),
    )
    return "|".join(parts)


def parse_bank_money_in(value: Any) -> Decimal | None:
    return parse_money(value)


def parse_bank_money_out(value: Any) -> Decimal | None:
    amount = parse_money(value)
    if amount is None:
        return None
    return abs(amount).quantize(Decimal("0.01"))


def combined_description(row: dict[str, Any], column_map: dict[str, str]) -> str | None:
    narrative_parts = []
    for header, value in row.items():
        if normalise_header(header).startswith("narrative"):
            text = clean_text(value)
            if text:
                narrative_parts.append(text)
    if narrative_parts:
        return " | ".join(narrative_parts)
    return clean_text(get_row_value(row, column_map, "description"))


def extract_booking_reference(text_parts: list[str | None]) -> str | None:
    haystack = " ".join(part or "" for part in text_parts)
    match = re.search(r"\bOTC[-_\s]?\d+\b|\bOTC\d+\b", haystack, flags=re.IGNORECASE)
    if not match:
        return None
    return normalise_booking_ref(match.group(0))


def find_booking_reference(text_parts: list[str | None], booking_refs: set[str]) -> str | None:
    extracted_ref = extract_booking_reference(text_parts)
    if extracted_ref:
        return extracted_ref

    haystack = " ".join(part or "" for part in text_parts).upper()
    for booking_ref in booking_refs:
        if booking_ref.upper() in haystack:
            return booking_ref
    return None


def default_allocation_type(money_in: Decimal | None, money_out: Decimal | None) -> str | None:
    if money_out is not None and money_out > Decimal("0.00"):
        return "supplier_payment"
    if money_in is not None and money_in > Decimal("0.00"):
        return "customer_receipt"
    return None


def close_bank_exceptions(db: Session, bank_transaction_id: int) -> None:
    for exception in db.scalars(
        select(ExceptionRecord).where(
            ExceptionRecord.related_table == "bank_transactions",
            ExceptionRecord.related_record_id == bank_transaction_id,
            ExceptionRecord.status.in_(("open", "reviewing")),
        )
    ):
        exception.status = "resolved"


def create_bank_exception(
    db: Session,
    bank_transaction: BankTransaction,
    title: str,
    detail: str,
    severity: str,
) -> None:
    db.add(
        ExceptionRecord(
            exception_type="bank_transaction",
            severity=severity,
            status="open",
            title=title,
            detail=detail,
            related_table="bank_transactions",
            related_record_id=bank_transaction.id,
        )
    )


def import_bank_statement_report(
    db: Session,
    upload_batch: UploadBatch,
    filename: str,
    content: bytes,
    actor_user_id: int | None,
) -> BankStatementImportResult:
    headers, rows = read_tabular_rows(filename, content)
    result = BankStatementImportResult(row_count=len(rows))
    column_map = build_column_map(headers)
    missing_fields = sorted(field for field in REQUIRED_FIELDS if field not in column_map)

    if missing_fields:
        result.rejected_rows = len(rows)
        friendly_names = ", ".join(missing_fields).replace("_", " ")
        result.errors.append(f"Required bank statement column(s) missing: {friendly_names}.")
        return result

    booking_ids_by_ref = {
        booking_ref: booking_id
        for booking_ref, booking_id in db.execute(select(Booking.booking_ref, Booking.id)).all()
    }
    booking_refs = set(booking_ids_by_ref)
    duplicate_keys_in_this_upload: set[str] = set()

    for index, row in enumerate(rows, start=2):
        try:
            transaction_date = parse_date(get_row_value(row, column_map, "transaction_date"))
            if transaction_date is None:
                raise ValueError("Transaction Date is missing.")

            values = {
                "upload_batch_id": upload_batch.id,
                "transaction_date": transaction_date,
                "description": combined_description(row, column_map),
                "money_in": parse_bank_money_in(get_row_value(row, column_map, "money_in")),
                "money_out": parse_bank_money_out(get_row_value(row, column_map, "money_out")),
                "balance": parse_money(get_row_value(row, column_map, "balance")),
                "account_type": clean_text(get_row_value(row, column_map, "account_type")),
                "transaction_reference": clean_text(get_row_value(row, column_map, "transaction_reference")),
            }

            if values["money_in"] is None and values["money_out"] is None and values["balance"] is None:
                raise ValueError("At least one money column is required.")

            duplicate_key = build_duplicate_key(values)
            existing_duplicate = db.scalar(
                select(BankTransaction).where(BankTransaction.duplicate_key == duplicate_key).limit(1)
            )
            matched_booking_ref = find_booking_reference(
                [values["description"], values["transaction_reference"]],
                booking_refs,
            )
            booking_id = booking_ids_by_ref.get(matched_booking_ref or "")
            values["duplicate_key"] = duplicate_key
            values["booking_ref"] = matched_booking_ref
            values["booking_id"] = booking_id
            values["allocation_type"] = default_allocation_type(values["money_in"], values["money_out"])

            if existing_duplicate is not None:
                for field_name, value in values.items():
                    setattr(existing_duplicate, field_name, value)
                if booking_id:
                    existing_duplicate.match_status = "matched_booking_ref"
                    close_bank_exceptions(db, existing_duplicate.id)
                elif matched_booking_ref:
                    existing_duplicate.match_status = "unmatched_booking_ref"
                else:
                    existing_duplicate.match_status = "unmatched"
                duplicate_keys_in_this_upload.add(duplicate_key)
                result.accepted_rows += 1
                continue

            if duplicate_key in duplicate_keys_in_this_upload:
                values["match_status"] = "duplicate"
            elif booking_id:
                values["match_status"] = "matched_booking_ref"
            elif matched_booking_ref:
                values["match_status"] = "unmatched_booking_ref"
            else:
                values["match_status"] = "unmatched"

            bank_transaction = BankTransaction(**values)
            db.add(bank_transaction)
            db.flush()

            if values["match_status"] == "duplicate":
                create_bank_exception(
                    db=db,
                    bank_transaction=bank_transaction,
                    title="Duplicate bank transaction",
                    detail="This bank transaction matches an existing imported transaction.",
                    severity="low",
                )
            elif values["match_status"] == "unmatched":
                create_bank_exception(
                    db=db,
                    bank_transaction=bank_transaction,
                    title="Unmatched bank transaction",
                    detail=(
                        "This bank transaction did not match a booking reference. "
                        "It should be reviewed by Head Office."
                    ),
                    severity="medium",
                )
            elif values["match_status"] == "unmatched_booking_ref":
                create_bank_exception(
                    db=db,
                    bank_transaction=bank_transaction,
                    title="Bank transaction has booking reference not yet imported",
                    detail=(
                        "This bank transaction contains a booking reference, but the booking is not in the "
                        "Head Office database yet."
                    ),
                    severity="medium",
                )

            duplicate_keys_in_this_upload.add(duplicate_key)
            result.accepted_rows += 1
        except ValueError as exc:
            result.rejected_rows += 1
            result.errors.append(f"Row {index}: {exc}")

    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action="bank_statement_import",
            table_name="upload_batches",
            record_id=upload_batch.id,
            description=(
                f"Bank statement import accepted {result.accepted_rows} row(s) "
                f"and rejected {result.rejected_rows} row(s)."
            ),
        )
    )
    return result
