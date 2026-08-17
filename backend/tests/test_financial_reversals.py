from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Borrower, CapitalLedgerEntry, FinancialReversal, Loan, Tenant, User
from app.routers.capital import add_capital, capital_balance, list_capital_entries, reverse_capital_entry
from app.routers.loans import get_loan_detail, reverse_payment
from app.schemas import CapitalDepositCreate, PaymentCreate, ReversalCreate
from app.services.interest import add_month
from app.services.loans import accrue_due_interest, post_initial_interest, record_payment


def make_database() -> tuple[Session, Tenant, User, Loan]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    tenant = Tenant(name="Audit tenant")
    db.add(tenant)
    db.flush()
    user = User(
        tenant_id=tenant.id,
        email="audit@example.com",
        email_normalized="audit@example.com",
        full_name="Auditor",
        password_hash="not-used-in-unit-test",
    )
    borrower = Borrower(tenant_id=tenant.id, full_name="Borrower")
    db.add_all([user, borrower])
    db.flush()
    loan = Loan(
        tenant_id=tenant.id,
        borrower_id=borrower.id,
        original_principal=Decimal("100.00"),
        principal_outstanding=Decimal("100.00"),
        monthly_interest_rate=Decimal("8.00"),
        start_date=date(2026, 8, 17),
        next_interest_date=add_month(date(2026, 8, 17)),
    )
    db.add(loan)
    db.flush()
    post_initial_interest(db, loan)
    db.commit()
    return db, tenant, user, loan


def reversal_payload(reason: str = "Duplicate entry") -> ReversalCreate:
    return ReversalCreate(reason=reason, reversed_at=datetime(2026, 8, 19, 12, tzinfo=timezone.utc))


def test_payment_reversal_restores_balances_and_preserves_audit_history() -> None:
    db, tenant, user, loan = make_database()
    try:
        payment = record_payment(
            db,
            loan,
            PaymentCreate(
                amount_received=Decimal("18.00"),
                amount_to_interest=Decimal("8.00"),
                amount_to_principal=Decimal("10.00"),
                received_at=datetime(2026, 8, 18, 12, tzinfo=timezone.utc),
            ),
        )
        db.commit()

        detail = reverse_payment(loan.id, payment.id, reversal_payload(), tenant.id, user, db)

        assert detail.principal_outstanding == Decimal("100.00")
        assert detail.accrued_interest == Decimal("8.00")
        assert detail.total_collected == Decimal("0.00")
        assert detail.payments[0].reversal_reason == "Duplicate entry"
        assert detail.payments[0].reversed_at is not None
        assert capital_balance(db, tenant.id) == Decimal("0.00")
        assert db.scalar(select(FinancialReversal).where(FinancialReversal.payment_id == payment.id)) is not None

        with pytest.raises(HTTPException) as error:
            reverse_payment(loan.id, payment.id, reversal_payload(), tenant.id, user, db)
        assert error.value.status_code == 422
    finally:
        db.close()


def test_reversing_payoff_reopens_loan_and_allows_corrected_payoff() -> None:
    db, tenant, user, loan = make_database()
    try:
        first_payoff = record_payment(
            db,
            loan,
            PaymentCreate(
                amount_received=Decimal("108.00"),
                amount_to_interest=Decimal("8.00"),
                amount_to_principal=Decimal("100.00"),
                received_at=datetime(2026, 8, 18, 12, tzinfo=timezone.utc),
            ),
        )
        db.commit()
        assert loan.status.value == "paid"

        reverse_payment(loan.id, first_payoff.id, reversal_payload("Wrong allocation"), tenant.id, user, db)
        assert loan.status.value == "active"
        assert loan.closed_at is None

        record_payment(
            db,
            loan,
            PaymentCreate(
                amount_received=Decimal("108.00"),
                amount_to_interest=Decimal("8.00"),
                amount_to_principal=Decimal("100.00"),
                received_at=datetime(2026, 8, 19, 13, tzinfo=timezone.utc),
            ),
        )
        db.commit()
        detail = get_loan_detail(loan.id, tenant.id, db)
        assert detail.status.value == "paid"
        assert detail.total_collected == Decimal("108.00")
    finally:
        db.close()


def test_payment_reversal_is_blocked_after_later_interest_cycle() -> None:
    db, tenant, user, loan = make_database()
    try:
        payment = record_payment(
            db,
            loan,
            PaymentCreate(
                amount_received=Decimal("18.00"),
                amount_to_interest=Decimal("8.00"),
                amount_to_principal=Decimal("10.00"),
                received_at=datetime(2026, 8, 18, 12, tzinfo=timezone.utc),
            ),
        )
        accrue_due_interest(db, loan, date(2026, 9, 17))
        db.commit()

        with pytest.raises(HTTPException) as error:
            reverse_payment(loan.id, payment.id, reversal_payload(), tenant.id, user, db)
        assert error.value.status_code == 422
        assert "ciclo de interés posterior" in error.value.detail
    finally:
        db.close()


def test_capital_reversal_posts_counterentry_and_marks_original() -> None:
    db, tenant, user, _ = make_database()
    try:
        entry = add_capital(
            CapitalDepositCreate(
                amount=Decimal("500.00"),
                occurred_at=datetime(2026, 8, 18, 12, tzinfo=timezone.utc),
            ),
            tenant.id,
            db,
        )
        assert capital_balance(db, tenant.id) == Decimal("500.00")

        reversed_entry = reverse_capital_entry(entry.id, reversal_payload("Amount entered twice"), tenant.id, user, db)
        assert reversed_entry.reversed_at is not None
        assert reversed_entry.reversible is False
        assert capital_balance(db, tenant.id) == Decimal("0.00")
        entries = list_capital_entries(tenant.id, db)
        assert len(entries) == 2
        assert any(row.entry_type.value == "adjustment" for row in entries)
        adjustment = db.scalar(
            select(CapitalLedgerEntry).where(CapitalLedgerEntry.amount == Decimal("-500.00"))
        )
        assert adjustment is not None
    finally:
        db.close()
