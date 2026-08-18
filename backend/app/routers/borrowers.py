from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import require_tenant_id
from ..models import (
    Borrower,
    CapitalLedgerEntry,
    FinancialReversal,
    InterestAccrual,
    LedgerEntryType,
    Loan,
    LoanClosure,
    LoanStatus,
    Payment,
    Tenant,
)
from ..schemas import BorrowerCreate, BorrowerPerformanceRead, BorrowerRead, BorrowerSummary, BorrowerUpdate
from ..services.interest import money


router = APIRouter(prefix="/borrowers", tags=["borrowers"])


def borrower_summary_query(tenant_id: str):
    return (
        select(
            Borrower,
            func.count(Loan.id).filter(Loan.status == LoanStatus.active).label("active_loan_count"),
            func.coalesce(
                func.sum(Loan.principal_outstanding).filter(Loan.status == LoanStatus.active), 0
            ).label("outstanding_principal"),
            func.coalesce(
                func.sum(Loan.accrued_interest).filter(Loan.status == LoanStatus.active), 0
            ).label("accrued_interest"),
        )
        .outerjoin(Loan, (Loan.borrower_id == Borrower.id) & (Loan.tenant_id == tenant_id))
        .where(Borrower.tenant_id == tenant_id)
        .group_by(Borrower.id)
    )


def serialize_summary(row: object) -> BorrowerSummary:
    borrower, active_count, principal, interest = row
    return BorrowerSummary.model_validate(borrower).model_copy(
        update={
            "active_loan_count": int(active_count or 0),
            "outstanding_principal": Decimal(principal or 0),
            "accrued_interest": Decimal(interest or 0),
        }
    )


@router.get("", response_model=list[BorrowerSummary])
def list_borrowers(
    tenant_id: Annotated[str, Depends(require_tenant_id)],
    db: Annotated[Session, Depends(get_db)],
) -> list[BorrowerSummary]:
    rows = db.execute(borrower_summary_query(tenant_id).order_by(Borrower.full_name)).all()
    return [serialize_summary(row) for row in rows]


