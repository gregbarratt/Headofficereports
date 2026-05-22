from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    false,
    func,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


Money = Numeric(14, 2)


class UploadBatch(Base):
    __tablename__ = "upload_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    upload_type: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="pending", server_default="pending", nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    accepted_rows: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    rejected_rows: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
        server_default=func.now(),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_ref: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    booking_company: Mapped[str] = mapped_column(String(80), default="otc", server_default="otc", index=True, nullable=False)
    imported_booking_status: Mapped[str | None] = mapped_column(String(80), nullable=True)
    normalised_status: Mapped[str | None] = mapped_column(String(80), index=True, nullable=True)
    customer_last_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    agent_in_charge: Mapped[str | None] = mapped_column(String(160), nullable=True)
    destination: Mapped[str | None] = mapped_column(String(255), nullable=True)
    travel_elements_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    departure_date: Mapped[date | None] = mapped_column(Date, index=True, nullable=True)
    return_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    passenger_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    booking_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    customer_balance_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    imported_customer_outstanding: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    imported_supplier_outstanding: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    gross_booking_value: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    expected_supplier_nett: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    non_trusted_total_received: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    non_trusted_paid_supplier: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    non_trusted_projected_profit: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    flight_included: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    accommodation_included: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    cruise_included: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    extras_included: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    package_included: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    atol_review_status: Mapped[str | None] = mapped_column(String(120), nullable=True)
    atol_certificate_issued: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    last_master_upload_batch_id: Mapped[int | None] = mapped_column(ForeignKey("upload_batches.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SupplierPayment(Base):
    __tablename__ = "supplier_payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    upload_batch_id: Mapped[int | None] = mapped_column(ForeignKey("upload_batches.id"), nullable=True)
    booking_id: Mapped[int | None] = mapped_column(ForeignKey("bookings.id"), nullable=True)
    payment_source: Mapped[str] = mapped_column(String(40), default="taps", server_default="taps", index=True, nullable=False)
    booking_ref: Mapped[str | None] = mapped_column(String(80), index=True, nullable=True)
    supplier_payment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    product_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    supplier_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payment_supplier_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    booking_date_imported: Mapped[date | None] = mapped_column(Date, nullable=True)
    departure_date_imported: Mapped[date | None] = mapped_column(Date, nullable=True)
    supplier_payment_method: Mapped[str | None] = mapped_column(String(120), nullable=True)
    supplier_payment_amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    associated_vat: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    duplicate_key: Mapped[str | None] = mapped_column(String(512), index=True, nullable=True)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    match_status: Mapped[str] = mapped_column(String(80), default="unmatched", server_default="unmatched", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CustomerPayment(Base):
    __tablename__ = "customer_payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    upload_batch_id: Mapped[int | None] = mapped_column(ForeignKey("upload_batches.id"), nullable=True)
    booking_id: Mapped[int | None] = mapped_column(ForeignKey("bookings.id"), nullable=True)
    payment_source: Mapped[str] = mapped_column(String(40), default="sings", server_default="sings", index=True, nullable=False)
    transaction_id: Mapped[str | None] = mapped_column(String(160), index=True, nullable=True)
    booking_ref: Mapped[str | None] = mapped_column(String(80), index=True, nullable=True)
    invoice_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    settlement_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    gross_amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    fee_amount: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    net_settled_amount: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    fee_is_estimated: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    payment_method: Mapped[str | None] = mapped_column(String(120), nullable=True)
    card_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    card_brand: Mapped[str | None] = mapped_column(String(120), nullable=True)
    transaction_status: Mapped[str | None] = mapped_column(String(120), nullable=True)
    refund_indicator: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    chargeback_indicator: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    merchant_account: Mapped[str | None] = mapped_column(String(160), nullable=True)
    settlement_batch_reference: Mapped[str | None] = mapped_column(String(160), nullable=True)
    match_confidence: Mapped[str] = mapped_column(String(80), default="unmatched", server_default="unmatched", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class BookingCheckAdjustment(Base):
    __tablename__ = "booking_check_adjustments"
    __table_args__ = (UniqueConstraint("booking_ref", "field_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_ref: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    field_name: Mapped[str] = mapped_column(String(80), nullable=False)
    adjusted_amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class BankTransaction(Base):
    __tablename__ = "bank_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    upload_batch_id: Mapped[int | None] = mapped_column(ForeignKey("upload_batches.id"), nullable=True)
    booking_id: Mapped[int | None] = mapped_column(ForeignKey("bookings.id"), nullable=True)
    booking_ref: Mapped[str | None] = mapped_column(String(80), index=True, nullable=True)
    allocation_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    transaction_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    money_in: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    money_out: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    balance: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    account_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    transaction_reference: Mapped[str | None] = mapped_column(String(160), index=True, nullable=True)
    duplicate_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    match_status: Mapped[str] = mapped_column(String(80), default="unmatched", server_default="unmatched", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ManualTrustBalance(Base):
    __tablename__ = "manual_trust_balances"

    id: Mapped[int] = mapped_column(primary_key=True)
    trust_value: Mapped[Decimal] = mapped_column(Money, nullable=False)
    balance_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    entered_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class TraveltekSyncRun(Base):
    __tablename__ = "traveltek_sync_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(40), default="running", server_default="running", index=True, nullable=False)
    sync_type: Mapped[str] = mapped_column(String(80), default="active_booking_check", server_default="active_booking_check", nullable=False)
    checked_bookings: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    api_call_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    proposals_created: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TraveltekBookingUpdate(Base):
    __tablename__ = "traveltek_booking_updates"

    id: Mapped[int] = mapped_column(primary_key=True)
    sync_run_id: Mapped[int | None] = mapped_column(ForeignKey("traveltek_sync_runs.id"), nullable=True)
    booking_id: Mapped[int | None] = mapped_column(ForeignKey("bookings.id"), nullable=True)
    booking_ref: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    field_name: Mapped[str] = mapped_column(String(120), nullable=False)
    field_label: Mapped[str] = mapped_column(String(160), nullable=False)
    current_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    traveltek_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="open", server_default="open", index=True, nullable=False)
    raw_source: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class Refund(Base):
    __tablename__ = "refunds"

    id: Mapped[int] = mapped_column(primary_key=True)
    upload_batch_id: Mapped[int | None] = mapped_column(ForeignKey("upload_batches.id"), nullable=True)
    booking_id: Mapped[int | None] = mapped_column(ForeignKey("bookings.id"), nullable=True)
    booking_ref: Mapped[str | None] = mapped_column(String(80), index=True, nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    refund_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    refund_amount_due: Mapped[Decimal] = mapped_column(Money, nullable=False)
    refund_amount_paid: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    refund_status: Mapped[str] = mapped_column(String(80), default="due", server_default="due", index=True, nullable=False)
    supplier_refund_expected: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    supplier_refund_received: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    paid_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class InsuranceCost(Base):
    __tablename__ = "insurance_costs"

    id: Mapped[int] = mapped_column(primary_key=True)
    upload_batch_id: Mapped[int | None] = mapped_column(ForeignKey("upload_batches.id"), nullable=True)
    booking_id: Mapped[int | None] = mapped_column(ForeignKey("bookings.id"), nullable=True)
    booking_ref: Mapped[str | None] = mapped_column(String(80), index=True, nullable=True)
    external_reference: Mapped[str | None] = mapped_column(String(160), nullable=True)
    trade_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    trading_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lead_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    departure_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    supplement_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gross_amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    discount_amount: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    net_amount: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    insurance_cost_amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    insurance_status: Mapped[str | None] = mapped_column(String(80), index=True, nullable=True)
    created_at_imported: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_update_imported: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duplicate_key: Mapped[str | None] = mapped_column(String(512), index=True, nullable=True)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    match_status: Mapped[str] = mapped_column(String(80), default="unmatched", server_default="unmatched", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AgentCommission(Base):
    __tablename__ = "agent_commissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    upload_batch_id: Mapped[int | None] = mapped_column(ForeignKey("upload_batches.id"), nullable=True)
    booking_id: Mapped[int | None] = mapped_column(ForeignKey("bookings.id"), nullable=True)
    booking_ref: Mapped[str | None] = mapped_column(String(80), index=True, nullable=True)
    agent_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    commission_basis: Mapped[str | None] = mapped_column(String(120), nullable=True)
    gross_commission: Mapped[Decimal] = mapped_column(Money, nullable=False)
    deductions: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    net_commission_due: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    commission_status: Mapped[str] = mapped_column(
        String(80),
        default="accrued",
        server_default="accrued",
        index=True,
        nullable=False,
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    paid_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PaymentMethodRule(Base):
    __tablename__ = "payment_method_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(120), nullable=False)
    card_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    card_brand: Mapped[str | None] = mapped_column(String(120), nullable=True)
    percentage_fee: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0, server_default="0", nullable=False)
    fixed_fee: Mapped[Decimal] = mapped_column(Money, default=0, server_default="0", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true(), nullable=False)
    active_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    active_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class WeeklySnapshot(Base):
    __tablename__ = "weekly_snapshots"
    __table_args__ = (UniqueConstraint("week_start_date", "week_end_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    week_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    week_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="generated", server_default="generated", nullable=False)
    generated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class WeeklySnapshotBooking(Base):
    __tablename__ = "weekly_snapshot_bookings"
    __table_args__ = (UniqueConstraint("weekly_snapshot_id", "booking_ref"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    weekly_snapshot_id: Mapped[int] = mapped_column(ForeignKey("weekly_snapshots.id"), nullable=False)
    booking_id: Mapped[int | None] = mapped_column(ForeignKey("bookings.id"), nullable=True)
    booking_ref: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    booking_status: Mapped[str | None] = mapped_column(String(80), nullable=True)
    gross_booking_value: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    expected_supplier_nett: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    customer_payments_total: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    card_fees_total: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    supplier_payments_total: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    refunds_due_total: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    refunds_paid_total: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    commission_due_total: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    calculated_trust_balance: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    atol_required: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    atol_certificate_issued: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)


class ExceptionRecord(Base):
    __tablename__ = "exceptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    exception_type: Mapped[str] = mapped_column(String(120), nullable=False)
    severity: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="open", server_default="open", index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    booking_id: Mapped[int | None] = mapped_column(ForeignKey("bookings.id"), nullable=True)
    booking_ref: Mapped[str | None] = mapped_column(String(80), nullable=True)
    related_table: Mapped[str | None] = mapped_column(String(120), nullable=True)
    related_record_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class ReportRun(Base):
    __tablename__ = "report_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_type: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="pending", server_default="pending", nullable=False)
    requested_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    output_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class EmailRecipient(Base):
    __tablename__ = "email_recipients"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Setting(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(160), nullable=False)
    table_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    record_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    before_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
        server_default=func.now(),
        nullable=False,
    )
