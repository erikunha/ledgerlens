"""The cost of a case, the total of a cohort and the cost per correctly resolved case.

What they guarantee, and why: (a) every amount is a `Decimal`, and a float is refused; (b) a price that was never
verified leaves the money unmeasured, and the report names the price that is missing; (c) the four categories of the
cost do not overlap, and a category that counts the same money twice is refused; (d) the denominator of the cost per
resolved case holds only the cases the code resolved, and the cases that went to a person pay their cost of the
review and are not in the denominator; (e) a cohort with no resolved case produces no number and the reason why;
(f) the module computes and never calls a model, and it never imports the API.

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
    CATEGORY_COMPUTE,
    CATEGORY_MODEL,
    CATEGORY_REVIEW,
    CaseCost,
    CohortCost,
    CostCategory,
    double_counted_categories,
)

# The price of the two models of the cohort, with the day they were last checked.
PRICE_MINI = PriceSnapshot(
    source="manual",
    last_verified=date(2026, 11, 8),
    input_per_1m_usd=Decimal("0.40"),
    output_per_1m_usd=Decimal("1.60"),
)
PRICE_FULL = PriceSnapshot(
    source="manual",
    last_verified=date(2026, 11, 8),
    input_per_1m_usd=Decimal("2.00"),
    output_per_1m_usd=Decimal("8.00"),
)

ASSUMPTIONS = Assumptions(
    review=ReviewAssumption(minutes=Decimal("15"), hourly_rate_usd=Decimal("60.00"), source="manual"),
    prices=(("gpt-4.1-mini", PRICE_MINI), ("gpt-4.1", PRICE_FULL)),
)


def _model_cost(usd: str) -> CostCategory:
    """A category of the cost of a case, with the money of the calls of the models."""
    return CostCategory(name=CATEGORY_MODEL, usd=Decimal(usd), known=True)


def test_the_money_of_a_case_is_a_decimal_and_a_float_is_refused() -> None:
    """Every amount of the economics is a `Decimal`, and a float is refused.

    Why it matters: the money of a cohort is a division, and a division in floating point is a number nobody can
    check (FR-010).
    """
    with pytest.raises(ValueError, match="Decimal"):
        CostCategory(name=CATEGORY_MODEL, usd=0.5, known=True)  # type: ignore[arg-type]


def test_the_total_of_a_case_sums_its_categories() -> None:
    """The total of a case is the sum of the categories that are known."""
    case = CaseCost(
        case_id="EC-01",
        categories=(
            _model_cost("0.010"),
            CostCategory(name=CATEGORY_COMPUTE, usd=Decimal("0.002"), known=True),
            CostCategory(name=CATEGORY_REVIEW, usd=Decimal("15.00"), known=True),
        ),
        resolved=True,
        went_to_person=False,
    )

    assert case.total_usd == Decimal("15.012")


def test_a_category_that_is_not_known_leaves_the_total_unmeasured() -> None:
    """A category whose money nobody knows leaves the total unmeasured, and it is never a zero.

    Why it matters: a partial sum would say that the call was free, and unknown is never zero (FR-011).
    """
    case = CaseCost(
        case_id="EC-01",
        categories=(
            _model_cost("0.010"),
            CostCategory(name=CATEGORY_COMPUTE, usd=None, known=False, reason="the price was never verified"),
        ),
        resolved=True,
        went_to_person=False,
    )

    assert case.total_usd is None
    assert case.unknown_categories() == (CATEGORY_COMPUTE,)


def test_a_case_that_counted_the_same_money_twice_is_refused() -> None:
    """Two categories of the same name count the same money twice, and the module refuses it.

    Why it matters: a total that counts the same money twice is a number nobody can reconcile with the money that
    was really spent.
    """
    twice = (_model_cost("0.010"), _model_cost("0.020"))

    # The helper names the category that overlaps, so a reader of a report knows which one it was.
    assert double_counted_categories(twice) == (CATEGORY_MODEL,)

    with pytest.raises(ValueError, match="twice"):
        CaseCost(case_id="EC-01", categories=twice, resolved=True, went_to_person=False)


def test_the_cost_per_resolved_case_divides_the_total_by_the_cases_the_code_resolved() -> None:
    """The number is the total divided by the resolved cases, and the denominator is visible."""
    cohort = CohortCost(
        cohort_id="cohort-1",
        cases=(
            CaseCost(case_id="EC-01", categories=(_model_cost("0.010"),), resolved=True, went_to_person=False),
            CaseCost(case_id="EC-02", categories=(_model_cost("0.020"),), resolved=True, went_to_person=False),
            CaseCost(
                case_id="EC-03",
                categories=(_model_cost("0.030"), CostCategory(name=CATEGORY_REVIEW, usd=Decimal("15.00"), known=True)),
                resolved=False,
                went_to_person=True,
            ),
        ),
        assumptions=ASSUMPTIONS,
    )

    # The total is the money of the three cases, and the denominator holds the two the code resolved.
    assert cohort.total_usd == Decimal("15.060")
    assert cohort.resolved_cases == 2
    assert cohort.cost_per_resolved_usd == Decimal("7.530")


def test_a_case_that_went_to_a_person_is_not_in_the_denominator_and_pays_its_review() -> None:
    """A case that a person saw pays the money of the review and it is not a resolved case.

    Why it matters: a denominator that counts the cases a person resolved would hide the cost of the escalation.
    """
    cohort = CohortCost(
        cohort_id="cohort-1",
        cases=(
            CaseCost(case_id="EC-01", categories=(_model_cost("0.010"),), resolved=True, went_to_person=False),
            CaseCost(
                case_id="EC-02",
                categories=(CostCategory(name=CATEGORY_REVIEW, usd=Decimal("15.00"), known=True),),
                resolved=False,
                went_to_person=True,
            ),
        ),
        assumptions=ASSUMPTIONS,
    )

    assert cohort.total_usd == Decimal("15.010")
    assert cohort.resolved_cases == 1
    assert cohort.cost_per_resolved_usd == Decimal("15.010")


def test_a_cohort_with_no_resolved_case_produces_no_number_and_the_reason() -> None:
    """A cohort where nothing was resolved has no cost per resolved case, and it says why.

    Why it matters: a division by zero would be an infinity or an error, and neither tells the reader that the
    cohort resolved nothing.
    """
    cohort = CohortCost(
        cohort_id="cohort-1",
        cases=(
            CaseCost(
                case_id="EC-01",
                categories=(CostCategory(name=CATEGORY_REVIEW, usd=Decimal("15.00"), known=True),),
                resolved=False,
                went_to_person=True,
            ),
        ),
        assumptions=ASSUMPTIONS,
    )

    assert cohort.cost_per_resolved_usd is None
    assert cohort.cost_per_resolved_reason


def test_a_cohort_with_an_unknown_price_produces_no_number_and_names_the_price() -> None:
    """A cohort whose money is unknown says which category is missing, and prints no amount."""
    cohort = CohortCost(
        cohort_id="cohort-1",
        cases=(
            CaseCost(
                case_id="EC-01",
                categories=(
                    CostCategory(
                        name=CATEGORY_MODEL,
                        usd=None,
                        known=False,
                        reason="the price of gpt-4.1 was never verified",
                    ),
                ),
                resolved=True,
                went_to_person=False,
            ),
        ),
        assumptions=ASSUMPTIONS,
    )

    assert cohort.total_usd is None
    assert cohort.cost_per_resolved_usd is None
    assert any("gpt-4.1" in reason for reason in cohort.unknown_reasons())


def test_every_report_of_the_cost_names_the_assumptions_it_used() -> None:
    """A report of the cost carries the assumptions, so the number is never read without them."""
    cohort = CohortCost(
        cohort_id="cohort-1",
        cases=(CaseCost(case_id="EC-01", categories=(_model_cost("0.010"),), resolved=True, went_to_person=False),),
        assumptions=ASSUMPTIONS,
    )

    report = cohort.to_dict()

    assert report["assumptions"]["review"]["minutes"] == "15"
    assert report["assumptions"]["review"]["cost_usd"] == "15.00"
    assert report["resolved_cases"] == 1
    assert report["cost_per_resolved_usd"] == "0.010"


def test_the_module_computes_and_never_calls_a_model_and_never_imports_the_api() -> None:
    """The economics module reads the results of the runs that already happened.

    Why it matters: the module is a leaf of the domain, and a module that called a model would be a second way of
    calling one, outside the budget and outside the trace of the run (ADR-037, FR-013).
    """
    package = Path(__file__).resolve().parents[2] / "ledgerlens" / "economics"
    forbidden_prefixes = ("ledgerlens.api", "ledgerlens.offline", "ledgerlens.config")

    for module in sorted(package.glob("*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                assert not name.startswith(forbidden_prefixes), f"{module.name} imports {name}"


def test_no_module_of_the_package_holds_a_binary_float_literal() -> None:
    """No module of the economics holds a float literal, because the money is a `Decimal`.

    Why it matters: a float literal in a path that computes money is a rounding that nobody sees.
    """
    package = Path(__file__).resolve().parents[2] / "ledgerlens" / "economics"

    for module in sorted(package.glob("*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, float):
                pytest.fail(f"{module.name} holds the float literal {node.value}")
