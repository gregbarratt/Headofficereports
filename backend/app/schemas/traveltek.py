from datetime import date, datetime

from pydantic import BaseModel, Field


class TraveltekSyncRequest(BaseModel):
    limit: int = Field(default=25, ge=1, le=500)


class TraveltekBookingImportRequest(BaseModel):
    start_date: date
    end_date: date
    date_type: str = Field(default="booking_date", pattern="^(departure_date|booking_date)$")
    limit: int = Field(default=25, ge=1, le=500)


class TraveltekFullCatchUpBatchRequest(BaseModel):
    start_date: date
    end_date: date
    batch_days: int = Field(default=30, ge=1, le=92)
    limit: int = Field(default=100, ge=1, le=500)
    reset_progress: bool = False


class TraveltekActiveMaintenanceRequest(BaseModel):
    new_booking_start_date: date
    new_booking_end_date: date
    new_booking_limit: int = Field(default=100, ge=1, le=500)
    refresh_limit: int = Field(default=100, ge=1, le=500)
    active_window_days: int = Field(default=60, ge=1, le=365)


class TraveltekUpdateEverythingBatchRequest(BaseModel):
    limit: int = Field(default=25, ge=1, le=500)
    reset_progress: bool = False


class TraveltekNewReferenceScanRequest(BaseModel):
    max_references: int = Field(default=25, ge=1, le=200)
    stop_after_missing: int = Field(default=10, ge=1, le=50)


class TraveltekSyncRunRead(BaseModel):
    id: int
    status: str
    sync_type: str
    checked_bookings: int
    api_call_count: int
    proposals_created: int
    error_summary: str | None
    started_at: datetime
    finished_at: datetime | None

    model_config = {"from_attributes": True}


class TraveltekBookingUpdateRead(BaseModel):
    id: int
    sync_run_id: int | None
    booking_ref: str
    field_name: str
    field_label: str
    current_value: str | None
    traveltek_value: str | None
    traveltek_key_details: dict[str, str | None] | None = None
    status: str
    detected_at: datetime
    reviewed_at: datetime | None

    model_config = {"from_attributes": True}


class TraveltekUpdateStatusRequest(BaseModel):
    status: str


class TraveltekUpdateSummary(BaseModel):
    open_count: int
    reviewing_count: int
    resolved_count: int
    ignored_count: int


class TraveltekUpdatesResponse(BaseModel):
    configured: bool
    latest_run: TraveltekSyncRunRead | None
    summary: TraveltekUpdateSummary
    updates: list[TraveltekBookingUpdateRead]


class TraveltekFullCatchUpBatchResponse(BaseModel):
    run: TraveltekSyncRunRead | None
    batch_start_date: date | None
    batch_end_date: date | None
    next_start_date: date | None
    complete: bool
    estimated_calls_this_batch: int
    message: str


class TraveltekActiveMaintenanceResponse(BaseModel):
    new_booking_run: TraveltekSyncRunRead
    refresh_run: TraveltekSyncRunRead
    active_window_start_date: date
    estimated_calls_this_run: int
    message: str


class TraveltekUpdateEverythingBatchResponse(BaseModel):
    run: TraveltekSyncRunRead | None
    complete: bool
    next_booking_ref: str | None
    estimated_calls_this_batch: int
    message: str


class TraveltekNewReferenceScanResponse(BaseModel):
    run: TraveltekSyncRunRead
    started_after_booking_ref: str | None
    first_checked_booking_ref: str | None
    last_checked_booking_ref: str | None
    created_count: int
    updated_count: int
    missing_count: int
    message: str


class TraveltekSingleBookingRefreshResponse(BaseModel):
    booking_ref: str
    status: str
    changed: bool
    changes: list[dict[str, str | None]]
    extracted: dict[str, str | None]
    message: str


class TraveltekChangeLogRead(BaseModel):
    id: int
    booking_ref: str | None
    change_type: str
    changed_fields: list[str]
    changes: list[dict[str, str | None]]
    description: str | None
    created_at: datetime


class TraveltekStatusResponse(BaseModel):
    configured: bool
    base_url_configured: bool
    secure_base_url_configured: bool
    username_configured: bool
    password_configured: bool
    sitename_configured: bool
    max_calls_per_run: int
    latest_run: TraveltekSyncRunRead | None
    open_update_count: int
