from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_super_admin
from app.core.config import settings
from app.db.session import get_db
from app.models.reporting import AuditLog, TraveltekBookingUpdate, TraveltekSyncRun
from app.models.user import User
from app.schemas.traveltek import (
    TraveltekBookingImportRequest,
    TraveltekBookingUpdateRead,
    TraveltekStatusResponse,
    TraveltekSyncRequest,
    TraveltekSyncRunRead,
    TraveltekUpdateStatusRequest,
    TraveltekUpdateSummary,
    TraveltekUpdatesResponse,
)
from app.services.traveltek_service import (
    apply_traveltek_update_to_booking,
    import_traveltek_bookings_by_date_range,
    is_valid_traveltek_update_value,
    scan_active_bookings_for_traveltek_updates,
)


router = APIRouter(prefix="/api/traveltek", tags=["Traveltek"])
VALID_UPDATE_STATUSES = {"open", "reviewing", "resolved", "ignored"}


def latest_run(db: Session) -> TraveltekSyncRun | None:
    return db.scalar(select(TraveltekSyncRun).order_by(TraveltekSyncRun.started_at.desc(), TraveltekSyncRun.id.desc()).limit(1))


def visible_traveltek_updates(db: Session, status_filter: str = "all", limit: int | None = None) -> list[TraveltekBookingUpdate]:
    statement = select(TraveltekBookingUpdate).order_by(
        TraveltekBookingUpdate.detected_at.desc(),
        TraveltekBookingUpdate.id.desc(),
    )
    if status_filter != "all":
        statement = statement.where(TraveltekBookingUpdate.status == status_filter)

    updates = [
        update
        for update in db.scalars(statement)
        if is_valid_traveltek_update_value(update.field_name, update.traveltek_value)
    ]
    return updates[:limit] if limit is not None else updates


def update_summary(db: Session) -> TraveltekUpdateSummary:
    updates = visible_traveltek_updates(db)
    counts = {status_value: 0 for status_value in VALID_UPDATE_STATUSES}
    for update in updates:
        counts[update.status] = counts.get(update.status, 0) + 1
    return TraveltekUpdateSummary(
        open_count=counts["open"],
        reviewing_count=counts["reviewing"],
        resolved_count=counts["resolved"],
        ignored_count=counts["ignored"],
    )


@router.get("/status", response_model=TraveltekStatusResponse)
def traveltek_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> TraveltekStatusResponse:
    return TraveltekStatusResponse(
        configured=settings.traveltek_api_configured,
        base_url_configured=bool(settings.traveltek_api_base_url.strip()),
        secure_base_url_configured=bool(settings.traveltek_secure_api_base_url.strip()),
        username_configured=bool(settings.traveltek_username.strip()),
        password_configured=bool(settings.traveltek_password.strip()),
        sitename_configured=bool(settings.traveltek_sitename.strip()),
        max_calls_per_run=settings.traveltek_max_calls_per_run,
        latest_run=latest_run(db),
        open_update_count=len(visible_traveltek_updates(db, "open")),
    )


@router.get("/updates", response_model=TraveltekUpdatesResponse)
def list_traveltek_updates(
    status_filter: str = Query("open", alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> TraveltekUpdatesResponse:
    if status_filter not in VALID_UPDATE_STATUSES and status_filter != "all":
        status_filter = "open"

    return TraveltekUpdatesResponse(
        configured=settings.traveltek_api_configured,
        latest_run=latest_run(db),
        summary=update_summary(db),
        updates=visible_traveltek_updates(db, status_filter, limit=500),
    )


@router.post("/sync-active-bookings", response_model=TraveltekSyncRunRead)
def sync_active_bookings(
    request: TraveltekSyncRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> TraveltekSyncRun:
    limit = min(request.limit, settings.traveltek_max_calls_per_run)
    return scan_active_bookings_for_traveltek_updates(db, limit=limit, actor_user_id=current_user.id)


@router.post("/import-bookings", response_model=TraveltekSyncRunRead)
def import_bookings_from_traveltek(
    request: TraveltekBookingImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> TraveltekSyncRun:
    if request.end_date < request.start_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="End date must be after start date.")

    limit = min(request.limit, settings.traveltek_max_calls_per_run)
    return import_traveltek_bookings_by_date_range(
        db=db,
        start_date=request.start_date,
        end_date=request.end_date,
        date_type="booking_date",
        limit=limit,
        actor_user_id=current_user.id,
    )


@router.patch("/updates/{update_id}", response_model=TraveltekBookingUpdateRead)
def update_traveltek_update_status(
    update_id: int,
    request: TraveltekUpdateStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> TraveltekBookingUpdate:
    next_status = request.status.strip().lower()
    if next_status not in VALID_UPDATE_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Update status is not recognised.")

    update = db.get(TraveltekBookingUpdate, update_id)
    if update is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Traveltek update was not found.")

    previous_status = update.status
    applied_data = None
    if next_status == "resolved":
        applied_data = apply_traveltek_update_to_booking(db, update)

    update.status = next_status
    if next_status in {"resolved", "ignored"}:
        update.reviewed_at = datetime.now(UTC)
        update.reviewed_by_user_id = current_user.id

    db.add(
        AuditLog(
            actor_user_id=current_user.id,
            action="traveltek_update_status",
            table_name="traveltek_booking_updates",
            record_id=update.id,
            description=f"Traveltek update changed from {previous_status} to {next_status}.",
            before_data={"status": previous_status, "booking_update": applied_data["before"] if applied_data else None},
            after_data={"status": next_status, "booking_update": applied_data["after"] if applied_data else None},
        )
    )
    db.commit()
    db.refresh(update)
    return update
