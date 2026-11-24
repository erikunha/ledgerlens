"""The expected loss of a policy, with the classes of the error kept apart and the unknowns named.

What it computes: how much a policy loses when it is wrong, over a cohort whose labels the code produced. The
question it answers is not "which policy is better" but "what does each policy cost when it fails", because the
losses are assumptions of the reader and the counts are facts of the cohort.

Why the classes of the error are kept apart: a policy that accepts a case it should reject and a policy that rejects a
case it should accept do not lose the same money. A number that merged the two would hide which one hurt, and the
whole point of the utility is that the two are not symmetric.

Why two classes that overlap are refused before the sum: the classes of the error have to be mutually exclusive, and a
case that is in two of them would be counted twice. The refusal names the overlap instead of adding it up.

Why an uncalibrated probability is unknown and not a point: a probability that nobody calibrated is a confidence, and
reading a confidence as a probability turns a guess into a number of money. The module publishes the count, the loss
and the range of the class, and it says that the probability was never calibrated.

Why a loss that nobody knows leaves the total unknown: a missing loss treated as a zero would say that the error was
free, and unknown is never zero.

Why the module publishes no return: a return is a claim about the future, and this module computes over the runs that
already happened. It publishes the loss, the coverage and the assumptions, and the reader decides what they are worth.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from ledgerlens.economics.assumptions import Assumptions

__all__ = [
    "CLASS_FALSE_ACCEPT",
    "CLASS_FALSE_REJECT",
    "CLASS_TRUE_ACCEPT",
    "CLASS_TRUE_REJECT",
    "CoveragePoint",
    "ErrorClass",
    "PolicyComparison",
    "PolicyLoss",
    "RiskCoverageCurve",
    "compare_policies",
    "expected_loss_of",
    "risk_coverage_curve",
]

# The four classes of the outcome of a policy. The two of the error carry the names of the design, because a
# reader has to see which of the two hurt.
CLASS_TRUE_ACCEPT = "true_accept"
CLASS_FALSE_ACCEPT = "false_accept"
CLASS_FALSE_REJECT = "false_reject"
CLASS_TRUE_REJECT = "true_reject"


def _decimal_of(value: Any, field_name: str) -> Decimal:
    """The amount as a `Decimal`, and a float is refused.

    Why a float is refused and not converted: a float is already a rounded number, and converting it hides the
    rounding inside the money (FR-010).
    """
    if isinstance(value, bool) or not isinstance(value, Decimal):
        raise ValueError(f"the {field_name} of the utility is a Decimal, not {type(value).__name__}")
    return value


@dataclass(frozen=True)
class ErrorClass:
    """One class of the outcome of a policy: how many cases it holds and what each one costs when it happens.

    Why the probability is a field and not computed: the module reads the labels the cohort produced and it never
    turns a confidence into a probability. A class with no probability carries one that nobody calibrated, and the
    module publishes it as unknown.
    """

    name: str
    count: int
    loss_usd: Decimal | None
    probability: Decimal | None
    # The classes this one overlaps with, when the caller knows that a case can be in both of them.
    overlaps_with: tuple[str, ...] = ()
    # Where the loss came from, so that a reader knows it is an assumption.
    source: str = "unstated"

    def __post_init__(self) -> None:
        if self.count < 0:
            raise ValueError(f"the class {self.name!r} holds a negative number of cases")
        if self.loss_usd is not None:
            _decimal_of(self.loss_usd, "loss of a class")
        if self.probability is not None:
            _decimal_of(self.probability, "probability of a class")
            if self.probability < 0 or self.probability > 1:
                raise ValueError(f"the probability of the class {self.name!r} is not between zero and one")

    @property
    def is_measurable(self) -> bool:
        """Whether the class can be summed: its loss is known and its probability was calibrated."""
        return self.loss_usd is not None and self.probability is not None

    def to_dict(self) -> dict[str, Any]:
        """The class as a dictionary, for the published result."""
        return {
            "name": self.name,
            "count": self.count,
            "loss_usd": None if self.loss_usd is None else str(self.loss_usd),
            "probability": None if self.probability is None else str(self.probability),
            "overlaps_with": list(self.overlaps_with),
            "source": self.source,
        }


@dataclass(frozen=True)
class PolicyLoss:
    """The expected loss of a policy over a cohort, class by class.

    Why the total is None when a class is not measurable: a partial sum would understate the loss of the policy and
    the reader would take it for the whole.
    """

    by_class: dict[str, Decimal]
    total_usd: Decimal | None
    unknown_reasons: tuple[str, ...]
    # The names of the classes that could not be summed, kept apart from the reasons so that the two never drift.
    unknown: tuple[str, ...] = ()
    # The source of the probability of each class, so that a reader knows which number rests on a measurement.
    sources: dict[str, str] = field(default_factory=dict)
    assumptions: Assumptions = field(default_factory=lambda: Assumptions())

    def unknown_classes(self) -> tuple[str, ...]:
        """The names of the classes that could not be summed."""
        return self.unknown

    def to_dict(self) -> dict[str, Any]:
        """The loss as a dictionary, for the published result."""
        return {
            "by_class": {name: str(value) for name, value in self.by_class.items()},
            "total_usd": None if self.total_usd is None else str(self.total_usd),
            "unknown_reasons": list(self.unknown_reasons),
            "sources": dict(self.sources),
            "assumptions": self.assumptions.to_dict(),
        }


def expected_loss_of(
    classes: Sequence[ErrorClass],
    *,
    assumptions: Assumptions | None = None,
) -> PolicyLoss:
    """The expected loss of a policy over the classes of the cohort.

    Why the overlap is refused before the sum: a case that is in two classes of the error would be counted twice, and
    the number would overstate the loss of the policy.

    Why an uncalibrated probability leaves the class out of the sum: the probability of a class that nobody
    calibrated is unknown, and a class with an unknown probability has an expected loss that nobody computed. The
    class is named in the reasons, so the reader sees which part of the number is missing.
    """
    names = {error_class.name for error_class in classes}
    for error_class in classes:
        for other in error_class.overlaps_with:
            if other in names:
                raise ValueError(
                    f"the classes {error_class.name!r} and {other!r} overlap, so the sum would count the same case "
                    "twice: partition the classes or name the overlap"
                )

    by_class: dict[str, Decimal] = {}
    reasons: list[str] = []
    unknown: list[str] = []
    total = Decimal("0")
    measurable = True
    for error_class in classes:
        if error_class.loss_usd is None:
            measurable = False
            by_class[error_class.name] = Decimal("0")
            unknown.append(error_class.name)
            reasons.append(f"{error_class.name}: the loss of the class was never stated")
            continue
        if error_class.probability is None:
            measurable = False
            by_class[error_class.name] = Decimal("0")
            unknown.append(error_class.name)
            reasons.append(f"{error_class.name}: the probability of the class was never calibrated")
            continue
        contribution = error_class.loss_usd * Decimal(error_class.count) * error_class.probability
        by_class[error_class.name] = contribution
        total += contribution
    return PolicyLoss(
        by_class=by_class,
        total_usd=total if measurable else None,
        unknown_reasons=tuple(reasons),
        unknown=tuple(unknown),
        sources={error_class.name: error_class.source for error_class in classes},
        assumptions=assumptions or Assumptions(),
    )


@dataclass(frozen=True)
class CoveragePoint:
    """One point of the curve of the risk and the coverage: a label, how many cases it covers and its risk."""

    label: str
    coverage: Decimal
    risk: Decimal | None

    def to_dict(self) -> dict[str, Any]:
        """The point as a dictionary, for the published result."""
        return {
            "label": self.label,
            "coverage": str(self.coverage),
            "risk": None if self.risk is None else str(self.risk),
        }


@dataclass(frozen=True)
class RiskCoverageCurve:
    """The curve of the risk against the coverage, over the labels that carry a probability.

    Why the labels left out are named: a curve that silently dropped the labels it could not measure would look
    complete, and the reader would think that the whole cohort is on it.
    """

    points: tuple[CoveragePoint, ...]
    left_out: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """The curve as a dictionary, for the published result."""
        return {
            "points": [point.to_dict() for point in self.points],
            "left_out": list(self.left_out),
        }


@dataclass(frozen=True)
class PolicyComparison:
    """The comparison of the automatic resolution, of the review of everything and of the abstention.

    Why the three are compared over the same cohort: they pay for different things, and a comparison over different
    mixes of cases would measure the mixes and not the policies.

    Why the count of the cases is published: a reader has to see how many cases each of the three policies covered,
    because a policy that abstains on everything is cheap for a reason nobody can read.
    """

    automatic: PolicyLoss
    review: PolicyLoss
    abstention: PolicyLoss
    cases: int
    assumptions: Assumptions = field(default_factory=lambda: Assumptions())

    def to_dict(self) -> dict[str, Any]:
        """The comparison as a dictionary, for the published result."""
        return {
            "automatic": self.automatic.to_dict(),
            "review": self.review.to_dict(),
            "abstention": self.abstention.to_dict(),
            "cases": self.cases,
            "assumptions": self.assumptions.to_dict(),
        }


def compare_policies(
    classes: Sequence[ErrorClass],
    *,
    review_cost_usd: Decimal,
    abstained_count: int,
    assumptions: Assumptions | None = None,
) -> PolicyComparison:
    """The three policies compared over the same cohort, with the money of the review of each.

    Why the review catches the errors it reviews: a person who reads the case sees the mistake the system made, and
    the assumption is published with the result so that a reader who disagrees can change it.

    Why the abstention reviews only the uncertain cases: that is what an abstention is, and the count of the cases
    it reviews is an assumption of the reader and it is published.

    Why no policy is recommended: the three losses are what the reader has to weigh, and the module computes them
    and names them. It publishes no return.
    """
    assumptions = assumptions or Assumptions()
    cases = sum(error_class.count for error_class in classes)
    automatic = expected_loss_of(classes, assumptions=assumptions)

    # A review of every case catches every error the system made, and it costs the review of every case.
    review_total = review_cost_usd * Decimal(cases)
    review = PolicyLoss(
        by_class={"review": review_total},
        total_usd=review_total,
        unknown_reasons=(),
        sources={"review": "the assumption of the reader"},
        assumptions=assumptions,
    )

    # An abstention reviews only the uncertain cases, and the cases it reviews are the ones it did not settle.
    abstention_total = review_cost_usd * Decimal(abstained_count)
    abstention = PolicyLoss(
        by_class={"review": abstention_total},
        total_usd=abstention_total,
        unknown_reasons=(),
        sources={"review": "the assumption of the reader"},
        assumptions=assumptions,
    )
    return PolicyComparison(
        automatic=automatic,
        review=review,
        abstention=abstention,
        cases=cases,
        assumptions=assumptions,
    )


def risk_coverage_curve(classes: Sequence[ErrorClass]) -> RiskCoverageCurve:
    """The curve of the risk against the coverage, over the labels that carry a calibrated probability.

    Why the coverage is the count and not a share: the reader of a curve has to see the number of cases it covers,
    because a share over an unknown denominator is a share of nothing.

    Why the risk of a point is None when the loss of the label is unknown: the risk of a label is the money it costs,
    and a label with no known loss has no known risk.
    """
    points: list[CoveragePoint] = []
    left_out: list[str] = []
    coverage = Decimal("0")
    for error_class in classes:
        if error_class.probability is None:
            left_out.append(error_class.name)
            continue
        coverage += Decimal(error_class.count)
        risk = None if error_class.loss_usd is None else error_class.loss_usd * error_class.probability
        points.append(CoveragePoint(label=error_class.name, coverage=coverage, risk=risk))
    return RiskCoverageCurve(points=tuple(points), left_out=tuple(left_out))
