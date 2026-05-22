from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class BankTransactionRead(BaseModel):
    id: int
    upload_batch_id: int | None
    booking_ref: str | None
    allocation_type: str | None
    transaction_date: date
    description: str | None
    money_in: Decimal | None
    money_out: Decimal | None
    balance: Decimal | None
    account_type: str | None
    transaction_reference: str | None
    match_status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class BankTransactionSummaryRead(BaseModel):
    total_rows: int
    latest_trust_balance: Decimal | None
    latest_trust_balance_date: date | None
    matched_count: int
    unmatched_count: int
    duplicate_count: int


class BankTransactionListResponse(BaseModel):
    transactions: list[BankTransactionRead]
    unallocated_transactions: list[BankTransactionRead]
    summary: BankTransactionSummaryRead


class BankTransactionAllocationRequest(BaseModel):
    booking_ref: str
    allocation_type: str | None = None
