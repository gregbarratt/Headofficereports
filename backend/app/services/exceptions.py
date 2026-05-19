from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.reporting import (
    AgentCommission,
    AuditLog,
    BankTransaction,
    Booking,
    CustomerPayment,
    ExceptionRecord,
    Refund,
    SupplierPayment,
)
from app.services.trust_reconciliation import calculate_trust_reconciliation


ZERO = Decimal("0.00")
CLOSED_STATUSES = {"resolved", "ignored"}
ACTIVE_STATUSES = {"open", "reviewing"}
MANAGED_EXCEPTION_TYPES = {
    "trust_shortfall",
    "unmatched_customer_payment",
    "lower_confidence_customer_payment",
    "unmatched_supplier_payment",
    "duplicate_supplier_payment",
    "missing_supplier_reference",
    "supplier_overpaid",
    "supplier_balance_due_departed",
    "cancelled_booking_supplier_due",
    "cancelled_booking_commission_due",
    "unmatched_bank_transaction",
    "duplicate_bank_transaction",
    "refund_overdue",
    "unmatched_refund",
    "atol_certificate_missing",
    "estimated_card_fee",
}


@dataclass(frozen=True)
class ExceptionFinding:
    exception_type: str
    severity: str
    title: str
    detail: str
    booking_id: int | None = None
    booking_ref: str | None = None
    related_table: str | None = None
    related_record_id: int | None = None


@dataclass
class ExceptionGenerationResult:
    generated_count: int = 0
    created_count: int = 0
    updated_count: int = 0
    auto_resolved_count: int = 0


def money(value: Decimal | None) -> Decimal:
    if value is None:
        return ZERO
    return Decimal(value).quantize(Decimal("0.01"))


def positive(value: Decimal) -> Decimal:
    return value if value > ZERO else ZERO


def is_cancelled(booking: Booking) -> bool:
    return (booking.normalised_status or "").lower() == "cancelled"


def commission_is_due(commission: AgentCommission) -> bool:
    status = (commission.commission_status or "").lower()
    return money(commission.net_commission_due) > ZERO and status not in {"paid", "cancelled", "clawed_back"}


def refund_unpaid(refund: Refund) -> Decimal:
    return positive(money(refund.refund_amount_due) - money(refund.refund_amount_paid))


def exception_identity(finding: ExceptionFinding) -> tuple:
    return (
        finding.exception_type,
        finding.booking_ref,
        finding.related_table,
        finding.related_record_id,
    )


def find_existing_exception(db: Session, finding: ExceptionFinding) -> ExceptionRecord | None:
    statement = select(ExceptionRecord).where(ExceptionRecord.exception_type == finding.exception_type)

    if finding.booking_ref is None:
        statement = statement.where(ExceptionRecord.booking_ref.is_(None))
    else:
        statement = statement.where(ExceptionRecord.booking_ref == finding.booking_ref)

    if finding.related_table is None:
        statement = statement.where(ExceptionRecord.related_table.is_(None))
    else:
        statement = statement.where(ExceptionRecord.related_table == finding.related_table)

    if finding.related_record_id is None:
        statement = statement.where(ExceptionRecord.related_record_id.is_(None))
    else:
        statement = statement.where(ExceptionRecord.related_record_id == finding.related_record_id)

    existing = db.scalar(statement.order_by(ExceptionRecord.id.desc()).limit(1))
    if existing:
        return existing

    if finding.related_table == "bank_transactions" and finding.exception_type in {
        "unmatched_bank_transaction",
        "duplicate_bank_transaction",
    }:
        return db.scalar(
            select(ExceptionRecord)
            .where(
                ExceptionRecord.exception_type == "bank_transaction",
                ExceptionRecord.related_table == finding.related_table,
                ExceptionRecord.related_record_id == finding.related_record_id,
            )
            .order_by(ExceptionRecord.id.desc())
            .limit(1)
        )

    return None


