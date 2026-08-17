from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Borrower, Loan, Payment, Tenant
from app.routers.loans import add_collateral_recovery, get_loan_detail, update_loan_performance, write_off_loan
from app.schemas import CollateralRecoveryCreate, LoanPerformanceUpdate, LoanWriteOffCreate
from app.services.interest import add_month
from app.services.loans import post_initial_interest


def make_loan() -> tuple[Session, Tenant, Loan]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    tenant = Tenant(name="Alfredo")
    db.add(tenant)
    db.flush()
    borrower = Borrower(tenant_id=tenant.id, full_name="Borrower")
    db.add(borrower)
    db.flush()
    loan = Loan(
        tenant_id=tenant.id,
        borrower_id=borrower.id,
        original_principal=Decimal("1000.00"),
        principal_outstanding=Decimal("1000.00"),
        monthly_interest_rate=Decimal("8.00"),
        start_date=date(2026, 1, 1),
        next_interest_date=add_month(date(2026, 1, 1)),
    )
    db.add(loan)
    db.flush()
    post_initial_interest(db, loan)
    db.commit()
    return db, tenant, loan


def add_historical_collection(db: Session, loan: Loan) -> None:
    db.add(
        Payment(
            tenant_id=loan.tenant_id,
            loan_id=loan.id,
            amount_received=Decimal("1200.00"),
            amount_to_interest=Decimal("500.00"),
            amount_to_principal=Decimal("700.00"),
            unapplied_amount=Decimal("0.00"),
            received_at=datetime(2026, 5, 1, 12, tzinfo=timezone.utc),
        )
    )
    loan.principal_outstanding = Decimal("300.00")
    loan.accrued_interest = Decimal("0.00")
    db.commit()


def test_written_off_loan_can_be_contract_failure_and_economic_gain() -> None:
    db, tenant, loan = make_loan()
    try:
        add_historical_collection(db, loan)
        detail = write_off_loan(
            loan.id,
            LoanWriteOffCreate(
                closed_at=datetime(2026, 5, 2, 12, tzinfo=timezone.utc),
                late_payment_count=2,
                notes="Stopped paying principal",
            ),
            tenant.id,
            db,
        )

        assert detail.status.value == "written_off"
        assert detail.performance is not None
        assert detail.performance.contract_fulfilled is False
        assert detail.performance.principal_shortfall == Decimal("300.00")
        assert detail.performance.total_recovered == Decimal("1200.00")
        assert detail.performance.economic_result == Decimal("200.00")
        assert detail.performance.economic_outcome == "earnings"
        assert detail.performance.late_payment_count == 2
    finally:
        db.close()


def test_later_collateral_recovery_recalculates_result_and_capital() -> None:
    db, tenant, loan = make_loan()
    try:
        detail = write_off_loan(
            loan.id,
            LoanWriteOffCreate(closed_at=datetime(2026, 1, 2, 12, tzinfo=timezone.utc)),
            tenant.id,
            db,
        )
        assert detail.performance.economic_result == Decimal("-1000.00")

        detail = add_collateral_recovery(
            loan.id,
            CollateralRecoveryCreate(
                amount=Decimal("1100.00"),
                occurred_at=datetime(2026, 1, 3, 12, tzinfo=timezone.utc),
            ),
            tenant.id,
            db,
        )
        assert detail.performance.collateral_recovered == Decimal("1100.00")
        assert detail.performance.economic_result == Decimal("100.00")
        assert detail.performance.economic_outcome == "earnings"
    finally:
        db.close()


def test_closed_performance_can_be_corrected_but_not_cross_tenants() -> None:
    db, tenant, loan = make_loan()
    try:
        write_off_loan(
            loan.id,
            LoanWriteOffCreate(closed_at=datetime(2026, 1, 2, 12, tzinfo=timezone.utc)),
            tenant.id,
            db,
        )
        detail = update_loan_performance(
            loan.id,
            LoanPerformanceUpdate(late_payment_count=4, notes="Corrected from paper records"),
            tenant.id,
            db,
        )
        assert detail.performance.late_payment_count == 4
        assert detail.performance.notes == "Corrected from paper records"

        other = Tenant(name="Other")
        db.add(other)
        db.commit()
        with pytest.raises(HTTPException) as error:
            get_loan_detail(loan.id, other.id, db)
        assert error.value.status_code == 404
    finally:
        db.close()
