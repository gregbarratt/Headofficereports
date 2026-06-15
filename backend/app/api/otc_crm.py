from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_super_admin
from app.db.session import get_db
from app.models.reporting import Booking, OtcCrmBookingRow
from app.models.user import User
from app.schemas.otc_crm import OtcCrmBookingRowRead, OtcCrmComparisonResponse, OtcCrmSummaryRead


router = APIRouter(prefix="/api/otc-crm", tags=["OTC CRM"])


@router.get("", response_model=OtcCrmComparisonResponse)
def list_otc_crm_comparisons(
    status: str = Query(default="all"),
    search: str = Query(default=""),
    limit: int = Query(default=2500, ge=1, le=10000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> OtcCrmComparisonResponse:
    base_statement = select(OtcCrmBookingRow, Booking).outerjoin(Booking, OtcCrmBookingRow.booking_id == Booking.id)
    count_statement = select(func.count()).select_from(OtcCrmBookingRow)

    if status == "matched":
        base_statement = base_statement.where(OtcCrmBookingRow.match_status == "matched")
        count_statement = count_statement.where(OtcCrmBookingRow.match_status == "matched")
    elif status == "unmatched":
        base_statement = base_statement.where(OtcCrmBookingRow.match_status == "unmatched")
        count_statement = count_statement.where(OtcCrmBookingRow.match_status == "unmatched")
    elif status == "different":
        base_statement = base_statement.where(OtcCrmBookingRow.comparison_status == "different")
        count_statement = count_statement.where(OtcCrmBookingRow.comparison_status == "different")
    elif status == "agent_updated":
        base_statement = base_statement.where(OtcCrmBookingRow.agent_updated.is_(True))
        count_statement = count_statement.where(OtcCrmBookingRow.agent_updated.is_(True))

    cleaned_search = search.strip()
    if cleaned_search:
        pattern = f"%{cleaned_search}%"
        search_filter = (
            OtcCrmBookingRow.booking_ref.ilike(pattern)
            | OtcCrmBookingRow.crm_booking_ref.ilike(pattern)
            | OtcCrmBookingRow.customer_name.ilike(pattern)
            | OtcCrmBookingRow.agent_name.ilike(pattern)
            | OtcCrmBookingRow.destination.ilike(pattern)
        )
        base_statement = base_statement.where(search_filter)
        count_statement = count_statement.where(search_filter)

    rows = db.execute(
        base_statement.order_by(OtcCrmBookingRow.created_at.desc(), OtcCrmBookingRow.id.desc()).limit(limit)
    ).all()

    output_rows = []
    for crm_row, booking in rows:
        update_values = {}
        if booking is not None:
            update_values = {
                "traveltek_customer_name": booking.customer_last_name,
                "traveltek_agent_name": booking.agent_in_charge,
                "traveltek_destination": booking.destination,
                "traveltek_gross_amount": booking.gross_booking_value,
                "traveltek_net_amount": booking.expected_supplier_nett,
                "traveltek_passenger_count": booking.passenger_count,
                "traveltek_departure_date": booking.departure_date,
                "traveltek_return_date": booking.return_date,
            }
        output_rows.append(OtcCrmBookingRowRead.model_validate(crm_row).model_copy(update=update_values))

    summary = OtcCrmSummaryRead(
        total_rows=db.scalar(select(func.count()).select_from(OtcCrmBookingRow)) or 0,
        matched_rows=db.scalar(
            select(func.count()).select_from(OtcCrmBookingRow).where(OtcCrmBookingRow.match_status == "matched")
        )
        or 0,
        unmatched_rows=db.scalar(
            select(func.count()).select_from(OtcCrmBookingRow).where(OtcCrmBookingRow.match_status == "unmatched")
        )
        or 0,
        different_rows=db.scalar(
            select(func.count()).select_from(OtcCrmBookingRow).where(OtcCrmBookingRow.comparison_status == "different")
        )
        or 0,
        agent_updated_rows=db.scalar(
            select(func.count()).select_from(OtcCrmBookingRow).where(OtcCrmBookingRow.agent_updated.is_(True))
        )
        or 0,
    )
    return OtcCrmComparisonResponse(rows=output_rows, summary=summary)
