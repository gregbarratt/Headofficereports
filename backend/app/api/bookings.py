from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_super_admin
from app.db.session import get_db
from app.models.reporting import AuditLog, Booking, BookingCheckAdjustment
from app.models.user import User
from app.schemas.booking import BookingCheckAdjustmentUpdate, BookingChecksResponse, BookingListResponse
from app.services.booking_checks import ADJUSTABLE_FIELDS, build_booking_checks, money


router = APIRouter(prefix="/api/bookings", tags=["Bookings"])


@router.get("", response_model=BookingListResponse)
def list_bookings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> BookingListResponse:
    total = db.scalar(select(func.count()).select_from(Booking)) or 0
    statement = select(Booking).order_by(Booking.updated_at.desc(), Booking.id.desc()).limit(200)
    bookings = list(db.scalars(statement))
    return BookingListResponse(bookings=bookings, total=total)


@router.get("/checks", response_model=BookingChecksResponse)
def list_booking_checks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> BookingChecksResponse:
    return build_booking_checks(db)


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
