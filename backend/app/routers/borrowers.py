from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import require_tenant_id
from ..models import Borrower, Loan, LoanStatus, Tenant
from ..schemas import BorrowerCreate, BorrowerRead, BorrowerSummary


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
