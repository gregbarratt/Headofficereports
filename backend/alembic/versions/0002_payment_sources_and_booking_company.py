"""Add payment sources and booking company.

Revision ID: 0002_payment_sources_and_booking_company
Revises: 0001_phase_2_core_schema
Create Date: 2026-05-19
"""
from alembic import op
import sqlalchemy as sa


revision = "0002_payment_sources_and_booking_company"
down_revision = "0001_phase_2_core_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "bookings",
        sa.Column("booking_company", sa.String(length=80), nullable=False, server_default="otc"),
    )
    op.execute(
        """
        UPDATE bookings
        SET booking_company = CASE
            WHEN upper(booking_ref) LIKE 'OTC%' THEN 'otc'
            WHEN upper(booking_ref) LIKE 'LEM%' THEN 'lemieux'
            WHEN upper(booking_ref) LIKE 'LMX%' THEN 'lemieux'
            WHEN upper(booking_ref) LIKE 'LM-%' THEN 'lemieux'
            WHEN upper(booking_ref) LIKE 'LM_%' THEN 'lemieux'
            WHEN upper(booking_ref) LIKE '%LEMIEUX%' THEN 'lemieux'
            ELSE 'review'
        END
        """
    )
    op.create_index("ix_bookings_booking_company", "bookings", ["booking_company"])

    op.add_column(
        "supplier_payments",
        sa.Column("payment_source", sa.String(length=40), nullable=False, server_default="taps"),
    )
    op.execute(
        """
        UPDATE supplier_payments
        SET duplicate_key = payment_source || '|' || duplicate_key
        WHERE duplicate_key IS NOT NULL
          AND duplicate_key NOT LIKE 'taps|%'
          AND duplicate_key NOT LIKE 'tt|%'
        """
    )
    op.create_index("ix_supplier_payments_payment_source", "supplier_payments", ["payment_source"])

    op.add_column(
        "customer_payments",
        sa.Column("payment_source", sa.String(length=40), nullable=False, server_default="sings"),
    )
    op.create_index("ix_customer_payments_payment_source", "customer_payments", ["payment_source"])


def downgrade() -> None:
    op.drop_index("ix_customer_payments_payment_source", table_name="customer_payments")
    op.drop_column("customer_payments", "payment_source")

    op.drop_index("ix_supplier_payments_payment_source", table_name="supplier_payments")
    op.drop_column("supplier_payments", "payment_source")

    op.drop_index("ix_bookings_booking_company", table_name="bookings")
    op.drop_column("bookings", "booking_company")
