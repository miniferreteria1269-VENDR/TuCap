from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Borrower, Loan, Tenant
from app.schemas import LoanCreate, PaymentCreate
from app.services.interest import add_month
from app.services.loans import accrue_due_interest, post_initial_interest, record_payment


def test_legacy_first_interest_date_maps_to_next_interest_date() -> None:
    payload = LoanCreate(
        borrower_id="borrower-id",
        original_principal=Decimal("100.00"),
        monthly_interest_rate=Decimal("8.00"),
        start_date=date(2026, 8, 17),
        first_interest_date=date(2026, 9, 17),
    )

    assert payload.next_interest_date == date(2026, 9, 17)


def make_loan(db: Session) -> Loan:
    tenant = Tenant(name="Test tenant")
    db.add(tenant)
    db.flush()
    borrower = Borrower(tenant_id=tenant.id, full_name="Test borrower")
    db.add(borrower)
    db.flush()

    principal = Decimal("100.00")
    rate = Decimal("8.00")
    start = date(2026, 8, 17)
    loan = Loan(
        tenant_id=tenant.id,
        borrower_id=borrower.id,
        original_principal=principal,
        principal_outstanding=principal,
        monthly_interest_rate=rate,
        start_date=start,
        next_interest_date=add_month(start),
    )
    db.add(loan)
    db.flush()
    post_initial_interest(db, loan)
    db.flush()
    return loan


def test_next_day_payoff_includes_full_initial_month_interest() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        loan = make_loan(db)

        payment = record_payment(
            db,
            loan,
            PaymentCreate(
                amount_received=Decimal("108.00"),
                amount_to_interest=Decimal("8.00"),
                amount_to_principal=Decimal("100.00"),
                received_at=datetime(2026, 8, 18, 12, tzinfo=timezone.utc),
            ),
        )

        assert payment.amount_to_interest == Decimal("8.00")
        assert loan.accrued_interest == Decimal("0.00")
        assert loan.principal_outstanding == Decimal("0.00")
        assert loan.status.value == "paid"


def test_next_cycle_uses_reduced_principal_without_compounding() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        loan = make_loan(db)
        record_payment(
            db,
            loan,
            PaymentCreate(
                amount_received=Decimal("58.00"),
                amount_to_interest=Decimal("8.00"),
                amount_to_principal=Decimal("50.00"),
                received_at=datetime(2026, 8, 18, 12, tzinfo=timezone.utc),
            ),
        )

        added = accrue_due_interest(db, loan, date(2026, 9, 17))

        assert added == Decimal("4.00")
        assert loan.accrued_interest == Decimal("4.00")
        assert loan.principal_outstanding == Decimal("50.00")