def upsert_exception(db: Session, finding: ExceptionFinding, now: datetime) -> tuple[int, str]:
    existing = find_existing_exception(db, finding)
    if existing is None:
        exception = ExceptionRecord(
            exception_type=finding.exception_type,
            severity=finding.severity,
            status="open",
            title=finding.title,
            detail=finding.detail,
            booking_id=finding.booking_id,
            booking_ref=finding.booking_ref,
            related_table=finding.related_table,
            related_record_id=finding.related_record_id,
            detected_at=now,
        )
        db.add(exception)
        db.flush()
        return exception.id, "created"

    if existing.status not in CLOSED_STATUSES:
        existing.exception_type = finding.exception_type
        existing.severity = finding.severity
        existing.title = finding.title
        existing.detail = finding.detail
        existing.booking_id = finding.booking_id
        existing.booking_ref = finding.booking_ref
        existing.related_table = finding.related_table
        existing.related_record_id = finding.related_record_id
        existing.resolved_at = None
        existing.resolved_by_user_id = None
        return existing.id, "updated"

    return existing.id, "closed"


def build_exception_findings(db: Session) -> list[ExceptionFinding]:
    today = datetime.now(UTC).date()
    findings: list[ExceptionFinding] = []

    bookings = list(db.scalars(select(Booking)))
    bookings_by_ref = {booking.booking_ref: booking for booking in bookings}
    supplier_payments = list(db.scalars(select(SupplierPayment).where(SupplierPayment.payment_source == "taps")))
    customer_payments = list(db.scalars(select(CustomerPayment).where(CustomerPayment.payment_source == "sings")))
    bank_transactions = list(db.scalars(select(BankTransaction)))
    refunds = list(db.scalars(select(Refund)))
    commissions = list(db.scalars(select(AgentCommission)))

    trust = calculate_trust_reconciliation(db)
    if trust.summary.actual_trust_balance is not None and money(trust.summary.trust_variance) < ZERO:
        findings.append(
            ExceptionFinding(
                exception_type="trust_shortfall",
                severity="critical",
                title="Trust shortfall",
                detail=(
                    f"Actual trust balance is {money(trust.summary.actual_trust_balance)} and required trust "
                    f"balance is {money(trust.summary.required_trust_balance)}. "
                    f"Variance is {money(trust.summary.trust_variance)}."
                ),
            )
        )

    supplier_totals: dict[str, Decimal] = {}
    for payment in supplier_payments:
        if payment.booking_ref:
            supplier_totals[payment.booking_ref] = supplier_totals.get(payment.booking_ref, ZERO) + money(
                payment.supplier_payment_amount
            )

        if payment.booking_id is None or payment.match_status == "unmatched":
            findings.append(
                ExceptionFinding(
                    exception_type="unmatched_supplier_payment",
                    severity="high",
                    title="Unmatched supplier payment",
                    detail="Supplier payment has not matched a booking reference in our database.",
                    booking_ref=payment.booking_ref,
                    related_table="supplier_payments",
                    related_record_id=payment.id,
                )
            )

        if payment.is_duplicate:
            findings.append(
                ExceptionFinding(
                    exception_type="duplicate_supplier_payment",
                    severity="medium",
                    title="Duplicate supplier payment",
                    detail="This supplier payment matches another imported supplier payment line.",
                    booking_id=payment.booking_id,
                    booking_ref=payment.booking_ref,
                    related_table="supplier_payments",
                    related_record_id=payment.id,
                )
            )

        if not payment.supplier_name or not payment.payment_supplier_name:
            findings.append(
                ExceptionFinding(
                    exception_type="missing_supplier_reference",
                    severity="medium",
                    title="Missing supplier reference",
                    detail="Supplier name or payment supplier name is missing on this payment line.",
                    booking_id=payment.booking_id,
                    booking_ref=payment.booking_ref,
                    related_table="supplier_payments",
                    related_record_id=payment.id,
                )
            )

    for booking in bookings:
        expected_supplier_nett = money(booking.expected_supplier_nett)
        if expected_supplier_nett == ZERO:
            continue

        supplier_paid = supplier_totals.get(booking.booking_ref, ZERO)
        supplier_balance_due = money(expected_supplier_nett - supplier_paid)

        if supplier_paid > expected_supplier_nett:
            findings.append(
                ExceptionFinding(
                    exception_type="supplier_overpaid",
                    severity="high",
                    title="Supplier overpaid",
                    detail=(
                        f"Supplier payments total {supplier_paid}, but expected supplier nett is "
                        f"{expected_supplier_nett}."
                    ),
                    booking_id=booking.id,
                    booking_ref=booking.booking_ref,
                    related_table="bookings",
                    related_record_id=booking.id,
                )
            )

        if supplier_balance_due > ZERO and booking.departure_date and booking.departure_date < today:
            findings.append(
                ExceptionFinding(
                    exception_type="supplier_balance_due_departed",
                    severity="high",
                    title="Supplier balance due after departure",
                    detail=(
                        f"Supplier balance due is {supplier_balance_due}, and the departure date has passed."
                    ),
                    booking_id=booking.id,
                    booking_ref=booking.booking_ref,
                    related_table="bookings",
                    related_record_id=booking.id,
                )
            )

        if supplier_balance_due > ZERO and is_cancelled(booking):
            findings.append(
                ExceptionFinding(
                    exception_type="cancelled_booking_supplier_due",
                    severity="high",
                    title="Cancelled booking with supplier balance due",
                    detail=f"Cancelled booking still shows supplier balance due of {supplier_balance_due}.",
                    booking_id=booking.id,
                    booking_ref=booking.booking_ref,
                    related_table="bookings",
                    related_record_id=booking.id,
                )
            )

    for payment in customer_payments:
        if payment.match_confidence == "unmatched":
            findings.append(
                ExceptionFinding(
                    exception_type="unmatched_customer_payment",
                    severity="high",
                    title="Unmatched customer payment",
                    detail="Customer payment has not matched a booking reference in our database.",
                    booking_id=payment.booking_id,
                    booking_ref=payment.booking_ref,
                    related_table="customer_payments",
                    related_record_id=payment.id,
                )
            )
        elif payment.match_confidence == "lower_confidence":
            findings.append(
                ExceptionFinding(
                    exception_type="lower_confidence_customer_payment",
                    severity="medium",
                    title="Customer payment matched with lower confidence",
                    detail="Customer payment was matched using name, amount and date rather than booking reference.",
                    booking_id=payment.booking_id,
                    booking_ref=payment.booking_ref,
                    related_table="customer_payments",
                    related_record_id=payment.id,
                )
            )

        if payment.fee_is_estimated:
            findings.append(
                ExceptionFinding(
                    exception_type="estimated_card_fee",
                    severity="low",
                    title="Estimated card fee used",
                    detail="SINGs/Singhs did not provide an actual fee, so the fallback fee rule was used.",
                    booking_id=payment.booking_id,
                    booking_ref=payment.booking_ref,
                    related_table="customer_payments",
                    related_record_id=payment.id,
                )
            )

    for transaction in bank_transactions:
        if transaction.match_status == "unmatched":
            findings.append(
                ExceptionFinding(
                    exception_type="unmatched_bank_transaction",
                    severity="medium",
                    title="Unmatched bank transaction",
                    detail="Bank transaction did not match a booking reference and needs review.",
                    related_table="bank_transactions",
                    related_record_id=transaction.id,
                )
            )
        elif transaction.match_status == "duplicate":
            findings.append(
                ExceptionFinding(
                    exception_type="duplicate_bank_transaction",
                    severity="low",
                    title="Duplicate bank transaction",
                    detail="Bank transaction matches another imported bank line.",
                    related_table="bank_transactions",
                    related_record_id=transaction.id,
                )
            )

    for refund in refunds:
        unpaid = refund_unpaid(refund)
        if unpaid > ZERO and refund.due_date and refund.due_date < today and refund.refund_status != "cancelled":
            findings.append(
                ExceptionFinding(
                    exception_type="refund_overdue",
                    severity="high",
                    title="Refund overdue",
                    detail=f"Refund has {unpaid} unpaid and the due date has passed.",
                    booking_id=refund.booking_id,
                    booking_ref=refund.booking_ref,
                    related_table="refunds",
                    related_record_id=refund.id,
                )
            )

        if refund.booking_ref and refund.booking_ref not in bookings_by_ref:
            findings.append(
                ExceptionFinding(
                    exception_type="unmatched_refund",
                    severity="medium",
                    title="Refund booking not found",
                    detail="Refund contains a booking reference that is not in our booking database.",
                    booking_ref=refund.booking_ref,
                    related_table="refunds",
                    related_record_id=refund.id,
                )
            )
        elif not refund.booking_ref:
            findings.append(
                ExceptionFinding(
                    exception_type="unmatched_refund",
                    severity="medium",
                    title="Refund missing booking reference",
                    detail="Refund does not include a booking reference.",
                    related_table="refunds",
                    related_record_id=refund.id,
                )
            )

    for commission in commissions:
        booking = bookings_by_ref.get(commission.booking_ref or "")
        if booking and is_cancelled(booking) and commission_is_due(commission):
            findings.append(
                ExceptionFinding(
                    exception_type="cancelled_booking_commission_due",
                    severity="medium",
                    title="Cancelled booking with commission due",
                    detail="Commission is still due or accrued on a cancelled booking.",
                    booking_id=booking.id,
                    booking_ref=booking.booking_ref,
                    related_table="agent_commissions",
                    related_record_id=commission.id,
                )
            )

    for booking in bookings:
        atol_status = (booking.atol_review_status or "").lower()
        if "non-flight" in atol_status:
            continue
        if ("atol required" in atol_status or "likely required" in atol_status or "atol review" in atol_status) and not booking.atol_certificate_issued:
            severity = "high" if "required" in atol_status else "medium"
            findings.append(
                ExceptionFinding(
                    exception_type="atol_certificate_missing",
                    severity=severity,
                    title="ATOL certificate review needed",
                    detail=f"ATOL status is '{booking.atol_review_status}', but no certificate is marked as issued.",
                    booking_id=booking.id,
                    booking_ref=booking.booking_ref,
                    related_table="bookings",
                    related_record_id=booking.id,
                )
            )

    unique_findings = {}
    for finding in findings:
        unique_findings[exception_identity(finding)] = finding
    return list(unique_findings.values())


