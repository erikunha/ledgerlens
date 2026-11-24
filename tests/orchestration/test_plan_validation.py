"""The plan of a case of the studio: the validation that runs before any step.

What they guarantee, and why: (a) a plan with a cycle is refused at the planning and no step ran, because a plan with
a cycle has no order; (b) a plan that names a step that does not exist is refused, because a plan that cannot run
fully is not a plan; (c) the order of the steps is the order of the dependencies and not the order a model wrote
them down.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import pytest

from ledgerlens.orchestration.plan import PlanRefused, steps_in_order, validate_plan
from ledgerlens.schemas import OrchestrationPlan, OrchestrationStep


def _plan(*steps: OrchestrationStep) -> OrchestrationPlan:
    """The plan of the steps that the test hands over."""
    return OrchestrationPlan(steps=list(steps), snapshot="a" * 64)


def test_a_plan_with_a_cycle_is_refused_at_the_planning() -> None:
    """A cycle has no order, and the refusal happens before any step runs."""
    plan = _plan(
        OrchestrationStep(id="one", goal="read", tool="query_ledger", depends_on=["two"]),
        OrchestrationStep(id="two", goal="read", tool="query_ledger", depends_on=["one"]),
    )

    with pytest.raises(PlanRefused, match="cycle"):
        validate_plan(plan)


def test_a_step_that_depends_on_itself_is_refused() -> None:
    """A step that waits for itself waits for ever."""
    plan = _plan(OrchestrationStep(id="one", goal="read", tool="query_ledger", depends_on=["one"]))

    with pytest.raises(PlanRefused, match="depends on itself"):
        validate_plan(plan)


def test_a_step_that_depends_on_a_step_that_does_not_exist_is_refused() -> None:
    """A plan that names a step nobody wrote is a plan that cannot run."""
    plan = _plan(OrchestrationStep(id="one", goal="read", tool="query_ledger", depends_on=["ghost"]))

    with pytest.raises(PlanRefused, match="no such step"):
        validate_plan(plan)


def test_two_steps_with_the_same_id_are_refused() -> None:
    """Two steps with the same id are two steps that the trace cannot tell apart."""
    plan = _plan(
        OrchestrationStep(id="one", goal="read", tool="query_ledger"),
        OrchestrationStep(id="one", goal="read again", tool="query_ledger"),
    )

    with pytest.raises(PlanRefused, match="same id"):
        validate_plan(plan)


def test_the_order_of_the_steps_is_the_order_of_the_dependencies() -> None:
    """The order comes from the graph and not from the order the steps were written down."""
    plan = _plan(
        OrchestrationStep(id="third", goal="compute", tool="calculate", depends_on=["second"]),
        OrchestrationStep(id="second", goal="read", tool="query_ledger", depends_on=["first"]),
        OrchestrationStep(id="first", goal="read", tool="query_ledger"),
    )

    ordered = [step.id for step in steps_in_order(plan)]

    assert ordered == ["first", "second", "third"]


def test_a_valid_plan_comes_back_from_the_validation() -> None:
    """The validation is a gate and not a transformation: the plan comes back as it went in."""
    plan = _plan(OrchestrationStep(id="one", goal="read", tool="query_ledger"))

    assert validate_plan(plan) is plan
