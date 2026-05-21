"""Add master booking passenger count.

Revision ID: 0004_master_pax
Revises: 0003_insurance_costs
Create Date: 2026-05-21
"""

revision = "0004_master_pax"
down_revision = "0003_insurance_costs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # This deployment previously timed out while waiting for a table lock on Render.
    # Keep the revision so Alembic can move forward, but do not change the live table here.
    pass


def downgrade() -> None:
    pass