def generate_exceptions(db: Session, actor_user_id: int | None = None) -> ExceptionGenerationResult:
    now = datetime.now(UTC)
    result = ExceptionGenerationResult()
    active_exception_ids: set[int] = set()

    for finding in build_exception_findings(db):
        exception_id, action = upsert_exception(db, finding, now)
        active_exception_ids.add(exception_id)
        result.generated_count += 1
        if action == "created":
            result.created_count += 1
        elif action == "updated":
            result.updated_count += 1

    managed_active_statement = select(ExceptionRecord).where(
        ExceptionRecord.exception_type.in_(MANAGED_EXCEPTION_TYPES),
        ExceptionRecord.status.in_(ACTIVE_STATUSES),
    )
    for exception in db.scalars(managed_active_statement):
        if exception.id in active_exception_ids:
            continue
        exception.status = "resolved"
        exception.resolved_at = now
        exception.resolved_by_user_id = actor_user_id
        exception.detail = (
            f"{exception.detail or ''} Automatically resolved because this issue is no longer detected."
        ).strip()
        result.auto_resolved_count += 1

    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action="exception_generation",
            table_name="exceptions",
            description=(
                f"Exception scan found {result.generated_count} current issue(s), created "
                f"{result.created_count}, updated {result.updated_count}, and auto-resolved "
                f"{result.auto_resolved_count}."
            ),
        )
    )
    return result
