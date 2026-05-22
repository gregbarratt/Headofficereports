"""Add Traveltek booking update review tables.

Revision ID: 0008_traveltek_updates
Revises: 0007_manual_trust_balance
Create Date: 2026-05-22
"""
from alembic import op
import sqlalchemy as sa


revision = "0008_traveltek_updates"
down_revision = "0007_manual_trust_balance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "traveltek_sync_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("status", sa.String(length=40), server_default="running", nullable=False),
        sa.Column("sync_type", sa.String(length=80), server_default="active_booking_check", nullable=False),
        sa.Column("checked_bookings", sa.Integer(), server_default="0", nullable=False),
        sa.Column("api_call_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("proposals_created", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("requested_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_traveltek_sync_runs_status", "traveltek_sync_runs", ["status"])

    op.create_table(
        "traveltek_booking_updates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sync_run_id", sa.Integer(), sa.ForeignKey("traveltek_sync_runs.id"), nullable=True),
        sa.Column("booking_id", sa.Integer(), sa.ForeignKey("bookings.id"), nullable=True),
        sa.Column("booking_ref", sa.String(length=80), nullable=False),
        sa.Column("field_name", sa.String(length=120), nullable=False),
        sa.Column("field_label", sa.String(length=160), nullable=False),
        sa.Column("current_value", sa.Text(), nullable=True),
        sa.Column("traveltek_value", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=40), server_default="open", nullable=False),
        sa.Column("raw_source", sa.JSON(), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_traveltek_booking_updates_booking_ref", "traveltek_booking_updates", ["booking_ref"])
    op.create_index("ix_traveltek_booking_updates_status", "traveltek_booking_updates", ["status"])


def downgrade() -> None:
    op.drop_index("ix_traveltek_booking_updates_status", table_name="traveltek_booking_updates")
    op.drop_index("ix_traveltek_booking_updates_booking_ref", table_name="traveltek_booking_updates")
    op.drop_table("traveltek_booking_updates")
    op.drop_index("ix_traveltek_sync_runs_status", table_name="traveltek_sync_runs")
    op.drop_table("traveltek_sync_runs")
