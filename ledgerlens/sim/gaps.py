"""Gap filler: what the public source does not have.

Pure functions and small planners for cross-currency refunds with a merchant markup, chargebacks,
settlement arithmetic and fees. Money is `Decimal` and integer minor units; every rounding is
half to even. Each planner takes a `random.Random` so a component reads its own substream.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_EVEN, Decimal

from ledgerlens.sim.calendars import payout_date

__all__ = [
    "CHARGEBACK_FIXED_FEE_MINOR",
    "PROCESSING_FEE_PCT",
    "ChargebackPlan",
    "CrossCurrencyRefund",
    "SettlementAmounts",
    "convert_minor",
    "cross_currency_refund",
    "draw_chargeback_rate",
    "draw_reason",
    "payout_date",
    "period_bounds",
    "plan_chargeback",
    "refund_applied_rate",
    "settlement_amounts",
]

FOUR_DECIMALS = Decimal("0.0001")
MAX_MARKUP_PCT = Decimal("3.0")  # policy ceiling: up to 3.0 percent over the reference rate
PROCESSING_FEE_PCT = Decimal("2.9")
CHARGEBACK_FIXED_FEE_MINOR = 1500  # 15.00 in the settlement currency, per chargeback opened in the period
REASON_MIX = (("FRD", 40), ("NRC", 25), ("NAD", 20), ("DUP", 10), ("OTH", 5))
OUTCOME_WON_SHARE = 0.35
_ZERO_EXPONENT = frozenset({"JPY", "KRW", "CLP", "ISK", "VND"})


def _exponent(currency: str) -> int:
    return 0 if currency.upper() in _ZERO_EXPONENT else 2


def convert_minor(amount_minor: int, rate: Decimal, from_currency: str, to_currency: str) -> int:
    """Convert integer minor units at `rate` (units of `to` per unit of `from`), half to even."""
    scaled = Decimal(amount_minor) * rate * Decimal(10) ** (_exponent(to_currency) - _exponent(from_currency))
    return int(scaled.quantize(Decimal(1), ROUND_HALF_EVEN))


def refund_applied_rate(reference_rate: Decimal, markup_pct: Decimal) -> Decimal:
    """Rate the merchant applies: the reference rate of the refund date times `1 - markup`, 4 decimals."""
    if markup_pct < 0 or markup_pct > MAX_MARKUP_PCT:
        raise ValueError(f"markup must be between 0 and {MAX_MARKUP_PCT} percent, got {markup_pct}")
    return (reference_rate * (Decimal(1) - markup_pct / Decimal(100))).quantize(FOUR_DECIMALS, ROUND_HALF_EVEN)


@dataclass(frozen=True)
class CrossCurrencyRefund:
    applied_rate: Decimal
    payout_minor: int
    reference_rate: Decimal
    markup_pct: Decimal


def cross_currency_refund(
    amount_minor: int, from_currency: str, to_currency: str, reference_rate: Decimal, markup_pct: Decimal
) -> CrossCurrencyRefund:
    """Refund of `amount_minor` (in `from_currency`) paid to the customer in `to_currency`."""
    applied = refund_applied_rate(reference_rate, markup_pct)
    return CrossCurrencyRefund(
        applied_rate=applied,
        payout_minor=convert_minor(amount_minor, applied, from_currency, to_currency),
        reference_rate=reference_rate,
        markup_pct=markup_pct,
    )


@dataclass(frozen=True)
class SettlementAmounts:
    gross_minor: int
    refunds_minor: int
    fees_minor: int
    net_minor: int


def settlement_amounts(
    gross_minor: int,
    refunds_minor: int,
    chargebacks_opened: int,
    *,
    fee_pct: Decimal = PROCESSING_FEE_PCT,
    fixed_fee_minor: int = CHARGEBACK_FIXED_FEE_MINOR,
) -> SettlementAmounts:
    """`fees = fee_pct of gross + fixed fee per chargeback opened`, and `net = gross - refunds - fees`."""
    percentage = int((Decimal(gross_minor) * fee_pct / Decimal(100)).quantize(Decimal(1), ROUND_HALF_EVEN))
    fees = percentage + fixed_fee_minor * chargebacks_opened
    return SettlementAmounts(gross_minor, refunds_minor, fees, gross_minor - refunds_minor - fees)


def period_bounds(day: date) -> tuple[date, date]:
    """The Monday-to-Sunday settlement week that contains `day`."""
    start = day - timedelta(days=day.weekday())
    return start, start + timedelta(days=6)


def draw_chargeback_rate(rng: random.Random) -> Decimal:
    """A merchant's chargeback rate in percent of captured transactions, 0.1 to 1.2."""
    return Decimal(rng.randrange(10, 121)) / Decimal(100)


def draw_reason(rng: random.Random) -> str:
    codes, weights = zip(*REASON_MIX, strict=True)
    return rng.choices(codes, weights)[0]


@dataclass(frozen=True)
class ChargebackPlan:
    """When a chargeback happens and how it ends. `steps` stops at the as-of date."""

    opened_at: datetime
    deadline: date
    outcome: str  # "won" or "lost": how the case ends if it runs to the end
    steps: tuple[tuple[str, datetime], ...]  # (stage, when), starting with "opened"


def plan_chargeback(rng: random.Random, captured_at: datetime, end: datetime) -> ChargebackPlan | None:
    """Plan a chargeback on a payment captured at `captured_at`, or None if it would open after `end`.

    Opened 10 to 60 days after capture, deadline 10 to 14 days after opening, evidence asked a day
    later, resolved a few days after the deadline. Won 35 percent of the time. A lost case may have
    no evidence submitted.
    """
    opened = captured_at + timedelta(days=rng.randint(10, 60), hours=rng.randint(0, 8), minutes=rng.randrange(60))
    if opened > end:
        return None
    deadline = opened.date() + timedelta(days=rng.randint(10, 14))
    outcome = "won" if rng.random() < OUTCOME_WON_SHARE else "lost"
    submitted = outcome == "won" or rng.random() < 0.7
    requested = opened + timedelta(days=1, hours=rng.randint(0, 6))
    steps: list[tuple[str, datetime]] = [("opened", opened), ("evidence_requested", requested)]
    if submitted:
        latest = datetime.combine(deadline - timedelta(days=1), requested.time())
        span = max(1, int((latest - requested).total_seconds() // 3600))
        steps.append(("evidence_submitted", requested + timedelta(hours=rng.randint(1, span))))
    resolved = datetime.combine(deadline + timedelta(days=rng.randint(3, 10)), opened.time())
    steps.append((outcome, resolved))
    return ChargebackPlan(opened, deadline, outcome, tuple(step for step in steps if step[1] <= end))
