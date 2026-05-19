from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_super_admin
from app.db.session import get_db
from app.models.reporting import CustomerPayment, UploadBatch
from app.models.user import User
from app.schemas.customer_payment import (
    FellohBackfillRequest,
    FellohBackfillResponse,
    CustomerPaymentListResponse,
    CustomerPaymentSummaryRead,
    FellohSyncRequest,
    FellohSyncResponse,
)
from app.services.sings_service import (
    SingsApiError,
    SingsApiNotConfiguredError,
    count_date_chunks,
    get_sings_service,
    run_felloh_customer_payment_backfill,
    sync_felloh_customer_payments,
)


router = APIRouter(prefix="/api/customer-payments", tags=["Customer Payments"])

ZERO = Decimal("0.00")


def money(value: Decimal | None) -> Decimal:
    if value is None:
        return ZERO
    return value.quantize(Decimal("0.01"))


@router.get("", response_model=CustomerPaymentListResponse)
def list_customer_payments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> CustomerPaymentListResponse:
    payment_statement = (
        select(CustomerPayment)
        .order_by(CustomerPayment.created_at.desc(), CustomerPayment.id.desc())
        .limit(200)
    )
    payments = list(db.scalars(payment_statement))
    all_payments = list(db.scalars(select(CustomerPayment)))

    gross_total = sum((money(payment.gross_amount) for payment in all_payments), ZERO)
    fee_total = sum((money(payment.fee_amount) for payment in all_payments), ZERO)
    actual_fee_total = sum(
        (money(payment.fee_amount) for payment in all_payments if not payment.fee_is_estimated),
        ZERO,
    )
    estimated_fee_total = sum(
        (money(payment.fee_amount) for payment in all_payments if payment.fee_is_estimated),
        ZERO,
    )
    net_settled_total = sum((money(payment.net_settled_amount) for payment in all_payments), ZERO)
    sings_payments = [payment for payment in all_payments if payment.payment_source == "sings"]
    tt_payments = [payment for payment in all_payments if payment.payment_source == "tt"]
    sings_gross_total = sum((money(payment.gross_amount) for payment in sings_payments), ZERO)
    tt_gross_total = sum((money(payment.gross_amount) for payment in tt_payments), ZERO)

    summary = CustomerPaymentSummaryRead(
        total_rows=len(all_payments),
        gross_total=money(gross_total),
        fee_total=money(fee_total),
        actual_fee_total=money(actual_fee_total),
        estimated_fee_total=money(estimated_fee_total),
        net_settled_total=money(net_settled_total),
        sings_gross_total=money(sings_gross_total),
        tt_gross_total=money(tt_gross_total),
        source_variance=money(sings_gross_total - tt_gross_total),
        matched_count=sum(
            1 for payment in all_payments if payment.match_confidence in {"booking_ref", "invoice_ref"}
        ),
        lower_confidence_count=sum(1 for payment in all_payments if payment.match_confidence == "lower_confidence"),
        unmatched_count=sum(1 for payment in all_payments if payment.match_confidence == "unmatched"),
    )

    return CustomerPaymentListResponse(payments=payments, summary=summary)


@router.post("/sync-felloh", response_model=FellohSyncResponse)
def sync_felloh_payments(
    request: FellohSyncRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> FellohSyncResponse:
    if request.end_date < request.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End date must be on or after start date.",
        )

    try:
        result = sync_felloh_customer_payments(
            db=db,
            start_date=request.start_date,
            end_date=request.end_date,
            actor_user_id=current_user.id,
        )
    except SingsApiNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except SingsApiError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    db.commit()
    return FellohSyncResponse(
        start_date=result.start_date,
        end_date=result.end_date,
        fetched_transactions=result.fetched_transactions,
        created_rows=result.created_rows,
        updated_rows=result.updated_rows,
        checked_rows=result.checked_rows,
        skipped_rows=result.skipped_rows,
        actual_fee_rows=result.actual_fee_rows,
        estimated_fee_rows=result.estimated_fee_rows,
        unmatched_rows=result.unmatched_rows,
        warnings=result.warnings,
    )


@router.post("/sync-felloh-backfill", response_model=FellohBackfillResponse, status_code=status.HTTP_202_ACCEPTED)
def start_felloh_backfill(
    request: FellohBackfillRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> FellohBackfillResponse:
    if request.end_date < request.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End date must be on or after start date.",
        )

    active_backfill = db.scalar(
        select(UploadBatch)
        .where(UploadBatch.upload_type == "felloh_customer_payment_backfill")
        .where(UploadBatch.status.in_(["queued", "importing"]))
        .limit(1)
    )
    if active_backfill:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A Felloh catch-up sync is already running. Check Upload Centre for progress.",
        )

    try:
        get_sings_service().ensure_configured()
    except SingsApiNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    chunk_count = count_date_chunks(request.start_date, request.end_date, request.chunk_days)
    backfill_batch = UploadBatch(
        upload_type="felloh_customer_payment_backfill",
        original_filename=(
            f"Felloh API catch-up {request.start_date.isoformat()} "
            f"to {request.end_date.isoformat()}"
        ),
        status="queued",
        uploaded_by_user_id=current_user.id,
        uploaded_at=datetime.now(UTC),
    )
    db.add(backfill_batch)
    db.commit()
    db.refresh(backfill_batch)

    background_tasks.add_task(
        run_felloh_customer_payment_backfill,
        request.start_date,
        request.end_date,
        current_user.id,
        backfill_batch.id,
        request.chunk_days,
    )

    return FellohBackfillResponse(
        batch_id=backfill_batch.id,
        start_date=request.start_date,
        end_date=request.end_date,
        chunk_days=request.chunk_days,
        chunk_count=chunk_count,
        message=(
            f"Felloh catch-up started in the background across {chunk_count} date block(s). "
            "Check Upload Centre for progress."
        ),
    )
