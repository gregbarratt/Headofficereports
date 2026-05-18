from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class AgentCommissionRead(BaseModel):
    id: int
    upload_batch_id: int | None
    booking_ref: str | None
    agent_name: str | None
    commission_basis: str | None
    gross_commission: Decimal
    deductions: Decimal | None
    net_commission_due: Decimal | None
    commission_status: str
    due_date: date | None
    paid_date: date | None
    match_status: str
    created_at: datetime


class TrueProfitRead(BaseModel):
    booking_ref: str
    customer_last_name: str | None
    gross_booking_value: Decimal | None
    expected_supplier_nett: Decimal | None
    payment_fees: Decimal
    estimated_payment_fees: Decimal
    agent_commission: Decimal
    refunds_adjustments: Decimal
    true_booking_profit: Decimal | None
    true_margin_percentage: Decimal | None
    true_profit_status: str
    missing_items: list[str]


class AgentCommissionSummaryRead(BaseModel):
    total_rows: int
    gross_commission_total: Decimal
    deductions_total: Decimal
    net_commission_due_total: Decimal
    accrued_count: int
    due_count: int
    paid_count: int
    withheld_count: int
    clawed_back_count: int
    cancelled_count: int
    unmatched_count: int


class AgentCommissionListResponse(BaseModel):
    commissions: list[AgentCommissionRead]
    true_profits: list[TrueProfitRead]
    summary: AgentCommissionSummaryRead
