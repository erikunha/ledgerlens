"""The cost of a case, the total of a cohort and the cost per correctly resolved case.

What it computes: the money that a cohort of cases cost, and the money that each case that was resolved cost on
average. The number that matters to a reader is not the total: it is the cost of a case that was actually settled,
because a case that was escalated to a person was not settled by the system.

Why the categories do not overlap: the cost of a case has four parts, the money of the calls of the models, the money
of the compute, the money of the review by a person and the money assumed for the error the case left behind. A part
that counted the same money twice would make the total a number that nobody can reconcile with the money that was
really spent, so a case with two parts of the same name is refused.

Why an unknown is never a zero: a price that was never verified leaves the money of a category unmeasured, and the
total of the cohort with it. A zero would say that the call was free, and the reader of a cost that says nothing
would believe it (FR-011).

Why the denominator holds only the cases the code resolved: a case that went to a person is a case the system did
not settle, and it pays the money of its review without being a case that was resolved. The denominator is published
next to the number and the cases that went to a person are named, so a reader can see what the number covers.

Why the module never calls a model: it reads the results of the runs that already happened. The oracle of a resolved
case comes from the code that resolved it, and the module never recomputes a verdict.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from ledgerlens.economics.assumptions import Assumptions

__all__ = [
    "CATEGORY_COMPUTE",
    "CATEGORY_ERROR",
    "CATEGORY_MODEL",
    "CATEGORY_REVIEW",
    "CATEGORIES",
    "CaseCost",
    "CohortComparison",
    "CohortCost",
    "CostCategory",
    "compare_cohorts",
    "double_counted_categories",
]

# The money of the calls of the models of the case.
CATEGORY_MODEL = "model"
# The money of the compute the case used, outside the calls of the models.
CATEGORY_COMPUTE = "compute"
# The money of the review of the case by a person.
CATEGORY_REVIEW = "review"
# The money assumed for the error that the case left behind.
CATEGORY_ERROR = "error_assumption"

# The four categories of the cost of a case, in the order a reader reads them.
CATEGORIES = (CATEGORY_MODEL, CATEGORY_COMPUTE, CATEGORY_REVIEW, CATEGORY_ERROR)


def _decimal_of(value: Any, field: str) -> Decimal:
    """The amount as a `Decimal`, and a float is refused.

    Why a float is refused and not converted: a float is already a rounded number, and converting it hides the
    rounding inside the money (FR-010).
    """
    if isinstance(value, bool) or not isinstance(value, Decimal):
        raise ValueError(f"the {field} of the cost is a Decimal, not {type(value).__name__}")
    return value


def double_counted_categories(categories: Sequence[CostCategory]) -> tuple[str, ...]:
    """The names of the categories that appear more than once, and the ones that appear once are not named.

    Why it is a function and not a check inside the constructor: a reader of a report of the cost wants to know
    which categories overlapped, and not only that something overlapped.
    """
    seen: set[str] = set()
    twice: list[str] = []
    for category in categories:
        if category.name in seen and category.name not in twice:
            twice.append(category.name)
        seen.add(category.name)
    return tuple(twice)


@dataclass(frozen=True)
class CostCategory:
    """One part of the cost of a case, with the money or with the reason why it is unknown.

    Why the money and the reason are one value and not two: a part with no money is a part nobody could measure,
    and the reason is what tells the reader which part it was and what is missing.
    """

    name: str
    usd: Decimal | None
    known: bool
    reason: str = ""

    def __post_init__(self) -> None:
        if self.usd is not None:
            _decimal_of(self.usd, "money of a category")
        if self.known and self.usd is None:
            raise ValueError(f"the category {self.name!r} is known and carries no money")
        if not self.known and not self.reason:
            raise ValueError(f"the category {self.name!r} is not known and says no reason")

    def to_dict(self) -> dict[str, Any]:
        """The category as a dictionary, for the report of the cost."""
        return {
            "name": self.name,
            "usd": None if self.usd is None else str(self.usd),
            "known": self.known,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class CaseCost:
    """The cost of one case, in the parts that do not overlap, and what happened to it.

    Why `resolved` is a field and not computed here: the oracle of a resolved case comes from the code that resolved
    it, and a module that recomputed the verdict would be a second oracle that could disagree with the first.
    """

    case_id: str
    categories: tuple[CostCategory, ...]
    # Whether the code settled the case, and whether a person saw it.
    resolved: bool
    went_to_person: bool

    def __post_init__(self) -> None:
        twice = double_counted_categories(self.categories)
        if twice:
            raise ValueError(
                f"the cost of the case {self.case_id!r} counts the same money twice, in the category {twice[0]!r}"
            )

    @property
    def total_usd(self) -> Decimal | None:
        """The money of the case, or None when a part of it is unknown.

        Why the whole total and not the sum of the known parts: a partial sum reads as the cost of the case, and it
        is not (FR-011).
        """
        if self.unknown_categories():
            return None
        total = Decimal("0")
        for category in self.categories:
            total += category.usd if category.usd is not None else Decimal("0")
        return total

    def unknown_categories(self) -> tuple[str, ...]:
        """The names of the parts of the cost that nobody could measure."""
        return tuple(category.name for category in self.categories if not category.known)

    def to_dict(self) -> dict[str, Any]:
        """The case as a dictionary, for the report of the cost."""
        total = self.total_usd
        return {
            "case_id": self.case_id,
            "categories": [category.to_dict() for category in self.categories],
            "resolved": self.resolved,
            "went_to_person": self.went_to_person,
            "total_usd": None if total is None else str(total),
        }


@dataclass(frozen=True)
class CohortCost:
    """The cost of a cohort of cases, and the cost of each case the code resolved.

    Why the cohort carries its digest: a comparison of two cohorts is only a comparison when the two cohorts are the
    same cases, and the digest is what says that they are.
    """

    cohort_id: str
    cases: tuple[CaseCost, ...]
    assumptions: Assumptions
    # The digest of the cases of the cohort, and not its name: two runs can carry the same name over different
    # cases, and only the digest tells that the two cohorts are the same.
    cohort_digest: str = ""

    @property
    def total_usd(self) -> Decimal | None:
        """The money of the whole cohort, or None when a part of it is unknown."""
        if self.unknown_reasons():
            return None
        total = Decimal("0")
        for case in self.cases:
            total += case.total_usd if case.total_usd is not None else Decimal("0")
        return total

    @property
    def resolved_cases(self) -> int:
        """The number of cases the code resolved, and it is the denominator of the cost per resolved case."""
        return sum(1 for case in self.cases if case.resolved)

    @property
    def cases_to_person(self) -> tuple[str, ...]:
        """The cases that a person saw, named so that a reader sees what the denominator leaves out."""
        return tuple(case.case_id for case in self.cases if case.went_to_person)

    @property
    def cost_per_resolved_usd(self) -> Decimal | None:
        """The money of a resolved case, or None when the cohort resolved nothing or the money is unknown.

        Why it is None and not an infinity: a division by zero is not a cost, and the reader has to know that the
        cohort resolved nothing.
        """
        resolved = self.resolved_cases
        if resolved == 0:
            return None
        total = self.total_usd
        if total is None:
            return None
        return total / Decimal(resolved)

    @property
    def cost_per_resolved_reason(self) -> str | None:
        """Why the cost per resolved case does not exist, when it does not exist."""
        if self.cost_per_resolved_usd is not None:
            return None
        if self.resolved_cases == 0:
            return (
                "the cohort resolved no case, so the cost of a resolved case does not exist: the denominator is zero "
                "and the cases that went to a person are not in it"
            )
        reasons = self.unknown_reasons()
        if reasons:
            return f"the money of the cohort is unknown: {'; '.join(reasons)}"
        return "the cost of a resolved case does not exist"

    def unknown_reasons(self) -> tuple[str, ...]:
        """The reasons why the money of the cohort is unknown, one per case that carries an unknown part."""
        reasons: list[str] = []
        for case in self.cases:
            for category in case.categories:
                if not category.known:
                    reasons.append(f"{case.case_id}: {category.name}: {category.reason}")
        return tuple(reasons)

    def to_dict(self) -> dict[str, Any]:
        """The cohort as a dictionary, for the report of the cost.

        Why the assumptions travel with the report: a number that is read without the assumptions that produced it
        is a number that nobody can reproduce.
        """
        total = self.total_usd
        per_resolved = self.cost_per_resolved_usd
        return {
            "cohort_id": self.cohort_id,
            "cohort_digest": self.cohort_digest,
            "cases": [case.to_dict() for case in self.cases],
            "total_usd": None if total is None else str(total),
            "resolved_cases": self.resolved_cases,
            "cases_to_person": list(self.cases_to_person),
            "cost_per_resolved_usd": None if per_resolved is None else str(per_resolved),
            "cost_per_resolved_reason": self.cost_per_resolved_reason,
            "unknown_reasons": list(self.unknown_reasons()),
            "assumptions": self.assumptions.to_dict(),
        }


@dataclass(frozen=True)
class CohortComparison:
    """The comparison of two architectures over the same cohort.

    Why the difference is a number and not a claim: the comparison publishes the two numbers, the difference between
    them and the denominator of each, and the reader decides what the difference is worth.

    Why the denominator is published for each arm and not once: the two arms resolved a different number of cases,
    and a single denominator would belong to one of them and hide the other.
    """

    first: CohortCost
    second: CohortCost
    cost_per_resolved_usd: dict[str, Decimal | None]
    difference_usd: Decimal | None
    denominators: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        """The comparison as a dictionary, for the published result."""
        return {
            "cohort_digest": self.first.cohort_digest,
            "cost_per_resolved_usd": {
                name: None if value is None else str(value) for name, value in self.cost_per_resolved_usd.items()
            },
            "difference_usd": None if self.difference_usd is None else str(self.difference_usd),
            "denominators": dict(self.denominators),
            "cohorts": {self.first.cohort_id: self.first.to_dict(), self.second.cohort_id: self.second.to_dict()},
            "assumptions": self.first.assumptions.to_dict(),
        }


def compare_cohorts(first: CohortCost, second: CohortCost) -> CohortComparison:
    """The comparison of two architectures over the same cohort, or a refusal when the cohorts differ.

    Why the digest and not the name: the name of a cohort is what a caller typed and the digest is what the cases
    are, and only the second one can tell that two cohorts hold the same cases. A comparison over two different
    cohorts measures the difference between the cohorts and not the difference between the architectures.

    Why it never chooses a model: the comparison reads the results of the runs that already happened.
    """
    if first.cohort_digest != second.cohort_digest:
        raise ValueError(
            "the two cohorts are not the same cohort, so the comparison is refused: the digest of the first is "
            f"{first.cohort_digest!r} and the digest of the second is {second.cohort_digest!r}"
        )
    first_cost = first.cost_per_resolved_usd
    second_cost = second.cost_per_resolved_usd
    difference = None if first_cost is None or second_cost is None else first_cost - second_cost
    return CohortComparison(
        first=first,
        second=second,
        cost_per_resolved_usd={first.cohort_id: first_cost, second.cohort_id: second_cost},
        difference_usd=difference,
        denominators={first.cohort_id: first.resolved_cases, second.cohort_id: second.resolved_cases},
    )
