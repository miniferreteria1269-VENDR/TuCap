from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import require_tenant_id
from ..models import Borrower, CapitalLedgerEntry, LedgerEntryType, Loan
from ..schemas import LoanCreate, LoanRead, PaymentCreate, PaymentPreview, PaymentResult
from ..services.interest import add_month, suggested_payment_allocation
from ..services.loans import (
    accrue_due_interest,
    get_tenant_loan,
    post_initial_interest,
    record_payment,
)


router = APIRouter(prefix="/loans", tags=["loans"])


@router.get("", response_model=list[LoanRead])
def list_loans(
    tenant_id: Annotated[str, Depends(require_tenant_id)],
    db: Annotated[Session, Depends(get_db)],
    borrower_id: str | None = None,
) -> list[Loan]:
    query = select(Loan).where(Loan.tenant_id == tenant_id)
    if borrower_id is not None:
        query = query.where(Loan.borrower_id == borrower_id)
    return list(db.scalars(query.order_by(Loan.created_at.desc())))


@router.post("", response_model=LoanRead, status_code=status.HTTP_201_CREATED)
def create_loan(
    payload: LoanCreate,
    tenant_id: Annotated[str, Depends(require_tenant_id)],
    db: Annotated[Session, Depends(get_db)],
) -> Loan:
    borrower = db.scalar(
        select(Borrower).where(Borrower.id == payload.borrower_id, Borrower.tenant_id == tenant_id)
    )
    if borrower is None:
        raise HTTPException(status_code=404, detail="Borrower not found")

    loan = Loan(
        tenant_id=tenant_id,
        principal_outstanding=payload.original_principal,
        next_interest_date=payload.next_interest_date or add_month(payload.start_date),
        **payload.model_dump(exclude={"next_interest_date"}),
    )
    db.add(loan)
    db.flush()
    post_initial_interest(db, loan)
    db.add(
        CapitalLedgerEntry(
            tenant_id=tenant_id,
            entry_type=LedgerEntryType.loan_disbursement,
            amount=-payload.original_principal,
            loan_id=loan.id,
            occurred_at=datetime.combine(payload.start_date, time(12), tzinfo=timezone.utc),
        )
    )
    db.commit()
    db.refresh(loan)
    return loan


@router.get("/{loan_id}/payment-preview", response_model=PaymentPreview)
def preview_payment(
    loan_id: str,
    amount_received: Annotated[Decimal, Query(ge=0)],
    as_of: Annotated[date, Query()],
    tenant_id: Annotated[str, Depends(require_tenant_id)],
    db: Annotated[Session, Depends(get_db)],
) -> PaymentPreview:
    loan = get_tenant_loan(db, tenant_id, loan_id)
    accrue_due_interest(db, loan, as_of)
    to_interest, to_principal, unapplied = suggested_payment_allocation(
        amount_received, loan.accrued_interest, loan.principal_outstanding
    )
    preview_interest = loan.accrued_interest
    preview_principal = loan.principal_outstanding
    db.rollback()
    return PaymentPreview(
        accrued_interest=preview_interest,
        principal_outstanding=preview_principal,
        amount_received=amount_received,
        suggested_to_interest=to_interest,
        suggested_to_principal=to_principal,
        unapplied_amount=unapplied,
    )


@router.post("/{loan_id}/payments", response_model=PaymentResult, status_code=status.HTTP_201_CREATED)
def receive_payment(
    loan_id: str,
    payload: PaymentCreate,
    tenant_id: Annotated[str, Depends(require_tenant_id)],
    db: Annotated[Session, Depends(get_db)],
) -> PaymentResult:
    loan = get_tenant_loan(db, tenant_id, loan_id)
    payment = record_payment(db, loan, payload)
    db.commit()
    db.refresh(payment)
    db.refresh(loan)
    return PaymentResult(payment=payment, loan=loan)
