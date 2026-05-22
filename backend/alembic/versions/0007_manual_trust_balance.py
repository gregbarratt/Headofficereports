"""Add manual trust balances.

Revision ID: 0007_manual_trust_balance
Revises: 0006_bank_alloc
Create Date: 2026-05-22
"""
from alembic import op
import sqlalchemy as sa


revision = "0007_manual_trust_balance"
down_revision = "0006_bank_alloc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    money = sa.Numeric(14, 2)
    op.create_table(
        "manual_trust_balances",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("trust_value", money, nullable=False),
        sa.Column("balance_date", sa.Date(), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("entered_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_manual_trust_balances_balance_date", "manual_trust_balances", ["balance_date"])
    op.create_index("ix_manual_trust_balances_checked_at", "manual_trust_balances", ["checked_at"])


def downgrade() -> None:
    op.drop_index("ix_manual_trust_balances_checked_at", table_name="manual_trust_balances")
    op.drop_index("ix_manual_trust_balances_balance_date", table_name="manual_trust_balances")
    op.drop_table("manual_trust_balances")
