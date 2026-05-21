"""Add booking check adjustments.

Revision ID: 0005_check_adjust
Revises: 0004_master_pax
Create Date: 2026-05-21
"""
from alembic import op
import sqlalchemy as sa


revision = "0005_check_adjust"
down_revision = "0004_master_pax"
branch_labels = None
depends_on = None


def upgrade() -> None:
    money = sa.Numeric(14, 2)
    op.create_table(
        "booking_check_adjustments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("booking_ref", sa.String(length=80), nullable=False),
        sa.Column("field_name", sa.String(length=80), nullable=False),
        sa.Column("adjusted_amount", money, nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("booking_ref", "field_name"),
    )
    op.create_index("ix_booking_check_adjustments_booking_ref", "booking_check_adjustments", ["booking_ref"])


def downgrade() -> None:
    op.drop_index("ix_booking_check_adjustments_booking_ref", table_name="booking_check_adjustments")
    op.drop_table("booking_check_adjustments")
