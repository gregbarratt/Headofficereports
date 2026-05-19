"""Add payment sources and booking company.

Revision ID: 0002_payment_sources
Revises: 0001_phase_2_core_schema
Create Date: 2026-05-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import table, column


revision = "0002_payment_sources"
down_revision = "0001_phase_2_core_schema"
branch_labels = None
depends_on = None


bookings_table = table(
    "bookings",
    column("booking_ref", sa.String()),
    column("booking_company", sa.String()),
)

supplier_payments_table = table(
    "supplier_payments",
    column("payment_source", sa.String()),
    column("duplicate_key", sa.String()),
)


def booking_company_for_reference(booking_ref: str | None) -> str:
    reference = (booking_ref or "").strip().upper()
    if reference.startswith("OTC"):
        return "otc"
    if reference.startswith(("LEM", "LMX", "LM-", "LM_")) or "LEMIEUX" in reference:
        return "lemieux"
    return "review"


def upgrade() -> None:
    op.add_column(
        "bookings",
        sa.Column("booking_company", sa.String(length=80), nullable=False, server_default="otc"),
    )
    connection = op.get_bind()
    booking_refs = connection.execute(sa.select(bookings_table.c.booking_ref)).scalars()
    for booking_ref in booking_refs:
        connection.execute(
            bookings_table.update()
            .where(bookings_table.c.booking_ref == booking_ref)
            .values(booking_company=booking_company_for_reference(booking_ref))
        )
    op.create_index("ix_bookings_booking_company", "bookings", ["booking_company"])

    op.add_column(
        "supplier_payments",
        sa.Column("payment_source", sa.String(length=40), nullable=False, server_default="taps"),
    )
    duplicate_rows = connection.execute(
        sa.select(supplier_payments_table.c.duplicate_key).where(supplier_payments_table.c.duplicate_key.is_not(None))
    ).scalars()
    for duplicate_key in duplicate_rows:
        if duplicate_key.startswith(("taps|", "tt|")):
            continue
        connection.execute(
            supplier_payments_table.update()
            .where(supplier_payments_table.c.duplicate_key == duplicate_key)
            .values(duplicate_key=f"taps|{duplicate_key}")
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
