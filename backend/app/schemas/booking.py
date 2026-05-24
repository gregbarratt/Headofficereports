from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class BookingRead(BaseModel):
    id: int
    booking_ref: str
    traveltek_booking_id: str | None = None
    booking_company: str
    imported_booking_status: str | None
    normalised_status: str | None
    customer_last_name: str | None
    agent_in_charge: str | None
    destination: str | None
    travel_elements_raw: str | None
    supplier_references_raw: str | None = None
    departure_date: date | None
    return_date: date | None
    passenger_count: int | None
    booking_date: datetime | None
    customer_balance_due_date: date | None
    imported_customer_outstanding: Decimal | None
    imported_supplier_outstanding: Decimal | None
    gross_booking_value: Decimal | None
    expected_supplier_nett: Decimal | None
    non_trusted_total_due: Decimal | None = None
    non_trusted_total_received: Decimal | None = None
    non_trusted_paid_supplier: Decimal | None = None
    non_trusted_projected_profit: Decimal | None = None
    flight_included: bool
    accommodation_included: bool
    cruise_included: bool
    extras_included: bool
    package_included: bool
    atol_review_status: str | None
    last_master_upload_batch_id: int | None
    updated_at: datetime

    model_config = {"from_attributes": True}


class BookingListResponse(BaseModel):
    bookings: list[BookingRead]
    total: int


class BookingCheckRow(BaseModel):
    booking_ref: str
    traveltek_booking_id: str | None = None
    booking_company: str
    normalised_status: str | None
    customer_last_name: str | None
    agent_in_charge: str | None
    destination: str | None
    travel_elements_raw: str | None
    supplier_references_raw: str | None = None
    departure_date: date | None
    return_date: date | None = None
    passenger_count: int | None = None
    gross_booking_value: Decimal | None
    expected_supplier_nett: Decimal | None
    insurance_cost_total: Decimal
    expected_supplier_total: Decimal | None
    supplier_taps_total: Decimal
    supplier_tt_total: Decimal
    supplier_expected_variance: Decimal | None
    supplier_tt_variance: Decimal
    supplier_expected_check: str
    supplier_tt_check: str
    customer_sings_total: Decimal
    customer_tt_total: Decimal
    customer_expected_variance: Decimal | None
    customer_tt_variance: Decimal
    customer_expected_check: str
    customer_tt_check: str
    review_status: str
    review_note: str
    raw_gross_booking_value: Decimal | None
    raw_expected_supplier_total: Decimal | None
    raw_supplier_taps_total: Decimal
    raw_supplier_tt_total: Decimal
    raw_customer_sings_total: Decimal
    raw_customer_tt_total: Decimal
    traveltek_total_due: Decimal | None
    traveltek_total_amount_paid: Decimal | None
    traveltek_customer_outstanding: Decimal | None
    traveltek_due_to_suppliers: Decimal | None
    traveltek_paid_to_supplier: Decimal | None
    traveltek_projected_profit: Decimal | None
    manual_adjustments: dict[str, Decimal]
    manual_adjustment_note: str | None
    has_manual_adjustment: bool


class BookingChecksSummary(BaseModel):
    total_bookings: int
    supplier_expected_matches: int
    supplier_tt_matches: int
    customer_expected_matches: int
    customer_tt_matches: int
    fully_matched: int
    needs_review: int
    error_count: int
    awaiting_count: int


class BookingChecksResponse(BaseModel):
    summary: BookingChecksSummary
    bookings: list[BookingCheckRow]


class BookingCheckAdjustmentUpdate(BaseModel):
    gross_booking_value: Decimal | None = None
    expected_supplier_total: Decimal | None = None
    supplier_taps_total: Decimal | None = None
    supplier_tt_total: Decimal | None = None
    customer_sings_total: Decimal | None = None
    customer_tt_total: Decimal | None = None
    note: str | None = None
