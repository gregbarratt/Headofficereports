from __future__ import annotations

import smtplib
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from email.message import EmailMessage

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.reporting import (
    AgentCommission,
    BankTransaction,
    Booking,
    CustomerPayment,
    EmailRecipient,
    ExceptionRecord,
    Refund,
    ReportRun,
    SupplierPayment,
)
from app.services.reports import REPORT_TYPES, generate_excel_report
from app.services.trust_reconciliation import calculate_trust_reconciliation
from app.services.weekly_snapshots import compare_snapshots, latest_snapshot, movement_summary, previous_snapshot, snapshot_rows


ZERO = Decimal("0.00")
ACTIVE_EXCEPTION_STATUSES = {"open", "reviewing"}
COMMISSION_DUE_STATUSES = {"accrued", "due", "withheld"}


@dataclass(frozen=True)
class EmailAttachment:
    filename: str
    content: bytes


@dataclass(frozen=True)
class WeeklyEmailSummary:
    actual_trust_balance: Decimal | None
    required_trust_balance: Decimal
    trust_variance: Decimal | None
    live_bookings: int
    new_bookings: int
    cancelled_bookings: int
    refunds_due: Decimal
    supplier_payments_due: Decimal
    agent_commission_due: Decimal
    atol_exceptions: int
    unmatched_transactions: int
    critical_exceptions: int


@dataclass(frozen=True)
class WeeklyEmailResult:
    recipient_count: int
    attachment_count: int


def money(value: Decimal | None) -> Decimal:
    if value is None:
        return ZERO
    return Decimal(value).quantize(Decimal("0.01"))


def positive(value: Decimal) -> Decimal:
    return value if value > ZERO else ZERO


def money_text(value: Decimal | None) -> str:
    if value is None:
        return "Not imported"
    return f"GBP {money(value):,.2f}"


def active_recipients(db: Session) -> list[EmailRecipient]:
    return list(
        db.scalars(
            select(EmailRecipient)
            .where(EmailRecipient.is_active.is_(True))
            .order_by(EmailRecipient.email)
        )
    )


def booking_status_count(db: Session, statuses: set[str]) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(Booking)
            .where(Booking.normalised_status.in_(statuses))
        )
        or 0
    )


def supplier_payments_due(db: Session) -> Decimal:
    totals = {
        booking_ref: money(total)
        for booking_ref, total in db.execute(
            select(SupplierPayment.booking_ref, func.sum(SupplierPayment.supplier_payment_amount))
            .where(SupplierPayment.booking_ref.is_not(None))
            .where(SupplierPayment.payment_source == "taps")
            .group_by(SupplierPayment.booking_ref)
        )
    }
    total_due = ZERO
    for booking in db.scalars(select(Booking)):
        expected = money(booking.expected_supplier_nett)
        if expected == ZERO:
            continue
        total_due += positive(expected - totals.get(booking.booking_ref, ZERO))
    return money(total_due)


def commission_due(db: Session) -> Decimal:
    return money(
        db.scalar(
            select(func.sum(AgentCommission.net_commission_due)).where(
                AgentCommission.commission_status.in_(COMMISSION_DUE_STATUSES)
            )
        )
    )


def count_active_exceptions(db: Session, *, severity: str | None = None, exception_type: str | None = None) -> int:
    statement = select(func.count()).select_from(ExceptionRecord).where(ExceptionRecord.status.in_(ACTIVE_EXCEPTION_STATUSES))
    if severity:
        statement = statement.where(ExceptionRecord.severity == severity)
    if exception_type:
        statement = statement.where(ExceptionRecord.exception_type == exception_type)
    return db.scalar(statement) or 0


def unmatched_transaction_count(db: Session) -> int:
    customer = (
        db.scalar(
            select(func.count())
            .select_from(CustomerPayment)
            .where(CustomerPayment.match_confidence == "unmatched", CustomerPayment.payment_source == "sings")
        )
        or 0
    )
    supplier = (
        db.scalar(
            select(func.count())
            .select_from(SupplierPayment)
            .where(SupplierPayment.match_status == "unmatched", SupplierPayment.payment_source == "taps")
        )
        or 0
    )
    bank = db.scalar(select(func.count()).select_from(BankTransaction).where(BankTransaction.match_status == "unmatched")) or 0
    refunds = (
        db.scalar(
            select(func.count())
            .select_from(Refund)
            .where((Refund.booking_id.is_(None)) | (Refund.booking_ref.is_(None)))
        )
        or 0
    )
    return customer + supplier + bank + refunds


