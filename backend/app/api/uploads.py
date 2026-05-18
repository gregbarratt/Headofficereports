from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_super_admin
from app.core.uploads import UPLOAD_TYPES
from app.db.session import get_db
from app.models.reporting import UploadBatch
from app.models.user import User
from app.schemas.upload import UploadBatchRead, UploadTypeRead
from app.services.uploads import (
    build_stored_filename,
    clean_filename,
    inspect_upload_content,
    read_upload_file,
    save_upload_file,
)


router = APIRouter(prefix="/api/uploads", tags=["Uploads"])


def to_upload_batch_read(batch: UploadBatch) -> UploadBatchRead:
    return UploadBatchRead(
        id=batch.id,
        upload_type=batch.upload_type,
        upload_type_label=UPLOAD_TYPES.get(batch.upload_type, batch.upload_type),
        original_filename=batch.original_filename,
        status=batch.status,
        row_count=batch.row_count,
        accepted_rows=batch.accepted_rows,
        rejected_rows=batch.rejected_rows,
        error_summary=batch.error_summary,
        uploaded_at=batch.uploaded_at,
        completed_at=batch.completed_at,
    )


@router.get("/types", response_model=list[UploadTypeRead])
def list_upload_types(current_user: User = Depends(get_current_super_admin)) -> list[UploadTypeRead]:
    return [UploadTypeRead(value=value, label=label) for value, label in UPLOAD_TYPES.items()]


@router.get("", response_model=list[UploadBatchRead])
def list_upload_batches(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> list[UploadBatchRead]:
    statement = select(UploadBatch).order_by(UploadBatch.uploaded_at.desc(), UploadBatch.id.desc()).limit(100)
    batches = db.scalars(statement).all()
    return [to_upload_batch_read(batch) for batch in batches]


@router.post("", response_model=UploadBatchRead, status_code=status.HTTP_201_CREATED)
async def create_upload_batch(
    upload_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> UploadBatchRead:
    if upload_type not in UPLOAD_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload type is not recognised.",
        )

    original_filename = clean_filename(file.filename or "upload")
    batch = UploadBatch(
        upload_type=upload_type,
        original_filename=original_filename,
        status="validating",
        uploaded_by_user_id=current_user.id,
    )
    db.add(batch)
    db.flush()

    content = await read_upload_file(file)
    validation = inspect_upload_content(original_filename, content)
    batch.row_count = validation.row_count
    batch.accepted_rows = validation.accepted_rows
    batch.rejected_rows = validation.rejected_rows
    batch.error_summary = validation.error_summary
    batch.completed_at = datetime.now(UTC)

    if validation.passed:
        stored_filename = build_stored_filename(batch.id, original_filename)
        save_upload_file(content, stored_filename)
        batch.stored_filename = stored_filename
        batch.status = "validated"
    else:
        batch.status = "failed"

    db.commit()
    db.refresh(batch)

    if not validation.passed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=validation.error_summary,
        )

    return to_upload_batch_read(batch)
