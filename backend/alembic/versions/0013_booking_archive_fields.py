"""Add booking archive and commission review flags.

Revision ID: 0013_booking_archive_fields
Revises: 0012_tt_booking_id
Create Date: 2026-05-25
"""
from alembic import op
import sqlalchemy as sa


revision = "0013_booking_archive_fields"
down_revision = "0012_tt_booking_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "bookings",
        sa.Column("is_archived", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column("bookings", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("bookings", sa.Column("archive_note", sa.Text(), nullable=True))
    op.add_column(
        "bookings",
        sa.Column("agent_commission_review_required", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column("bookings", sa.Column("agent_commission_review_note", sa.Text(), nullable=True))
    op.create_index("ix_bookings_is_archived", "bookings", ["is_archived"])
    op.create_index(
        "ix_bookings_agent_commission_review_required",
        "bookings",
        ["agent_commission_review_required"],
    )


def downgrade() -> None:
    op.drop_index("ix_bookings_agent_commission_review_required", table_name="bookings")
    op.drop_index("ix_bookings_is_archived", table_name="bookings")
    op.drop_column("bookings", "agent_commission_review_note")
    op.drop_column("bookings", "agent_commission_review_required")
    op.drop_column("bookings", "archive_note")
    op.drop_column("bookings", "archived_at")
    op.drop_column("bookings", "is_archived")
