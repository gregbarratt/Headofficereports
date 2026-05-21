"""Add insurance costs.

Revision ID: 0003_insurance_costs
Revises: 0002_payment_sources
Create Date: 2026-05-20
"""
from alembic import op
import sqlalchemy as sa


revision = "0003_insurance_costs"
down_revision = "0002_payment_sources"
branch_labels = None
depends_on = None


money = sa.Numeric(14, 2)


def upgrade() -> None:
    op.create_table(
        "insurance_costs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("upload_batch_id", sa.Integer(), sa.ForeignKey("upload_batches.id"), nullable=True),
        sa.Column("booking_id", sa.Integer(), sa.ForeignKey("bookings.id"), nullable=True),
        sa.Column("booking_ref", sa.String(length=80), nullable=True),
        sa.Column("external_reference", sa.String(length=160), nullable=True),
        sa.Column("trade_code", sa.String(length=80), nullable=True),
        sa.Column("trading_name", sa.String(length=255), nullable=True),
        sa.Column("lead_name", sa.String(length=255), nullable=True),
        sa.Column("departure_date", sa.Date(), nullable=True),
        sa.Column("supplement_type", sa.String(length=255), nullable=True),
        sa.Column("gross_amount", money, nullable=False),
        sa.Column("discount_amount", money, nullable=True),
        sa.Column("net_amount", money, nullable=True),
        sa.Column("insurance_cost_amount", money, nullable=False),
        sa.Column("insurance_status", sa.String(length=80), nullable=True),
        sa.Column("created_at_imported", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_update_imported", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duplicate_key", sa.String(length=512), nullable=True),
        sa.Column("is_duplicate", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("match_status", sa.String(length=80), nullable=False, server_default="unmatched"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_insurance_costs_booking_ref", "insurance_costs", ["booking_ref"])
    op.create_index("ix_insurance_costs_duplicate_key", "insurance_costs", ["duplicate_key"])
    op.create_index("ix_insurance_costs_insurance_status", "insurance_costs", ["insurance_status"])


def downgrade() -> None:
    op.drop_index("ix_insurance_costs_insurance_status", table_name="insurance_costs")
    op.drop_index("ix_insurance_costs_duplicate_key", table_name="insurance_costs")
    op.drop_index("ix_insurance_costs_booking_ref", table_name="insurance_costs")
    op.drop_table("insurance_costs")
