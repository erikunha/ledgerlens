"""The trace of a run of the studio: one event per step, with the budget it had and the reason it stopped.

What they guarantee, and why: (a) every step of the run has its own event, because a run that publishes no trace
is a run nobody can read; (b) the event names the budget the run had and the reason the step stopped, because a
reader who sees that a step failed has to see why; (c) the trace names the specialist that answered each part of the
question, because a specialist is a role and the reader has to know which one answered (FR-009).

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from ledgerlens.byok.budget import BudgetCoordinator
from ledgerlens.byok.registry import ProviderRegistry
from ledgerlens.observability.trace_event import InMemoryTraceSink, TraceEventStream
from ledgerlens.orchestration.dispatcher import Permissions
from ledgerlens.orchestration.scheduler import run_plan
from ledgerlens.run_context import RunBudget
from ledgerlens.schemas import OrchestrationPlan, OrchestrationStep


def _tools() -> dict[str, Any]:
    """A registry of tools that answers with an evidence reference."""

    def _tool(arguments: dict[str, Any]) -> dict[str, Any]:
        return {"evidence_refs": ["sql:1"], "spend_usd": Decimal("0.10")}

    return {"query_ledger": _tool, "calculate": _tool}


def _run() -> tuple[Any, Any]:
    """A run of the studio with two steps and the trace of it."""
    plan = OrchestrationPlan(
        steps=[
            OrchestrationStep(id="read", goal="read the ledger", tool="query_ledger", specialist="ledger_reader"),
            OrchestrationStep(
                id="compute",
                goal="compute",
                tool="calculate",
                specialist="calculator",
                depends_on=["read"],
            ),
        ]
    )
    sink = InMemoryTraceSink()
    stream = TraceEventStream("run-of-the-studio", sink, mode="deterministic_sandbox")
    budget = BudgetCoordinator(RunBudget(max_model_calls=4, max_tool_calls=8), ProviderRegistry([]))
    outcome = run_plan(
        plan,
        permissions=Permissions(tools=frozenset({"query_ledger", "calculate"}), accounts=frozenset()),
        tools=_tools(),
        budget=budget,
        concurrency=1,
        stream=stream,
    )
    return outcome, sink.read_from("run-of-the-studio")


def test_every_step_of_the_run_has_its_own_event() -> None:
    """A run that publishes no event per step is a run nobody can read."""
    outcome, events = _run()

    started = [event for event in events if event.event_type == "span.started"]
    ended = [event for event in events if event.event_type == "span.ended"]

    assert [event.span_id for event in started] == ["read", "compute"]
    assert [event.span_id for event in ended] == ["read", "compute"]
    assert len(events) == len(outcome.results) * 2 + 2


def test_the_event_of_a_step_names_the_specialist_that_answered_it() -> None:
    """The trace says which specialist answered which part of the question (FR-009)."""
    _, events = _run()

    ended = {event.span_id: event for event in events if event.event_type == "span.ended"}

    assert ended["read"].payload["specialist"] == "ledger_reader"
    assert ended["compute"].payload["specialist"] == "calculator"


def test_the_event_of_a_step_names_the_budget_the_run_had_and_the_reason_it_stopped() -> None:
    """The budget and the reason travel with the event of the step."""
    _, events = _run()

    ended = {event.span_id: event for event in events if event.event_type == "span.ended"}

    for step_id in ("read", "compute"):
        assert ended[step_id].payload["budget"]["max_tool_calls"] == 8
        assert ended[step_id].payload["reason"] == "the step answered"
        assert ended[step_id].payload["status"] == "ok"


def test_the_trace_names_the_plan_and_the_end_of_the_run() -> None:
    """The run publishes the plan it read and the way it ended."""
    _, events = _run()

    kinds = [event.event_type for event in events]
    assert kinds[0] == "plan.created"
    assert kinds[-1] == "run.completed"