@router.get("/{borrower_id}", response_model=BorrowerSummary)
def get_borrower(
    borrower_id: str,
    tenant_id: Annotated[str, Depends(require_tenant_id)],
    db: Annotated[Session, Depends(get_db)],
) -> BorrowerSummary:
    row = db.execute(
        borrower_summary_query(tenant_id).where(Borrower.id == borrower_id)
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Borrower not found")
    return serialize_summary(row)


@router.get("/{borrower_id}/performance", response_model=BorrowerPerformanceRead)
def get_borrower_performance(
    borrower_id: str,
    tenant_id: Annotated[str, Depends(require_tenant_id)],
    db: Annotated[Session, Depends(get_db)],
) -> BorrowerPerformanceRead:
    borrower = db.scalar(
        select(Borrower).where(Borrower.id == borrower_id, Borrower.tenant_id == tenant_id)
    )
    if borrower is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    loans = list(
        db.scalars(
            select(Loan).where(Loan.borrower_id == borrower.id, Loan.tenant_id == tenant_id)
        )
    )
    loan_ids = [loan.id for loan in loans]
    if not loan_ids:
        return BorrowerPerformanceRead(
            borrower_id=borrower.id,
            total_loans=0,
            active_loans=0,
            paid_loans=0,
            written_off_loans=0,
            total_principal_lent=Decimal("0.00"),
            active_principal_exposure=Decimal("0.00"),
            active_interest_receivable=Decimal("0.00"),
            total_principal_collected=Decimal("0.00"),
            total_interest_collected=Decimal("0.00"),
            collateral_recovered=Decimal("0.00"),
            total_recovered=Decimal("0.00"),
            closed_principal_lent=Decimal("0.00"),
            closed_total_recovered=Decimal("0.00"),
            closed_economic_result=Decimal("0.00"),
            economic_outcome="no_closed_loans",
            completion_rate=Decimal("0.00"),
            late_payment_count=0,
            average_closed_duration_days=0,
            average_monthly_result=Decimal("0.00"),
        )

    reversed_payment_ids = select(FinancialReversal.payment_id).where(
        FinancialReversal.tenant_id == tenant_id,
        FinancialReversal.payment_id.is_not(None),
    )
    payment_rows = db.execute(
        select(
            Payment.loan_id,
            func.coalesce(func.sum(Payment.amount_to_principal), 0),
            func.coalesce(func.sum(Payment.amount_to_interest), 0),
            func.coalesce(func.sum(Payment.amount_received), 0),
        )
        .where(
            Payment.tenant_id == tenant_id,
            Payment.loan_id.in_(loan_ids),
            Payment.id.not_in(reversed_payment_ids),
        )
        .group_by(Payment.loan_id)
    ).all()
    payments_by_loan = {
        loan_id: (Decimal(principal or 0), Decimal(interest or 0), Decimal(received or 0))
        for loan_id, principal, interest, received in payment_rows
    }

    reversed_ledger_ids = select(FinancialReversal.ledger_entry_id).where(
        FinancialReversal.tenant_id == tenant_id,
        FinancialReversal.ledger_entry_id.is_not(None),
    )
    collateral_rows = db.execute(
        select(CapitalLedgerEntry.loan_id, func.coalesce(func.sum(CapitalLedgerEntry.amount), 0))
        .where(
            CapitalLedgerEntry.tenant_id == tenant_id,
            CapitalLedgerEntry.loan_id.in_(loan_ids),
            CapitalLedgerEntry.entry_type == LedgerEntryType.collateral_recovery,
            CapitalLedgerEntry.id.not_in(reversed_ledger_ids),
        )
        .group_by(CapitalLedgerEntry.loan_id)
    ).all()
    collateral_by_loan = {loan_id: Decimal(amount or 0) for loan_id, amount in collateral_rows}

    closures = list(
        db.scalars(
            select(LoanClosure).where(
                LoanClosure.tenant_id == tenant_id,
                LoanClosure.loan_id.in_(loan_ids),
            )
        )
    )
    closure_by_loan = {closure.loan_id: closure for closure in closures}
    accrual_rows = db.execute(
        select(InterestAccrual.loan_id, func.count(InterestAccrual.id))
        .where(InterestAccrual.tenant_id == tenant_id, InterestAccrual.loan_id.in_(loan_ids))
        .group_by(InterestAccrual.loan_id)
    ).all()
    accrual_count_by_loan = {loan_id: int(count or 0) for loan_id, count in accrual_rows}

    active_loans = sum(loan.status == LoanStatus.active for loan in loans)
    paid_loans = sum(loan.status == LoanStatus.paid for loan in loans)
    written_off_loans = sum(loan.status == LoanStatus.written_off for loan in loans)
    closed_count = paid_loans + written_off_loans
    total_principal_lent = sum((loan.original_principal for loan in loans), Decimal("0"))
    active_exposure = sum(
        (loan.principal_outstanding for loan in loans if loan.status == LoanStatus.active),
        Decimal("0"),
    )
    active_interest = sum(
        (loan.accrued_interest for loan in loans if loan.status == LoanStatus.active),
        Decimal("0"),
    )
    total_principal_collected = sum((row[0] for row in payments_by_loan.values()), Decimal("0"))
    total_interest_collected = sum((row[1] for row in payments_by_loan.values()), Decimal("0"))
    payment_total = sum((row[2] for row in payments_by_loan.values()), Decimal("0"))
    collateral_total = sum(collateral_by_loan.values(), Decimal("0"))

    closed_loans = [loan for loan in loans if loan.status != LoanStatus.active]
    closed_principal_lent = sum((loan.original_principal for loan in closed_loans), Decimal("0"))
    closed_total_recovered = sum(
        (
            payments_by_loan.get(loan.id, (Decimal("0"), Decimal("0"), Decimal("0")))[2]
            + collateral_by_loan.get(loan.id, Decimal("0"))
            for loan in closed_loans
        ),
        Decimal("0"),
    )
    closed_economic_result = money(closed_total_recovered - closed_principal_lent)
    economic_outcome = (
        "no_closed_loans"
        if closed_count == 0
        else "earnings"
        if closed_economic_result > 0
        else "loss"
        if closed_economic_result < 0
        else "break_even"
    )
    late_count = sum(
        closure_by_loan[loan.id].late_payment_count
        for loan in closed_loans
        if loan.id in closure_by_loan
    )
    durations = [
        max(((closure_by_loan.get(loan.id).closed_at if closure_by_loan.get(loan.id) else loan.closed_at).date() - loan.start_date).days, 0)
        for loan in closed_loans
        if (closure_by_loan.get(loan.id) and closure_by_loan.get(loan.id).closed_at) or loan.closed_at
    ]
    closed_billed_months = sum(max(accrual_count_by_loan.get(loan.id, 0), 1) for loan in closed_loans)

    return BorrowerPerformanceRead(
        borrower_id=borrower.id,
        total_loans=len(loans),
        active_loans=active_loans,
        paid_loans=paid_loans,
        written_off_loans=written_off_loans,
        total_principal_lent=money(total_principal_lent),
        active_principal_exposure=money(active_exposure),
        active_interest_receivable=money(active_interest),
        total_principal_collected=money(total_principal_collected),
        total_interest_collected=money(total_interest_collected),
        collateral_recovered=money(collateral_total),
        total_recovered=money(payment_total + collateral_total),
        closed_principal_lent=money(closed_principal_lent),
        closed_total_recovered=money(closed_total_recovered),
        closed_economic_result=closed_economic_result,
        economic_outcome=economic_outcome,
        completion_rate=money(Decimal(paid_loans * 100) / closed_count) if closed_count else Decimal("0.00"),
        late_payment_count=late_count,
        average_closed_duration_days=round(sum(durations) / len(durations)) if durations else 0,
        average_monthly_result=money(closed_economic_result / closed_billed_months) if closed_billed_months else Decimal("0.00"),
    )


@router.post("", response_model=BorrowerRead, status_code=status.HTTP_201_CREATED)
def create_borrower(
    payload: BorrowerCreate,
    tenant_id: Annotated[str, Depends(require_tenant_id)],
    db: Annotated[Session, Depends(get_db)],
) -> Borrower:
    if db.get(Tenant, tenant_id) is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    borrower = Borrower(tenant_id=tenant_id, **payload.model_dump())
    db.add(borrower)
    db.commit()
    db.refresh(borrower)
    return borrower


@router.patch("/{borrower_id}", response_model=BorrowerSummary)
def update_borrower(
    borrower_id: str,
    payload: BorrowerUpdate,
    tenant_id: Annotated[str, Depends(require_tenant_id)],
    db: Annotated[Session, Depends(get_db)],
) -> BorrowerSummary:
    borrower = db.scalar(
        select(Borrower).where(Borrower.id == borrower_id, Borrower.tenant_id == tenant_id)
    )
    if borrower is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    for field, value in payload.model_dump().items():
        setattr(borrower, field, value)
    db.commit()

    row = db.execute(
        borrower_summary_query(tenant_id).where(Borrower.id == borrower.id)
    ).one()
    return serialize_summary(row)
