from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Borrower, CapitalLedgerEntry, LedgerEntryType, Loan, Tenant
from app.routers.capital import capital_balance, withdraw_capital
from app.routers.loans import get_loan_detail
from app.schemas import CapitalWithdrawalCreate, PaymentCreate
from app.services.interest import add_month
from app.services.loans import post_initial_interest, record_payment


def make_database() -> tuple[Session, Tenant, Borrower, Loan]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    tenant = Tenant(name="Test tenant")
    db.add(tenant)
    db.flush()
    borrower = Borrower(tenant_id=tenant.id, full_name="Test borrower")
    db.add(borrower)
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
    return db, tenant, borrower, loan


def test_loan_detail_returns_payment_and_interest_history() -> None:
    db, tenant, _, loan = make_database()
    try:
        record_payment(
            db,
            loan,
            PaymentCreate(
                amount_received=Decimal("18.00"),
                amount_to_interest=Decimal("8.00"),
                amount_to_principal=Decimal("10.00"),
                received_at=datetime(2026, 8, 18, 12, tzinfo=timezone.utc),
                notes="First payment",
            ),
        )
        db.commit()

        detail = get_loan_detail(loan.id, tenant.id, db)

        assert detail.total_collected == Decimal("18.00")
        assert detail.total_interest_collected == Decimal("8.00")
        assert detail.total_principal_collected == Decimal("10.00")
        assert len(detail.payments) == 1
        assert detail.payments[0].notes == "First payment"
        assert len(detail.interest_accruals) == 1
        assert detail.interest_accruals[0].amount == Decimal("8.00")
    finally:
        db.close()


def test_loan_detail_cannot_cross_tenant_boundary() -> None:
    db, _, _, loan = make_database()
    try:
        other = Tenant(name="Other tenant")
        db.add(other)
        db.commit()
        with pytest.raises(HTTPException) as error:
            get_loan_detail(loan.id, other.id, db)
        assert error.value.status_code == 404
    finally:
        db.close()


def test_withdrawal_reduces_only_tenant_capital() -> None:
    db, tenant, _, _ = make_database()
    try:
        other = Tenant(name="Other tenant")
        db.add(other)
        db.flush()
        db.add_all(
            [
                CapitalLedgerEntry(
                    tenant_id=tenant.id,
                    entry_type=LedgerEntryType.capital_deposit,
                    amount=Decimal("500.00"),
                    occurred_at=datetime(2026, 8, 17, 12, tzinfo=timezone.utc),
                ),
                CapitalLedgerEntry(
                    tenant_id=other.id,
                    entry_type=LedgerEntryType.capital_deposit,
                    amount=Decimal("1000.00"),
                    occurred_at=datetime(2026, 8, 17, 12, tzinfo=timezone.utc),
                ),
            ]
        )
        db.commit()

        entry = withdraw_capital(
            CapitalWithdrawalCreate(
                amount=Decimal("120.00"),
                occurred_at=datetime(2026, 8, 18, 12, tzinfo=timezone.utc),
                notes="Personal use",
            ),
            tenant.id,
            db,
        )

        assert entry.amount == Decimal("-120.00")
        assert entry.notes == "Personal use"
        assert capital_balance(db, tenant.id) == Decimal("380.00")
        assert capital_balance(db, other.id) == Decimal("1000.00")
    finally:
        db.close()


def test_withdrawal_cannot_exceed_available_capital() -> None:
    db, tenant, _, _ = make_database()
    try:
        db.add(
            CapitalLedgerEntry(
                tenant_id=tenant.id,
                entry_type=LedgerEntryType.capital_deposit,
                amount=Decimal("25.00"),
                occurred_at=datetime(2026, 8, 17, 12, tzinfo=timezone.utc),
            )
        )
        db.commit()

        with pytest.raises(HTTPException) as error:
            withdraw_capital(
                CapitalWithdrawalCreate(amount=Decimal("25.01")),
                tenant.id,
                db,
            )
        assert error.value.status_code == 422
        assert capital_balance(db, tenant.id) == Decimal("25.00")
    finally:
        db.close()
