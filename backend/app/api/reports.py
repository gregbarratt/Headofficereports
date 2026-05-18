from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_super_admin
from app.db.session import get_db
from app.models.reporting import ReportRun
from app.models.user import User
from app.schemas.report import ReportRunListResponse, ReportTypeRead
from app.services.reports import REPORT_TYPES, create_report_run, generate_excel_report


router = APIRouter(prefix="/api/reports", tags=["Reports"])


@router.get("/types", response_model=list[ReportTypeRead])
def list_report_types(current_user: User = Depends(get_current_super_admin)) -> list[ReportTypeRead]:
    return [ReportTypeRead(value=value, label=label) for value, label in REPORT_TYPES.items()]


@router.get("/runs", response_model=ReportRunListResponse)
def list_report_runs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> ReportRunListResponse:
    runs = list(db.scalars(select(ReportRun).order_by(ReportRun.started_at.desc(), ReportRun.id.desc()).limit(50)))
    return ReportRunListResponse(runs=runs)


@router.post("/{report_type}/excel")
def export_report_excel(
    report_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> StreamingResponse:
    if report_type not in REPORT_TYPES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report type not found.")

    report_run = create_report_run(db, report_type=report_type, actor_user_id=current_user.id)
    try:
        filename, content = generate_excel_report(db, report_type)
        report_run.status = "completed"
        report_run.finished_at = datetime.now(UTC)
        report_run.output_filename = filename
        db.commit()
    except Exception as exc:
        report_run.status = "failed"
        report_run.finished_at = datetime.now(UTC)
        report_run.error_summary = str(exc)
        db.commit()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Report export failed.") from exc

    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )
