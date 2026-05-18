from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_super_admin
from app.db.session import get_db
from app.models.reporting import BankTransaction
from app.models.user import User
from app.schemas.bank_transaction import (
    BankTransactionListResponse,
    BankTransactionSummaryRead,
)


router = APIRouter(prefix="/api/bank-transactions", tags=["Bank Transactions"])


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

    summary = BankTransactionSummaryRead(
        total_rows=len(all_transactions),
        latest_trust_balance=money(latest_transaction.balance) if latest_transaction else None,
        latest_trust_balance_date=latest_transaction.transaction_date if latest_transaction else None,
        unmatched_count=sum(1 for transaction in all_transactions if transaction.match_status == "unmatched"),
        duplicate_count=sum(1 for transaction in all_transactions if transaction.match_status == "duplicate"),
    )

    return BankTransactionListResponse(
        transactions=transactions,
        summary=summary,
    )
