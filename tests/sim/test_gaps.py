"""Gap rules: cross-currency refunds with a markup, settlement arithmetic, fees and payout dates.

All money math is `Decimal` with round-half-even.
"""

from __future__ import annotations

import random
from datetime import date, datetime
from decimal import Decimal

import pytest

from ledgerlens.sim import gaps
from ledgerlens.sim.calendars import add_business_days, is_business_day, payout_date


def test_markup_plan_refund_uses_the_refund_date_rate_times_one_minus_markup():
    reference = Decimal("5.6339")  # ECB, EUR to BRL on 2026-10-20

    refund = gaps.cross_currency_refund(10000, "EUR", "BRL", reference, Decimal("2.5"))

    assert refund.applied_rate == Decimal("5.4931")  # 5.6339 x 0.975 = 5.4930525
    assert refund.payout_minor == 54931  # BRL 549.31
    assert refund.reference_rate == reference
    assert refund.markup_pct == Decimal("2.5")


def test_standard_plan_refund_uses_the_reference_rate_untouched():
    refund = gaps.cross_currency_refund(10000, "EUR", "BRL", Decimal("5.6339"), Decimal("0"))
    assert refund.applied_rate == Decimal("5.6339")
    assert refund.payout_minor == 56339


@pytest.mark.parametrize(
    ("reference", "expected"),
    [
        (Decimal("2.00005"), Decimal("2.0000")),  # tie goes to the even digit, not up
        (Decimal("2.00015"), Decimal("2.0002")),
        (Decimal("2.00025"), Decimal("2.0002")),
        (Decimal("2.00035"), Decimal("2.0004")),
    ],
)
def test_the_applied_rate_rounds_half_even_to_four_decimals(reference, expected):
    assert gaps.refund_applied_rate(reference, Decimal("0")) == expected


@pytest.mark.parametrize(("minor", "rate", "expected"), [(1, "0.5", 0), (3, "0.5", 2), (5, "0.5", 2), (7, "0.5", 4)])
def test_converted_minor_units_round_half_even(minor, rate, expected):
    assert gaps.convert_minor(minor, Decimal(rate), "EUR", "BRL") == expected


def test_conversion_respects_currencies_without_minor_units():
    # JPY has no minor unit: 1000 EUR cents (EUR 10.00) at 160 yen per euro is 1600 yen, not 160000.
    assert gaps.convert_minor(1000, Decimal("160"), "EUR", "JPY") == 1600
    assert gaps.convert_minor(1600, Decimal("0.00625"), "JPY", "EUR") == 1000


def test_markup_is_never_negative_or_above_the_policy_ceiling():
    with pytest.raises(ValueError):
        gaps.refund_applied_rate(Decimal("5"), Decimal("-1"))
    with pytest.raises(ValueError):
        gaps.refund_applied_rate(Decimal("5"), Decimal("3.5"))


def test_settlement_net_is_gross_minus_refunds_minus_fees():
    result = gaps.settlement_amounts(gross_minor=1_000_000, refunds_minor=12_345, chargebacks_opened=2)

    assert result.fees_minor == 29_000 + 2 * 1_500  # 2.9 percent of gross plus 15.00 per chargeback
    assert result.net_minor == result.gross_minor - result.refunds_minor - result.fees_minor == 955_655


@pytest.mark.parametrize(
    ("gross", "fee"),
    [(500, 14), (1500, 44), (2500, 72), (0, 0), (100_000, 2_900)],  # 14.5 -> 14, 43.5 -> 44, 72.5 -> 72
)
def test_the_percentage_fee_rounds_half_even(gross, fee):
    assert gaps.settlement_amounts(gross, 0, 0).fees_minor == fee


@pytest.mark.parametrize("seed", range(5))
def test_net_identity_holds_for_random_periods(seed):
    rng = random.Random(seed)
    for _ in range(50):
        gross, refunds, chargebacks = rng.randrange(0, 5_000_000), rng.randrange(0, 400_000), rng.randrange(0, 6)
        result = gaps.settlement_amounts(gross, refunds, chargebacks)
        assert result.net_minor == gross - refunds - result.fees_minor
        assert (
            result.fees_minor
            == int((Decimal(gross) * Decimal("0.029")).quantize(Decimal(1), "ROUND_HALF_EVEN")) + 1500 * chargebacks
        )


