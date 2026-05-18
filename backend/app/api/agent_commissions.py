from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_super_admin
from app.db.session import get_db
from app.models.reporting import AgentCommission, Booking, CustomerPayment, Refund
from app.models.user import User
from app.schemas.agent_commission import (
    AgentCommissionListResponse,
    AgentCommissionRead,
    AgentCommissionSummaryRead,
    TrueProfitRead,
)


router = APIRouter(prefix="/api/agent-commissions", tags=["Agent Commissions"])

ZERO = Decimal("0.00")


def money(value: Decimal | None) -> Decimal:
    if value is None:
        return ZERO
    return Decimal(value).quantize(Decimal("0.01"))


def margin_percentage(profit: Decimal | None, gross_booking_value: Decimal | None) -> Decimal | None:
    if profit is None or gross_booking_value is None or money(gross_booking_value) == ZERO:
        return None
    return ((profit / money(gross_booking_value)) * Decimal("100")).quantize(Decimal("0.01"))


def to_commission_read(commission: AgentCommission) -> AgentCommissionRead:
    return AgentCommissionRead(
        id=commission.id,
        upload_batch_id=commission.upload_batch_id,
        booking_ref=commission.booking_ref,
        agent_name=commission.agent_name,
        commission_basis=commission.commission_basis,
        gross_commission=money(commission.gross_commission),
        deductions=money(commission.deductions),
        net_commission_due=money(commission.net_commission_due),
        commission_status=commission.commission_status,
        due_date=commission.due_date,
        paid_date=commission.paid_date,
        match_status="matched" if commission.booking_id else "unmatched",
        created_at=commission.created_at,
    )


def build_true_profit_rows(
    bookings: list[Booking],
    customer_payments: list[CustomerPayment],
    commissions: list[AgentCommission],
    refunds: list[Refund],
) -> list[TrueProfitRead]:
    payments_by_booking: dict[str, list[CustomerPayment]] = {}
    for payment in customer_payments:
        if payment.booking_ref and payment.match_confidence != "unmatched":
            payments_by_booking.setdefault(payment.booking_ref, []).append(payment)

    commissions_by_booking: dict[str, list[AgentCommission]] = {}
    for commission in commissions:
        if commission.booking_ref:
            commissions_by_booking.setdefault(commission.booking_ref, []).append(commission)

    refunds_by_booking: dict[str, list[Refund]] = {}
    for refund in refunds:
        if refund.booking_ref:
            refunds_by_booking.setdefault(refund.booking_ref, []).append(refund)

    rows = []
    for booking in bookings:
        booking_payments = payments_by_booking.get(booking.booking_ref, [])
        booking_commissions = commissions_by_booking.get(booking.booking_ref, [])
        booking_refunds = refunds_by_booking.get(booking.booking_ref, [])

        payment_fees = sum((money(payment.fee_amount) for payment in booking_payments), ZERO)
        estimated_payment_fees = sum(
            (money(payment.fee_amount) for payment in booking_payments if payment.fee_is_estimated),
            ZERO,
        )
        agent_commission = sum((money(commission.net_commission_due) for commission in booking_commissions), ZERO)
        refunds_adjustments = sum((money(refund.refund_amount_due) for refund in booking_refunds), ZERO)

        missing_items = []
        if booking.gross_booking_value is None:
            missing_items.append("Awaiting gross booking value")
        if booking.expected_supplier_nett is None:
            missing_items.append("Awaiting expected supplier nett")
        if not booking_payments:
            missing_items.append("Awaiting SINGs/Singhs fee data")
        if any(payment.fee_amount is None for payment in booking_payments):
            missing_items.append("Awaiting actual card fee data")
        if not booking_commissions:
            missing_items.append("Awaiting commission data")

        true_profit = None
        if booking.gross_booking_value is not None and booking.expected_supplier_nett is not None:
            true_profit = (
                money(booking.gross_booking_value)
                - money(booking.expected_supplier_nett)
                - payment_fees
                - agent_commission
                - refunds_adjustments
            )

        if missing_items:
            status = "incomplete"
        elif estimated_payment_fees > ZERO:
            status = "calculated_with_estimated_fees"
        else:
            status = "calculated"

        rows.append(
            TrueProfitRead(
                booking_ref=booking.booking_ref,
                customer_last_name=booking.customer_last_name,
                gross_booking_value=booking.gross_booking_value,
                expected_supplier_nett=booking.expected_supplier_nett,
                payment_fees=money(payment_fees),
                estimated_payment_fees=money(estimated_payment_fees),
                agent_commission=money(agent_commission),
                refunds_adjustments=money(refunds_adjustments),
                true_booking_profit=money(true_profit) if true_profit is not None else None,
                true_margin_percentage=margin_percentage(true_profit, booking.gross_booking_value),
                true_profit_status=status,
                missing_items=missing_items,
            )
        )
    return rows


@router.get("", response_model=AgentCommissionListResponse)
def list_agent_commissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> AgentCommissionListResponse:
    commissions = list(
        db.scalars(
            select(AgentCommission)
            .order_by(AgentCommission.created_at.desc(), AgentCommission.id.desc())
            .limit(200)
        )
    )
    all_commissions = list(db.scalars(select(AgentCommission)))
    bookings = list(db.scalars(select(Booking).order_by(Booking.updated_at.desc(), Booking.id.desc()).limit(500)))
    customer_payments = list(db.scalars(select(CustomerPayment)))
    refunds = list(db.scalars(select(Refund)))

    summary = AgentCommissionSummaryRead(
        total_rows=len(all_commissions),
        gross_commission_total=money(sum((money(commission.gross_commission) for commission in all_commissions), ZERO)),
        deductions_total=money(sum((money(commission.deductions) for commission in all_commissions), ZERO)),
        net_commission_due_total=money(
            sum((money(commission.net_commission_due) for commission in all_commissions), ZERO)
        ),
        accrued_count=sum(1 for commission in all_commissions if commission.commission_status == "accrued"),
        due_count=sum(1 for commission in all_commissions if commission.commission_status == "due"),
        paid_count=sum(1 for commission in all_commissions if commission.commission_status == "paid"),
        withheld_count=sum(1 for commission in all_commissions if commission.commission_status == "withheld"),
        clawed_back_count=sum(1 for commission in all_commissions if commission.commission_status == "clawed_back"),
        cancelled_count=sum(1 for commission in all_commissions if commission.commission_status == "cancelled"),
        unmatched_count=sum(1 for commission in all_commissions if commission.booking_id is None),
    )

    return AgentCommissionListResponse(
        commissions=[to_commission_read(commission) for commission in commissions],
        true_profits=build_true_profit_rows(bookings, customer_payments, all_commissions, refunds),
        summary=summary,
    )
