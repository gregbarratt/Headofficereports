from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.reporting import AuditLog, Booking, CustomerPayment, PaymentMethodRule, UploadBatch
from app.services.master_booking_import import (
    clean_text,
    normalise_header,
    parse_date,
    parse_money,
    read_tabular_rows,
)


COLUMN_ALIASES = {
    "transaction_id": ("transaction id", "transaction reference", "payment id", "id"),
    "booking_ref": ("booking reference", "booking ref", "booking_reference", "booking_ref"),
    "invoice_reference": ("invoice reference", "invoice ref", "invoice number", "invoice_reference"),
    "customer_name": ("customer name", "customer", "payer name", "cardholder name", "name"),
    "payment_date": ("payment date", "transaction date", "date"),
    "settlement_date": ("settlement date", "settled date", "settlement_date"),
    "gross_amount": ("gross amount", "gross", "amount", "payment amount", "customer gross payment"),
    "fee_amount": ("fee amount", "fee", "card fee", "processing fee", "actual fee"),
    "net_settled_amount": ("net settled amount", "net settled", "net amount", "settled amount"),
    "payment_method": ("payment method", "method"),
    "card_type": ("card type", "card_type"),
    "card_brand": ("card brand", "card_brand", "brand"),
    "transaction_status": ("transaction status", "status"),
    "refund_indicator": ("refund indicator", "refund", "is refund"),
    "chargeback_indicator": ("chargeback indicator", "chargeback", "is chargeback"),
    "merchant_account": ("merchant account", "merchant", "account"),
    "settlement_batch_reference": (
        "settlement batch reference",
        "settlement batch",
        "batch reference",
        "settlement_batch_reference",
    ),
}

REQUIRED_FIELDS = {"gross_amount"}
TRUE_VALUES = {"1", "true", "yes", "y", "refund", "refunded", "chargeback", "charged back"}


@dataclass
class CustomerPaymentImportResult:
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


