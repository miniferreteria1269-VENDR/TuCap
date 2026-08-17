from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Borrower, Loan, Tenant, User
from app.routers.capital import (
    add_capital,
    get_capital_period_report,
    reverse_capital_entry,
    withdraw_capital,
)
from app.routers.loans import write_off_loan
from app.schemas import (
    CapitalDepositCreate,
    CapitalWithdrawalCreate,
    LoanWriteOffCreate,
    PaymentCreate,
    ReversalCreate,
)
from app.services.interest import add_month
from app.services.loans import post_initial_interest, record_payment


def make_database() -> tuple[Session, Tenant, Borrower, User]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    tenant = Tenant(name="Reporting tenant")
    db.add(tenant)
    db.flush()
    borrower = Borrower(tenant_id=tenant.id, full_name="Borrower")
    user = User(
        tenant_id=tenant.id,
        email="report@example.com",
        email_normalized="report@example.com",
        full_name="Reporter",
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
    start: date,
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


def test_period_report_separates_activity_and_closed_results() -> None:
    db, tenant, borrower, user = make_database()
    try:
        add_capital(
            CapitalDepositCreate(
                amount=Decimal("500.00"),
                occurred_at=datetime(2026, 1, 1, 12, tzinfo=timezone.utc),
            ),
            tenant.id,
            db,
        )
        duplicate_deposit = add_capital(
            CapitalDepositCreate(
                amount=Decimal("25.00"),
                occurred_at=datetime(2026, 1, 2, 12, tzinfo=timezone.utc),
            ),
            tenant.id,
            db,
        )
        reverse_capital_entry(
            duplicate_deposit.id,
            ReversalCreate(
                reason="Duplicate deposit",
                reversed_at=datetime(2026, 1, 2, 13, tzinfo=timezone.utc),
            ),
            tenant.id,
            user,
            db,
        )
        withdraw_capital(
            CapitalWithdrawalCreate(
                amount=Decimal("50.00"),
                occurred_at=datetime(2026, 1, 3, 12, tzinfo=timezone.utc),
            ),
            tenant.id,
            db,
        )

        paid = add_loan(db, tenant, borrower, "100.00", "8.00", date(2026, 1, 5))
        record_payment(
            db,
            paid,
            PaymentCreate(
                amount_received=Decimal("108.00"),
                amount_to_interest=Decimal("8.00"),
                amount_to_principal=Decimal("100.00"),
                received_at=datetime(2026, 1, 6, 12, tzinfo=timezone.utc),
            ),
        )
        db.commit()

        written_off = add_loan(db, tenant, borrower, "200.00", "10.00", date(2026, 1, 10))
        record_payment(
            db,
            written_off,
            PaymentCreate(
                amount_received=Decimal("70.00"),
                amount_to_interest=Decimal("20.00"),
                amount_to_principal=Decimal("50.00"),
                received_at=datetime(2026, 1, 12, 12, tzinfo=timezone.utc),
            ),
        )
        db.commit()
        write_off_loan(
            written_off.id,
            LoanWriteOffCreate(
                closed_at=datetime(2026, 1, 15, 12, tzinfo=timezone.utc),
                collateral_recovery_amount=Decimal("100.00"),
            ),
            tenant.id,
            db,
        )
        add_loan(db, tenant, borrower, "50.00", "5.00", date(2026, 1, 20))

        report = get_capital_period_report(date(2026, 1, 1), date(2026, 1, 31), tenant.id, db)

        assert report.payments_collected == Decimal("178.00")
        assert report.interest_collected == Decimal("28.00")
        assert report.principal_collected == Decimal("150.00")
        assert report.capital_lent == Decimal("350.00")
        assert report.new_loans == 3
        assert report.capital_deposited == Decimal("500.00")
        assert report.capital_withdrawn == Decimal("50.00")
        assert report.collateral_recovered == Decimal("100.00")
        assert report.loans_closed == 2
        assert report.loans_paid == 1
        assert report.loans_written_off == 1
        assert report.closed_principal_lent == Decimal("300.00")
        assert report.closed_total_recovered == Decimal("278.00")
        assert report.realized_economic_result == Decimal("-22.00")
    finally:
        db.close()


def test_period_report_is_inclusive_and_tenant_isolated() -> None:
    db, tenant, borrower, _ = make_database()
    try:
        add_loan(db, tenant, borrower, "75.00", "4.00", date(2026, 2, 28))
        other = Tenant(name="Other")
        db.add(other)
        db.flush()
        other_borrower = Borrower(tenant_id=other.id, full_name="Other borrower")
        db.add(other_borrower)
        db.flush()
        add_loan(db, other, other_borrower, "900.00", "5.00", date(2026, 2, 28))

        report = get_capital_period_report(date(2026, 2, 28), date(2026, 2, 28), tenant.id, db)
        assert report.capital_lent == Decimal("75.00")
        assert report.new_loans == 1

        with pytest.raises(HTTPException) as error:
            get_capital_period_report(date(2026, 3, 2), date(2026, 3, 1), tenant.id, db)
        assert error.value.status_code == 422
    finally:
        db.close()
