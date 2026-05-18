from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_super_admin
from app.db.session import get_db
from app.models.reporting import AuditLog, ExceptionRecord
from app.models.user import User
from app.schemas.exception import (
    ExceptionGenerationRead,
    ExceptionListResponse,
    ExceptionRead,
    ExceptionStatusUpdate,
    ExceptionSummaryRead,
)
from app.services.exceptions import generate_exceptions


router = APIRouter(prefix="/api/exceptions", tags=["Exceptions"])

VALID_STATUSES = {"open", "reviewing", "resolved", "ignored"}
VALID_SEVERITIES = {"critical", "high", "medium", "low"}


def build_summary(exceptions: list[ExceptionRecord]) -> ExceptionSummaryRead:
    return ExceptionSummaryRead(
        total_count=len(exceptions),
        open_count=sum(1 for exception in exceptions if exception.status == "open"),
        reviewing_count=sum(1 for exception in exceptions if exception.status == "reviewing"),
        resolved_count=sum(1 for exception in exceptions if exception.status == "resolved"),
        ignored_count=sum(1 for exception in exceptions if exception.status == "ignored"),
        critical_count=sum(1 for exception in exceptions if exception.severity == "critical"),
        high_count=sum(1 for exception in exceptions if exception.severity == "high"),
        medium_count=sum(1 for exception in exceptions if exception.severity == "medium"),
        low_count=sum(1 for exception in exceptions if exception.severity == "low"),
    )


@router.get("", response_model=ExceptionListResponse)
def list_exceptions(
    status_filter: str | None = Query(default=None, alias="status"),
    severity_filter: str | None = Query(default=None, alias="severity"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> ExceptionListResponse:
    generation = generate_exceptions(db, actor_user_id=current_user.id)
    db.commit()

    all_exceptions = list(db.scalars(select(ExceptionRecord)))
    statement = select(ExceptionRecord).order_by(
        ExceptionRecord.detected_at.desc(),
        ExceptionRecord.id.desc(),
    )

    if status_filter and status_filter != "all":
        if status_filter not in VALID_STATUSES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid exception status.")
        statement = statement.where(ExceptionRecord.status == status_filter)

    if severity_filter and severity_filter != "all":
        if severity_filter not in VALID_SEVERITIES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid exception severity.")
        statement = statement.where(ExceptionRecord.severity == severity_filter)

    exceptions = list(db.scalars(statement.limit(300)))
    return ExceptionListResponse(
        exceptions=exceptions,
        summary=build_summary(all_exceptions),
        generation=ExceptionGenerationRead(
            generated_count=generation.generated_count,
            created_count=generation.created_count,
            updated_count=generation.updated_count,
            auto_resolved_count=generation.auto_resolved_count,
        ),
    )


@router.post("/generate", response_model=ExceptionGenerationRead)
def generate_current_exceptions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> ExceptionGenerationRead:
    generation = generate_exceptions(db, actor_user_id=current_user.id)
    db.commit()
    return ExceptionGenerationRead(
        generated_count=generation.generated_count,
        created_count=generation.created_count,
        updated_count=generation.updated_count,
        auto_resolved_count=generation.auto_resolved_count,
    )


@router.patch("/{exception_id}", response_model=ExceptionRead)
def update_exception_status(
    exception_id: int,
    payload: ExceptionStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> ExceptionRecord:
    next_status = payload.status
    if next_status not in VALID_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid exception status.")

    exception = db.get(ExceptionRecord, exception_id)
    if exception is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exception not found.")

    previous_status = exception.status
    exception.status = next_status
    if next_status in {"resolved", "ignored"}:
        exception.resolved_at = datetime.now(UTC)
        exception.resolved_by_user_id = current_user.id
    else:
        exception.resolved_at = None
        exception.resolved_by_user_id = None

    db.add(
        AuditLog(
            actor_user_id=current_user.id,
            action="exception_status_update",
            table_name="exceptions",
            record_id=exception.id,
            description=f"Exception status changed from {previous_status} to {next_status}.",
            before_data={"status": previous_status},
            after_data={"status": next_status},
        )
    )
    db.commit()
    db.refresh(exception)
    return exception
