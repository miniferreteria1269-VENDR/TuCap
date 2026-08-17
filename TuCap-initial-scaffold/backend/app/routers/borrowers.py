from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import require_tenant_id
from ..models import Borrower, Tenant
from ..schemas import BorrowerCreate, BorrowerRead


router = APIRouter(prefix="/borrowers", tags=["borrowers"])


@router.get("", response_model=list[BorrowerRead])
def list_borrowers(
    tenant_id: Annotated[str, Depends(require_tenant_id)],
    db: Annotated[Session, Depends(get_db)],
) -> list[Borrower]:
    return list(
        db.scalars(
            select(Borrower)
            .where(Borrower.tenant_id == tenant_id)
            .order_by(Borrower.full_name)
        )
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

