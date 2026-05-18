from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class TrustBookingRead(BaseModel):
    booking_ref: str
    customer_last_name: str | None
    booking_status: str | None
    gross_booking_value: Decimal | None
    expected_supplier_nett: Decimal | None
    customer_payments_received: Decimal
    card_fees: Decimal
    estimated_card_fees: Decimal
    net_trust_receipts: Decimal
    supplier_payments_made: Decimal
    refunds_paid: Decimal
    refunds_due: Decimal
    refunds_unpaid: Decimal
    current_booking_trust_balance: Decimal
    required_trust_balance_contribution: Decimal
    trust_status: str
    missing_items: list[str]


class TrustSummaryRead(BaseModel):
    customer_payments_received: Decimal
    card_fees: Decimal
    estimated_card_fees: Decimal
    net_trust_receipts: Decimal
    supplier_payments_made: Decimal
    refunds_paid: Decimal
    refunds_due: Decimal
    refunds_unpaid: Decimal
    positive_booking_trust_balances: Decimal
    unmatched_customer_receipts: Decimal
    required_trust_balance: Decimal
    actual_trust_balance: Decimal | None
    trust_variance: Decimal | None
    bank_status: str


class TrustReconciliationResponse(BaseModel):
    generated_at: datetime
    summary: TrustSummaryRead
    bookings: list[TrustBookingRead]