def test_the_b3_holiday_case_pays_on_the_14th():
    # Period ends Sunday 2026-10-11. Monday 2026-10-12 is a B3 holiday (Our Lady of Aparecida).
    assert payout_date(date(2026, 10, 11), "BRL") == date(2026, 10, 14)


def test_the_same_period_follows_each_currency_calendar():
    end = date(2026, 10, 11)
    assert payout_date(end, "EUR") == date(2026, 10, 13)  # TARGET is open on 2026-10-12
    assert payout_date(end, "USD") == date(2026, 10, 14)  # Columbus Day
    assert payout_date(end, "GBP") == date(2026, 10, 13)  # no calendar: weekends only


def test_target_holidays_skip_easter_monday():
    assert payout_date(date(2026, 4, 5), "EUR") == date(2026, 4, 8)  # Mon 6 April is a TARGET holiday
    assert payout_date(date(2026, 4, 5), "BRL") == date(2026, 4, 7)


def test_business_day_helpers():
    assert not is_business_day(date(2026, 11, 7), "EUR")  # Saturday
    assert is_business_day(date(2026, 11, 6), "EUR")
    assert add_business_days(date(2026, 11, 6), 1, "EUR") == date(2026, 11, 9)
    assert add_business_days(date(2026, 11, 6), 0, "EUR") == date(2026, 11, 6)


def test_weekly_periods_run_monday_to_sunday():
    assert gaps.period_bounds(date(2026, 10, 7)) == (date(2026, 10, 5), date(2026, 10, 11))
    assert gaps.period_bounds(date(2026, 10, 11)) == (date(2026, 10, 5), date(2026, 10, 11))
    assert gaps.period_bounds(date(2026, 10, 5)) == (date(2026, 10, 5), date(2026, 10, 11))


def test_chargeback_draws_follow_the_reason_mix_and_rate_range():
    rng = random.Random("42:chargebacks")
    reasons = [gaps.draw_reason(rng) for _ in range(4000)]
    share = {code: reasons.count(code) / len(reasons) for code in set(reasons)}
    assert set(share) == {"FRD", "DUP", "NRC", "NAD", "OTH"}
    assert share["FRD"] == pytest.approx(0.40, abs=0.04)
    assert share["NRC"] == pytest.approx(0.25, abs=0.04)
    assert share["OTH"] == pytest.approx(0.05, abs=0.02)
    rates = [gaps.draw_chargeback_rate(rng) for _ in range(200)]
    assert min(rates) >= Decimal("0.1") and max(rates) <= Decimal("1.2")


def test_chargeback_timeline_opens_late_has_a_short_deadline_and_stops_at_the_as_of_date():
    rng = random.Random("1:chargebacks")
    captured = datetime(2026, 8, 1, 10, 0)
    end = datetime(2026, 11, 7, 23, 59)
    saw_resolved = False
    for _ in range(200):
        plan = gaps.plan_chargeback(rng, captured, end)
        assert plan is not None
        assert 10 <= (plan.opened_at - captured).days <= 60
        assert 10 <= (plan.deadline - plan.opened_at.date()).days <= 14
        stages = [stage for stage, _ in plan.steps]
        times = [when for _, when in plan.steps]
        assert stages[0] == "opened" and stages[1] == "evidence_requested"
        assert times == sorted(times) and times[-1] <= end
        assert not set(stages[:-1]) & {"won", "lost"}, "nothing happens after the case is closed"
        if stages[-1] in {"won", "lost"}:
            saw_resolved = True
            assert stages[-1] == plan.outcome
            assert times[-1].date() > plan.deadline
    assert saw_resolved
    assert saw_resolved


def test_a_chargeback_that_would_open_after_the_as_of_date_is_not_planned():
    rng = random.Random("3:chargebacks")
    assert gaps.plan_chargeback(rng, datetime(2026, 11, 5, 9), datetime(2026, 11, 7, 23)) is None


def test_chargeback_outcome_mix_is_about_35_percent_won():
    rng = random.Random("7:chargebacks")
    plans = [gaps.plan_chargeback(rng, datetime(2026, 1, 5, 9), datetime(2026, 11, 7, 23)) for _ in range(3000)]
    won = sum(1 for plan in plans if plan and plan.outcome == "won")
    assert won / len(plans) == pytest.approx(0.35, abs=0.04)
