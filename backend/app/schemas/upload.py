from datetime import datetime

from pydantic import BaseModel


class UploadTypeRead(BaseModel):
    value: str
    label: str


class UploadBatchRead(BaseModel):
    id: int
    upload_type: str
    upload_type_label: str
    original_filename: str
    status: str
    row_count: int
    accepted_rows: int
    rejected_rows: int
    error_summary: str | None
    uploaded_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}
