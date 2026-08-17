from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user, require_tenant_id
from ..models import CapitalLedgerEntry, FinancialReversal, LedgerEntryType, Loan, LoanStatus, Payment, Tenant, User
from ..schemas import CapitalDepositCreate, CapitalEntryRead, CapitalSummary, CapitalWithdrawalCreate, ReversalCreate
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
    reversed_payment_ids = select(FinancialReversal.payment_id).where(
        FinancialReversal.tenant_id == tenant_id,
        FinancialReversal.payment_id.is_not(None),
    )
    collected_this_month = db.scalar(
        select(func.coalesce(func.sum(Payment.amount_received), 0)).where(
            Payment.tenant_id == tenant_id,
            Payment.received_at >= month_start,
            Payment.id.not_in(reversed_payment_ids),
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


def capital_entry_response(entry: CapitalLedgerEntry, reversal: FinancialReversal | None = None) -> CapitalEntryRead:
    return CapitalEntryRead.model_validate(entry).model_copy(
        update={
            "reversed_at": reversal.reversed_at if reversal else None,
            "reversal_reason": reversal.reason if reversal else None,
            "reversible": reversal is None and entry.entry_type in {
                LedgerEntryType.capital_deposit,
                LedgerEntryType.withdrawal,
                LedgerEntryType.collateral_recovery,
            },
        }
    )


@router.get("/entries", response_model=list[CapitalEntryRead])
def list_capital_entries(
    tenant_id: Annotated[str, Depends(require_tenant_id)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = 50,
) -> list[CapitalEntryRead]:
    safe_limit = min(max(limit, 1), 200)
    entries = list(
        db.scalars(
            select(CapitalLedgerEntry)
            .where(
                CapitalLedgerEntry.tenant_id == tenant_id,
                (
                    CapitalLedgerEntry.entry_type.in_([
                        LedgerEntryType.capital_deposit,
                        LedgerEntryType.withdrawal,
                        LedgerEntryType.collateral_recovery,
                    ])
                    | ((CapitalLedgerEntry.entry_type == LedgerEntryType.adjustment) & CapitalLedgerEntry.payment_id.is_(None))
                ),
            )
            .order_by(CapitalLedgerEntry.occurred_at.desc(), CapitalLedgerEntry.created_at.desc())
            .limit(safe_limit)
        )
    )
    reversals = list(
        db.scalars(
            select(FinancialReversal).where(
                FinancialReversal.tenant_id == tenant_id,
                FinancialReversal.ledger_entry_id.in_([entry.id for entry in entries]),
            )
        )
    ) if entries else []
    reversal_by_entry = {reversal.ledger_entry_id: reversal for reversal in reversals}
    return [capital_entry_response(entry, reversal_by_entry.get(entry.id)) for entry in entries]


@router.post("/entries/{entry_id}/reverse", response_model=CapitalEntryRead)
def reverse_capital_entry(
    entry_id: str,
    payload: ReversalCreate,
    tenant_id: Annotated[str, Depends(require_tenant_id)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CapitalEntryRead:
    entry = db.scalar(
        select(CapitalLedgerEntry).where(
            CapitalLedgerEntry.id == entry_id,
            CapitalLedgerEntry.tenant_id == tenant_id,
        )
    )
    if entry is None:
        raise HTTPException(status_code=404, detail="Movimiento de capital no encontrado")
    if entry.entry_type not in {
        LedgerEntryType.capital_deposit,
        LedgerEntryType.withdrawal,
        LedgerEntryType.collateral_recovery,
    }:
        raise HTTPException(status_code=422, detail="Este movimiento no puede anularse directamente")
    if db.scalar(select(FinancialReversal).where(FinancialReversal.ledger_entry_id == entry.id)):
        raise HTTPException(status_code=422, detail="Este movimiento ya fue anulado")

    reversal = FinancialReversal(
        tenant_id=tenant_id,
        ledger_entry_id=entry.id,
        reversed_by_user_id=user.id,
        reason=payload.reason.strip(),
        reversed_at=payload.reversed_at,
    )
    db.add(reversal)
    db.add(
        CapitalLedgerEntry(
            tenant_id=tenant_id,
            entry_type=LedgerEntryType.adjustment,
            amount=-entry.amount,
            loan_id=entry.loan_id,
            occurred_at=payload.reversed_at,
            notes=f"Reversal: {payload.reason.strip()}",
        )
    )
    db.commit()
    return capital_entry_response(entry, reversal)


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
