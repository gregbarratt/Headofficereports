from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.reporting import (
    AgentCommission,
    BankTransaction,
    Booking,
    CustomerPayment,
    ManualTrustBalance,
    Refund,
    SupplierPayment,
)
from app.schemas.trust_reconciliation import (
    TrustBookingRead,
    TrustReconciliationResponse,
    TrustSummaryRead,
)


ZERO = Decimal("0.00")


def money(value: Decimal | None) -> Decimal:
    if value is None:
        return ZERO
    return Decimal(value).quantize(Decimal("0.01"))


def positive(value: Decimal) -> Decimal:
    return value if value > ZERO else ZERO


def net_payment_amount(payment: CustomerPayment) -> Decimal:
    return money(payment.gross_amount) - money(payment.fee_amount)


def trusted_customer_payment(payment: CustomerPayment) -> bool:
    return payment.payment_source == "sings"


def trusted_supplier_payment(payment: SupplierPayment) -> bool:
    return payment.payment_source == "taps"


def latest_trust_bank_balance(db: Session) -> Decimal | None:
    manual_statement = (
        select(ManualTrustBalance)
        .order_by(ManualTrustBalance.checked_at.desc(), ManualTrustBalance.id.desc())
        .limit(1)
    )
    latest_manual_balance = db.scalar(manual_statement)
    if latest_manual_balance is not None:
        return money(latest_manual_balance.trust_value)

    trust_statement = (
        select(BankTransaction)
        .where(BankTransaction.balance.is_not(None), BankTransaction.account_type.ilike("%trust%"))
        .order_by(BankTransaction.transaction_date.desc(), BankTransaction.id.desc())
        .limit(1)
    )
    latest_transaction = db.scalar(trust_statement)

    if latest_transaction is None:
        any_statement = (
            select(BankTransaction)
            .where(BankTransaction.balance.is_not(None))
            .order_by(BankTransaction.transaction_date.desc(), BankTransaction.id.desc())
            .limit(1)
        )
        latest_transaction = db.scalar(any_statement)

    return money(latest_transaction.balance) if latest_transaction else None


def has_manual_trust_balance(db: Session) -> bool:
    return db.scalar(select(ManualTrustBalance.id).limit(1)) is not None


