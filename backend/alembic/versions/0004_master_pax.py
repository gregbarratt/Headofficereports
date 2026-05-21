"""Add master booking passenger count.

Revision ID: 0004_master_pax
Revises: 0003_insurance_costs
Create Date: 2026-05-21
"""
from alembic import op
import sqlalchemy as sa


revision = "0004_master_pax"
down_revision = "0003_insurance_costs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bookings", sa.Column("passenger_count", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("bookings", "passenger_count")