def parse_bool(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    return normalise_header(value) in TRUE_VALUES


def normalised_value(value: str | None) -> str:
    return normalise_header(value or "")


def find_booking_by_reference(db: Session, booking_ref: str | None, invoice_reference: str | None) -> tuple[Booking | None, str]:
    if booking_ref:
        booking = db.scalar(select(Booking).where(Booking.booking_ref == booking_ref))
        if booking:
            return booking, "booking_ref"

    if invoice_reference:
        booking = db.scalar(select(Booking).where(Booking.booking_ref == invoice_reference))
        if booking:
            return booking, "invoice_ref"

    return None, "unmatched"


def find_lower_confidence_booking(
    db: Session,
    customer_name: str | None,
    gross_amount: Decimal,
    payment_date: date | None,
) -> Booking | None:
    if not customer_name or not payment_date:
        return None

    possible_last_name = customer_name.strip().split()[-1]
    if not possible_last_name:
        return None

    statement = select(Booking).where(Booking.customer_last_name.ilike(possible_last_name))
    for booking in db.scalars(statement):
        if booking.gross_booking_value is not None and booking.gross_booking_value == gross_amount:
            return booking
    return None


def rule_matches(rule_value: str | None, payment_value: str | None) -> bool:
    if not rule_value:
        return True
    if not payment_value:
        return False
    return normalised_value(rule_value) == normalised_value(payment_value)


def find_payment_method_rule(
    db: Session,
    payment_method: str | None,
    card_type: str | None,
    card_brand: str | None,
    payment_date: date | None,
) -> PaymentMethodRule | None:
    if not payment_method:
        return None

    rules = db.scalars(select(PaymentMethodRule).where(PaymentMethodRule.is_active.is_(True))).all()
    best_rule = None
    best_score = -1
    for rule in rules:
        if normalised_value(rule.payment_method) != normalised_value(payment_method):
            continue
        if rule.active_from and payment_date and rule.active_from > payment_date:
            continue
        if rule.active_to and payment_date and rule.active_to < payment_date:
            continue
        if not rule_matches(rule.card_type, card_type) or not rule_matches(rule.card_brand, card_brand):
            continue

        score = 1
        if rule.card_type:
            score += 2
        if rule.card_brand:
            score += 2
        if score > best_score:
            best_rule = rule
            best_score = score
    return best_rule


def calculate_estimated_fee(gross_amount: Decimal, rule: PaymentMethodRule | None) -> Decimal | None:
    if rule is None:
        return None
    percentage = Decimal(rule.percentage_fee or 0)
    fixed = Decimal(rule.fixed_fee or 0)
    fee = (gross_amount * percentage / Decimal("100")) + fixed
    return fee.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def import_customer_payment_report(
    db: Session,
    upload_batch: UploadBatch,
    filename: str,
    content: bytes,
    actor_user_id: int | None,
    payment_source: str = "sings",
) -> CustomerPaymentImportResult:
    headers, rows = read_tabular_rows(filename, content)
    result = CustomerPaymentImportResult(row_count=len(rows))
    column_map = build_column_map(headers)
    missing_fields = sorted(field for field in REQUIRED_FIELDS if field not in column_map)

    if missing_fields:
        result.rejected_rows = len(rows)
        friendly_names = ", ".join(missing_fields).replace("_", " ")
        result.errors.append(f"Required customer payment column(s) missing: {friendly_names}.")
        return result

    for index, row in enumerate(rows, start=2):
        try:
            gross_amount = parse_money(get_row_value(row, column_map, "gross_amount"))
            if gross_amount is None:
                raise ValueError("Gross Amount is missing.")

            booking_ref = clean_text(get_row_value(row, column_map, "booking_ref"))
            invoice_reference = clean_text(get_row_value(row, column_map, "invoice_reference"))
            customer_name = clean_text(get_row_value(row, column_map, "customer_name"))
            payment_date = parse_date(get_row_value(row, column_map, "payment_date"))
            fee_amount = parse_money(get_row_value(row, column_map, "fee_amount"))
            net_settled_amount = parse_money(get_row_value(row, column_map, "net_settled_amount"))
            payment_method = clean_text(get_row_value(row, column_map, "payment_method"))
            card_type = clean_text(get_row_value(row, column_map, "card_type"))
            card_brand = clean_text(get_row_value(row, column_map, "card_brand"))

            booking, match_confidence = find_booking_by_reference(db, booking_ref, invoice_reference)
            if booking is None:
                booking = find_lower_confidence_booking(db, customer_name, gross_amount, payment_date)
                if booking is not None:
                    match_confidence = "lower_confidence"

            fee_is_estimated = False
            if fee_amount is None:
                rule = find_payment_method_rule(db, payment_method, card_type, card_brand, payment_date)
                fee_amount = calculate_estimated_fee(gross_amount, rule)
                fee_is_estimated = fee_amount is not None

            if net_settled_amount is None and fee_amount is not None:
                net_settled_amount = (gross_amount - fee_amount).quantize(Decimal("0.01"))

            db.add(
                CustomerPayment(
                    upload_batch_id=upload_batch.id,
                    booking_id=booking.id if booking else None,
                    payment_source=payment_source,
                    transaction_id=clean_text(get_row_value(row, column_map, "transaction_id")),
                    booking_ref=booking_ref or (booking.booking_ref if booking else None),
                    invoice_reference=invoice_reference,
                    customer_name=customer_name,
                    payment_date=payment_date,
                    settlement_date=parse_date(get_row_value(row, column_map, "settlement_date")),
                    gross_amount=gross_amount,
                    fee_amount=fee_amount,
                    net_settled_amount=net_settled_amount,
                    fee_is_estimated=fee_is_estimated,
                    payment_method=payment_method,
                    card_type=card_type,
                    card_brand=card_brand,
                    transaction_status=clean_text(get_row_value(row, column_map, "transaction_status")),
                    refund_indicator=parse_bool(get_row_value(row, column_map, "refund_indicator")),
                    chargeback_indicator=parse_bool(get_row_value(row, column_map, "chargeback_indicator")),
                    merchant_account=clean_text(get_row_value(row, column_map, "merchant_account")),
                    settlement_batch_reference=clean_text(
                        get_row_value(row, column_map, "settlement_batch_reference")
                    ),
                    match_confidence=match_confidence,
                )
            )
            result.accepted_rows += 1
        except ValueError as exc:
            result.rejected_rows += 1
            result.errors.append(f"Row {index}: {exc}")

    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action="customer_payment_import",
            table_name="upload_batches",
            record_id=upload_batch.id,
            description=(
                f"Customer payment import accepted {result.accepted_rows} row(s) "
                f"and rejected {result.rejected_rows} row(s)."
            ),
        )
    )
    return result
