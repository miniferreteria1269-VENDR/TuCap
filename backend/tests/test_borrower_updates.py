from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Borrower, BorrowerStatus, Loan, Tenant
from app.routers.borrowers import update_borrower
from app.routers.loans import create_loan
from app.schemas import BorrowerUpdate, LoanCreate


def borrower_update(**overrides: object) -> BorrowerUpdate:
    values = {
        "full_name": "María Actualizada",
        "phone": "7000-0000",
        "email": "maria@example.com",
        "address": "San Salvador",
        "government_id": "00000000-0",
        "credit_limit": Decimal("450.00"),
        "notes": "Perfil revisado",
        "status": BorrowerStatus.inactive,
    }
    values.update(overrides)
    return BorrowerUpdate(**values)


def make_database() -> tuple[Session, Tenant, Borrower]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    tenant = Tenant(name="Owner tenant")
    db.add(tenant)
    db.flush()
    borrower = Borrower(
        tenant_id=tenant.id,
        full_name="María Original",
        credit_limit=Decimal("100.00"),
    )
    db.add(borrower)
    db.commit()
    return db, tenant, borrower


def test_update_borrower_changes_profile_and_status_without_losing_summary() -> None:
    db, tenant, borrower = make_database()
    try:
        loan = Loan(
            tenant_id=tenant.id,
            borrower_id=borrower.id,
            original_principal=Decimal("100.00"),
            principal_outstanding=Decimal("80.00"),
            monthly_interest_rate=Decimal("8.00"),
            accrued_interest=Decimal("6.40"),
            start_date=date(2026, 8, 1),
            next_interest_date=date(2026, 9, 1),
        )
        db.add(loan)
        db.commit()

        result = update_borrower(borrower.id, borrower_update(), tenant.id, db)

        assert result.full_name == "María Actualizada"
        assert result.status == BorrowerStatus.inactive
        assert result.credit_limit == Decimal("450.00")
        assert result.active_loan_count == 1
        assert result.outstanding_principal == Decimal("80.00")
        assert result.accrued_interest == Decimal("6.40")
        assert db.get(Loan, loan.id) is not None
    finally:
        db.close()


def test_update_borrower_is_tenant_isolated() -> None:
    db, _, borrower = make_database()
    try:
        other_tenant = Tenant(name="Other tenant")
        db.add(other_tenant)
        db.commit()

        with pytest.raises(HTTPException) as error:
            update_borrower(borrower.id, borrower_update(), other_tenant.id, db)

        assert error.value.status_code == 404
        db.refresh(borrower)
        assert borrower.full_name == "María Original"
        assert borrower.status == BorrowerStatus.active
    finally:
        db.close()


@pytest.mark.parametrize("borrower_status", [BorrowerStatus.inactive, BorrowerStatus.blocked])
def test_non_active_borrower_cannot_receive_new_loan(borrower_status: BorrowerStatus) -> None:
    db, tenant, borrower = make_database()
    try:
        borrower.status = borrower_status
        db.commit()

        with pytest.raises(HTTPException) as error:
            create_loan(
                LoanCreate(
                    borrower_id=borrower.id,
                    original_principal=Decimal("100.00"),
                    monthly_interest_rate=Decimal("8.00"),
                    start_date=date(2026, 8, 18),
                ),
                tenant.id,
                db,
            )

        assert error.value.status_code == 409
        assert db.query(Loan).count() == 0
    finally:
        db.close()
