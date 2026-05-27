from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_session_factory
from app.models.reporting import AuditLog, Booking, CustomerPayment, UploadBatch
from app.services.customer_payment_import import (
    calculate_estimated_fee,
    find_booking_by_reference,
    find_lower_confidence_booking,
    find_payment_method_rule,
)


MAX_TAKE = 25
FELLOH_ACCEPTED_TRANSACTION_STATUSES = {
    "",
    "CAPTURED",
    "COMPLETE",
    "COMPLETED",
    "PAID",
    "SETTLED",
    "SUCCESS",
    "SUCCESSFUL",
    "SUCCEEDED",
}
FELLOH_REJECTED_TRANSACTION_STATUSES = {
    "CANCELLED",
    "CANCELED",
    "DECLINED",
    "FAILED",
    "PENDING",
    "REFUNDED",
    "VOID",
}


@dataclass(frozen=True)
class SingsApiConfig:
    base_url: str
    public_key: str
    private_key: str
    organisation_id: str


class SingsApiNotConfiguredError(RuntimeError):
    pass


class SingsApiError(RuntimeError):
    pass


@dataclass
class FellohSyncResult:
    start_date: date
    end_date: date
    fetched_transactions: int = 0
    created_rows: int = 0
    updated_rows: int = 0
    checked_rows: int = 0
    skipped_rows: int = 0
    actual_fee_rows: int = 0
    estimated_fee_rows: int = 0
    unmatched_rows: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass
class FellohBackfillResult:
    start_date: date
    end_date: date
    chunk_days: int
    chunk_count: int = 0
    fetched_transactions: int = 0
    created_rows: int = 0
    updated_rows: int = 0
    checked_rows: int = 0
    skipped_rows: int = 0
    actual_fee_rows: int = 0
    estimated_fee_rows: int = 0
    unmatched_rows: int = 0
    warnings: list[str] = field(default_factory=list)


