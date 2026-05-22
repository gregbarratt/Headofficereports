from decimal import Decimal
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_super_admin
from app.db.session import get_db
from app.models.reporting import AuditLog, BankTransaction, Booking, ExceptionRecord, ManualTrustBalance
from app.models.user import User
from app.schemas.bank_transaction import (
    BankTransactionAllocationRequest,
    BankTransactionListResponse,
    BankTransactionRead,
    BankTransactionSummaryRead,
    HeadOfficeCostListResponse,
    HeadOfficeCostSummaryRead,
    ManualTrustBalanceCreate,
    ManualTrustBalanceRead,
)
from app.services.master_booking_import import normalise_booking_ref


router = APIRouter(prefix="/api/bank-transactions", tags=["Bank Transactions"])
ZERO = Decimal("0.00")
ALLOCATION_TYPES = {
    "customer_receipt",
    "supplier_payment",
    "refund",
    "bank_charge",
    "head_office_cost",
    "transfer",
    "sings_settlement",
    "amex_settlement",
    "other",
}


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


def get_latest_manual_trust_balance(db: Session) -> ManualTrustBalance | None:
    return db.scalar(
        select(ManualTrustBalance)
        .order_by(ManualTrustBalance.checked_at.desc(), ManualTrustBalance.id.desc())
        .limit(1)
    )


def is_unmatched_bank_transaction(transaction: BankTransaction) -> bool:
    if transaction.match_status in {
        "duplicate",
        "accounted_for_elsewhere",
        "matched_booking_ref",
        "matched_manual",
    }:
        return False
    return transaction.booking_id is None


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
    latest_manual_balance = get_latest_manual_trust_balance(db)
    unallocated_transactions = [
        transaction
        for transaction in all_transactions
        if is_unmatched_bank_transaction(transaction)
    ][:200]

    summary = BankTransactionSummaryRead(
        total_rows=len(all_transactions),
        latest_trust_balance=(
            money(latest_manual_balance.trust_value)
            if latest_manual_balance
            else money(latest_transaction.balance)
            if latest_transaction
            else None
        ),
        latest_trust_balance_date=(
            latest_manual_balance.balance_date
            if latest_manual_balance
            else latest_transaction.transaction_date
            if latest_transaction
            else None
        ),
        latest_trust_balance_checked_at=latest_manual_balance.checked_at if latest_manual_balance else None,
        latest_trust_balance_source="manual" if latest_manual_balance else "bank_statement" if latest_transaction else "missing",
        matched_count=sum(
            1
            for transaction in all_transactions
            if transaction.booking_id is not None or transaction.match_status == "matched_manual"
        ),
        unmatched_count=sum(1 for transaction in all_transactions if is_unmatched_bank_transaction(transaction)),
        duplicate_count=sum(1 for transaction in all_transactions if transaction.match_status == "duplicate"),
    )

    return BankTransactionListResponse(
        transactions=transactions,
        unallocated_transactions=unallocated_transactions,
        summary=summary,
    )


@router.get("/head-office-costs", response_model=HeadOfficeCostListResponse)
def list_head_office_costs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> HeadOfficeCostListResponse:
    all_costs = list(
        db.scalars(
            select(BankTransaction)
            .where(BankTransaction.allocation_type == "head_office_cost")
            .order_by(BankTransaction.transaction_date.desc(), BankTransaction.id.desc())
        )
    )
    total_money_in = sum((cost.money_in or ZERO) for cost in all_costs)
    total_money_out = sum((cost.money_out or ZERO) for cost in all_costs)
    dates = [cost.transaction_date for cost in all_costs if cost.transaction_date]

    return HeadOfficeCostListResponse(
        costs=all_costs[:1000],
        summary=HeadOfficeCostSummaryRead(
            total_rows=len(all_costs),
            total_money_in=money(total_money_in) or ZERO,
            total_money_out=money(total_money_out) or ZERO,
            net_spend=money(total_money_out - total_money_in) or ZERO,
            first_date=min(dates) if dates else None,
            last_date=max(dates) if dates else None,
        ),
    )


@router.post("/manual-trust-balance", response_model=ManualTrustBalanceRead, status_code=status.HTTP_201_CREATED)
def create_manual_trust_balance(
    request: ManualTrustBalanceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> ManualTrustBalance:
    checked_at = request.checked_at or datetime.now(UTC)
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=UTC)

    balance = ManualTrustBalance(
        trust_value=money(request.trust_value),
        balance_date=request.balance_date,
        checked_at=checked_at,
        note=(request.note or "").strip() or None,
        entered_by_user_id=current_user.id,
    )
    db.add(balance)
    db.flush()
    db.add(
        AuditLog(
            actor_user_id=current_user.id,
            action="manual_trust_balance_created",
            table_name="manual_trust_balances",
            record_id=balance.id,
            description=f"Manual trust balance entered for {balance.balance_date}.",
            after_data={
                "trust_value": str(balance.trust_value),
                "balance_date": balance.balance_date.isoformat(),
                "checked_at": balance.checked_at.isoformat(),
                "note": balance.note,
            },
        )
    )
    db.commit()
    db.refresh(balance)
    return balance


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

    if allocation_type == "head_office_cost":
        transaction.booking_id = None
        transaction.booking_ref = None
        transaction.allocation_type = allocation_type
        transaction.match_status = "matched_manual"
        resolve_bank_transaction_exceptions(db, transaction.id, current_user.id)
        db.add(
            AuditLog(
                actor_user_id=current_user.id,
                action="bank_transaction_head_office_cost",
                table_name="bank_transactions",
                record_id=transaction.id,
                description=f"Marked bank transaction {transaction.id} as a Head Office cost.",
                before_data=before_data,
                after_data={
                    "booking_ref": None,
                    "allocation_type": allocation_type,
                    "match_status": transaction.match_status,
                },
            )
        )
        db.commit()
        db.refresh(transaction)
        return transaction

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
