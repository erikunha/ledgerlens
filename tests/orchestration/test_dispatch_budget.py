"""The scheduler: the steps under the cap of the concurrency, spending from the budget of the run.

What they guarantee, and why: (a) a run that a cap stopped names the cap and carries the partial result, because a
run that stops without saying why cannot be compared with the arm that did not stop; (b) no call happens outside the
budget, because the cap is checked before the tool is called; (c) a plan with a cycle never runs a step.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from ledgerlens.byok.budget import BudgetCoordinator
from ledgerlens.byok.registry import ProviderRegistry
from ledgerlens.orchestration.dispatcher import Permissions
from ledgerlens.orchestration.plan import PlanRefused
from ledgerlens.orchestration.scheduler import run_plan
from ledgerlens.run_context import RunBudget
from ledgerlens.schemas import OrchestrationPlan, OrchestrationStep


def _tools(calls: list[str]) -> dict[str, Any]:
    """A registry of tools that records the calls it received."""

    def _make(name: str):
        def _tool(arguments: dict[str, Any]) -> dict[str, Any]:
            calls.append(name)
            return {"evidence_refs": ["sql:1"], "spend_usd": Decimal("0.10")}

        return _tool

    return {"query_ledger": _make("query_ledger"), "calculate": _make("calculate")}


def _coordinator(max_tool_calls: int | None) -> BudgetCoordinator:
    """A coordinator with the caps of the test."""
    return BudgetCoordinator(
        RunBudget(max_model_calls=4, max_tool_calls=max_tool_calls),
        ProviderRegistry([]),
    )


def _permissions() -> Permissions:
    """The permissions of a run that may call the two tools of the test."""
    return Permissions(tools=frozenset({"query_ledger", "calculate"}), accounts=frozenset())


def test_a_run_that_a_cap_stopped_names_the_cap_and_carries_the_partial_result() -> None:
    """The cap is named and the result of the steps that ran is published (SC-003)."""
    calls: list[str] = []
    plan = OrchestrationPlan(
        steps=[
            OrchestrationStep(id="one", goal="read", tool="query_ledger"),
            OrchestrationStep(id="two", goal="read again", tool="query_ledger"),
            OrchestrationStep(id="three", goal="read a third time", tool="query_ledger"),
        ]
    )

    outcome = run_plan(
        plan,
        permissions=_permissions(),
        tools=_tools(calls),
        budget=_coordinator(1),
        concurrency=1,
    )

    assert outcome.cut_by == "max_tool_calls"
    assert outcome.stopped_by_a_cap is True
    assert len(calls) == 1
    answered = [result for result in outcome.results if result.status == "ok"]
    assert len(answered) == 1
    assert answered[0].step_id == "one"
    # The steps that did not run say why, and they never call a tool.
    stopped = [result for result in outcome.results if result.status != "ok"]
    assert all("the run stopped at the cap max_tool_calls" in (result.error or "") for result in stopped)


def test_no_call_happens_outside_the_budget() -> None:
    """The cap is checked before the tool is called, so the money of the visitor is not spent outside it."""
    calls: list[str] = []
    plan = OrchestrationPlan(
        steps=[
            OrchestrationStep(id="one", goal="read", tool="query_ledger"),
            OrchestrationStep(id="two", goal="read again", tool="query_ledger"),
        ]
    )

    outcome = run_plan(
        plan,
        permissions=_permissions(),
        tools=_tools(calls),
        budget=_coordinator(1),
        concurrency=1,
    )

    assert len(calls) == 1
    assert outcome.cut_by == "max_tool_calls"


def test_a_run_that_the_budget_holds_answers_every_step() -> None:
    """A run that nobody stopped answers every step of the plan."""
    calls: list[str] = []
    plan = OrchestrationPlan(
        steps=[
            OrchestrationStep(id="one", goal="read", tool="query_ledger"),
            OrchestrationStep(id="two", goal="compute", tool="calculate", depends_on=["one"]),
        ]
    )

    outcome = run_plan(
        plan,
        permissions=_permissions(),
        tools=_tools(calls),
        budget=_coordinator(4),
        concurrency=2,
    )

    assert outcome.cut_by is None
    assert [result.step_id for result in outcome.results] == ["one", "two"]
    assert all(result.status == "ok" for result in outcome.results)
    assert calls == ["query_ledger", "calculate"]


def test_a_plan_with_a_cycle_never_runs_a_step() -> None:
    """The plan is validated before anything runs, so a plan that cannot run never spends anything (FR-005)."""
    calls: list[str] = []
    plan = OrchestrationPlan(
        steps=[
            OrchestrationStep(id="one", goal="read", tool="query_ledger", depends_on=["two"]),
            OrchestrationStep(id="two", goal="read", tool="query_ledger", depends_on=["one"]),
        ]
    )

    with pytest.raises(PlanRefused):
        run_plan(
            plan,
            permissions=_permissions(),
            tools=_tools(calls),
            budget=_coordinator(4),
            concurrency=2,
        )

    assert calls == []


def test_the_money_the_run_spent_is_published_with_the_result() -> None:
    """The spend of the steps is the money of the run, and it is a `Decimal`."""
    calls: list[str] = []
    plan = OrchestrationPlan(steps=[OrchestrationStep(id="one", goal="read", tool="query_ledger")])

    outcome = run_plan(
        plan,
        permissions=_permissions(),
        tools=_tools(calls),
        budget=_coordinator(4),
        concurrency=1,
    )

    assert outcome.results[0].spend_usd == Decimal("0.10")


def test_a_run_that_spends_more_than_the_cap_of_the_money_stops_with_the_name_of_the_cap() -> None:
    """The cap of the money of the run stops the run and it is named."""
    calls: list[str] = []
    plan = OrchestrationPlan(
        steps=[
            OrchestrationStep(id="one", goal="read", tool="query_ledger"),
            OrchestrationStep(id="two", goal="read again", tool="query_ledger"),
        ]
    )
    permissions = Permissions(
        tools=frozenset({"query_ledger"}),
        accounts=frozenset(),
        max_spend_usd=Decimal("0.05"),
    )

    outcome = run_plan(
        plan,
        permissions=permissions,
        tools=_tools(calls),
        budget=_coordinator(4),
        concurrency=1,
    )

    assert outcome.cut_by == "max_spend_usd"
    assert len(calls) == 1