class SingsService:
    """Felloh/SINGs API client.

    Felloh authenticates with public/private keys, then returns a bearer token.
    Customer payment CSV/XLSX upload still remains available as a fallback.
    """

    def __init__(self, config: SingsApiConfig | None = None) -> None:
        self.config = config or SingsApiConfig(
            base_url=settings.felloh_api_base_url.strip().rstrip("/"),
            public_key=settings.felloh_public_key.strip(),
            private_key=settings.felloh_private_key.strip(),
            organisation_id=settings.felloh_organisation_id.strip(),
        )
        self._token: str | None = None
        self._token_expires_at: datetime | None = None

    def ensure_configured(self) -> None:
        if not (
            self.config.base_url
            and self.config.public_key
            and self.config.private_key
            and self.config.organisation_id
        ):
            raise SingsApiNotConfiguredError(
                "Felloh/SINGs API is not configured. Add the Felloh public key, private key and organisation ID in Render."
            )

    def _request_json(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.config.base_url}{path}"
        body = json.dumps(payload or {}).encode("utf-8") if payload is not None else None
        headers = {"Content-Type": "application/json"}
        if path != "/token":
            headers["Authorization"] = f"Bearer {self.get_token()}"

        request = Request(url, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=30) as response:
                response_body = response.read().decode("utf-8")
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise SingsApiError(f"Felloh API returned {exc.code}: {error_body}") from exc
        except URLError as exc:
            raise SingsApiError(f"Felloh API could not be reached: {exc.reason}") from exc

        try:
            return json.loads(response_body)
        except json.JSONDecodeError as exc:
            raise SingsApiError("Felloh API returned a response that was not valid JSON.") from exc

    def get_token(self) -> str:
        self.ensure_configured()
        if self._token and self._token_expires_at and self._token_expires_at > datetime.now(UTC):
            return self._token

        response = self._request_json(
            "POST",
            "/token",
            {"public_key": self.config.public_key, "private_key": self.config.private_key},
        )
        data = response.get("data") or {}
        token = data.get("token")
        if not token:
            raise SingsApiError("Felloh token response did not include a bearer token.")

        expiry_time = data.get("expiry_time")
        if expiry_time:
            self._token_expires_at = datetime.fromtimestamp(int(expiry_time), UTC) - timedelta(minutes=2)
        else:
            self._token_expires_at = datetime.now(UTC) + timedelta(minutes=30)
        self._token = token
        return token

    def _fetch_paginated(
        self,
        path: str,
        start_date: date | None = None,
        end_date: date | None = None,
        extra_payload: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        self.ensure_configured()
        skip = 0
        records: list[dict[str, Any]] = []

        while True:
            payload: dict[str, Any] = {
                "organisation": self.config.organisation_id,
                "skip": skip,
                "take": MAX_TAKE,
            }
            if start_date:
                payload["date_from"] = start_date.isoformat()
            if end_date:
                payload["date_to"] = end_date.isoformat()
            if extra_payload:
                payload.update(extra_payload)

            response = self._request_json("POST", path, payload)
            data = response.get("data") or []
            if isinstance(data, dict):
                data = [data]
            if not isinstance(data, list):
                raise SingsApiError("Felloh API returned data in an unexpected format.")

            records.extend(record for record in data if isinstance(record, dict))
            count = int((response.get("meta") or {}).get("count") or len(data))
            skip += len(data)
            if not data or skip >= count:
                break

        return records

    def fetch_transactions(self, start_date: date | None = None, end_date: date | None = None) -> list[dict[str, Any]]:
        transactions = self._fetch_paginated(
            "/agent/transactions",
            start_date=start_date,
            end_date=end_date,
            extra_payload={"statuses": ["COMPLETE"]},
        )
        if transactions:
            return transactions

        # Some Felloh accounts expose completed transactions under different
        # status wording. If the strict filter returns nothing, retry without
        # the filter and let the importer reject failed/pending statuses safely.
        return self._fetch_paginated("/agent/transactions", start_date=start_date, end_date=end_date)

    def fetch_charges(self, start_date: date | None = None, end_date: date | None = None) -> list[dict[str, Any]]:
        return self._fetch_paginated("/agent/charges", start_date=start_date, end_date=end_date)

    def fetch_settlements(self, start_date: date | None = None, end_date: date | None = None) -> list[dict[str, Any]]:
        return self._fetch_paginated("/bank/batch", start_date=start_date, end_date=end_date)

    def fetch_refunds(self, start_date: date | None = None, end_date: date | None = None) -> list[dict[str, Any]]:
        return self._fetch_paginated("/agent/refunds", start_date=start_date, end_date=end_date)

    def fetch_chargebacks(self, start_date: date | None = None, end_date: date | None = None) -> list[dict[str, Any]]:
        return self._fetch_paginated("/agent/chargebacks", start_date=start_date, end_date=end_date)


def get_sings_service() -> SingsService:
    return SingsService()


def object_id(value: Any) -> str | None:
    if isinstance(value, dict):
        raw_value = value.get("id") or value.get("name")
    else:
        raw_value = value
    if raw_value is None:
        return None
    text = str(raw_value).strip()
    return text or None


def parse_felloh_date(value: Any) -> date | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            return None


def money_from_felloh_amount(amount: Any, currency: str | None) -> Decimal | None:
    if amount is None:
        return None
    try:
        value = Decimal(str(amount))
    except InvalidOperation:
        return None
    if (currency or "").upper().endswith("X"):
        value = value / Decimal("100")
    return value.quantize(Decimal("0.01"))


def normalised_felloh_status(value: Any) -> str:
    return str(object_id(value) or "").strip().upper()


def transaction_can_be_imported(transaction: dict[str, Any]) -> bool:
    status = normalised_felloh_status(transaction.get("status"))
    if status in FELLOH_REJECTED_TRANSACTION_STATUSES:
        return False
    if status in FELLOH_ACCEPTED_TRANSACTION_STATUSES:
        return True
    return False


def felloh_status_counts(transactions: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for transaction in transactions:
        status = normalised_felloh_status(transaction.get("status")) or "NO_STATUS"
        counts[status] = counts.get(status, 0) + 1
    return counts


def format_felloh_sync_note(
    start_date: date,
    end_date: date,
    fetched_count: int,
    imported_count: int,
    skipped_count: int,
    status_counts: dict[str, int],
) -> str:
    statuses = ", ".join(f"{status}: {count}" for status, count in sorted(status_counts.items())) or "none"
    return (
        f"{start_date.isoformat()} to {end_date.isoformat()}: "
        f"Felloh returned {fetched_count}, importable {imported_count}, skipped {skipped_count}. "
        f"Statuses: {statuses}."
    )


def build_charge_totals_by_transaction(charges: list[dict[str, Any]]) -> dict[str, Decimal]:
    totals: dict[str, Decimal] = {}
    for charge in charges:
        transaction_id = object_id(charge.get("transaction"))
        if not transaction_id:
            continue
        amount = money_from_felloh_amount(charge.get("amount"), charge.get("currency"))
        if amount is None:
            continue
        totals[transaction_id] = (totals.get(transaction_id, Decimal("0.00")) + amount).quantize(Decimal("0.01"))
    return totals


def upsert_felloh_transaction(
    db: Session,
    transaction: dict[str, Any],
    charge_totals_by_transaction: dict[str, Decimal],
    sync_batch_id: int,
) -> tuple[str, bool, bool, bool]:
    transaction_id = object_id(transaction.get("id"))
    if not transaction_id:
        return "skipped", False, False, True

    currency = object_id(transaction.get("currency"))
    gross_amount = money_from_felloh_amount(transaction.get("amount"), currency)
    if gross_amount is None:
        return "skipped", False, False, True

    booking_data = transaction.get("booking") if isinstance(transaction.get("booking"), dict) else {}
    payment_link_data = transaction.get("payment_link") if isinstance(transaction.get("payment_link"), dict) else {}
    metadata = transaction.get("metadata") if isinstance(transaction.get("metadata"), dict) else {}

    booking_ref = object_id(booking_data.get("booking_reference"))
    customer_name = object_id(booking_data.get("customer_name")) or object_id(payment_link_data.get("customer_name"))
    payment_date = parse_felloh_date(transaction.get("completed_at")) or parse_felloh_date(transaction.get("created_at"))
    payment_method = object_id(transaction.get("type")) or object_id(transaction.get("method"))
    card_type = object_id(metadata.get("card_type")) or object_id(metadata.get("bin_type"))
    card_brand = object_id(metadata.get("payment_brand"))

    booking, match_confidence = find_booking_by_reference(db, booking_ref, None)
    if booking is None:
        booking = find_lower_confidence_booking(db, customer_name, gross_amount, payment_date)
        if booking is not None:
            match_confidence = "lower_confidence"

    fee_amount = charge_totals_by_transaction.get(transaction_id)
    fee_is_estimated = False
    used_actual_fee = fee_amount is not None
    if fee_amount is None:
        rule = find_payment_method_rule(db, payment_method, card_type, card_brand, payment_date)
        fee_amount = calculate_estimated_fee(gross_amount, rule)
        fee_is_estimated = fee_amount is not None

    net_settled_amount = None
    if fee_amount is not None:
        net_settled_amount = (gross_amount - fee_amount).quantize(Decimal("0.01"))

    values = {
        "booking_id": booking.id if booking else None,
        "payment_source": "sings",
        "booking_ref": booking_ref or (booking.booking_ref if booking else None),
        "invoice_reference": None,
        "customer_name": customer_name,
        "payment_date": payment_date,
        "settlement_date": None,
        "gross_amount": gross_amount,
        "fee_amount": fee_amount,
        "net_settled_amount": net_settled_amount,
        "fee_is_estimated": fee_is_estimated,
        "payment_method": payment_method,
        "card_type": card_type,
        "card_brand": card_brand,
        "transaction_status": object_id(transaction.get("status")),
        "refund_indicator": False,
        "chargeback_indicator": False,
        "merchant_account": object_id(transaction.get("organisation")),
        "settlement_batch_reference": None,
        "match_confidence": match_confidence,
    }

    existing = db.scalar(
        select(CustomerPayment)
        .where(CustomerPayment.transaction_id == transaction_id, CustomerPayment.payment_source == "sings")
        .limit(1)
    )
    if existing:
        has_changes = any(getattr(existing, key) != value for key, value in values.items())
        if not has_changes:
            return "checked", used_actual_fee, fee_is_estimated, match_confidence == "unmatched"

        for key, value in values.items():
            setattr(existing, key, value)
        return "updated", used_actual_fee, fee_is_estimated, match_confidence == "unmatched"

    db.add(CustomerPayment(upload_batch_id=sync_batch_id, transaction_id=transaction_id, **values))
    return "created", used_actual_fee, fee_is_estimated, match_confidence == "unmatched"


def sync_felloh_customer_payments(
    db: Session,
    start_date: date,
    end_date: date,
    actor_user_id: int | None,
    service: SingsService | None = None,
) -> FellohSyncResult:
    service = service or get_sings_service()
    result = FellohSyncResult(start_date=start_date, end_date=end_date)
    sync_batch = UploadBatch(
        upload_type="felloh_customer_payment_sync",
        original_filename=f"Felloh API sync {start_date.isoformat()} to {end_date.isoformat()}",
        status="importing",
        uploaded_by_user_id=actor_user_id,
    )
    db.add(sync_batch)
    db.flush()

    transactions = service.fetch_transactions(start_date=start_date, end_date=end_date)
    result.fetched_transactions = len(transactions)
    status_counts = felloh_status_counts(transactions)
    importable_transactions = [transaction for transaction in transactions if transaction_can_be_imported(transaction)]

    try:
        charge_totals_by_transaction = build_charge_totals_by_transaction(
            service.fetch_charges(start_date=start_date, end_date=end_date)
        )
    except SingsApiError as exc:
        charge_totals_by_transaction = {}
        result.warnings.append(f"Felloh charges could not be fetched, so fee rules were used where available: {exc}")

    for transaction in importable_transactions:
        action, used_actual_fee, used_estimated_fee, is_unmatched = upsert_felloh_transaction(
            db, transaction, charge_totals_by_transaction, sync_batch.id
        )
        if action == "created":
            result.created_rows += 1
        elif action == "updated":
            result.updated_rows += 1
        elif action == "checked":
            result.checked_rows += 1
        else:
            result.skipped_rows += 1
        if used_actual_fee:
            result.actual_fee_rows += 1
        elif used_estimated_fee:
            result.estimated_fee_rows += 1
        if is_unmatched:
            result.unmatched_rows += 1

    skipped_by_status = len(transactions) - len(importable_transactions)
    if skipped_by_status:
        result.skipped_rows += skipped_by_status

    sync_batch.row_count = result.fetched_transactions
    sync_batch.accepted_rows = result.created_rows + result.updated_rows + result.checked_rows
    sync_batch.rejected_rows = result.skipped_rows
    sync_note = format_felloh_sync_note(
        start_date,
        end_date,
        result.fetched_transactions,
        len(importable_transactions),
        skipped_by_status,
        status_counts,
    )
    sync_batch.error_summary = " ".join([sync_note, *result.warnings]).strip()
    sync_batch.status = "imported_with_errors" if result.warnings or result.skipped_rows else "imported"
    sync_batch.completed_at = datetime.now(UTC)

    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action="felloh_customer_payment_sync",
            table_name="customer_payments",
            description=(
                f"Felloh sync fetched {result.fetched_transactions} transaction(s), "
                f"created {result.created_rows}, cross-checked {result.checked_rows}, "
                f"updated {result.updated_rows}, skipped {result.skipped_rows}."
            ),
            after_data={
                "sync_batch_id": sync_batch.id,
                "start_date": result.start_date.isoformat(),
                "end_date": result.end_date.isoformat(),
                "warnings": result.warnings,
            },
        )
    )
    return result


