"""Add Traveltek booking id.

Revision ID: 0012_tt_booking_id
Revises: 0011_tt_supplier_refs
Create Date: 2026-05-24
"""
from alembic import op
import sqlalchemy as sa


revision = "0012_tt_booking_id"
down_revision = "0011_tt_supplier_refs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bookings", sa.Column("traveltek_booking_id", sa.String(length=80), nullable=True))
    op.create_index("ix_bookings_traveltek_booking_id", "bookings", ["traveltek_booking_id"])


def downgrade() -> None:
    op.drop_index("ix_bookings_traveltek_booking_id", table_name="bookings")
    op.drop_column("bookings", "traveltek_booking_id")
