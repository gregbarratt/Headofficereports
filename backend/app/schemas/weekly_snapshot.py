from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class WeeklySnapshotRead(BaseModel):
    id: int
    week_start_date: date
    week_end_date: date
    status: str
    generated_at: datetime
    booking_count: int


class WeeklySnapshotBookingRead(BaseModel):
    booking_ref: str
    booking_status: str | None
    gross_booking_value: Decimal | None
    expected_supplier_nett: Decimal | None
    customer_payments_total: Decimal | None
    card_fees_total: Decimal | None
    supplier_payments_total: Decimal | None
    refunds_due_total: Decimal | None
    refunds_paid_total: Decimal | None
    commission_due_total: Decimal | None
    calculated_trust_balance: Decimal | None
    atol_required: bool
    atol_certificate_issued: bool

    model_config = {"from_attributes": True}


class WeeklyMovementRead(BaseModel):
    booking_ref: str
    movement_type: str
    field_name: str
    previous_value: str | None
    current_value: str | None
    description: str


class WeeklyMovementSummaryRead(BaseModel):
    movement_count: int
    new_bookings: int
    cancelled_bookings: int
    completed_bookings: int
    changed_booking_value: int
    changed_supplier_cost: int
    changed_payment_position: int
    changed_supplier_payment_position: int
    changed_refund_position: int
    changed_commission_position: int
    changed_atol_status: int


class WeeklySnapshotDetailResponse(BaseModel):
    current_snapshot: WeeklySnapshotRead
    previous_snapshot: WeeklySnapshotRead | None
    summary: WeeklyMovementSummaryRead
    movements: list[WeeklyMovementRead]
    bookings: list[WeeklySnapshotBookingRead]


class WeeklySnapshotListResponse(BaseModel):
    snapshots: list[WeeklySnapshotRead]
    latest: WeeklySnapshotDetailResponse | None
