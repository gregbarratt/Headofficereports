"""Add Traveltek total due comparison field.

Revision ID: 0010_tt_total_due
Revises: 0009_tt_booking_fields
Create Date: 2026-05-24
"""
from alembic import op
import sqlalchemy as sa


revision = "0010_tt_total_due"
down_revision = "0009_tt_booking_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bookings", sa.Column("non_trusted_total_due", sa.Numeric(14, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("bookings", "non_trusted_total_due")
