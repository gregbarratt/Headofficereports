from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi import Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_super_admin
from app.db.session import get_db
from app.models.reporting import AuditLog, Booking, BookingCheckAdjustment
from app.models.user import User
from app.schemas.booking import BookingArchiveUpdate, BookingCheckAdjustmentUpdate, BookingChecksResponse, BookingListResponse
from app.services.booking_checks import ADJUSTABLE_FIELDS, build_booking_checks, money


router = APIRouter(prefix="/api/bookings", tags=["Bookings"])


@router.get("", response_model=BookingListResponse)
def list_bookings(
    limit: int = Query(default=10000, ge=1, le=20000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> BookingListResponse:
    total = db.scalar(select(func.count()).select_from(Booking)) or 0
    statement = select(Booking).order_by(Booking.booking_ref.asc()).limit(limit)
    bookings = list(db.scalars(statement))
    return BookingListResponse(bookings=bookings, total=total)


@router.get("/checks", response_model=BookingChecksResponse)
def list_booking_checks(
    limit: int = Query(default=250, ge=1, le=10000),
    search: str = Query(default=""),
    review: str = Query(default="all"),
    company: str = Query(default="all"),
    supplier: str = Query(default="all"),
    customer: str = Query(default="all"),
    archive: str = Query(default="active"),
    commission_review: str = Query(default="all"),
    departure_from: str = Query(default=""),
    departure_to: str = Query(default=""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> BookingChecksResponse:
    return build_booking_checks(
        db,
        limit=limit,
        search=search,
        review_filter=review,
        company_filter=company,
        supplier_filter=supplier,
        customer_filter=customer,
        archive_filter=archive,
        commission_review_filter=commission_review,
        departure_from=departure_from,
        departure_to=departure_to,
    )


@router.put("/checks/{booking_ref}/adjustments", response_model=BookingChecksResponse)
def update_booking_check_adjustments(
    booking_ref: str,
    request: BookingCheckAdjustmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> BookingChecksResponse:
    normalised_ref = booking_ref.strip().upper()
    existing = {
        adjustment.field_name: adjustment
        for adjustment in db.scalars(
            select(BookingCheckAdjustment).where(BookingCheckAdjustment.booking_ref == normalised_ref)
        )
    }
    requested_values = request.model_dump(exclude={"note"})
    note = (request.note or "").strip() or None

    before_data = {
        field_name: str(money(adjustment.adjusted_amount))
        for field_name, adjustment in existing.items()
    }
    after_data = {}

    for field_name in ADJUSTABLE_FIELDS:
        amount = requested_values.get(field_name)
        current = existing.get(field_name)

        if amount is None:
            if current is not None:
                db.delete(current)
            continue

        after_data[field_name] = str(money(amount))
        if current is None:
            db.add(
                BookingCheckAdjustment(
                    booking_ref=normalised_ref,
                    field_name=field_name,
                    adjusted_amount=money(amount),
                    note=note,
                    updated_by_user_id=current_user.id,
                )
            )
        else:
            current.adjusted_amount = money(amount)
            current.note = note
            current.updated_by_user_id = current_user.id

    db.add(
        AuditLog(
            actor_user_id=current_user.id,
            action="booking_check_adjustment",
            table_name="booking_check_adjustments",
            description=f"Updated booking check adjustments for {normalised_ref}.",
            before_data=before_data,
            after_data={**after_data, "note": note},
        )
    )
    db.commit()
    return build_booking_checks(db)


@router.patch("/checks/{booking_ref}/archive")
def update_booking_archive_status(
    booking_ref: str,
    request: BookingArchiveUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> dict:
    normalised_ref = booking_ref.strip().upper()
    booking = db.scalar(select(Booking).where(Booking.booking_ref == normalised_ref))
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking was not found.")

    before_data = {
        "is_archived": booking.is_archived,
        "archive_note": booking.archive_note,
        "agent_commission_review_required": booking.agent_commission_review_required,
        "agent_commission_review_note": booking.agent_commission_review_note,
    }

    if request.is_archived is not None:
        booking.is_archived = request.is_archived
        booking.archived_at = datetime.now(UTC) if request.is_archived else None
        if request.is_archived:
            booking.archive_note = (request.archive_note or "").strip() or None
        else:
            booking.archive_note = None
    elif request.archive_note is not None:
        booking.archive_note = request.archive_note.strip() or None

    if request.agent_commission_review_required is not None:
        booking.agent_commission_review_required = request.agent_commission_review_required
        if not request.agent_commission_review_required:
            booking.agent_commission_review_note = None

    if request.agent_commission_review_note is not None and booking.agent_commission_review_required:
        booking.agent_commission_review_note = request.agent_commission_review_note.strip() or None

    after_data = {
        "is_archived": booking.is_archived,
        "archive_note": booking.archive_note,
        "agent_commission_review_required": booking.agent_commission_review_required,
        "agent_commission_review_note": booking.agent_commission_review_note,
    }
    db.add(
        AuditLog(
            actor_user_id=current_user.id,
            action="booking_archive_status_updated",
            table_name="bookings",
            record_id=booking.id,
            description=f"Updated archive or commission review status for {normalised_ref}.",
            before_data=before_data,
            after_data=after_data,
        )
    )
    db.commit()
    return {"booking_ref": booking.booking_ref, **after_data}
