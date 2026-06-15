"""Add OTC CRM booking import rows.

Revision ID: 0014_otc_crm_rows
Revises: 0013_booking_archive_fields
Create Date: 2026-06-15
"""
from alembic import op
import sqlalchemy as sa


revision = "0014_otc_crm_rows"
down_revision = "0013_booking_archive_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "otc_crm_booking_rows",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("upload_batch_id", sa.Integer(), nullable=True),
        sa.Column("booking_id", sa.Integer(), nullable=True),
        sa.Column("crm_booking_ref", sa.String(length=80), nullable=True),
        sa.Column("booking_ref", sa.String(length=80), nullable=True),
        sa.Column("customer_name", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("destination", sa.String(length=255), nullable=True),
        sa.Column("agent_name", sa.String(length=160), nullable=True),
        sa.Column("qc_status", sa.String(length=80), nullable=True),
        sa.Column("gross_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("net_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("profit_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("commission_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("passenger_count", sa.Integer(), nullable=True),
        sa.Column("departure_date", sa.Date(), nullable=True),
        sa.Column("return_date", sa.Date(), nullable=True),
        sa.Column("created_date", sa.Date(), nullable=True),
        sa.Column("previous_agent_name", sa.String(length=160), nullable=True),
        sa.Column("agent_updated", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("match_status", sa.String(length=80), server_default="unmatched", nullable=False),
        sa.Column("comparison_status", sa.String(length=80), server_default="not_checked", nullable=False),
        sa.Column("comparison_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"]),
        sa.ForeignKeyConstraint(["upload_batch_id"], ["upload_batches.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_otc_crm_booking_rows_booking_ref", "otc_crm_booking_rows", ["booking_ref"])
    op.create_index("ix_otc_crm_booking_rows_comparison_status", "otc_crm_booking_rows", ["comparison_status"])
    op.create_index("ix_otc_crm_booking_rows_crm_booking_ref", "otc_crm_booking_rows", ["crm_booking_ref"])
    op.create_index("ix_otc_crm_booking_rows_match_status", "otc_crm_booking_rows", ["match_status"])


def downgrade() -> None:
    op.drop_index("ix_otc_crm_booking_rows_match_status", table_name="otc_crm_booking_rows")
    op.drop_index("ix_otc_crm_booking_rows_crm_booking_ref", table_name="otc_crm_booking_rows")
    op.drop_index("ix_otc_crm_booking_rows_comparison_status", table_name="otc_crm_booking_rows")
    op.drop_index("ix_otc_crm_booking_rows_booking_ref", table_name="otc_crm_booking_rows")
    op.drop_table("otc_crm_booking_rows")
