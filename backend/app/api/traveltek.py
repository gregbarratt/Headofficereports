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
    TraveltekActiveMaintenanceRequest,
    TraveltekActiveMaintenanceResponse,
    TraveltekBookingImportRequest,
    TraveltekBookingUpdateRead,
    TraveltekChangeLogRead,
    TraveltekFullCatchUpBatchRequest,
    TraveltekFullCatchUpBatchResponse,
    TraveltekStatusResponse,
    TraveltekSyncRequest,
    TraveltekSyncRunRead,
    TraveltekUpdateStatusRequest,
    TraveltekUpdateEverythingBatchRequest,
    TraveltekUpdateEverythingBatchResponse,
    TraveltekUpdateSummary,
    TraveltekUpdatesResponse,
)
from app.services.traveltek_service import (
    add_traveltek_booking_change_log,
    apply_traveltek_update_to_booking,
    import_traveltek_bookings_by_date_range,
    is_valid_traveltek_update_value,
    run_active_maintenance_update,
    run_full_catchup_batch,
    run_update_everything_existing_booking_batch,
    scan_active_bookings_for_traveltek_updates,
    traveltek_field_label,
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


@router.get("/change-log", response_model=list[TraveltekChangeLogRead])
def get_traveltek_change_log(
    limit: int = Query(default=100, ge=1, le=500),
    change_type: str = Query(default="all"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> list[dict]:
    actions = {
        "created": "traveltek_booking_created",
        "changed": "traveltek_booking_changed",
        "cancelled": "traveltek_booking_cancelled",
    }
    allowed_actions = set(actions.values())
    statement = select(AuditLog).where(AuditLog.action.in_(allowed_actions))
    if change_type != "all":
        selected_action = actions.get(change_type)
        if selected_action is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Change type is not recognised.")
        statement = statement.where(AuditLog.action == selected_action)
    statement = statement.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit)

    rows = []
    for audit_log in db.scalars(statement):
        after_data = audit_log.after_data or {}
        rows.append(
            {
                "id": audit_log.id,
                "booking_ref": after_data.get("booking_ref"),
                "change_type": after_data.get("change_type") or audit_log.action.replace("traveltek_booking_", ""),
                "changed_fields": after_data.get("changed_fields") or [],
                "changes": after_data.get("changes") or [],
                "description": audit_log.description,
                "created_at": audit_log.created_at,
            }
        )
    return rows


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


@router.post("/full-catch-up/next-batch", response_model=TraveltekFullCatchUpBatchResponse)
def run_full_catch_up_next_batch(
    request: TraveltekFullCatchUpBatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> dict:
    if request.end_date < request.start_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="End date must be after start date.")

    try:
        return run_full_catchup_batch(
            db=db,
            start_date=request.start_date,
            end_date=request.end_date,
            batch_days=request.batch_days,
            limit=min(request.limit, settings.traveltek_max_calls_per_run),
            reset_progress=request.reset_progress,
            actor_user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/active-maintenance", response_model=TraveltekActiveMaintenanceResponse)
def run_active_maintenance(
    request: TraveltekActiveMaintenanceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> dict:
    if request.new_booking_end_date < request.new_booking_start_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New booking end date must be after start date.")

    try:
        return run_active_maintenance_update(
            db=db,
            new_booking_start_date=request.new_booking_start_date,
            new_booking_end_date=request.new_booking_end_date,
            new_booking_limit=min(request.new_booking_limit, settings.traveltek_max_calls_per_run),
            refresh_limit=min(request.refresh_limit, settings.traveltek_max_calls_per_run),
            active_window_days=request.active_window_days,
            actor_user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/update-everything/next-batch", response_model=TraveltekUpdateEverythingBatchResponse)
def run_update_everything_next_batch(
    request: TraveltekUpdateEverythingBatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> dict:
    try:
        return run_update_everything_existing_booking_batch(
            db=db,
            limit=min(request.limit, settings.traveltek_max_calls_per_run),
            reset_progress=request.reset_progress,
            actor_user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


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
        if applied_data:
            before_booking = applied_data.get("before") or {}
            after_booking = applied_data.get("after") or {}
            changes = [
                {
                    "field_name": field_name,
                    "field_label": traveltek_field_label(field_name),
                    "previous_value": before_booking.get(field_name),
                    "new_value": after_booking.get(field_name),
                }
                for field_name in after_booking
                if field_name != "booking_ref" and before_booking.get(field_name) != after_booking.get(field_name)
            ]
            add_traveltek_booking_change_log(
                db,
                booking_ref=update.booking_ref,
                booking_id=update.booking_id,
                sync_run_id=update.sync_run_id,
                changes=changes,
                created=False,
                actor_user_id=current_user.id,
            )

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
