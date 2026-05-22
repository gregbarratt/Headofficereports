from decimal import Decimal
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_super_admin
from app.db.session import get_db
from app.models.reporting import AuditLog, BankTransaction, Booking, ExceptionRecord
from app.models.user import User
from app.schemas.bank_transaction import (
    BankTransactionAllocationRequest,
    BankTransactionListResponse,
    BankTransactionRead,
    BankTransactionSummaryRead,
)
from app.services.master_booking_import import normalise_booking_ref


router = APIRouter(prefix="/api/bank-transactions", tags=["Bank Transactions"])
ALLOCATION_TYPES = {"customer_receipt", "supplier_payment", "refund", "bank_charge", "transfer", "other"}


def money(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(value).quantize(Decimal("0.01"))


def get_latest_trust_transaction(db: Session) -> BankTransaction | None:
    trust_statement = (
        select(BankTransaction)
        .where(BankTransaction.balance.is_not(None), BankTransaction.account_type.ilike("%trust%"))
        .order_by(BankTransaction.transaction_date.desc(), BankTransaction.id.desc())
        .limit(1)
    )
    latest_transaction = db.scalar(trust_statement)
    if latest_transaction is not None:
        return latest_transaction

    any_statement = (
        select(BankTransaction)
        .where(BankTransaction.balance.is_not(None))
        .order_by(BankTransaction.transaction_date.desc(), BankTransaction.id.desc())
        .limit(1)
    )
    return db.scalar(any_statement)


@router.get("", response_model=BankTransactionListResponse)
def list_bank_transactions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> BankTransactionListResponse:
    transactions = list(
        db.scalars(
            select(BankTransaction)
            .order_by(BankTransaction.transaction_date.desc(), BankTransaction.id.desc())
            .limit(200)
        )
    )
    all_transactions = list(db.scalars(select(BankTransaction)))
    latest_transaction = get_latest_trust_transaction(db)
    unallocated_transactions = [
        transaction
        for transaction in all_transactions
        if transaction.match_status != "duplicate" and transaction.booking_id is None
    ][:200]

    summary = BankTransactionSummaryRead(
        total_rows=len(all_transactions),
        latest_trust_balance=money(latest_transaction.balance) if latest_transaction else None,
        latest_trust_balance_date=latest_transaction.transaction_date if latest_transaction else None,
        matched_count=sum(1 for transaction in all_transactions if transaction.booking_id is not None),
        unmatched_count=sum(
            1
            for transaction in all_transactions
            if transaction.match_status != "duplicate" and transaction.booking_id is None
        ),
        duplicate_count=sum(1 for transaction in all_transactions if transaction.match_status == "duplicate"),
    )

    return BankTransactionListResponse(
        transactions=transactions,
        unallocated_transactions=unallocated_transactions,
        summary=summary,
    )


def resolve_bank_transaction_exceptions(db: Session, transaction_id: int, user_id: int) -> None:
    for exception in db.scalars(
        select(ExceptionRecord).where(
            ExceptionRecord.related_table == "bank_transactions",
            ExceptionRecord.related_record_id == transaction_id,
            ExceptionRecord.status.in_(("open", "reviewing")),
        )
    ):
        exception.status = "resolved"
        exception.resolved_at = datetime.now(UTC)
        exception.resolved_by_user_id = user_id


@router.put("/{transaction_id}/allocate", response_model=BankTransactionRead)
def allocate_bank_transaction_to_booking(
    transaction_id: int,
    request: BankTransactionAllocationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> BankTransaction:
    transaction = db.get(BankTransaction, transaction_id)
    if transaction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bank transaction was not found.",
        )

    booking_ref = normalise_booking_ref(request.booking_ref)
    if not booking_ref:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Enter a booking reference.",
        )

    booking = db.scalar(select(Booking).where(Booking.booking_ref == booking_ref))
    if booking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Booking {booking_ref} was not found. Import the booking first, then attach the bank transaction.",
        )

    allocation_type = (request.allocation_type or "").strip().lower() or None
    if allocation_type and allocation_type not in ALLOCATION_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Allocation type is not recognised.",
        )

    if allocation_type is None:
        if transaction.money_out and transaction.money_out > ZERO:
            allocation_type = "supplier_payment"
        elif transaction.money_in and transaction.money_in > ZERO:
            allocation_type = "customer_receipt"
        else:
            allocation_type = "other"

    before_data = {
        "booking_ref": transaction.booking_ref,
        "allocation_type": transaction.allocation_type,
        "match_status": transaction.match_status,
    }

    transaction.booking_id = booking.id
    transaction.booking_ref = booking.booking_ref
    transaction.allocation_type = allocation_type
    transaction.match_status = "matched_manual"
    resolve_bank_transaction_exceptions(db, transaction.id, current_user.id)

    db.add(
        AuditLog(
            actor_user_id=current_user.id,
            action="bank_transaction_allocation",
            table_name="bank_transactions",
            record_id=transaction.id,
            description=f"Attached bank transaction {transaction.id} to {booking.booking_ref}.",
            before_data=before_data,
            after_data={
                "booking_ref": booking.booking_ref,
                "allocation_type": allocation_type,
                "match_status": transaction.match_status,
            },
        )
    )
    db.commit()
    db.refresh(transaction)
    return transaction
