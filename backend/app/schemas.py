from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

from .models import BorrowerStatus, LedgerEntryType, LoanClosureReason, LoanStatus


class BorrowerCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=180)
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    government_id: str | None = None
    credit_limit: Decimal = Field(default=Decimal("0.00"), ge=0)
    notes: str | None = None


class BorrowerRead(BorrowerCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    status: BorrowerStatus
    created_at: datetime
    updated_at: datetime


class BorrowerSummary(BorrowerRead):
    active_loan_count: int = 0
    outstanding_principal: Decimal = Decimal("0.00")
    accrued_interest: Decimal = Decimal("0.00")


class LoanCreate(BaseModel):
    borrower_id: str
    original_principal: Decimal = Field(gt=0)
    monthly_interest_rate: Decimal = Field(ge=0)
    start_date: date
    next_interest_date: Annotated[
        date | None,
        Field(validation_alias=AliasChoices("next_interest_date", "first_interest_date")),
    ] = None
    collateral_description: str | None = None
    collateral_estimated_value: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None

    @model_validator(mode="after")
    def next_interest_must_follow_start(self) -> "LoanCreate":
        if self.next_interest_date is not None and self.next_interest_date <= self.start_date:
            raise ValueError("Next interest date must be after the loan date")
        return self


class LoanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    borrower_id: str
    original_principal: Decimal
    principal_outstanding: Decimal
    monthly_interest_rate: Decimal
    accrued_interest: Decimal
    start_date: date
    next_interest_date: date
    status: LoanStatus
    collateral_description: str | None
    collateral_estimated_value: Decimal | None
    notes: str | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PaymentCreate(BaseModel):
    amount_received: Decimal = Field(gt=0)
    amount_to_interest: Decimal = Field(ge=0)
    amount_to_principal: Decimal = Field(ge=0)
    received_at: datetime
    notes: str | None = None

    @model_validator(mode="after")
    def allocation_must_equal_received(self) -> "PaymentCreate":
        allocated = self.amount_to_interest + self.amount_to_principal
        if allocated != self.amount_received:
            raise ValueError("Interest and principal allocations must equal the amount received")
        return self


class PaymentRead(PaymentCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    loan_id: str
    unapplied_amount: Decimal
    created_at: datetime
    reversed_at: datetime | None = None
    reversal_reason: str | None = None


class PaymentPreview(BaseModel):
    accrued_interest: Decimal
    principal_outstanding: Decimal
    amount_received: Decimal
    suggested_to_interest: Decimal
    suggested_to_principal: Decimal
    unapplied_amount: Decimal


class PaymentResult(BaseModel):
    payment: PaymentRead
    loan: LoanRead


class InterestAccrualRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    cycle_date: date
    principal_basis: Decimal
    monthly_rate: Decimal
    amount: Decimal
    created_at: datetime


class LoanPerformanceRead(BaseModel):
    closure_reason: LoanClosureReason
    closed_at: datetime
    contract_fulfilled: bool
    principal_shortfall: Decimal
    interest_shortfall: Decimal
    payments_collected: Decimal
    collateral_recovered: Decimal
    total_recovered: Decimal
    economic_result: Decimal
    economic_outcome: str
    duration_days: int
    billed_months: int
    average_monthly_result: Decimal
    late_payment_count: int
    notes: str | None


class LoanDetailRead(LoanRead):
    payments: list[PaymentRead]
    interest_accruals: list[InterestAccrualRead]
    total_interest_collected: Decimal
    total_principal_collected: Decimal
    total_collected: Decimal
    performance: LoanPerformanceRead | None = None


class LoanWriteOffCreate(BaseModel):
    closed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    collateral_recovery_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    late_payment_count: int = Field(default=0, ge=0)
    notes: str | None = None


class CollateralRecoveryCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    notes: str | None = None


class LoanPerformanceUpdate(BaseModel):
    late_payment_count: int = Field(ge=0)
    notes: str | None = None


class HealthResponse(BaseModel):
    status: str
    service: str


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class AuthUserRead(BaseModel):
    id: str
    email: str
    full_name: str
    tenant_number: int
    disclaimer_accepted_at: datetime | None
    disclaimer_required: bool


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthUserRead


class DisclaimerAcceptance(BaseModel):
    accepted: bool


class CapitalDepositCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    notes: str | None = None


class CapitalWithdrawalCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    notes: str | None = None


class CapitalEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    entry_type: LedgerEntryType
    amount: Decimal
    loan_id: str | None
    occurred_at: datetime
    notes: str | None
    created_at: datetime
    reversed_at: datetime | None = None
    reversal_reason: str | None = None
    reversible: bool = False


class ReversalCreate(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
    reversed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CapitalSummary(BaseModel):
    capital_on_hand: Decimal
    principal_receivable: Decimal
    accrued_interest_receivable: Decimal
    active_loans: int
    collected_this_month: Decimal
