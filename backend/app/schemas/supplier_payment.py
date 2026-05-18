from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class SupplierPaymentRead(BaseModel):
    id: int
    upload_batch_id: int | None
    booking_ref: str | None
    supplier_payment_date: date | None
    product_type: str | None
    supplier_name: str | None
    payment_supplier_name: str | None
    booking_date_imported: date | None
    departure_date_imported: date | None
    supplier_payment_method: str | None
    supplier_payment_amount: Decimal
    associated_vat: Decimal | None
    is_duplicate: bool
    match_status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SupplierBookingReconciliationRead(BaseModel):
    booking_ref: str
    customer_last_name: str | None
    expected_supplier_nett: Decimal | None
    supplier_payments_total: Decimal
    supplier_balance_due: Decimal | None
    supplier_variance: Decimal | None
    supplier_reconciliation_status: str
    supplier_exception: str | None
    trust_status: str
    true_profit_status: str


class SupplierPaymentListResponse(BaseModel):
    payments: list[SupplierPaymentRead]
    reconciliations: list[SupplierBookingReconciliationRead]
    total: int