def calculate_trust_reconciliation(db: Session) -> TrustReconciliationResponse:
    bookings = list(db.scalars(select(Booking).order_by(Booking.updated_at.desc(), Booking.id.desc()).limit(500)))
    customer_payments = [payment for payment in db.scalars(select(CustomerPayment)) if trusted_customer_payment(payment)]
    supplier_payments = [payment for payment in db.scalars(select(SupplierPayment)) if trusted_supplier_payment(payment)]
    refunds = list(db.scalars(select(Refund)))
    commission_booking_refs = {
        booking_ref
        for booking_ref in db.scalars(select(AgentCommission.booking_ref).where(AgentCommission.booking_ref.is_not(None)))
    }

    customer_by_booking: dict[str, list[CustomerPayment]] = {}
    unmatched_customer_receipts = ZERO
    for payment in customer_payments:
        if payment.booking_ref and payment.match_confidence != "unmatched":
            customer_by_booking.setdefault(payment.booking_ref, []).append(payment)
        else:
            unmatched_customer_receipts += net_payment_amount(payment)

    supplier_paid_by_booking: dict[str, Decimal] = {}
    for payment in supplier_payments:
        if payment.booking_ref:
            supplier_paid_by_booking[payment.booking_ref] = (
                supplier_paid_by_booking.get(payment.booking_ref, ZERO) + money(payment.supplier_payment_amount)
            )

    refunds_by_booking: dict[str, list[Refund]] = {}
    unmatched_refunds: list[Refund] = []
    for refund in refunds:
        if refund.booking_ref:
            refunds_by_booking.setdefault(refund.booking_ref, []).append(refund)
        else:
            unmatched_refunds.append(refund)

    booking_rows = []
    positive_booking_trust_balances = ZERO
    total_customer_payments = sum((money(payment.gross_amount) for payment in customer_payments), ZERO)
    total_card_fees = sum((money(payment.fee_amount) for payment in customer_payments), ZERO)
    total_estimated_card_fees = sum(
        (money(payment.fee_amount) for payment in customer_payments if payment.fee_is_estimated),
        ZERO,
    )
    total_net_trust_receipts = total_customer_payments - total_card_fees
    total_supplier_payments = sum((money(payment.supplier_payment_amount) for payment in supplier_payments), ZERO)
    total_refunds_paid = ZERO
    total_refunds_due = ZERO
    total_refunds_unpaid = ZERO

    for booking in bookings:
        booking_customer_payments = customer_by_booking.get(booking.booking_ref, [])
        customer_payments_received = sum((money(payment.gross_amount) for payment in booking_customer_payments), ZERO)
        card_fees = sum((money(payment.fee_amount) for payment in booking_customer_payments), ZERO)
        estimated_card_fees = sum(
            (money(payment.fee_amount) for payment in booking_customer_payments if payment.fee_is_estimated),
            ZERO,
        )
        net_trust_receipts = customer_payments_received - card_fees
        supplier_payments_made = supplier_paid_by_booking.get(booking.booking_ref, ZERO)

        booking_refunds = refunds_by_booking.get(booking.booking_ref, [])
        refunds_paid = sum((money(refund.refund_amount_paid) for refund in booking_refunds), ZERO)
        refunds_due = sum((money(refund.refund_amount_due) for refund in booking_refunds), ZERO)
        refunds_unpaid = sum(
            (positive(money(refund.refund_amount_due) - money(refund.refund_amount_paid)) for refund in booking_refunds),
            ZERO,
        )

        current_booking_trust_balance = net_trust_receipts - supplier_payments_made - refunds_paid
        required_contribution = positive(current_booking_trust_balance) + refunds_unpaid
        positive_booking_trust_balances += positive(current_booking_trust_balance)

        missing_items = []
        if not booking_customer_payments:
            missing_items.append("Awaiting SINGs/Singhs payment data")
        if booking.expected_supplier_nett is not None and money(booking.expected_supplier_nett) > ZERO and supplier_payments_made == ZERO:
            missing_items.append("Awaiting supplier payment data")
        if any(payment.fee_amount is None for payment in booking_customer_payments):
            missing_items.append("Awaiting actual card fee data")
        if booking.booking_ref not in commission_booking_refs:
            missing_items.append("Awaiting commission data")

        trust_status = "calculated"
        if any(item.startswith("Awaiting SINGs") for item in missing_items):
            trust_status = "incomplete_awaiting_customer_payment"
        elif missing_items:
            trust_status = "calculated_with_missing_data"

        booking_rows.append(
            TrustBookingRead(
                booking_ref=booking.booking_ref,
                customer_last_name=booking.customer_last_name,
                booking_status=booking.normalised_status,
                gross_booking_value=booking.gross_booking_value,
                expected_supplier_nett=booking.expected_supplier_nett,
                customer_payments_received=money(customer_payments_received),
                card_fees=money(card_fees),
                estimated_card_fees=money(estimated_card_fees),
                net_trust_receipts=money(net_trust_receipts),
                supplier_payments_made=money(supplier_payments_made),
                refunds_paid=money(refunds_paid),
                refunds_due=money(refunds_due),
                refunds_unpaid=money(refunds_unpaid),
                current_booking_trust_balance=money(current_booking_trust_balance),
                required_trust_balance_contribution=money(required_contribution),
                trust_status=trust_status,
                missing_items=missing_items,
            )
        )

        total_refunds_paid += refunds_paid
        total_refunds_due += refunds_due
        total_refunds_unpaid += refunds_unpaid

    unmatched_refunds_unpaid = sum(
        (positive(money(refund.refund_amount_due) - money(refund.refund_amount_paid)) for refund in unmatched_refunds),
        ZERO,
    )
    total_refunds_due += sum((money(refund.refund_amount_due) for refund in unmatched_refunds), ZERO)
    total_refunds_paid += sum((money(refund.refund_amount_paid) for refund in unmatched_refunds), ZERO)
    total_refunds_unpaid += unmatched_refunds_unpaid

    required_trust_balance = (
        positive_booking_trust_balances
        + total_refunds_unpaid
        + positive(money(unmatched_customer_receipts))
    )
    actual_trust_balance = latest_trust_bank_balance(db)
    manual_trust_balance_entered = has_manual_trust_balance(db)
    trust_variance = money(actual_trust_balance - required_trust_balance) if actual_trust_balance is not None else None

    summary = TrustSummaryRead(
        customer_payments_received=money(total_customer_payments),
        card_fees=money(total_card_fees),
        estimated_card_fees=money(total_estimated_card_fees),
        net_trust_receipts=money(total_net_trust_receipts),
        supplier_payments_made=money(total_supplier_payments),
        refunds_paid=money(total_refunds_paid),
        refunds_due=money(total_refunds_due),
        refunds_unpaid=money(total_refunds_unpaid),
        positive_booking_trust_balances=money(positive_booking_trust_balances),
        unmatched_customer_receipts=money(unmatched_customer_receipts),
        required_trust_balance=money(required_trust_balance),
        actual_trust_balance=actual_trust_balance,
        trust_variance=trust_variance,
        bank_status=(
            "Manual trust balance entered"
            if manual_trust_balance_entered
            else "Bank statement imported"
            if actual_trust_balance is not None
            else "Awaiting bank statement"
        ),
    )

    return TrustReconciliationResponse(
        generated_at=datetime.now(UTC),
        summary=summary,
        bookings=booking_rows,
    )
