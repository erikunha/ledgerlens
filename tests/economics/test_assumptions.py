"""The assumptions of an economics run: the numbers the repository cannot measure.

What they guarantee, and why: (a) the minutes of a review and the rate of an hour are fields of the assumptions and
not constants of the code, so a reader of a result can change them and see what changes; (b) every result that uses an
assumption carries it, so a number is never read without the assumption that produced it; (c) every assumption names
where it comes from, because an assumption with no source is a guess with a name; (d) the money of an assumption is a
`Decimal`, and never a float.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ledgerlens.economics.assumptions import (
    UNKNOWN_SOURCE,
    Assumptions,
    PriceSnapshot,
    ReviewAssumption,
)


def test_the_minutes_of_a_review_are_a_field_and_not_a_constant_of_the_code() -> None:
    """The minutes a review takes is an assumption the reader sets, and not a number the code decided.

    Why it matters: the cost of a review is the biggest number of the utility of a decision, and a number that
    the code decided cannot be questioned by the person who reads the result.
    """
    assumptions = Assumptions(review=ReviewAssumption(minutes=Decimal("12.5")))

    assert assumptions.review.minutes == Decimal("12.5")
    assert assumptions.review.minutes != Decimal("0")


def test_the_rate_of_an_hour_is_a_field_and_not_a_constant_of_the_code() -> None:
    """The rate of an hour is an assumption the reader sets."""
    assumptions = Assumptions(review=ReviewAssumption(minutes=Decimal("10"), hourly_rate_usd=Decimal("42.00")))

    assert assumptions.review.hourly_rate_usd == Decimal("42.00")


def test_the_cost_of_a_review_is_the_rate_of_an_hour_times_the_minutes() -> None:
    """The money of a review is the rate of an hour times the minutes, and it is exact.

    Why it matters: the cost of the review enters the expected loss of a policy, and a loss computed in floating
    point is a loss that nobody can check.
    """
    review = ReviewAssumption(minutes=Decimal("15"), hourly_rate_usd=Decimal("60.00"))

    assert review.cost_usd == Decimal("15.00")


def test_every_assumption_names_where_it_comes_from() -> None:
    """An assumption with no source is a guess with a name, and the module refuses to build one.

    Why it matters: a reader of a result has to know which number is a fact of the repository and which one the
    reader supplied.
    """
    with pytest.raises(ValueError, match="source"):
        ReviewAssumption(minutes=Decimal("5"), source="")


def test_an_assumption_with_no_source_is_the_unknown_source() -> None:
    """The absence of a source is said in words, and it is never a source that says nothing."""
    review = ReviewAssumption(minutes=Decimal("5"))

    assert review.source == UNKNOWN_SOURCE


def test_every_assumption_carries_the_date_it_was_stated() -> None:
    """An assumption names the day it was stated, because the same number of another day is another number."""
    review = ReviewAssumption(minutes=Decimal("5"), stated_on=date(2026, 11, 24))

    assert review.stated_on == date(2026, 11, 24)


def test_a_price_snapshot_carries_the_source_and_the_day_of_the_price() -> None:
    """A price carries where it comes from and the day it was last checked.

    Why it matters: the price of a model is the number that decides whether a money is known, and a price with no
    day is a price that nobody checked.
    """
    snapshot = PriceSnapshot(
        source="manual",
        last_verified=date(2026, 11, 8),
        input_per_1m_usd=Decimal("0.40"),
        output_per_1m_usd=Decimal("1.60"),
    )

    assert snapshot.is_verified
    assert snapshot.last_verified == date(2026, 11, 8)


def test_a_price_that_was_never_verified_is_not_a_verified_price() -> None:
    """A price with no source, no day or no amount is not a price, and it never becomes one by being carried."""
    snapshot = PriceSnapshot(
        source=UNKNOWN_SOURCE,
        last_verified=None,
        input_per_1m_usd=None,
        output_per_1m_usd=None,
    )

    assert not snapshot.is_verified


def test_the_assumptions_of_a_result_travel_with_it() -> None:
    """A result that uses an assumption carries it, so the number is never read without it."""
    assumptions = Assumptions(review=ReviewAssumption(minutes=Decimal("7.5")))

    carried = assumptions.to_dict()

    assert carried["review"]["minutes"] == "7.5"
    assert carried["review"]["source"] == UNKNOWN_SOURCE


def test_the_money_of_an_assumption_is_never_a_float() -> None:
    """The rate of an hour is a `Decimal`, and a float is refused."""
    with pytest.raises(ValueError, match="Decimal"):
        ReviewAssumption(minutes=Decimal("5"), hourly_rate_usd=0.5)  # type: ignore[arg-type]
