from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user, require_tenant_id
from ..models import CapitalLedgerEntry, FinancialReversal, LedgerEntryType, Loan, LoanStatus, Payment, Tenant, User
from ..schemas import (
    CapitalDepositCreate,
    CapitalEntryRead,
    CapitalPeriodReport,
    CapitalSummary,
    CapitalWithdrawalCreate,
    ReversalCreate,
)
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


@router.get("/report", response_model=CapitalPeriodReport)
def get_capital_period_report(
    date_from: Annotated[date, Query()],
    date_to: Annotated[date, Query()],
    tenant_id: Annotated[str, Depends(require_tenant_id)],
    db: Annotated[Session, Depends(get_db)],
) -> CapitalPeriodReport:
    if date_to < date_from:
        raise HTTPException(status_code=422, detail="La fecha final no puede ser anterior a la inicial")

    range_start = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
    range_end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
    reversed_payment_ids = select(FinancialReversal.payment_id).where(
        FinancialReversal.tenant_id == tenant_id,
        FinancialReversal.payment_id.is_not(None),
    )
    principal_collected, interest_collected, payments_collected = db.execute(
        select(
            func.coalesce(func.sum(Payment.amount_to_principal), 0),
            func.coalesce(func.sum(Payment.amount_to_interest), 0),
            func.coalesce(func.sum(Payment.amount_received), 0),
        ).where(
            Payment.tenant_id == tenant_id,
            Payment.received_at >= range_start,
            Payment.received_at < range_end,
            Payment.id.not_in(reversed_payment_ids),
        )
    ).one()

    capital_lent, new_loans = db.execute(
        select(func.coalesce(func.sum(Loan.original_principal), 0), func.count(Loan.id)).where(
            Loan.tenant_id == tenant_id,
            Loan.start_date >= date_from,
            Loan.start_date <= date_to,
        )
    ).one()

    reversed_ledger_ids = select(FinancialReversal.ledger_entry_id).where(
        FinancialReversal.tenant_id == tenant_id,
        FinancialReversal.ledger_entry_id.is_not(None),
    )
    ledger_rows = db.execute(
        select(CapitalLedgerEntry.entry_type, func.coalesce(func.sum(CapitalLedgerEntry.amount), 0))
        .where(
            CapitalLedgerEntry.tenant_id == tenant_id,
            CapitalLedgerEntry.occurred_at >= range_start,
            CapitalLedgerEntry.occurred_at < range_end,
            CapitalLedgerEntry.entry_type.in_([
                LedgerEntryType.capital_deposit,
                LedgerEntryType.withdrawal,
                LedgerEntryType.collateral_recovery,
            ]),
            CapitalLedgerEntry.id.not_in(reversed_ledger_ids),
        )
        .group_by(CapitalLedgerEntry.entry_type)
    ).all()
    ledger_totals = {entry_type: Decimal(amount or 0) for entry_type, amount in ledger_rows}

    closed_loans = list(
        db.scalars(
            select(Loan).where(
                Loan.tenant_id == tenant_id,
                Loan.status.in_([LoanStatus.paid, LoanStatus.written_off]),
                Loan.closed_at >= range_start,
                Loan.closed_at < range_end,
            )
        )
    )
    closed_loan_ids = [loan.id for loan in closed_loans]
    recovered_by_loan: dict[str, Decimal] = {}
    if closed_loan_ids:
        payment_rows = db.execute(
            select(Payment.loan_id, func.coalesce(func.sum(Payment.amount_received), 0))
            .where(
                Payment.tenant_id == tenant_id,
                Payment.loan_id.in_(closed_loan_ids),
                Payment.id.not_in(reversed_payment_ids),
            )
            .group_by(Payment.loan_id)
        ).all()
        for loan_id, amount in payment_rows:
            recovered_by_loan[loan_id] = Decimal(amount or 0)
        collateral_rows = db.execute(
            select(CapitalLedgerEntry.loan_id, func.coalesce(func.sum(CapitalLedgerEntry.amount), 0))
            .where(
                CapitalLedgerEntry.tenant_id == tenant_id,
                CapitalLedgerEntry.loan_id.in_(closed_loan_ids),
                CapitalLedgerEntry.entry_type == LedgerEntryType.collateral_recovery,
                CapitalLedgerEntry.id.not_in(reversed_ledger_ids),
            )
            .group_by(CapitalLedgerEntry.loan_id)
        ).all()
        for loan_id, amount in collateral_rows:
            recovered_by_loan[loan_id] = recovered_by_loan.get(loan_id, Decimal("0")) + Decimal(amount or 0)

    closed_principal_lent = sum((loan.original_principal for loan in closed_loans), Decimal("0"))
    closed_total_recovered = sum(
        (recovered_by_loan.get(loan.id, Decimal("0")) for loan in closed_loans), Decimal("0")
    )

    return CapitalPeriodReport(
        date_from=date_from,
        date_to=date_to,
        payments_collected=money(Decimal(payments_collected or 0)),
        interest_collected=money(Decimal(interest_collected or 0)),
        principal_collected=money(Decimal(principal_collected or 0)),
        capital_lent=money(Decimal(capital_lent or 0)),
        new_loans=int(new_loans or 0),
        capital_deposited=money(ledger_totals.get(LedgerEntryType.capital_deposit, Decimal("0"))),
        capital_withdrawn=money(abs(ledger_totals.get(LedgerEntryType.withdrawal, Decimal("0")))),
        collateral_recovered=money(ledger_totals.get(LedgerEntryType.collateral_recovery, Decimal("0"))),
        loans_closed=len(closed_loans),
        loans_paid=sum(loan.status == LoanStatus.paid for loan in closed_loans),
        loans_written_off=sum(loan.status == LoanStatus.written_off for loan in closed_loans),
        closed_principal_lent=money(closed_principal_lent),
        closed_total_recovered=money(closed_total_recovered),
        realized_economic_result=money(closed_total_recovered - closed_principal_lent),
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