def latest_movement_counts(db: Session) -> tuple[int, int]:
    snapshot = latest_snapshot(db)
    if snapshot is None:
        return 0, 0
    previous = previous_snapshot(db, snapshot)
    if previous is None:
        return 0, 0
    summary = movement_summary(compare_snapshots(snapshot_rows(db, previous.id), snapshot_rows(db, snapshot.id)))
    return summary.new_bookings, summary.cancelled_bookings


def build_weekly_email_summary(db: Session) -> WeeklyEmailSummary:
    trust = calculate_trust_reconciliation(db)
    new_bookings, cancelled_bookings = latest_movement_counts(db)
    return WeeklyEmailSummary(
        actual_trust_balance=trust.summary.actual_trust_balance,
        required_trust_balance=trust.summary.required_trust_balance,
        trust_variance=trust.summary.trust_variance,
        live_bookings=booking_status_count(db, {"open", "amended/live"}),
        new_bookings=new_bookings,
        cancelled_bookings=cancelled_bookings,
        refunds_due=trust.summary.refunds_due,
        supplier_payments_due=supplier_payments_due(db),
        agent_commission_due=commission_due(db),
        atol_exceptions=count_active_exceptions(db, exception_type="atol_certificate_missing"),
        unmatched_transactions=unmatched_transaction_count(db),
        critical_exceptions=count_active_exceptions(db, severity="critical"),
    )


def weekly_email_body(summary: WeeklyEmailSummary) -> str:
    return "\n".join(
        [
            "Head Office weekly reporting summary",
            "",
            f"Actual Trust Balance: {money_text(summary.actual_trust_balance)}",
            f"Required Trust Balance: {money_text(summary.required_trust_balance)}",
            f"Trust Variance: {money_text(summary.trust_variance)}",
            f"Live Bookings: {summary.live_bookings}",
            f"New Bookings: {summary.new_bookings}",
            f"Cancelled Bookings: {summary.cancelled_bookings}",
            f"Refunds Due: {money_text(summary.refunds_due)}",
            f"Supplier Payments Due: {money_text(summary.supplier_payments_due)}",
            f"Agent Commission Due: {money_text(summary.agent_commission_due)}",
            f"ATOL Exceptions: {summary.atol_exceptions}",
            f"Unmatched Transactions: {summary.unmatched_transactions}",
            f"Critical Exceptions: {summary.critical_exceptions}",
            "",
            "Excel reports are attached.",
        ]
    )


def weekly_email_attachments(db: Session) -> list[EmailAttachment]:
    attachments = []
    for report_type in REPORT_TYPES:
        filename, content = generate_excel_report(db, report_type)
        attachments.append(EmailAttachment(filename=filename, content=content))
    return attachments


def smtp_ready() -> bool:
    return settings.smtp_configured


def send_email_message(message: EmailMessage) -> None:
    if not smtp_ready():
        raise ValueError("SMTP is not configured. Add SMTP_HOST and SMTP_FROM_EMAIL before sending email.")

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)


def send_weekly_email(db: Session, report_run: ReportRun) -> WeeklyEmailResult:
    if not smtp_ready():
        raise ValueError("SMTP is not configured. Add SMTP_HOST and SMTP_FROM_EMAIL before sending email.")

    recipients = active_recipients(db)
    if not recipients:
        raise ValueError("No active email recipients are configured.")

    summary = build_weekly_email_summary(db)
    attachments = weekly_email_attachments(db)
    subject_date = datetime.now(UTC).date().isoformat()

    message = EmailMessage()
    message["Subject"] = f"Head Office Weekly Reports - {subject_date}"
    message["From"] = settings.smtp_from_email
    message["To"] = ", ".join(recipient.email for recipient in recipients)
    message.set_content(weekly_email_body(summary))

    for attachment in attachments:
        message.add_attachment(
            attachment.content,
            maintype="application",
            subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=attachment.filename,
        )

    send_email_message(message)
    report_run.output_filename = f"weekly_email_{subject_date}.eml"
    return WeeklyEmailResult(recipient_count=len(recipients), attachment_count=len(attachments))
