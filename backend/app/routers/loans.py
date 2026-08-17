from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import require_tenant_id
from ..models import (
    Borrower,
    CapitalLedgerEntry,
    InterestAccrual,
    LedgerEntryType,
    Loan,
    LoanClosure,
    LoanClosureReason,
    LoanStatus,
    Payment,
)
from ..schemas import (
    CollateralRecoveryCreate,
    LoanCreate,
    LoanDetailRead,
    LoanPerformanceRead,
    LoanPerformanceUpdate,
    LoanRead,
    LoanWriteOffCreate,
    PaymentCreate,
    PaymentPreview,
    PaymentRead,
    PaymentResult,
)
from ..services.interest import add_month, money, suggested_payment_allocation
from ..services.loans import (
    accrue_due_interest,
    get_tenant_loan,
    post_initial_interest,
    record_payment,
)


router = APIRouter(prefix="/loans", tags=["loans"])


def build_performance(db: Session, loan: Loan, payments_collected: Decimal, accrual_count: int) -> LoanPerformanceRead | None:
    if loan.status == LoanStatus.active:
        return None

    closure = db.scalar(
        select(LoanClosure).where(
            LoanClosure.tenant_id == loan.tenant_id,
            LoanClosure.loan_id == loan.id,
        )
    )
    closed_at = closure.closed_at if closure else loan.closed_at
    if closed_at is None:
        return None

    collateral = db.scalar(
        select(func.coalesce(func.sum(CapitalLedgerEntry.amount), 0)).where(
            CapitalLedgerEntry.tenant_id == loan.tenant_id,
            CapitalLedgerEntry.loan_id == loan.id,
            CapitalLedgerEntry.entry_type == LedgerEntryType.collateral_recovery,
        )
    )
    collateral_recovered = money(Decimal(collateral or 0))
    total_recovered = money(payments_collected + collateral_recovered)
    economic_result = money(total_recovered - loan.original_principal)
    outcome = "earnings" if economic_result > 0 else "loss" if economic_result < 0 else "break_even"
    billed_months = max(accrual_count, 1)
    return LoanPerformanceRead(
        closure_reason=closure.reason if closure else LoanClosureReason(loan.status.value),
        closed_at=closed_at,
        contract_fulfilled=loan.status == LoanStatus.paid,
        principal_shortfall=money(closure.principal_shortfall if closure else loan.principal_outstanding),
        interest_shortfall=money(closure.interest_shortfall if closure else loan.accrued_interest),
        payments_collected=payments_collected,
        collateral_recovered=collateral_recovered,
        total_recovered=total_recovered,
        economic_result=economic_result,
        economic_outcome=outcome,
        duration_days=max((closed_at.date() - loan.start_date).days, 0),
        billed_months=billed_months,
        average_monthly_result=money(economic_result / billed_months),
        late_payment_count=closure.late_payment_count if closure else 0,
        notes=closure.notes if closure else None,
    )


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


@router.get("/{loan_id}", response_model=LoanDetailRead)
def get_loan_detail(
    loan_id: str,
    tenant_id: Annotated[str, Depends(require_tenant_id)],
    db: Annotated[Session, Depends(get_db)],
) -> LoanDetailRead:
    loan = get_tenant_loan(db, tenant_id, loan_id)
    payments = list(
        db.scalars(
            select(Payment)
            .where(Payment.tenant_id == tenant_id, Payment.loan_id == loan.id)
            .order_by(Payment.received_at.desc(), Payment.created_at.desc())
        )
    )
    accruals = list(
        db.scalars(
            select(InterestAccrual)
            .where(InterestAccrual.tenant_id == tenant_id, InterestAccrual.loan_id == loan.id)
            .order_by(InterestAccrual.cycle_date.desc())
        )
    )
    interest_collected = money(sum((payment.amount_to_interest for payment in payments), Decimal("0")))
    principal_collected = money(sum((payment.amount_to_principal for payment in payments), Decimal("0")))

    return LoanDetailRead(
        **LoanRead.model_validate(loan).model_dump(),
        payments=[PaymentRead.model_validate(payment) for payment in payments],
        interest_accruals=accruals,
        total_interest_collected=interest_collected,
        total_principal_collected=principal_collected,
        total_collected=money(interest_collected + principal_collected),
        performance=build_performance(
            db,
            loan,
            money(interest_collected + principal_collected),
            len(accruals),
        ),
    )


