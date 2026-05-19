from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class CustomerPaymentRead(BaseModel):
    id: int
    upload_batch_id: int | None
    payment_source: str
    transaction_id: str | None
    booking_ref: str | None
    invoice_reference: str | None
    customer_name: str | None
    payment_date: date | None
    settlement_date: date | None
    gross_amount: Decimal
    fee_amount: Decimal | None
    net_settled_amount: Decimal | None
    fee_is_estimated: bool
    payment_method: str | None
    card_type: str | None
    card_brand: str | None
    transaction_status: str | None
    refund_indicator: bool
    chargeback_indicator: bool
    merchant_account: str | None
    settlement_batch_reference: str | None
    match_confidence: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CustomerPaymentSummaryRead(BaseModel):
    total_rows: int
    gross_total: Decimal
    fee_total: Decimal
    actual_fee_total: Decimal
    estimated_fee_total: Decimal
    net_settled_total: Decimal
    sings_gross_total: Decimal
    tt_gross_total: Decimal
    source_variance: Decimal
    matched_count: int
    lower_confidence_count: int
    unmatched_count: int


class CustomerPaymentListResponse(BaseModel):
    payments: list[CustomerPaymentRead]
    summary: CustomerPaymentSummaryRead


class FellohSyncRequest(BaseModel):
    start_date: date
    end_date: date


class FellohSyncResponse(BaseModel):
    start_date: date
    end_date: date
    fetched_transactions: int
    created_rows: int
    updated_rows: int
    checked_rows: int
    skipped_rows: int
    actual_fee_rows: int
    estimated_fee_rows: int
    unmatched_rows: int
    warnings: list[str]
