from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_super_admin
from app.db.session import get_db
from app.models.reporting import Booking
from app.models.user import User
from app.schemas.booking import BookingListResponse


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
