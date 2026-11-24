"""The assumptions of an economics run: the numbers the repository cannot measure.

Why they exist: the cost of a review is the largest number of the utility of a decision, and the repository cannot
measure it: nobody timed a review of this repository, and the rate of an hour of a person is not a fact of the
code. A number that the code decided cannot be questioned by the person who reads the result, so the minutes of a
review and the rate of an hour are fields of this module and every result that uses one carries it.

Why a price snapshot is here and not only in the registry: the registry carries the price of a model, and a price
that was never verified has no amounts. The economics of a cohort needs the price of a call that a run made, and it
needs to say where the price came from and the day it was last checked, so the snapshot is a value of its own that a
result carries.

Why every amount is a `Decimal`: the money of a cohort is a division, and a division in floating point is a number
nobody can check (FR-010).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

__all__ = [
    "Assumptions",
    "PriceSnapshot",
    "ReviewAssumption",
    "UNKNOWN_SOURCE",
]

# The source of an assumption that nobody stated. It is a word and not an empty string, because a reader of a result
# has to see that the number came from nowhere in particular.
UNKNOWN_SOURCE = "unstated"


def _decimal_of(value: Any, field: str) -> Decimal:
    """The amount as a `Decimal`, and a float is refused.

    Why a float is refused and not converted: a float is already a rounded number, and converting it hides the
    rounding inside the money (FR-010).
    """
    if isinstance(value, bool) or not isinstance(value, Decimal):
        raise ValueError(f"the {field} of an assumption is a Decimal, not {type(value).__name__}")
    return value


@dataclass(frozen=True)
class ReviewAssumption:
    """What a review by a person costs: the minutes it takes and the rate of an hour.

    Why the two are separate: the minutes say how long a case waits for a person and the rate says what that time
    is worth, and the two change for different reasons. The money of a review is their product.
    """

    minutes: Decimal
    hourly_rate_usd: Decimal | None = None
    # Where the number came from and the day it was stated, so that a reader knows which numbers are facts.
    source: str = UNKNOWN_SOURCE
    stated_on: date | None = None

    def __post_init__(self) -> None:
        _decimal_of(self.minutes, "minutes")
        if self.hourly_rate_usd is not None:
            _decimal_of(self.hourly_rate_usd, "hourly rate")
        if not self.source:
            raise ValueError("an assumption names the source it came from, and an empty source is not a source")

    @property
    def cost_usd(self) -> Decimal | None:
        """The money of one review, or None when the rate of an hour was never stated.

        Why it is None and not zero: a review with no rate has no known cost, and a zero would say that the time
        of a person is free.
        """
        if self.hourly_rate_usd is None:
            return None
        return (self.hourly_rate_usd * self.minutes) / Decimal(60)

    def to_dict(self) -> dict[str, Any]:
        """The assumption as a dictionary, for the result that carries it."""
        cost = self.cost_usd
        return {
            "minutes": str(self.minutes),
            "hourly_rate_usd": None if self.hourly_rate_usd is None else str(self.hourly_rate_usd),
            "cost_usd": None if cost is None else str(cost),
            "source": self.source,
            "stated_on": self.stated_on.isoformat() if self.stated_on is not None else None,
        }


@dataclass(frozen=True)
class PriceSnapshot:
    """The price of a model, where it comes from and the day it was last checked.

    Why it repeats what the registry carries: the economics of a cohort reads the price of a call that a run made,
    and a price that left the registry with no day and no source would travel to the result with no provenance.
    A price that was never verified has no amounts, because a guess is worse than an absence (FR-011).
    """

    source: str = UNKNOWN_SOURCE
    last_verified: date | None = None
    input_per_1m_usd: Decimal | None = None
    output_per_1m_usd: Decimal | None = None

    def __post_init__(self) -> None:
        for field in ("input_per_1m_usd", "output_per_1m_usd"):
            amount = getattr(self, field)
            if amount is not None:
                _decimal_of(amount, field)

    @property
    def is_verified(self) -> bool:
        """Whether the price was really checked: a known source, a day and both amounts."""
        return (
            self.source != UNKNOWN_SOURCE
            and self.last_verified is not None
            and self.input_per_1m_usd is not None
            and self.output_per_1m_usd is not None
        )

    def to_dict(self) -> dict[str, Any]:
        """The price as a dictionary, for the result that carries it."""
        return {
            "source": self.source,
            "last_verified": self.last_verified.isoformat() if self.last_verified is not None else None,
            "input_per_1m_usd": None if self.input_per_1m_usd is None else str(self.input_per_1m_usd),
            "output_per_1m_usd": None if self.output_per_1m_usd is None else str(self.output_per_1m_usd),
            "verified": self.is_verified,
        }


@dataclass(frozen=True)
class Assumptions:
    """The assumptions of one economics run, together.

    Why one value and not one field per module: every result of the economics uses some of them, and a result that
    carries the assumptions it used is a result that a reader can reproduce.
    """

    review: ReviewAssumption = ReviewAssumption(minutes=Decimal("0"))
    # The price snapshot of each model of the cohort, by the identifier the run counted it under.
    prices: tuple[tuple[str, PriceSnapshot], ...] = ()

    def price_of(self, model_id: str) -> PriceSnapshot | None:
        """The price of a model, or None when the cohort carried no price for it.

        Why None and not an unverified price: a model with no price at all and a model with a price that was never
        verified are different facts, and the first is an absence in the cohort and the second a price the registry
        does not carry.
        """
        for identifier, snapshot in self.prices:
            if identifier == model_id:
                return snapshot
        return None

    def to_dict(self) -> dict[str, Any]:
        """The assumptions as a dictionary, for the result that carries them."""
        return {
            "review": self.review.to_dict(),
            "prices": {identifier: snapshot.to_dict() for identifier, snapshot in self.prices},
        }
