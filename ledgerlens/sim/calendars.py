"""Business-day calendars for settlement payouts, from the `holidays` library (no network).

The calendar follows the settlement currency: EUR uses the TARGET calendar
(`european_central_bank`), BRL the B3 exchange calendar (`brasil_bolsa_balcao`), USD the United
States federal holidays. Any other currency skips weekends only.
"""

from __future__ import annotations

from datetime import date, timedelta
from functools import cache

import holidays
from holidays.financial import BrasilBolsaBalcao, EuropeanCentralBank

_CALENDARS = {
    "EUR": ("TARGET", EuropeanCentralBank),
    "BRL": ("B3", BrasilBolsaBalcao),
    "USD": ("US", holidays.US),
}


@cache
def calendar_for(currency: str) -> holidays.HolidayBase | None:
    """The holiday calendar used for `currency`, or None when only weekends are skipped."""
    entry = _CALENDARS.get(currency.upper())
    return entry[1]() if entry else None


def calendar_name(currency: str) -> str:
    entry = _CALENDARS.get(currency.upper())
    return entry[0] if entry else "weekends"


def is_business_day(day: date, currency: str) -> bool:
    if day.weekday() >= 5:
        return False
    calendar = calendar_for(currency)
    return calendar is None or day not in calendar


def add_business_days(day: date, count: int, currency: str) -> date:
    """`count` business days after `day`. `day` itself is not counted, even when it is a business day."""
    if count < 0:
        raise ValueError("count must not be negative")
    current = day
    remaining = count
    while remaining:
        current += timedelta(days=1)
        if is_business_day(current, currency):
            remaining -= 1
    return current


def payout_date(period_end: date, currency: str, business_days: int = 2) -> date:
    """Payout date of a settlement: `business_days` business days after the period end."""
    return add_business_days(period_end, business_days, currency)
