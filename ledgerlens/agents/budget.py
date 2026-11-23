"""The ceiling of one turn of the agent loop: the caps, the reservation of the calls and the record of what it spent.

Why it exists: the agent loop had no ceiling in the paths that ship. The demo and the evaluation called
`investigate` with no budget, so the graph of the agent ran with the default of the library (9999 steps) and a
model that loops cost an unbounded number of calls of a provider and an unbounded wall clock (ADR-054).

What lives here and not in the integrator: how the caps become a limit of the graph (the `recursion_limit`),
how a call is counted (the coordinator of the run context, the only thing that enforces the caps, ADR-034) and
how the numbers of the turn are read back. The integrator wires the three together and turns an exhausted
budget into a result for a human.

The caps live in the `RunBudget` of the run context (`ledgerlens/run_context.py`), because ADR-034 put them
there, and the enforcement lives in the `BudgetCoordinator` (`ledgerlens/byok/budget.py`), because that is the
only thing that enforces them. A second enforcer would be a second source of the truth about the caps.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ToolCallRequest

from ledgerlens.byok.budget import BudgetCoordinator
from ledgerlens.byok.registry import ProviderRegistry
from ledgerlens.run_context import SHIPPED_RUN_BUDGET, RunBudget

__all__ = [
    "BudgetReservationMiddleware",
    "TurnBudget",
    "cap_sentence",
    "caps_of",
    "model_id_of",
    "recursion_limit_for",
    "shipped_turn_budget",
    "turn_of",
    "usage_of",
]

# The steps of the graph that one call of the model takes: the node of the model and the node of the tools. The
# limit of the graph is computed from it, so the graph stops a turn that loops and not a turn that works.
STEPS_PER_MODEL_CALL = 2

# The steps the graph needs besides the calls: the first call of the turn and the answer that ends it. The
# headroom keeps a turn that uses the whole cap from being cut by the graph before the reservation cuts it.
GRAPH_HEADROOM = 4

# Who counts the calls of a turn. The integrator counts when nobody else does (the demo and the evaluation),
# the caller counts when it holds the provider (the live path) and nobody counts when the graph was built
# elsewhere and the side that holds the provider counts on its own.
Owner = Literal["integrator", "caller", "none"]

# The value of every cap, in the words the result of a cut turn reads.
_CAP_LABELS = {
    "max_model_calls": "model calls",
    "max_tool_calls": "tool calls",
    "max_wall_seconds": "seconds",
    "max_input_tokens": "input tokens",
    "max_output_tokens": "output tokens",
    "max_estimated_usd": "US$",
}


@dataclass(frozen=True)
class TurnBudget:
    """The ceiling of one turn: the caps, the coordinator that counts them and the side that owns the counting.

    The owner is what keeps the counters from being counted twice: the reservation belongs to the side that
    holds the provider (ADR-054). The integrator counts only when nobody else does, and a caller that hands a
    coordinator in is the one that counts.
    """

    caps: RunBudget
    coordinator: BudgetCoordinator
    owner: Owner = "integrator"

    def reserve_model_call(self, model_id: str) -> None:
        """Asks the coordinator for one call of a model, when this module owns the counting.

        The reservation happens before the provider is called, so the money of a call the budget does not allow
        is never spent (FR-009).
        """
        if self.owner == "integrator":
            self.coordinator.reserve_model_call(model_id)

    def reserve_tool_call(self) -> None:
        """Asks the coordinator for one call of a tool, when this module owns the counting.

        Why the wall clock is checked here too: a turn that spends its time in the tools spends it without
        calling a model, and the cap of the wall clock is a cap of the turn (SC-003).
        """
        if self.owner == "integrator":
            self.coordinator.reserve_tool_call()

    def record_model_usage(self, model_id: str, *, input_tokens: int = 0, output_tokens: int = 0) -> None:
        """Records what the provider reported for a call of the model, when this module owns the counting.

        The provider is the only one who knows what the call really cost, so the tokens it reported are the
        ones the cap of the tokens is checked against (FR-009).
        """
        if self.owner == "integrator":
            self.coordinator.record_model_usage(model_id, input_tokens=input_tokens, output_tokens=output_tokens)

    def cut_by(self) -> str | None:
        """The cap that stopped the turn, when one did."""
        return self.coordinator.report().cut_by


def shipped_turn_budget(caps: RunBudget | None = None, *, owner: Owner = "integrator") -> TurnBudget:
    """The ceiling of a turn that nobody bounded: the caps of the core and a coordinator that counts them.

    The registry is empty on purpose: the price of the model of the demo and of the evaluation is unknown, so
    the money of the turn is unknown too and never zero (FR-011).
    """
    caps = caps or SHIPPED_RUN_BUDGET
    return TurnBudget(caps=caps, coordinator=BudgetCoordinator(caps, ProviderRegistry([])), owner=owner)


def recursion_limit_for(caps: RunBudget) -> int:
    """The ceiling of the steps of the graph, computed from the cap of the calls of the models.

    Why it is computed and not written down: the number that stops the loop of the graph and the number that
    stops the provider have to come from the same cap, or the graph would cut a turn the budget allows and
    the budget would allow a turn the graph cuts (ADR-054).
    """
    calls = caps.max_model_calls or SHIPPED_RUN_BUDGET.max_model_calls or 1
    return STEPS_PER_MODEL_CALL * calls + GRAPH_HEADROOM


def caps_of(caps: RunBudget) -> dict[str, Any]:
    """The caps of a turn, in the shape the trace carries."""
    return {
        "max_model_calls": caps.max_model_calls,
        "max_tool_calls": caps.max_tool_calls,
        "max_wall_seconds": caps.max_wall_seconds,
    }


def usage_of(coordinator: BudgetCoordinator) -> dict[str, Any]:
    """What the turn spent, in the shape the trace carries: the calls, the tokens, the time and the two costs.

    The money is a text or nothing at all: a turn whose price is unknown shows no amount, because a zero would
    read as "the model was free" (FR-011).
    """
    report = coordinator.report()
    return {
        "model_calls": report.model_calls,
        "tool_calls": report.tool_calls,
        "input_tokens": report.input_tokens,
        "output_tokens": report.output_tokens,
        "elapsed_seconds": round(report.elapsed_seconds, 3),
        "observed_cost_usd": None if report.observed_cost_usd is None else str(report.observed_cost_usd),
        "estimated_cost_usd": None if report.estimated_cost_usd is None else str(report.estimated_cost_usd),
        "price_known": report.price_known,
        "cut_by": report.cut_by,
    }


def cap_sentence(cap: str, caps: RunBudget | None = None) -> str:
    """The sentence that names the cap that stopped the turn and the value it had.

    It says the same as the refusal of the coordinator (FR-009): whoever reads the result has to know which
    limit was reached, because a turn that stopped and a model that failed look the same from the outside.
    """
    label = _CAP_LABELS.get(cap, cap)
    limit = _limit_of(cap, caps)
    return (
        f"the cap '{cap}' stopped the turn: the turn reached the cap of {limit} {label}, "
        "so the turn stops and a person takes it over"
    )


def _limit_of(cap: str, caps: RunBudget | None) -> str:
    """The value of the cap that stopped the turn, as the text the result reads."""
    if caps is None:
        return "the limit"
    value = getattr(caps, cap, None)
    return "the limit" if value is None else str(value)


def turn_of(runtime: Any) -> TurnBudget | None:
    """The ceiling of the turn that is running, or `None` when the run carries none.

    The ceiling travels with the run as its context, because a turn is one invocation of the graph and the
    follow-up is another invocation of the same turn.
    """
    context = getattr(runtime, "context", None)
    return context if isinstance(context, TurnBudget) else None


def model_id_of(model: Any) -> str:
    """The name the coordinator counts the call of a model under.

    Every model of the turn counts against the same cap, whatever its name (FR-012).
    """
    for attribute in ("model_name", "model", "model_id"):
        try:
            value = getattr(model, attribute, None)
        except Exception:  # a property that cannot answer is not a name
            continue
        if isinstance(value, str) and value:
            return value
    return type(model).__name__


def _tokens_of(response: Any) -> dict[str, int]:
    """The tokens the provider reported for a call of a model."""
    message: Any = response
    result = getattr(response, "result", None)
    if isinstance(result, list) and result:
        message = getattr(result[0], "message", result[0])
    usage = getattr(message, "usage_metadata", None) or {}
    return {
        "input_tokens": int(usage.get("input_tokens") or 0),
        "output_tokens": int(usage.get("output_tokens") or 0),
    }


class BudgetReservationMiddleware(AgentMiddleware):
    """Asks the ceiling of the turn before every call of a model and every call of a tool.

    Why the reservation is here and not in the model: the cap has to be checked before the provider is called,
    and the coordinator is the only thing that enforces the caps (ADR-034, ADR-054).

    Why it does nothing when the turn carries the ceiling of somebody else: the side that holds the provider
    is the one that reserves (the live path), and a second counter would count the same calls twice (ADR-054).
    """

    def wrap_model_call(self, request: ModelRequest, handler: Callable[[ModelRequest], Any]) -> Any:
        """Reserves the call of the model, runs it and records what the provider reported."""
        turn = turn_of(request.runtime)
        model_id = model_id_of(request.model)
        if turn is not None:
            turn.reserve_model_call(model_id)
        response = handler(request)
        if turn is not None:
            turn.record_model_usage(model_id, **_tokens_of(response))
        return response

    def wrap_tool_call(self, request: ToolCallRequest, handler: Callable[[ToolCallRequest], Any]) -> Any:
        """Reserves the call of the tool before the tool runs."""
        turn = turn_of(request.runtime)
        if turn is not None:
            turn.reserve_tool_call()
        return handler(request)

    async def awrap_model_call(self, request: ModelRequest, handler: Callable[[ModelRequest], Awaitable[Any]]) -> Any:
        """The asynchronous path of the reservation: the same caps, awaited."""
        turn = turn_of(request.runtime)
        model_id = model_id_of(request.model)
        if turn is not None:
            turn.reserve_model_call(model_id)
        response = await handler(request)
        if turn is not None:
            turn.record_model_usage(model_id, **_tokens_of(response))
        return response

    async def awrap_tool_call(
        self, request: ToolCallRequest, handler: Callable[[ToolCallRequest], Awaitable[Any]]
    ) -> Any:
        """The asynchronous path of the reservation of a tool."""
        turn = turn_of(request.runtime)
        if turn is not None:
            turn.reserve_tool_call()
        return await handler(request)
