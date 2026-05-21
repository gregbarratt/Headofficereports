from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class BookingRead(BaseModel):
    id: int
    booking_ref: str
    booking_company: str
    imported_booking_status: str | None
    normalised_status: str | None
    customer_last_name: str | None
    destination: str | None
    travel_elements_raw: str | None
    departure_date: date | None
    return_date: date | None
    booking_date: datetime | None
    customer_balance_due_date: date | None
    passenger_count: int | None
    imported_customer_outstanding: Decimal | None
    imported_supplier_outstanding: Decimal | None
    gross_booking_value: Decimal | None
    expected_supplier_nett: Decimal | None
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
