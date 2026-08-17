from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Borrower, Loan, Tenant, User
from app.routers.borrowers import get_borrower_performance
from app.routers.loans import reverse_payment, write_off_loan
from app.schemas import LoanWriteOffCreate, PaymentCreate, ReversalCreate
from app.services.interest import add_month
from app.services.loans import post_initial_interest, record_payment


def make_database() -> tuple[Session, Tenant, Borrower, User]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    tenant = Tenant(name="Performance tenant")
    db.add(tenant)
    db.flush()
    borrower = Borrower(tenant_id=tenant.id, full_name="Repeat borrower")
    user = User(
        tenant_id=tenant.id,
        email="owner@example.com",
        email_normalized="owner@example.com",
        full_name="Owner",
        password_hash="unused-in-unit-test",
    )
    db.add_all([borrower, user])
    db.commit()
    return db, tenant, borrower, user


def add_loan(
    db: Session,
    tenant: Tenant,
    borrower: Borrower,
    principal: str,
    rate: str,
    start: date = date(2026, 1, 1),
) -> Loan:
    loan = Loan(
        tenant_id=tenant.id,
        borrower_id=borrower.id,
        original_principal=Decimal(principal),
        principal_outstanding=Decimal(principal),
        monthly_interest_rate=Decimal(rate),
        start_date=start,
        next_interest_date=add_month(start),
    )
    db.add(loan)
    db.flush()
    post_initial_interest(db, loan)
    db.commit()
    return loan


def test_borrower_performance_separates_closed_results_from_active_exposure() -> None:
    db, tenant, borrower, _ = make_database()
    try:
        paid = add_loan(db, tenant, borrower, "100.00", "8.00")
        record_payment(
            db,
            paid,
            PaymentCreate(
                amount_received=Decimal("108.00"),
                amount_to_interest=Decimal("8.00"),
                amount_to_principal=Decimal("100.00"),
                received_at=datetime(2026, 1, 2, 12, tzinfo=timezone.utc),
            ),
        )
        db.commit()

        written_off = add_loan(db, tenant, borrower, "100.00", "8.00")
        record_payment(
            db,
            written_off,
            PaymentCreate(
                amount_received=Decimal("58.00"),
                amount_to_interest=Decimal("8.00"),
                amount_to_principal=Decimal("50.00"),
                received_at=datetime(2026, 1, 2, 12, tzinfo=timezone.utc),
            ),
        )
        db.commit()
        write_off_loan(
            written_off.id,
            LoanWriteOffCreate(
                closed_at=datetime(2026, 1, 4, 12, tzinfo=timezone.utc),
                collateral_recovery_amount=Decimal("20.00"),
                late_payment_count=2,
            ),
            tenant.id,
            db,
        )

        add_loan(db, tenant, borrower, "50.00", "10.00")
        performance = get_borrower_performance(borrower.id, tenant.id, db)

        assert performance.total_loans == 3
        assert performance.active_loans == 1
        assert performance.paid_loans == 1
        assert performance.written_off_loans == 1
        assert performance.total_principal_lent == Decimal("250.00")
        assert performance.active_principal_exposure == Decimal("50.00")
        assert performance.active_interest_receivable == Decimal("5.00")
        assert performance.total_principal_collected == Decimal("150.00")
        assert performance.total_interest_collected == Decimal("16.00")
        assert performance.collateral_recovered == Decimal("20.00")
        assert performance.total_recovered == Decimal("186.00")
        assert performance.closed_principal_lent == Decimal("200.00")
        assert performance.closed_total_recovered == Decimal("186.00")
        assert performance.closed_economic_result == Decimal("-14.00")
        assert performance.economic_outcome == "loss"
        assert performance.completion_rate == Decimal("50.00")
        assert performance.late_payment_count == 2
        assert performance.average_closed_duration_days == 2
        assert performance.average_monthly_result == Decimal("-7.00")
    finally:
        db.close()


def test_reversed_payment_is_excluded_from_borrower_history() -> None:
    db, tenant, borrower, user = make_database()
    try:
        loan = add_loan(db, tenant, borrower, "100.00", "8.00")
        payment = record_payment(
            db,
            loan,
            PaymentCreate(
                amount_received=Decimal("18.00"),
                amount_to_interest=Decimal("8.00"),
                amount_to_principal=Decimal("10.00"),
                received_at=datetime(2026, 1, 2, 12, tzinfo=timezone.utc),
            ),
        )
        db.commit()
        reverse_payment(
            loan.id,
            payment.id,
            ReversalCreate(
                reason="Duplicate payment",
                reversed_at=datetime(2026, 1, 2, 13, tzinfo=timezone.utc),
            ),
            tenant.id,
            user,
            db,
        )

        performance = get_borrower_performance(borrower.id, tenant.id, db)
        assert performance.total_recovered == Decimal("0.00")
        assert performance.total_principal_collected == Decimal("0.00")
        assert performance.total_interest_collected == Decimal("0.00")
    finally:
        db.close()


def test_empty_history_and_tenant_boundary() -> None:
    db, tenant, borrower, _ = make_database()
    try:
        performance = get_borrower_performance(borrower.id, tenant.id, db)
        assert performance.total_loans == 0
        assert performance.economic_outcome == "no_closed_loans"

        other = Tenant(name="Other tenant")
        db.add(other)
        db.commit()
        with pytest.raises(HTTPException) as error:
            get_borrower_performance(borrower.id, other.id, db)
        assert error.value.status_code == 404
    finally:
        db.close()
