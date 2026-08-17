from datetime import date, datetime, timezone
from decimal import Decimal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

from .models import BorrowerStatus, LoanStatus


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
    next_interest_date: date | None = Field(
        default=None,
        validation_alias=AliasChoices("next_interest_date", "first_interest_date"),
    )
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


class HealthResponse(BaseModel):
    status: str
    service: str


class CapitalDepositCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    notes: str | None = None


class CapitalEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    amount: Decimal
    occurred_at: datetime
    notes: str | None
    created_at: datetime


class CapitalSummary(BaseModel):
    capital_on_hand: Decimal
    principal_receivable: Decimal
    accrued_interest_receivable: Decimal
    active_loans: int
    collected_this_month: Decimal
