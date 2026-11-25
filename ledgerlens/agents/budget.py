"""The ceiling of one turn of the agent loop: the caps, the reservation of the calls and the record of what it spent.

Why it exists: the agent loop had no ceiling in the paths that ship. The demo and the evaluation called
`investigate` with no budget, so the graph of the agent ran with the default of the library (9999 steps) and a
model that loops cost an unbounded number of calls of a provider and an unbounded wall clock (ADR-054).

What lives here and not in the integrator: how the caps become a limit of the graph (the `recursion_limit`),
what the graph gets when the caller gave no cap of the calls of the models at all (the backstop of the
product), how a call is counted (the coordinator of the run context, the only thing that enforces the caps,
ADR-034) and how the numbers of the turn are read back. The integrator wires the three together and turns
an exhausted budget into a result for a human.

The caps live in the `RunBudget` of the run context (`ledgerlens/run_context.py`), because ADR-034 put them
there, and the enforcement lives in the `BudgetCoordinator` (`ledgerlens/byok/budget.py`), because that is the
only thing that enforces them. A second enforcer would be a second source of the truth about the caps.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ToolCallRequest

from ledgerlens.byok.budget import BudgetCoordinator
from ledgerlens.byok.registry import ProviderRegistry
from ledgerlens.run_context import SHIPPED_RUN_BUDGET, RunBudget

__all__ = [
    "BudgetReservationMiddleware",
    "CHARS_PER_TOKEN",
    "GRAPH_HEADROOM",
    "GRAPH_STEP_BACKSTOP",
    "GRAPH_STEPS",
    "NO_FALLBACK",
    "Owner",
    "PLANNED_OUTPUT_TOKENS",
    "STEPS_PER_MODEL_CALL",
    "TurnBudget",
    "TurnState",
    "cap_sentence",
    "caps_of",
    "derived_recursion_limit",
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

# The ceiling of the steps of the graph that a turn gets when the caller gave no cap of the calls of the
# models: the backstop of the product. It is the number the shipped paths derive (twelve calls of a model and
# the headroom), so a turn that nobody bounded is no longer than a turn of the shipped paths and no path that
# reaches the graph is unbounded (ADR-054).
#
# Why it is not a cap of the run: nobody gave one. A turn that the backstop stops is therefore not stopped by
# a cap, and the sentence that names the cut says so instead of naming a cap that nobody gave.
GRAPH_STEP_BACKSTOP = STEPS_PER_MODEL_CALL * (SHIPPED_RUN_BUDGET.max_model_calls or 0) + GRAPH_HEADROOM

# The name of the cut when the graph ran out of steps and the caller gave no cap of the calls of the models.
# It is not the name of a cap of the run: naming one would say that a caller gave a cap that it gave not.
GRAPH_STEPS = "graph_steps"

# The name of the cut when a model failed and the retry did not happen (ADR-084). It is not the name of a cap
# either: the turn did not reach a limit, the deployment consented to no retry or the budget did not cover it.
NO_FALLBACK = "no_fallback"

# The number of characters that one token of a text is worth. The rule is rough and it is only used to plan the
# tokens of a call, never to report them: the observed tokens are the ones the provider counted (FR-010).
CHARS_PER_TOKEN = 4

# The number of output tokens a call plans when the request says nothing. The plan is an estimate and the estimate
# is what the cap on the money is checked against, so it is bounded and small (FR-009).
PLANNED_OUTPUT_TOKENS = 512

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


@dataclass
class TurnState:
    """What a turn remembers while it runs: the decisions of the fallback and the call that the fallback reserved
    before it made it.

    Why it is a box and not a field of the ceiling: the ceiling of a turn is a frozen value, and these two things
    have to change while the turn runs. The box is per turn, so two turns of the same session never share a
    decision (ADR-084).

    Why the count of the retries is not here: the consent of the deployment says how many retries a task may get,
    and a task is a call of a model, so the count of the retries is the count of the call and it lives with the
    call (ADR-084).
    """

    # The decisions of the fallback of the turn, in the shape the trace carries.
    fallbacks: list[dict[str, Any]] = field(default_factory=list)
    # The identifier of the model whose call the fallback reserved before it made it. The reservation of the
    # graph reads it and does not reserve that call twice (ADR-084).
    reserved_next: str | None = None


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
    # What the turn remembers while it runs: the decisions of the fallback and the reservation that the fallback
    # made. The box is per turn, and the ceiling above it never changes (ADR-084).
    state: TurnState = field(default_factory=TurnState)

    def record_fallback(self, decision: dict[str, Any]) -> None:
        """Keeps the decision of a retry, so the trace of the turn shows the model of the retry and the reason."""
        self.state.fallbacks.append(decision)

    def mark_reserved(self, model_id: str) -> None:
        """Says that the next call of a model is already reserved, and under which identifier.

        Why the mark exists: the fallback reserves the call of a retry before it makes it, with the plan of the
        retry, and the reservation of the graph would reserve it a second time and count the same call twice
        (ADR-084).
        """
        self.state.reserved_next = model_id

    def take_reserved(self) -> str | None:
        """The identifier of the model whose call was already reserved, and the mark is consumed."""
        model_id = self.state.reserved_next
        self.state.reserved_next = None
        return model_id

    def clear_reserved(self) -> None:
        """Drops the mark of a reserved call, for the caller that made it and did not need it."""
        self.state.reserved_next = None

    def reserve_model_call(
        self,
        model_id: str,
        *,
        planned_input_tokens: int | None = None,
        planned_output_tokens: int | None = None,
    ) -> None:
        """Asks the coordinator for one call of a model, when this module owns the counting.

        The reservation happens before the provider is called, so the money of a call the budget does not allow
        is never spent (FR-009).

        Why the planned tokens are arguments: a cap of the tokens and a cap of the money are caps of a planned
        call, and a call without a plan has no cost to check, so a retry that does not say what it plans would
        pass a cap of the money that it does not fit.
        """
        if self.owner == "integrator":
            self.coordinator.reserve_model_call(
                model_id,
                planned_input_tokens=planned_input_tokens,
                planned_output_tokens=planned_output_tokens,
            )

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


def derived_recursion_limit(caps: RunBudget) -> int | None:
    """The ceiling of the steps of the graph that the cap of the calls of the models derives.

    Why it is computed and not written down: the number that stops the loop of the graph and the number that
    stops the provider have to come from the same cap, or the graph would cut a turn the budget allows and
    the budget would allow a turn the graph cuts (ADR-054).

    Why it can be nothing: a run that gave no cap of the calls of the models gave no limit at all (the
    `RunBudget` of the run context says that what is not given is not a limit). The graph then gets the
    backstop of the product (`recursion_limit_for`) and not a cap that nobody gave.
    """
    calls = caps.max_model_calls
    if calls is None:
        return None
    return STEPS_PER_MODEL_CALL * calls + GRAPH_HEADROOM


def recursion_limit_for(caps: RunBudget) -> int:
    """The ceiling of the steps of the graph that a turn with these caps gets.

    The derived one when the caller gave a cap of the calls of the models, and the backstop of the product
    when it gave none: no path that reaches the graph is unbounded (ADR-054), and the backstop is not a cap
    of the run, so the cut of the graph is never named after a cap that nobody gave.
    """
    derived = derived_recursion_limit(caps)
    return GRAPH_STEP_BACKSTOP if derived is None else derived


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

    The ceiling of the graph is not a cap of the run, so the sentence names it as what it is: a run that gave
    no cap of the calls of the models was not stopped by a cap (ADR-054). A cap that has no value is named
    without a number too, because a number that nobody gave is a number of nothing.
    """
    if cap == NO_FALLBACK:
        return (
            "a model of the turn failed and the retry did not happen: the consent of the deployment, the retries it "
            "left, the cascade of the deployment or the remaining budget of the run did not allow it, so the turn "
            "stops and a person takes it over"
        )
    if cap == GRAPH_STEPS:
        return (
            "the ceiling of the graph stopped the turn: the turn reached the ceiling of "
            f"{GRAPH_STEP_BACKSTOP} steps of the graph, so the turn stops and a person takes it over"
        )
    label = _CAP_LABELS.get(cap, cap)
    limit = _limit_of(cap, caps)
    reached = f"the cap of {limit} {label}" if limit is not None else f"the cap of {label}"
    return (
        f"the cap '{cap}' stopped the turn: the turn reached {reached}, "
        "so the turn stops and a person takes it over"
    )


