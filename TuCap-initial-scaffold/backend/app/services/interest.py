import calendar
from datetime import date
from decimal import Decimal, ROUND_HALF_UP


MONEY = Decimal("0.01")
PERCENT = Decimal("100")


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def add_month(value: date) -> date:
    year = value.year + (1 if value.month == 12 else 0)
    month = 1 if value.month == 12 else value.month + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def calculate_monthly_interest(principal: Decimal, monthly_rate_percent: Decimal) -> Decimal:
    """Simple monthly interest. Accrued interest is never included in the basis."""
    if principal < 0 or monthly_rate_percent < 0:
        raise ValueError("Principal and interest rate cannot be negative")
    return money(principal * monthly_rate_percent / PERCENT)


def suggested_payment_allocation(
    amount_received: Decimal,
    accrued_interest: Decimal,
    principal_outstanding: Decimal,
) -> tuple[Decimal, Decimal, Decimal]:
    """Allocate interest first, then principal, retaining any true excess as unapplied."""
    if any(value < 0 for value in (amount_received, accrued_interest, principal_outstanding)):
        raise ValueError("Payment values cannot be negative")

    to_interest = min(amount_received, accrued_interest)
    remaining = amount_received - to_interest
    to_principal = min(remaining, principal_outstanding)
    unapplied = remaining - to_principal
    return money(to_interest), money(to_principal), money(unapplied)

