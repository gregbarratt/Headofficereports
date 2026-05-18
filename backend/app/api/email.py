from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_super_admin
from app.db.session import get_db
from app.models.reporting import EmailRecipient, ReportRun
from app.models.user import User
from app.schemas.email import (
    EmailRecipientCreate,
    EmailRecipientListResponse,
    EmailRecipientRead,
    EmailRecipientUpdate,
    WeeklyEmailSendResponse,
)
from app.services.weekly_email import send_weekly_email


router = APIRouter(tags=["Email Reporting"])


def normalise_email(email: str) -> str:
    return email.strip().lower()


def validate_email(email: str) -> str:
    cleaned = normalise_email(email)
    if "@" not in cleaned or "." not in cleaned.split("@")[-1]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enter a valid email address.")
    return cleaned


@router.get("/api/email-recipients", response_model=EmailRecipientListResponse)
def list_email_recipients(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> EmailRecipientListResponse:
    recipients = list(db.scalars(select(EmailRecipient).order_by(EmailRecipient.email)))
    return EmailRecipientListResponse(recipients=recipients)


@router.post("/api/email-recipients", response_model=EmailRecipientRead)
def create_email_recipient(
    payload: EmailRecipientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> EmailRecipient:
    recipient = EmailRecipient(
        email=validate_email(payload.email),
        name=payload.name.strip() if payload.name else None,
        is_active=True,
    )
    db.add(recipient)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email recipient already exists.") from exc
    db.refresh(recipient)
    return recipient


@router.patch("/api/email-recipients/{recipient_id}", response_model=EmailRecipientRead)
def update_email_recipient(
    recipient_id: int,
    payload: EmailRecipientUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> EmailRecipient:
    recipient = db.get(EmailRecipient, recipient_id)
    if recipient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email recipient not found.")

    recipient.name = payload.name.strip() if payload.name else None
    recipient.is_active = payload.is_active
    db.commit()
    db.refresh(recipient)
    return recipient


@router.post("/api/weekly-email/send", response_model=WeeklyEmailSendResponse)
def send_weekly_report_email(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> WeeklyEmailSendResponse:
    report_run = ReportRun(
        report_type="weekly_email",
        status="running",
        requested_by_user_id=current_user.id,
    )
    db.add(report_run)
    db.flush()

    try:
        result = send_weekly_email(db, report_run)
        report_run.status = "completed"
        report_run.finished_at = datetime.now(UTC)
        db.commit()
    except ValueError as exc:
        report_run.status = "failed"
        report_run.finished_at = datetime.now(UTC)
        report_run.error_summary = str(exc)
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        report_run.status = "failed"
        report_run.finished_at = datetime.now(UTC)
        report_run.error_summary = "Weekly email send failed."
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Weekly email send failed.",
        ) from exc

    db.refresh(report_run)
    return WeeklyEmailSendResponse(
        message="Weekly email sent.",
        recipient_count=result.recipient_count,
        attachment_count=result.attachment_count,
        report_run=report_run,
    )
