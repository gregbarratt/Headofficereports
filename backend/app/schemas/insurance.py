from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class InsuranceCostRead(BaseModel):
    id: int
    upload_batch_id: int | None
    booking_ref: str | None
    external_reference: str | None
    trade_code: str | None
    trading_name: str | None
    lead_name: str | None
    departure_date: date | None
    supplement_type: str | None
    gross_amount: Decimal
    discount_amount: Decimal | None
    net_amount: Decimal | None
    insurance_cost_amount: Decimal
    insurance_status: str | None
    created_at_imported: datetime | None
    last_update_imported: datetime | None
    is_duplicate: bool
    match_status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class InsuranceSummaryRead(BaseModel):
    total_rows: int
    active_rows: int
    active_cost_total: Decimal
    unmatched_count: int
    duplicate_count: int


class InsuranceListResponse(BaseModel):
    costs: list[InsuranceCostRead]
    summary: InsuranceSummaryRead
