from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class RefundRead(BaseModel):
    id: int
    upload_batch_id: int | None
    booking_ref: str | None
    customer_name: str | None
    refund_reason: str | None
    refund_amount_due: Decimal
    refund_amount_paid: Decimal | None
    refund_unpaid: Decimal
    refund_status: str
    supplier_refund_expected: Decimal | None
    supplier_refund_received: Decimal | None
    supplier_refund_outstanding: Decimal
    due_date: date | None
    paid_date: date | None
    match_status: str
    created_at: datetime


class RefundSummaryRead(BaseModel):
    total_rows: int
    refund_amount_due_total: Decimal
    refund_amount_paid_total: Decimal
    refund_unpaid_total: Decimal
    supplier_refund_expected_total: Decimal
    supplier_refund_received_total: Decimal
    supplier_refund_outstanding_total: Decimal
    overdue_count: int
    unmatched_count: int


class RefundListResponse(BaseModel):
    refunds: list[RefundRead]
    summary: RefundSummaryRead
