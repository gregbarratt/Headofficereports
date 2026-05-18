"""Phase 2 core reporting schema.

Revision ID: 0001_phase_2_core_schema
Revises:
Create Date: 2026-05-18
"""
from alembic import op
import sqlalchemy as sa


revision = "0001_phase_2_core_schema"
down_revision = None
branch_labels = None
depends_on = None


money = sa.Numeric(14, 2)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=512), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("is_super_admin", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "upload_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("upload_type", sa.String(length=60), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_filename", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="pending"),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("accepted_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("uploaded_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_upload_batches_upload_type", "upload_batches", ["upload_type"])
    op.create_index("ix_upload_batches_uploaded_at", "upload_batches", ["uploaded_at"])

    op.create_table(
        "bookings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("booking_ref", sa.String(length=80), nullable=False),
        sa.Column("imported_booking_status", sa.String(length=80), nullable=True),
        sa.Column("normalised_status", sa.String(length=80), nullable=True),
        sa.Column("customer_last_name", sa.String(length=160), nullable=True),
        sa.Column("destination", sa.String(length=255), nullable=True),
        sa.Column("travel_elements_raw", sa.Text(), nullable=True),
        sa.Column("departure_date", sa.Date(), nullable=True),
        sa.Column("return_date", sa.Date(), nullable=True),
        sa.Column("booking_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("customer_balance_due_date", sa.Date(), nullable=True),
        sa.Column("imported_customer_outstanding", money, nullable=True),
        sa.Column("imported_supplier_outstanding", money, nullable=True),
        sa.Column("gross_booking_value", money, nullable=True),
        sa.Column("expected_supplier_nett", money, nullable=True),
        sa.Column("non_trusted_total_received", money, nullable=True),
        sa.Column("non_trusted_paid_supplier", money, nullable=True),
        sa.Column("non_trusted_projected_profit", money, nullable=True),
        sa.Column("flight_included", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("accommodation_included", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("cruise_included", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("extras_included", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("package_included", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("atol_review_status", sa.String(length=120), nullable=True),
        sa.Column("atol_certificate_issued", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("last_master_upload_batch_id", sa.Integer(), sa.ForeignKey("upload_batches.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("booking_ref"),
    )
    op.create_index("ix_bookings_booking_ref", "bookings", ["booking_ref"])
    op.create_index("ix_bookings_departure_date", "bookings", ["departure_date"])
    op.create_index("ix_bookings_normalised_status", "bookings", ["normalised_status"])

    op.create_table(
        "supplier_payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("upload_batch_id", sa.Integer(), sa.ForeignKey("upload_batches.id"), nullable=True),
        sa.Column("booking_id", sa.Integer(), sa.ForeignKey("bookings.id"), nullable=True),
        sa.Column("booking_ref", sa.String(length=80), nullable=True),
        sa.Column("supplier_payment_date", sa.Date(), nullable=True),
        sa.Column("product_type", sa.String(length=120), nullable=True),
        sa.Column("supplier_name", sa.String(length=255), nullable=True),
        sa.Column("payment_supplier_name", sa.String(length=255), nullable=True),
        sa.Column("booking_date_imported", sa.Date(), nullable=True),
        sa.Column("departure_date_imported", sa.Date(), nullable=True),
        sa.Column("supplier_payment_method", sa.String(length=120), nullable=True),
        sa.Column("supplier_payment_amount", money, nullable=False),
        sa.Column("associated_vat", money, nullable=True),
        sa.Column("duplicate_key", sa.String(length=512), nullable=True),
        sa.Column("is_duplicate", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("match_status", sa.String(length=80), nullable=False, server_default="unmatched"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_supplier_payments_booking_ref", "supplier_payments", ["booking_ref"])
    op.create_index("ix_supplier_payments_duplicate_key", "supplier_payments", ["duplicate_key"])

    op.create_table(
        "customer_payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("upload_batch_id", sa.Integer(), sa.ForeignKey("upload_batches.id"), nullable=True),
        sa.Column("booking_id", sa.Integer(), sa.ForeignKey("bookings.id"), nullable=True),
        sa.Column("transaction_id", sa.String(length=160), nullable=True),
        sa.Column("booking_ref", sa.String(length=80), nullable=True),
        sa.Column("invoice_reference", sa.String(length=120), nullable=True),
        sa.Column("customer_name", sa.String(length=255), nullable=True),
        sa.Column("payment_date", sa.Date(), nullable=True),
        sa.Column("settlement_date", sa.Date(), nullable=True),
        sa.Column("gross_amount", money, nullable=False),
        sa.Column("fee_amount", money, nullable=True),
        sa.Column("net_settled_amount", money, nullable=True),
        sa.Column("fee_is_estimated", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("payment_method", sa.String(length=120), nullable=True),
        sa.Column("card_type", sa.String(length=120), nullable=True),
        sa.Column("card_brand", sa.String(length=120), nullable=True),
        sa.Column("transaction_status", sa.String(length=120), nullable=True),
        sa.Column("refund_indicator", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("chargeback_indicator", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("merchant_account", sa.String(length=160), nullable=True),
        sa.Column("settlement_batch_reference", sa.String(length=160), nullable=True),
        sa.Column("match_confidence", sa.String(length=80), nullable=False, server_default="unmatched"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_customer_payments_booking_ref", "customer_payments", ["booking_ref"])
    op.create_index("ix_customer_payments_transaction_id", "customer_payments", ["transaction_id"])

    op.create_table(
        "bank_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("upload_batch_id", sa.Integer(), sa.ForeignKey("upload_batches.id"), nullable=True),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("money_in", money, nullable=True),
        sa.Column("money_out", money, nullable=True),
        sa.Column("balance", money, nullable=True),
        sa.Column("account_type", sa.String(length=80), nullable=True),
        sa.Column("transaction_reference", sa.String(length=160), nullable=True),
        sa.Column("duplicate_key", sa.String(length=512), nullable=True),
        sa.Column("match_status", sa.String(length=80), nullable=False, server_default="unmatched"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_bank_transactions_transaction_date", "bank_transactions", ["transaction_date"])
    op.create_index("ix_bank_transactions_reference", "bank_transactions", ["transaction_reference"])

    op.create_table(
        "refunds",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("upload_batch_id", sa.Integer(), sa.ForeignKey("upload_batches.id"), nullable=True),
        sa.Column("booking_id", sa.Integer(), sa.ForeignKey("bookings.id"), nullable=True),
        sa.Column("booking_ref", sa.String(length=80), nullable=True),
        sa.Column("customer_name", sa.String(length=255), nullable=True),
        sa.Column("refund_reason", sa.Text(), nullable=True),
        sa.Column("refund_amount_due", money, nullable=False),
        sa.Column("refund_amount_paid", money, nullable=True),
        sa.Column("refund_status", sa.String(length=80), nullable=False, server_default="due"),
        sa.Column("supplier_refund_expected", money, nullable=True),
        sa.Column("supplier_refund_received", money, nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("paid_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_refunds_booking_ref", "refunds", ["booking_ref"])
    op.create_index("ix_refunds_refund_status", "refunds", ["refund_status"])

    op.create_table(
        "agent_commissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("upload_batch_id", sa.Integer(), sa.ForeignKey("upload_batches.id"), nullable=True),
        sa.Column("booking_id", sa.Integer(), sa.ForeignKey("bookings.id"), nullable=True),
        sa.Column("booking_ref", sa.String(length=80), nullable=True),
        sa.Column("agent_name", sa.String(length=255), nullable=True),
        sa.Column("commission_basis", sa.String(length=120), nullable=True),
        sa.Column("gross_commission", money, nullable=False),
        sa.Column("deductions", money, nullable=True),
        sa.Column("net_commission_due", money, nullable=True),
        sa.Column("commission_status", sa.String(length=80), nullable=False, server_default="accrued"),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("paid_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_agent_commissions_booking_ref", "agent_commissions", ["booking_ref"])
    op.create_index("ix_agent_commissions_status", "agent_commissions", ["commission_status"])

    op.create_table(
        "payment_method_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("payment_method", sa.String(length=120), nullable=False),
        sa.Column("card_type", sa.String(length=120), nullable=True),
        sa.Column("card_brand", sa.String(length=120), nullable=True),
        sa.Column("percentage_fee", sa.Numeric(7, 4), nullable=False, server_default="0"),
        sa.Column("fixed_fee", money, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("active_from", sa.Date(), nullable=True),
        sa.Column("active_to", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "weekly_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("week_start_date", sa.Date(), nullable=False),
        sa.Column("week_end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="generated"),
        sa.Column("generated_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("week_start_date", "week_end_date"),
    )

    op.create_table(
        "weekly_snapshot_bookings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("weekly_snapshot_id", sa.Integer(), sa.ForeignKey("weekly_snapshots.id"), nullable=False),
        sa.Column("booking_id", sa.Integer(), sa.ForeignKey("bookings.id"), nullable=True),
        sa.Column("booking_ref", sa.String(length=80), nullable=False),
        sa.Column("booking_status", sa.String(length=80), nullable=True),
        sa.Column("gross_booking_value", money, nullable=True),
        sa.Column("expected_supplier_nett", money, nullable=True),
        sa.Column("customer_payments_total", money, nullable=True),
        sa.Column("card_fees_total", money, nullable=True),
        sa.Column("supplier_payments_total", money, nullable=True),
        sa.Column("refunds_due_total", money, nullable=True),
        sa.Column("refunds_paid_total", money, nullable=True),
        sa.Column("commission_due_total", money, nullable=True),
        sa.Column("calculated_trust_balance", money, nullable=True),
        sa.Column("atol_required", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("atol_certificate_issued", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.UniqueConstraint("weekly_snapshot_id", "booking_ref"),
    )
    op.create_index("ix_weekly_snapshot_bookings_booking_ref", "weekly_snapshot_bookings", ["booking_ref"])

    op.create_table(
        "exceptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("exception_type", sa.String(length=120), nullable=False),
        sa.Column("severity", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="open"),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("booking_id", sa.Integer(), sa.ForeignKey("bookings.id"), nullable=True),
        sa.Column("booking_ref", sa.String(length=80), nullable=True),
        sa.Column("related_table", sa.String(length=120), nullable=True),
        sa.Column("related_record_id", sa.Integer(), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_exceptions_status", "exceptions", ["status"])
    op.create_index("ix_exceptions_severity", "exceptions", ["severity"])

    op.create_table(
        "report_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("report_type", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="pending"),
        sa.Column("requested_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("output_filename", sa.String(length=255), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
    )
    op.create_index("ix_report_runs_report_type", "report_runs", ["report_type"])

    op.create_table(
        "email_recipients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("email"),
    )

    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=160), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_secret", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("key"),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(length=160), nullable=False),
        sa.Column("table_name", sa.String(length=120), nullable=True),
        sa.Column("record_id", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("before_data", sa.JSON(), nullable=True),
        sa.Column("after_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_table("settings")
    op.drop_table("email_recipients")
    op.drop_index("ix_report_runs_report_type", table_name="report_runs")
    op.drop_table("report_runs")
    op.drop_index("ix_exceptions_severity", table_name="exceptions")
    op.drop_index("ix_exceptions_status", table_name="exceptions")
    op.drop_table("exceptions")
    op.drop_index("ix_weekly_snapshot_bookings_booking_ref", table_name="weekly_snapshot_bookings")
    op.drop_table("weekly_snapshot_bookings")
    op.drop_table("weekly_snapshots")
    op.drop_table("payment_method_rules")
    op.drop_index("ix_agent_commissions_status", table_name="agent_commissions")
    op.drop_index("ix_agent_commissions_booking_ref", table_name="agent_commissions")
    op.drop_table("agent_commissions")
    op.drop_index("ix_refunds_refund_status", table_name="refunds")
    op.drop_index("ix_refunds_booking_ref", table_name="refunds")
    op.drop_table("refunds")
    op.drop_index("ix_bank_transactions_reference", table_name="bank_transactions")
    op.drop_index("ix_bank_transactions_transaction_date", table_name="bank_transactions")
    op.drop_table("bank_transactions")
    op.drop_index("ix_customer_payments_transaction_id", table_name="customer_payments")
    op.drop_index("ix_customer_payments_booking_ref", table_name="customer_payments")
    op.drop_table("customer_payments")
    op.drop_index("ix_supplier_payments_duplicate_key", table_name="supplier_payments")
    op.drop_index("ix_supplier_payments_booking_ref", table_name="supplier_payments")
    op.drop_table("supplier_payments")
    op.drop_index("ix_bookings_normalised_status", table_name="bookings")
    op.drop_index("ix_bookings_departure_date", table_name="bookings")
    op.drop_index("ix_bookings_booking_ref", table_name="bookings")
    op.drop_table("bookings")
    op.drop_index("ix_upload_batches_uploaded_at", table_name="upload_batches")
    op.drop_index("ix_upload_batches_upload_type", table_name="upload_batches")
    op.drop_table("upload_batches")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
