from datetime import date, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    CapitalLedgerEntry,
    InterestAccrual,
    LedgerEntryType,
    Loan,
    LoanStatus,
    Payment,
    utc_now,
)
from ..schemas import PaymentCreate
from .interest import add_month, calculate_monthly_interest, money


def accrue_due_interest(db: Session, loan: Loan, through_date: date) -> Decimal:
    """Post one auditable simple-interest entry for every completed monthly cycle."""
    total_added = Decimal("0.00")
    while loan.next_interest_date <= through_date:
        amount = calculate_monthly_interest(loan.principal_outstanding, loan.monthly_interest_rate)
        db.add(
            InterestAccrual(
                tenant_id=loan.tenant_id,
                loan_id=loan.id,
                cycle_date=loan.next_interest_date,
                principal_basis=loan.principal_outstanding,
                monthly_rate=loan.monthly_interest_rate,
                amount=amount,
            )
        )
        loan.accrued_interest = money(loan.accrued_interest + amount)
        total_added += amount
        loan.next_interest_date = add_month(loan.next_interest_date)
    return money(total_added)


def record_payment(db: Session, loan: Loan, payload: PaymentCreate) -> Payment:
    if loan.status != LoanStatus.active:
        raise HTTPException(status_code=422, detail="Payments can only be recorded on active loans")

    accrue_due_interest(db, loan, payload.received_at.date())

    if payload.amount_to_interest > loan.accrued_interest:
        raise HTTPException(status_code=422, detail="Interest allocation exceeds accrued interest")
    if payload.amount_to_principal > loan.principal_outstanding:
        raise HTTPException(status_code=422, detail="Principal allocation exceeds outstanding principal")

    total_due = money(loan.accrued_interest + loan.principal_outstanding)
    if payload.amount_received > total_due:
        raise HTTPException(status_code=422, detail="Payment exceeds the total outstanding balance")

    unapplied = money(
        payload.amount_received - payload.amount_to_interest - payload.amount_to_principal
    )
    payment = Payment(
        tenant_id=loan.tenant_id,
        loan_id=loan.id,
        amount_received=money(payload.amount_received),
        amount_to_interest=money(payload.amount_to_interest),
        amount_to_principal=money(payload.amount_to_principal),
        unapplied_amount=unapplied,
        received_at=payload.received_at,
        notes=payload.notes,
    )
    db.add(payment)
    db.flush()

    loan.accrued_interest = money(loan.accrued_interest - payload.amount_to_interest)
    loan.principal_outstanding = money(loan.principal_outstanding - payload.amount_to_principal)

    if loan.accrued_interest == 0 and loan.principal_outstanding == 0:
        loan.status = LoanStatus.paid
        loan.closed_at = utc_now()

    if payload.amount_to_interest:
        db.add(
            CapitalLedgerEntry(
                tenant_id=loan.tenant_id,
                entry_type=LedgerEntryType.payment_interest,
                amount=money(payload.amount_to_interest),
                loan_id=loan.id,
                payment_id=payment.id,
                occurred_at=payload.received_at,
            )
        )
    if payload.amount_to_principal:
        db.add(
            CapitalLedgerEntry(
                tenant_id=loan.tenant_id,
                entry_type=LedgerEntryType.payment_principal,
                amount=money(payload.amount_to_principal),
                loan_id=loan.id,
                payment_id=payment.id,
                occurred_at=payload.received_at,
            )
        )

    return payment


def get_tenant_loan(db: Session, tenant_id: str, loan_id: str) -> Loan:
    loan = db.scalar(select(Loan).where(Loan.id == loan_id, Loan.tenant_id == tenant_id))
    if loan is None:
        raise HTTPException(status_code=404, detail="Loan not found")
    return loan