@router.post("/{loan_id}/write-off", response_model=LoanDetailRead)
def write_off_loan(
    loan_id: str,
    payload: LoanWriteOffCreate,
    tenant_id: Annotated[str, Depends(require_tenant_id)],
    db: Annotated[Session, Depends(get_db)],
) -> LoanDetailRead:
    loan = get_tenant_loan(db, tenant_id, loan_id)
    if loan.status != LoanStatus.active:
        raise HTTPException(status_code=422, detail="Only active loans can be written off")
    if payload.closed_at.date() < loan.start_date:
        raise HTTPException(status_code=422, detail="Closure date cannot precede the loan date")

    accrue_due_interest(db, loan, payload.closed_at.date())
    loan.status = LoanStatus.written_off
    loan.closed_at = payload.closed_at
    db.add(
        LoanClosure(
            tenant_id=tenant_id,
            loan_id=loan.id,
            reason=LoanClosureReason.written_off,
            closed_at=payload.closed_at,
            principal_shortfall=money(loan.principal_outstanding),
            interest_shortfall=money(loan.accrued_interest),
            late_payment_count=payload.late_payment_count,
            notes=payload.notes,
        )
    )
    if payload.collateral_recovery_amount:
        db.add(
            CapitalLedgerEntry(
                tenant_id=tenant_id,
                entry_type=LedgerEntryType.collateral_recovery,
                amount=money(payload.collateral_recovery_amount),
                loan_id=loan.id,
                occurred_at=payload.closed_at,
                notes=payload.notes,
            )
        )
    db.commit()
    return get_loan_detail(loan.id, tenant_id, db)


@router.post("/{loan_id}/collateral-recoveries", response_model=LoanDetailRead, status_code=status.HTTP_201_CREATED)
def add_collateral_recovery(
    loan_id: str,
    payload: CollateralRecoveryCreate,
    tenant_id: Annotated[str, Depends(require_tenant_id)],
    db: Annotated[Session, Depends(get_db)],
) -> LoanDetailRead:
    loan = get_tenant_loan(db, tenant_id, loan_id)
    if loan.status != LoanStatus.written_off:
        raise HTTPException(status_code=422, detail="Collateral recovery requires a written-off loan")
    db.add(
        CapitalLedgerEntry(
            tenant_id=tenant_id,
            entry_type=LedgerEntryType.collateral_recovery,
            amount=money(payload.amount),
            loan_id=loan.id,
            occurred_at=payload.occurred_at,
            notes=payload.notes,
        )
    )
    db.commit()
    return get_loan_detail(loan.id, tenant_id, db)


@router.patch("/{loan_id}/performance", response_model=LoanDetailRead)
def update_loan_performance(
    loan_id: str,
    payload: LoanPerformanceUpdate,
    tenant_id: Annotated[str, Depends(require_tenant_id)],
    db: Annotated[Session, Depends(get_db)],
) -> LoanDetailRead:
    loan = get_tenant_loan(db, tenant_id, loan_id)
    if loan.status == LoanStatus.active:
        raise HTTPException(status_code=422, detail="Performance is only available for closed loans")
    closure = db.scalar(
        select(LoanClosure).where(LoanClosure.tenant_id == tenant_id, LoanClosure.loan_id == loan.id)
    )
    if closure is None:
        if loan.closed_at is None:
            raise HTTPException(status_code=422, detail="Loan has no closure date")
        closure = LoanClosure(
            tenant_id=tenant_id,
            loan_id=loan.id,
            reason=LoanClosureReason(loan.status.value),
            closed_at=loan.closed_at,
            principal_shortfall=money(loan.principal_outstanding),
            interest_shortfall=money(loan.accrued_interest),
        )
        db.add(closure)
    closure.late_payment_count = payload.late_payment_count
    closure.notes = payload.notes
    db.commit()
    return get_loan_detail(loan.id, tenant_id, db)


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
