from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.reporting import AuditLog, BankTransaction, Booking, ExceptionRecord, UploadBatch
from app.services.master_booking_import import (
    clean_text,
    normalise_header,
    parse_date,
    parse_money,
    read_tabular_rows,
)


COLUMN_ALIASES = {
    "transaction_date": ("transaction date", "date", "posted date", "bank date"),
    "description": ("description", "details", "narrative", "transaction description"),
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


def find_booking_reference(text_parts: list[str | None], booking_refs: set[str]) -> str | None:
    haystack = " ".join(part or "" for part in text_parts).upper()
    for booking_ref in booking_refs:
        if booking_ref.upper() in haystack:
            return booking_ref
    return None


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

    booking_refs = set(db.scalars(select(Booking.booking_ref)))
    duplicate_keys_in_this_upload: set[str] = set()

    for index, row in enumerate(rows, start=2):
        try:
            transaction_date = parse_date(get_row_value(row, column_map, "transaction_date"))
            if transaction_date is None:
                raise ValueError("Transaction Date is missing.")

            values = {
                "upload_batch_id": upload_batch.id,
                "transaction_date": transaction_date,
                "description": clean_text(get_row_value(row, column_map, "description")),
                "money_in": parse_money(get_row_value(row, column_map, "money_in")),
                "money_out": parse_money(get_row_value(row, column_map, "money_out")),
                "balance": parse_money(get_row_value(row, column_map, "balance")),
                "account_type": clean_text(get_row_value(row, column_map, "account_type")),
                "transaction_reference": clean_text(get_row_value(row, column_map, "transaction_reference")),
            }

            if values["money_in"] is None and values["money_out"] is None and values["balance"] is None:
                raise ValueError("At least one money column is required.")

            duplicate_key = build_duplicate_key(values)
            existing_duplicate_id = db.scalar(
                select(BankTransaction.id).where(BankTransaction.duplicate_key == duplicate_key).limit(1)
            )
            is_duplicate = duplicate_key in duplicate_keys_in_this_upload or existing_duplicate_id is not None
            matched_booking_ref = find_booking_reference(
                [values["description"], values["transaction_reference"]],
                booking_refs,
            )
            values["duplicate_key"] = duplicate_key
            if is_duplicate:
                values["match_status"] = "duplicate"
            elif matched_booking_ref:
                values["match_status"] = "matched_booking_ref"
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
