"""Add Traveltek booking source fields.

Revision ID: 0009_tt_booking_fields
Revises: 0008_traveltek_updates
Create Date: 2026-05-22
"""
from alembic import op
import sqlalchemy as sa


revision = "0009_tt_booking_fields"
down_revision = "0008_traveltek_updates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bookings", sa.Column("agent_in_charge", sa.String(length=160), nullable=True))
    op.add_column("bookings", sa.Column("passenger_count", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("bookings", "passenger_count")
    op.drop_column("bookings", "agent_in_charge")
