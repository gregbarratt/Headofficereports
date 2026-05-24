"""Add Traveltek supplier references.

Revision ID: 0011_tt_supplier_refs
Revises: 0010_tt_total_due
Create Date: 2026-05-24
"""
from alembic import op
import sqlalchemy as sa


revision = "0011_tt_supplier_refs"
down_revision = "0010_tt_total_due"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bookings", sa.Column("supplier_references_raw", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("bookings", "supplier_references_raw")