def _limit_of(cap: str, caps: RunBudget | None) -> str | None:
    """The value of the cap that stopped the turn, as the text the result reads.

    `None` when the run gave no value for the cap: the sentence then names the cap without a number.
    """
    if caps is None:
        return None
    value = getattr(caps, cap, None)
    return None if value is None else str(value)


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

    Why it does not reserve a call that the fallback already reserved: the fallback reserves the call of a
    retry before it makes it, with the plan of that retry, and reserving it here a second time would count the
    same call twice and would check the caps without the plan (ADR-084). The usage of that call is booked under
    the identifier the fallback reserved it under, so the reservation and the usage answer each other.
    """

    def wrap_model_call(self, request: ModelRequest, handler: Callable[[ModelRequest], Any]) -> Any:
        """Reserves the call of the model, runs it and records what the provider reported."""
        turn = turn_of(request.runtime)
        model_id = model_id_of(request.model)
        reserved = turn.take_reserved() if turn is not None else None
        if turn is not None and reserved is None:
            turn.reserve_model_call(model_id)
        response = handler(request)
        if turn is not None:
            turn.record_model_usage(reserved or model_id, **_tokens_of(response))
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
        reserved = turn.take_reserved() if turn is not None else None
        if turn is not None and reserved is None:
            turn.reserve_model_call(model_id)
        response = await handler(request)
        if turn is not None:
            turn.record_model_usage(reserved or model_id, **_tokens_of(response))
        return response

    async def awrap_tool_call(
        self, request: ToolCallRequest, handler: Callable[[ToolCallRequest], Awaitable[Any]]
    ) -> Any:
        """The asynchronous path of the reservation of a tool."""
        turn = turn_of(request.runtime)
        if turn is not None:
            turn.reserve_tool_call()
        return await handler(request)
