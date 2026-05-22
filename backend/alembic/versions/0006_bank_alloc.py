"""Add bank transaction booking allocation.

Revision ID: 0006_bank_alloc
Revises: 0005_check_adjust
Create Date: 2026-05-22
"""
from alembic import op
import sqlalchemy as sa


revision = "0006_bank_alloc"
down_revision = "0005_check_adjust"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bank_transactions", sa.Column("booking_id", sa.Integer(), nullable=True))
    op.add_column("bank_transactions", sa.Column("booking_ref", sa.String(length=80), nullable=True))
    op.add_column("bank_transactions", sa.Column("allocation_type", sa.String(length=80), nullable=True))
    op.create_foreign_key(
        "fk_bank_transactions_booking_id_bookings",
        "bank_transactions",
        "bookings",
        ["booking_id"],
        ["id"],
    )
    op.create_index("ix_bank_transactions_booking_ref", "bank_transactions", ["booking_ref"])


def downgrade() -> None:
    op.drop_index("ix_bank_transactions_booking_ref", table_name="bank_transactions")
    op.drop_constraint("fk_bank_transactions_booking_id_bookings", "bank_transactions", type_="foreignkey")
    op.drop_column("bank_transactions", "allocation_type")
    op.drop_column("bank_transactions", "booking_ref")
    op.drop_column("bank_transactions", "booking_id")
