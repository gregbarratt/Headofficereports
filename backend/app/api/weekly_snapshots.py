from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_super_admin
from app.db.session import get_db
from app.models.reporting import WeeklySnapshot, WeeklySnapshotBooking
from app.models.user import User
from app.schemas.weekly_snapshot import (
    WeeklyMovementRead,
    WeeklyMovementSummaryRead,
    WeeklySnapshotDetailResponse,
    WeeklySnapshotListResponse,
    WeeklySnapshotRead,
)
from app.services.weekly_snapshots import (
    compare_snapshots,
    generate_weekly_snapshot,
    movement_summary,
    previous_snapshot,
    snapshot_rows,
)


router = APIRouter(prefix="/api/weekly-snapshots", tags=["Weekly Snapshots"])


def snapshot_read(db: Session, snapshot: WeeklySnapshot) -> WeeklySnapshotRead:
    booking_count = (
        db.scalar(
            select(func.count())
            .select_from(WeeklySnapshotBooking)
            .where(WeeklySnapshotBooking.weekly_snapshot_id == snapshot.id)
        )
        or 0
    )
    return WeeklySnapshotRead(
        id=snapshot.id,
        week_start_date=snapshot.week_start_date,
        week_end_date=snapshot.week_end_date,
        status=snapshot.status,
        generated_at=snapshot.generated_at,
        booking_count=booking_count,
    )


def snapshot_detail(db: Session, snapshot: WeeklySnapshot) -> WeeklySnapshotDetailResponse:
    current_rows = snapshot_rows(db, snapshot.id)
    previous = previous_snapshot(db, snapshot)
    previous_rows = snapshot_rows(db, previous.id) if previous else []
    movements = compare_snapshots(previous_rows, current_rows) if previous else []
    summary = movement_summary(movements)

    return WeeklySnapshotDetailResponse(
        current_snapshot=snapshot_read(db, snapshot),
        previous_snapshot=snapshot_read(db, previous) if previous else None,
        summary=WeeklyMovementSummaryRead(**summary.__dict__),
        movements=[WeeklyMovementRead(**movement.__dict__) for movement in movements],
        bookings=current_rows,
    )


@router.get("", response_model=WeeklySnapshotListResponse)
def list_weekly_snapshots(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> WeeklySnapshotListResponse:
    snapshots = list(
        db.scalars(
            select(WeeklySnapshot)
            .order_by(WeeklySnapshot.week_start_date.desc(), WeeklySnapshot.id.desc())
            .limit(20)
        )
    )
    latest = snapshot_detail(db, snapshots[0]) if snapshots else None
    return WeeklySnapshotListResponse(
        snapshots=[snapshot_read(db, snapshot) for snapshot in snapshots],
        latest=latest,
    )


@router.post("/generate", response_model=WeeklySnapshotDetailResponse)
def generate_current_weekly_snapshot(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> WeeklySnapshotDetailResponse:
    snapshot = generate_weekly_snapshot(db, actor_user_id=current_user.id)
    db.commit()
    db.refresh(snapshot)
    return snapshot_detail(db, snapshot)
