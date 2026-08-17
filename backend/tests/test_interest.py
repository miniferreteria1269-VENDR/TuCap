from decimal import Decimal

import pytest

from app.services.interest import calculate_monthly_interest, suggested_payment_allocation


def test_simple_interest_does_not_include_accrued_interest() -> None:
    assert calculate_monthly_interest(Decimal("1000"), Decimal("5")) == Decimal("50.00")


def test_payment_suggestion_pays_interest_then_principal() -> None:
    result = suggested_payment_allocation(
        Decimal("140"), Decimal("50"), Decimal("1000")
    )
    assert result == (Decimal("50.00"), Decimal("90.00"), Decimal("0.00"))


def test_payment_suggestion_stops_at_balances() -> None:
    result = suggested_payment_allocation(
        Decimal("1200"), Decimal("50"), Decimal("1000")
    )
    assert result == (Decimal("50.00"), Decimal("1000.00"), Decimal("150.00"))


def test_negative_values_are_rejected() -> None:
    with pytest.raises(ValueError):
        calculate_monthly_interest(Decimal("-1"), Decimal("5"))