def count_date_chunks(start_date: date, end_date: date, chunk_days: int) -> int:
    return len(list(iter_date_chunks(start_date, end_date, chunk_days)))


def iter_date_chunks(start_date: date, end_date: date, chunk_days: int):
    current_start = start_date
    while current_start <= end_date:
        current_end = min(current_start + timedelta(days=chunk_days - 1), end_date)
        yield current_start, current_end
        current_start = current_end + timedelta(days=1)


def get_upload_batch(db: Session, batch_id: int) -> UploadBatch | None:
    return db.scalar(select(UploadBatch).where(UploadBatch.id == batch_id).limit(1))


def run_felloh_customer_payment_backfill(
    start_date: date,
    end_date: date,
    actor_user_id: int | None,
    parent_batch_id: int,
    chunk_days: int = 14,
) -> None:
    session_factory = get_session_factory()
    service = get_sings_service()
    result = FellohBackfillResult(
        start_date=start_date,
        end_date=end_date,
        chunk_days=chunk_days,
        chunk_count=count_date_chunks(start_date, end_date, chunk_days),
    )

    with session_factory() as db:
        parent_batch = get_upload_batch(db, parent_batch_id)
        if parent_batch is None:
            return
        parent_batch.status = "importing"
        db.commit()

        try:
            for chunk_start, chunk_end in iter_date_chunks(start_date, end_date, chunk_days):
                chunk_result = sync_felloh_customer_payments(
                    db=db,
                    start_date=chunk_start,
                    end_date=chunk_end,
                    actor_user_id=actor_user_id,
                    service=service,
                )
                db.commit()

                result.fetched_transactions += chunk_result.fetched_transactions
                result.created_rows += chunk_result.created_rows
                result.updated_rows += chunk_result.updated_rows
                result.checked_rows += chunk_result.checked_rows
                result.skipped_rows += chunk_result.skipped_rows
                result.actual_fee_rows += chunk_result.actual_fee_rows
                result.estimated_fee_rows += chunk_result.estimated_fee_rows
                result.unmatched_rows += chunk_result.unmatched_rows
                result.warnings.extend(chunk_result.warnings)

            parent_batch = get_upload_batch(db, parent_batch_id)
            if parent_batch:
                parent_batch.row_count = result.fetched_transactions
                parent_batch.accepted_rows = result.created_rows + result.updated_rows + result.checked_rows
                parent_batch.rejected_rows = result.skipped_rows
                parent_batch.error_summary = " ".join(result.warnings) if result.warnings else None
                parent_batch.status = "imported_with_errors" if result.warnings or result.skipped_rows else "imported"
                parent_batch.completed_at = datetime.now(UTC)
                db.add(
                    AuditLog(
                        actor_user_id=actor_user_id,
                        action="felloh_customer_payment_backfill",
                        table_name="customer_payments",
                        record_id=parent_batch.id,
                        description=(
                            f"Felloh backfill synced {result.chunk_count} date block(s), "
                            f"fetched {result.fetched_transactions} transaction(s), "
                            f"created {result.created_rows}, cross-checked {result.checked_rows}, "
                            f"updated {result.updated_rows}, skipped {result.skipped_rows}."
                        ),
                        after_data={
                            "start_date": result.start_date.isoformat(),
                            "end_date": result.end_date.isoformat(),
                            "chunk_days": result.chunk_days,
                            "chunk_count": result.chunk_count,
                            "warnings": result.warnings,
                        },
                    )
                )
                db.commit()
        except Exception as exc:
            db.rollback()
            parent_batch = get_upload_batch(db, parent_batch_id)
            if parent_batch:
                parent_batch.status = "failed"
                parent_batch.error_summary = str(exc)
                parent_batch.completed_at = datetime.now(UTC)
                db.commit()
