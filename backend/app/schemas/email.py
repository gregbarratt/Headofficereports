from datetime import datetime

from pydantic import BaseModel

from app.schemas.report import ReportRunRead


class EmailRecipientCreate(BaseModel):
    email: str
    name: str | None = None


class EmailRecipientUpdate(BaseModel):
    name: str | None = None
    is_active: bool


class EmailRecipientRead(BaseModel):
    id: int
    email: str
    name: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class EmailRecipientListResponse(BaseModel):
    recipients: list[EmailRecipientRead]


class WeeklyEmailSendResponse(BaseModel):
    message: str
    recipient_count: int
    attachment_count: int
    report_run: ReportRunRead
