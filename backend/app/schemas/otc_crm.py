from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class OtcCrmBookingRowRead(BaseModel):
    id: int
    upload_batch_id: int | None
    crm_booking_ref: str | None
    booking_ref: str | None
    customer_name: str | None
    email: str | None
    destination: str | None
    agent_name: str | None
    qc_status: str | None
    gross_amount: Decimal | None
    net_amount: Decimal | None
    profit_amount: Decimal | None
    commission_amount: Decimal | None
    passenger_count: int | None
    departure_date: date | None
    return_date: date | None
    created_date: date | None
    previous_agent_name: str | None
    agent_updated: bool
    match_status: str
    comparison_status: str
    comparison_notes: str | None
    traveltek_customer_name: str | None = None
    traveltek_agent_name: str | None = None
    traveltek_destination: str | None = None
    traveltek_gross_amount: Decimal | None = None
    traveltek_net_amount: Decimal | None = None
    traveltek_passenger_count: int | None = None
    traveltek_departure_date: date | None = None
    traveltek_return_date: date | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class OtcCrmSummaryRead(BaseModel):
    total_rows: int
    matched_rows: int
    unmatched_rows: int
    different_rows: int
    agent_updated_rows: int


class OtcCrmComparisonResponse(BaseModel):
    rows: list[OtcCrmBookingRowRead]
    summary: OtcCrmSummaryRead
