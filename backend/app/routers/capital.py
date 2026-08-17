from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import require_tenant_id
from ..models import CapitalLedgerEntry, LedgerEntryType, Loan, LoanStatus, Tenant
from ..schemas import CapitalDepositCreate, CapitalEntryRead, CapitalSummary, CapitalWithdrawalCreate
from ..services.interest import money


router = APIRouter(prefix="/capital", tags=["capital"])


def capital_balance(db: Session, tenant_id: str) -> Decimal:
    total = db.scalar(
        select(func.coalesce(func.sum(CapitalLedgerEntry.amount), 0)).where(
            CapitalLedgerEntry.tenant_id == tenant_id
        )
    )
    return money(Decimal(total or 0))


@router.get("/summary", response_model=CapitalSummary)
def get_capital_summary(
    tenant_id: Annotated[str, Depends(require_tenant_id)],
    db: Annotated[Session, Depends(get_db)],
) -> CapitalSummary:
    capital_on_hand = capital_balance(db, tenant_id)
    principal_receivable, accrued_interest, active_loans = db.execute(
        select(
            func.coalesce(func.sum(Loan.principal_outstanding), 0),
            func.coalesce(func.sum(Loan.accrued_interest), 0),
            func.count(Loan.id),
        ).where(Loan.tenant_id == tenant_id, Loan.status == LoanStatus.active)
    ).one()

    now = datetime.now(timezone.utc)
    month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    collected_this_month = db.scalar(
        select(func.coalesce(func.sum(CapitalLedgerEntry.amount), 0)).where(
            CapitalLedgerEntry.tenant_id == tenant_id,
            CapitalLedgerEntry.entry_type.in_(
                [LedgerEntryType.payment_interest, LedgerEntryType.payment_principal]
            ),
            CapitalLedgerEntry.occurred_at >= month_start,
        )
    )

    return CapitalSummary(
        capital_on_hand=capital_on_hand,
        principal_receivable=money(Decimal(principal_receivable or 0)),
        accrued_interest_receivable=money(Decimal(accrued_interest or 0)),
        active_loans=int(active_loans or 0),
        collected_this_month=money(Decimal(collected_this_month or 0)),
    )


@router.post("/deposits", response_model=CapitalEntryRead, status_code=status.HTTP_201_CREATED)
def add_capital(
    payload: CapitalDepositCreate,
    tenant_id: Annotated[str, Depends(require_tenant_id)],
    db: Annotated[Session, Depends(get_db)],
) -> CapitalLedgerEntry:
    if db.get(Tenant, tenant_id) is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    entry = CapitalLedgerEntry(
        tenant_id=tenant_id,
        entry_type=LedgerEntryType.capital_deposit,
        amount=money(payload.amount),
        occurred_at=payload.occurred_at,
        notes=payload.notes,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.post("/withdrawals", response_model=CapitalEntryRead, status_code=status.HTTP_201_CREATED)
def withdraw_capital(
    payload: CapitalWithdrawalCreate,
    tenant_id: Annotated[str, Depends(require_tenant_id)],
    db: Annotated[Session, Depends(get_db)],
) -> CapitalLedgerEntry:
    if db.get(Tenant, tenant_id) is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    available = capital_balance(db, tenant_id)
    amount = money(payload.amount)
    if amount > available:
        raise HTTPException(status_code=422, detail="Withdrawal exceeds capital on hand")

    entry = CapitalLedgerEntry(
        tenant_id=tenant_id,
        entry_type=LedgerEntryType.withdrawal,
        amount=-amount,
        occurred_at=payload.occurred_at,
        notes=payload.notes,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
