from datetime import datetime

from pydantic import BaseModel


class ReportTypeRead(BaseModel):
    value: str
    label: str


class ReportRunRead(BaseModel):
    id: int
    report_type: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    output_filename: str | None
    error_summary: str | None

    model_config = {"from_attributes": True}


class ReportRunListResponse(BaseModel):
    runs: list[ReportRunRead]
