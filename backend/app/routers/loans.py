from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user, require_tenant_id
from ..models import (
    Borrower,
    CapitalLedgerEntry,
    FinancialReversal,
    InterestAccrual,
    LedgerEntryType,
    Loan,
    LoanClosure,
    LoanClosureReason,
    LoanStatus,
    Payment,
    User,
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
    ReversalCreate,
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

    reversed_ledger_ids = select(FinancialReversal.ledger_entry_id).where(
        FinancialReversal.tenant_id == loan.tenant_id,
        FinancialReversal.ledger_entry_id.is_not(None),
    )
    collateral = db.scalar(
        select(func.coalesce(func.sum(CapitalLedgerEntry.amount), 0)).where(
            CapitalLedgerEntry.tenant_id == loan.tenant_id,
            CapitalLedgerEntry.loan_id == loan.id,
            CapitalLedgerEntry.entry_type == LedgerEntryType.collateral_recovery,
            CapitalLedgerEntry.id.not_in(reversed_ledger_ids),
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
    reversals = list(
        db.scalars(
            select(FinancialReversal).where(
                FinancialReversal.tenant_id == tenant_id,
                FinancialReversal.payment_id.in_([payment.id for payment in payments]),
            )
        )
    ) if payments else []
    reversal_by_payment = {reversal.payment_id: reversal for reversal in reversals}
    active_payments = [payment for payment in payments if payment.id not in reversal_by_payment]
    accruals = list(
        db.scalars(
            select(InterestAccrual)
            .where(InterestAccrual.tenant_id == tenant_id, InterestAccrual.loan_id == loan.id)
            .order_by(InterestAccrual.cycle_date.desc())
        )
    )
    interest_collected = money(sum((payment.amount_to_interest for payment in active_payments), Decimal("0")))
    principal_collected = money(sum((payment.amount_to_principal for payment in active_payments), Decimal("0")))

    return LoanDetailRead(
        **LoanRead.model_validate(loan).model_dump(),
        payments=[
            PaymentRead.model_validate(payment).model_copy(
                update={
                    "reversed_at": reversal_by_payment[payment.id].reversed_at if payment.id in reversal_by_payment else None,
                    "reversal_reason": reversal_by_payment[payment.id].reason if payment.id in reversal_by_payment else None,
                }
            )
            for payment in payments
        ],
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
    closure = db.scalar(select(LoanClosure).where(LoanClosure.loan_id == loan.id))
    if closure is None:
        closure = LoanClosure(
            tenant_id=tenant_id,
            loan_id=loan.id,
        )
        db.add(closure)
    closure.reason = LoanClosureReason.written_off
    closure.closed_at = payload.closed_at
    closure.principal_shortfall = money(loan.principal_outstanding)
    closure.interest_shortfall = money(loan.accrued_interest)
    closure.late_payment_count = payload.late_payment_count
    closure.notes = payload.notes
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


@router.post("/{loan_id}/payments/{payment_id}/reverse", response_model=LoanDetailRead)
def reverse_payment(
    loan_id: str,
    payment_id: str,
    payload: ReversalCreate,
    tenant_id: Annotated[str, Depends(require_tenant_id)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> LoanDetailRead:
    loan = get_tenant_loan(db, tenant_id, loan_id)
    payment = db.scalar(
        select(Payment).where(
            Payment.id == payment_id,
            Payment.loan_id == loan.id,
            Payment.tenant_id == tenant_id,
        )
    )
    if payment is None:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    if db.scalar(select(FinancialReversal).where(FinancialReversal.payment_id == payment.id)):
        raise HTTPException(status_code=422, detail="Este pago ya fue anulado")
    later_accrual = db.scalar(
        select(InterestAccrual.id).where(
            InterestAccrual.tenant_id == tenant_id,
            InterestAccrual.loan_id == loan.id,
            InterestAccrual.cycle_date > payment.received_at.date(),
        ).limit(1)
    )
    if later_accrual is not None:
        raise HTTPException(
            status_code=422,
            detail="Este pago no puede anularse porque ya se calculó un ciclo de interés posterior",
        )

    db.add(
        FinancialReversal(
            tenant_id=tenant_id,
            payment_id=payment.id,
            reversed_by_user_id=user.id,
            reason=payload.reason.strip(),
            reversed_at=payload.reversed_at,
        )
    )
    db.add(
        CapitalLedgerEntry(
            tenant_id=tenant_id,
            entry_type=LedgerEntryType.adjustment,
            amount=-money(payment.amount_received),
            loan_id=loan.id,
            payment_id=payment.id,
            occurred_at=payload.reversed_at,
            notes=f"Reversal: {payload.reason.strip()}",
        )
    )
    loan.principal_outstanding = money(loan.principal_outstanding + payment.amount_to_principal)
    loan.accrued_interest = money(loan.accrued_interest + payment.amount_to_interest)

    closure = db.scalar(select(LoanClosure).where(LoanClosure.loan_id == loan.id))
    if loan.status == LoanStatus.paid:
        loan.status = LoanStatus.active
        loan.closed_at = None
    elif loan.status == LoanStatus.written_off and closure is not None:
        closure.principal_shortfall = money(loan.principal_outstanding)
        closure.interest_shortfall = money(loan.accrued_interest)

    db.commit()
    return get_loan_detail(loan.id, tenant_id, db)
