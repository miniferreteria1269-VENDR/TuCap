import enum
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def uuid_string() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BorrowerStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    blocked = "blocked"


class LoanStatus(str, enum.Enum):
    active = "active"
    paid = "paid"
    written_off = "written_off"


class LedgerEntryType(str, enum.Enum):
    capital_deposit = "capital_deposit"
    loan_disbursement = "loan_disbursement"
    payment_interest = "payment_interest"
    payment_principal = "payment_principal"
    withdrawal = "withdrawal"
    collateral_recovery = "collateral_recovery"
    adjustment = "adjustment"


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    timezone_name: Mapped[str] = mapped_column(String(64), default="America/El_Salvador", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class TenantIdentifier(Base):
    """Stable human-facing tenant number, separate from the security-sensitive UUID."""

    __tablename__ = "tenant_identifiers"

    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), primary_key=True)
    tenant_number: Mapped[int] = mapped_column(Integer, unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (Index("ux_users_email_normalized", "email_normalized", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    email_normalized: Mapped[str] = mapped_column(String(254), nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    disclaimer_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class Borrower(Base):
    __tablename__ = "borrowers"
    __table_args__ = (Index("ix_borrowers_tenant_name", "tenant_id", "full_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(180), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(180))
    address: Mapped[str | None] = mapped_column(Text)
    government_id: Mapped[str | None] = mapped_column(String(80))
    credit_limit: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    status: Mapped[BorrowerStatus] = mapped_column(Enum(BorrowerStatus), default=BorrowerStatus.active, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    loans: Mapped[list["Loan"]] = relationship(back_populates="borrower")


class Loan(Base):
    __tablename__ = "loans"
    __table_args__ = (Index("ix_loans_tenant_status", "tenant_id", "status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    borrower_id: Mapped[str] = mapped_column(ForeignKey("borrowers.id"), index=True, nullable=False)
    original_principal: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    principal_outstanding: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    monthly_interest_rate: Mapped[Decimal] = mapped_column(Numeric(9, 4), nullable=False)
    accrued_interest: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    next_interest_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[LoanStatus] = mapped_column(Enum(LoanStatus), default=LoanStatus.active, nullable=False)
    collateral_description: Mapped[str | None] = mapped_column(Text)
    collateral_estimated_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    notes: Mapped[str | None] = mapped_column(Text)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    borrower: Mapped[Borrower] = relationship(back_populates="loans")
    interest_accruals: Mapped[list["InterestAccrual"]] = relationship(back_populates="loan")
    payments: Mapped[list["Payment"]] = relationship(back_populates="loan")


class InterestAccrual(Base):
    __tablename__ = "interest_accruals"
    __table_args__ = (
        Index("ux_interest_accrual_tenant_loan_cycle", "tenant_id", "loan_id", "cycle_date", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    loan_id: Mapped[str] = mapped_column(ForeignKey("loans.id"), index=True, nullable=False)
    cycle_date: Mapped[date] = mapped_column(Date, nullable=False)
    principal_basis: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    monthly_rate: Mapped[Decimal] = mapped_column(Numeric(9, 4), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    loan: Mapped[Loan] = relationship(back_populates="interest_accruals")


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (Index("ix_payments_tenant_received", "tenant_id", "received_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    loan_id: Mapped[str] = mapped_column(ForeignKey("loans.id"), index=True, nullable=False)
    amount_received: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    amount_to_interest: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    amount_to_principal: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    unapplied_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    loan: Mapped[Loan] = relationship(back_populates="payments")


class CapitalLedgerEntry(Base):
    __tablename__ = "capital_ledger_entries"
    __table_args__ = (Index("ix_ledger_tenant_occurred", "tenant_id", "occurred_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    entry_type: Mapped[LedgerEntryType] = mapped_column(Enum(LedgerEntryType), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    loan_id: Mapped[str | None] = mapped_column(ForeignKey("loans.id"), index=True)
    payment_id: Mapped[str | None] = mapped_column(ForeignKey("payments.id"), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
