from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas import PaymentCreate


def test_payment_allocation_must_equal_amount_received() -> None:
    with pytest.raises(ValidationError):
        PaymentCreate(
            amount_received=Decimal("100.00"),
            amount_to_interest=Decimal("25.00"),
            amount_to_principal=Decimal("50.00"),
            received_at=datetime.now(timezone.utc),
        )


def test_exact_payment_allocation_is_accepted() -> None:
    payment = PaymentCreate(
        amount_received=Decimal("100.00"),
        amount_to_interest=Decimal("25.00"),
        amount_to_principal=Decimal("75.00"),
        received_at=datetime.now(timezone.utc),
    )
    assert payment.amount_to_interest + payment.amount_to_principal == payment.amount_received

