from datetime import datetime

from pydantic import BaseModel


class ExceptionRead(BaseModel):
    id: int
    exception_type: str
    severity: str
    status: str
    title: str
    detail: str | None
    booking_ref: str | None
    related_table: str | None
    related_record_id: int | None
    detected_at: datetime
    resolved_at: datetime | None

    model_config = {"from_attributes": True}


class ExceptionSummaryRead(BaseModel):
    total_count: int
    open_count: int
    reviewing_count: int
    resolved_count: int
    ignored_count: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int


class ExceptionGenerationRead(BaseModel):
    generated_count: int
    created_count: int
    updated_count: int
    auto_resolved_count: int


class ExceptionListResponse(BaseModel):
    exceptions: list[ExceptionRead]
    summary: ExceptionSummaryRead
    generation: ExceptionGenerationRead


class ExceptionStatusUpdate(BaseModel):
    status: str
