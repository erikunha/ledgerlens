"""The scheduler: the independent steps of a plan under a concurrency cap, spending from the budget of the run.

Why every step spends from the budget of the run and not from a budget of its own: a fan-out that spends more than
the single agent would spend buys a worse answer for a bigger bill, and no measurement would survive it (FR-003).

Why the run stops at the cap with the name of the cap: a run that stops without saying why is a run that the reader
cannot compare with the arm that did not stop (SC-003).

Why the steps that may run at the same time run under a cap and not all at once: a fan-out without a cap spends the
budget of the run in one moment, and the budget of the run is the contract of the dispatch.

Why the coordinator of the run is the only thing that enforces the caps: ADR-034 and ADR-054 put the enforcement in
one place, and a second enforcer would be a second source of the truth about what the run may spend.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from ledgerlens.byok.budget import BudgetCoordinator, BudgetExceededError
from ledgerlens.observability.trace_event import TraceEvent, TraceEventDraft, TraceEventStream
from ledgerlens.orchestration.dispatcher import Permissions, dispatch
from ledgerlens.orchestration.plan import PlanRefused, steps_in_order
from ledgerlens.schemas import OrchestrationPlan, OrchestrationStep, StepResult

__all__ = ["RunOutcome", "run_plan"]

# The payload of the trace of a step: the specialist that answered it, the tool it called, the budget the run had and
# the reason the step stopped.
_PAYLOAD_KEYS = ("specialist", "tool", "budget", "reason", "status", "step_id", "spend_usd")


@dataclass(frozen=True)
class RunOutcome:
    """What a run of the studio produced: the results of the steps, the cap that stopped it and the trace.

    Why the partial result travels with the cap: a run that a cap stopped did not fail, and a reader that sees only
    the cap cannot tell what the run did before it stopped (SC-003).
    """

    results: tuple[StepResult, ...]
    cut_by: str | None
    events: tuple[TraceEvent, ...]
    plan: OrchestrationPlan

    @property
    def stopped_by_a_cap(self) -> bool:
        """Whether a cap of the budget stopped the run."""
        return self.cut_by is not None


def _waves(steps: list[OrchestrationStep]) -> list[list[OrchestrationStep]]:
    """The steps of the plan in the waves they may run in: a wave waits for the wave before it.

    Why the waves are computed and not the threads that are started: two steps of the same wave do not depend on each
    other, and a step of the next wave waits for every step of the wave before it.
    """
    waves: list[list[OrchestrationStep]] = []
    placed: set[str] = set()
    remaining = list(steps)
    while remaining:
        wave = [step for step in remaining if all(dependency in placed for dependency in step.depends_on)]
        if not wave:
            raise PlanRefused(f"the plan has no step that may run: {[step.id for step in remaining]}")
        waves.append(wave)
        placed.update(step.id for step in wave)
        remaining = [step for step in remaining if step.id not in placed]
    return waves


def _budget_payload(budget: BudgetCoordinator) -> dict[str, Any]:
    """The caps of the run as the trace carries them: what the step had, and not what it spent."""
    caps = budget.caps
    return {
        "max_model_calls": caps.max_model_calls,
        "max_tool_calls": caps.max_tool_calls,
        "max_estimated_usd": None if caps.max_estimated_usd is None else str(caps.max_estimated_usd),
    }


def run_plan(
    plan: OrchestrationPlan,
    *,
    permissions: Permissions,
    tools: Mapping[str, Callable[[Mapping[str, Any]], Any]],
    budget: BudgetCoordinator,
    concurrency: int = 2,
    stream: TraceEventStream | None = None,
) -> RunOutcome:
    """The run of the plan: the steps in their waves, under the cap of the concurrency, spending from the budget.

    Why the plan is validated before anything runs: a plan with a cycle has no order, and the refusal happens
    before the first tool call, so a plan that cannot run never spends anything (FR-005).

    Why the reservation of the budget happens before the call of the tool: the cap has to be checked before the money
    is spent, and a step that ran outside the budget spent money that the run was not allowed to spend (FR-003).
    """
    ordered = steps_in_order(plan)
    events: list[TraceEvent] = []

    def _emit(draft: TraceEventDraft) -> None:
        if stream is None:
            return
        event = stream.emit(draft)
        if event is not None:
            events.append(event)

    _emit(
        TraceEventDraft(
            event_type="plan.created",
            payload={
                "steps": len(plan.steps),
                "snapshot": plan.snapshot,
                "specialists": sorted({step.specialist for step in plan.steps if step.specialist}),
            },
        )
    )

    lock = threading.Lock()
    results: list[StepResult] = []
    cut_by: str | None = None
    spent = Decimal("0")

    def _run(step: OrchestrationStep) -> StepResult:
        """One step: the reservation of the budget, the call of the tool and the event of the trace."""
        nonlocal spent, cut_by
        with lock:
            if cut_by is not None:
                # The run already stopped, so the step never runs and never spends.
                return StepResult(
                    step_id=step.id,
                    status="skipped",
                    error=f"the run stopped at the cap {cut_by}",
                    specialist=step.specialist,
                )
            try:
                budget.reserve_tool_call()
            except BudgetExceededError as exceeded:
                cut_by = exceeded.cap
                return StepResult(
                    step_id=step.id,
                    status="refused",
                    error=f"the run stopped at the cap {exceeded.cap}",
                    specialist=step.specialist,
                )
        # The tool is called outside of the lock, because the concurrency of the wave is the point of the wave.
        result = dispatch(step, permissions=permissions, tools=tools, spend=spent)
        with lock:
            if result.spend_usd is not None:
                spent += result.spend_usd
            if permissions.max_spend_usd is not None and spent > permissions.max_spend_usd:
                # The money of the step was really spent, so the run stops with the name of the cap and the result
                # of the step is published: a run that stopped at the cap did what it did before it stopped.
                cut_by = "max_spend_usd"
        _emit(
            TraceEventDraft(
                event_type="span.started",
                span_id=step.id,
                payload={
                    "step_id": step.id,
                    "specialist": step.specialist,
                    "tool": step.tool,
                    "budget": _budget_payload(budget),
                },
            )
        )
        _emit(
            TraceEventDraft(
                event_type="span.ended",
                span_id=step.id,
                payload={
                    "step_id": step.id,
                    "specialist": result.specialist,
                    "tool": step.tool,
                    "status": result.status,
                    "spend_usd": None if result.spend_usd is None else str(result.spend_usd),
                    "reason": result.error or "the step answered",
                    "budget": _budget_payload(budget),
                },
            )
        )
        return result

    for wave in _waves(ordered):
        with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
            wave_results = list(pool.map(_run, wave))
        results.extend(wave_results)
        if cut_by is not None:
            break

    order = {step.id: index for index, step in enumerate(ordered)}
    results.sort(key=lambda result: order.get(result.step_id, len(order)))
    _emit(
        TraceEventDraft(
            event_type="run.failed" if cut_by else "run.completed",
            payload={
                "steps": len(results),
                "reason": f"the run stopped at the cap {cut_by}" if cut_by else "the run answered every step",
                "budget": _budget_payload(budget),
            },
        )
    )
    return RunOutcome(results=tuple(results), cut_by=cut_by, events=tuple(events), plan=plan)
