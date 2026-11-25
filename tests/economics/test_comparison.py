"""The comparison of two architectures over the same cohort.

What they guarantee, and why: (a) a comparison over two different cohorts is refused, because two cohorts are not
comparable; (b) the refusal is checked against the digest of the cohort and not against its name, because two runs
can carry the same name over different cases; (c) the comparison reads the results of the runs that already happened
and it never chooses a model; (d) the module of the economics never imports a model or a registry that calls one.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import ast
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ledgerlens.economics.assumptions import Assumptions, PriceSnapshot, ReviewAssumption
from ledgerlens.economics.cost import (
    CATEGORY_MODEL,
    CaseCost,
    CohortCost,
    CostCategory,
    compare_cohorts,
)

PRICE = PriceSnapshot(
    source="manual",
    last_verified=date(2026, 11, 8),
    input_per_1m_usd=Decimal("0.40"),
    output_per_1m_usd=Decimal("1.60"),
)
ASSUMPTIONS = Assumptions(
    review=ReviewAssumption(minutes=Decimal("15"), hourly_rate_usd=Decimal("60.00"), source="manual"),
    prices=(("gpt-4.1-mini", PRICE),),
)


def _cohort(cohort_id: str, digest: str, usd: str, resolved: int = 2) -> CohortCost:
    """A cohort of two cases, with the digest that says which cases it holds."""
    cases = tuple(
        CaseCost(
            case_id=f"EC-{index:02d}",
            categories=(CostCategory(name=CATEGORY_MODEL, usd=Decimal(usd), known=True),),
            resolved=index <= resolved,
            went_to_person=index > resolved,
        )
        for index in (1, 2)
    )
    return CohortCost(cohort_id=cohort_id, cases=cases, assumptions=ASSUMPTIONS, cohort_digest=digest)


def test_a_comparison_over_two_different_cohorts_is_refused() -> None:
    """Two cohorts over different cases are not comparable, and the module refuses the comparison.

    Why it matters: a comparison over two cohorts measures the difference between the cohorts and not the difference
    between the architectures.
    """
    with pytest.raises(ValueError, match="cohort"):
        compare_cohorts(_cohort("one_model", "digest-a", "0.010"), _cohort("cascade", "digest-b", "0.005"))


def test_the_refusal_is_checked_against_the_digest_and_not_against_the_name() -> None:
    """Two cohorts with the same name over different cases are refused, and the digest is what says it.

    Why it matters: the name of a cohort is what a caller typed and the digest is what the cases are, and only the
    second one can tell that two cohorts are the same.
    """
    with pytest.raises(ValueError, match="cohort"):
        compare_cohorts(_cohort("same-name", "digest-a", "0.010"), _cohort("same-name", "digest-b", "0.005"))


def test_a_comparison_over_the_same_cohort_is_published() -> None:
    """A comparison over the same cohort publishes the two numbers and the difference between them."""
    comparison = compare_cohorts(_cohort("one_model", "digest-a", "0.010"), _cohort("cascade", "digest-a", "0.005"))

    assert comparison.cost_per_resolved_usd["one_model"] == Decimal("0.010")
    assert comparison.cost_per_resolved_usd["cascade"] == Decimal("0.005")
    # The difference is the money of the case that the second architecture saved, and it is exact.
    assert comparison.difference_usd == Decimal("0.005")
    # The denominator of each arm is published, because the two arms resolved a different number of cases.
    assert comparison.denominators == {"one_model": 2, "cascade": 2}


def test_a_comparison_publishes_the_assumptions_of_both_cohorts() -> None:
    """The comparison carries the assumptions it used, so the numbers are never read without them."""
    comparison = compare_cohorts(_cohort("one_model", "digest-a", "0.010"), _cohort("cascade", "digest-a", "0.005"))

    assert comparison.to_dict()["assumptions"]["review"]["minutes"] == "15"


def test_a_comparison_never_chooses_a_model_and_never_imports_one() -> None:
    """The economics module imports no model and no registry that calls one.

    Why it matters: the comparison is over the results of the runs that already happened, and a module that could
    call a model would be a second way of calling one, outside the budget and outside the trace of the run
    (ADR-037, FR-013).
    """
    package = Path(__file__).resolve().parents[2] / "ledgerlens" / "economics"
    forbidden = ("ledgerlens.api", "ledgerlens.offline", "ledgerlens.config", "ledgerlens.agents")

    for module in sorted(package.glob("*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                assert not name.startswith(forbidden), f"{module.name} imports {name}"
