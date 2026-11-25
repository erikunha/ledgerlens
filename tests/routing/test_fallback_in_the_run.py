"""The retry of a failed model inside a run, when the deployment consented to it (ADR-084 and ADR-085).

What they guarantee, and why: (a) a triage that fails is retried with the next model of the cascade of the
deployment, and the run answers with the plan of the retry; (b) the model that failed is never called again, because
the money of the call that failed is already spent; (c) the usage of the retry is booked under the model of the
retry and not under the model that failed; (d) the plan of the retry reaches the caps of the money, so a retry that
does not fit never happens; (e) the consent of the deployment counts the retries of a task, and a task is a call of
a model; (f) the decision of the retry is in the trace and the reason of a stop is in the result; (g) the budget of
the turn is not charged for a call that never happens; (h) the cap that the coordinator recorded is the cap the
result names; (i) the caller that holds no provider builds no runner of the retry; (j) a deployment that consented to
no retry keeps the behaviour it had.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import asyncio
import json
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.errors import GraphBubbleUp
from pydantic import Field

from ledgerlens.agents.budget import (
    NO_FALLBACK,
    BudgetReservationMiddleware,
    TurnBudget,
    cap_sentence,
    shipped_turn_budget,
)
from ledgerlens.agents.fallback import (
    DIRECTION_DOWN,
    DIRECTION_UP,
    FallbackMiddleware,
    FallbackRunner,
    FallbackStopped,
    FallbackStrategy,
    planned_input_of,
    planned_input_of_request,
)
from ledgerlens.agents.integrator import build_integrator, investigate, run_triage
from ledgerlens.byok.budget import BudgetCoordinator
from ledgerlens.byok.registry import ALLOWLIST, ModelProfile, Pricing, ProviderRegistry
from ledgerlens.chains.triage import build_triage_declarative, triage_input_of
from ledgerlens.offline import ScriptedChatModel, text_message
from ledgerlens.run_context import RunBudget

# The cascade of the deployment, from the lightest model to the most capable one.
CASCADE = ("openai:gpt-4.1-mini", "openai:gpt-4.1")

# The consent of a deployment that allowed one retry.
STRATEGY = FallbackStrategy(name="one retry upwards", max_attempts=1, direction=DIRECTION_UP)

# The plan of a triage that answers: the smallest one the schema of the repository accepts.
PLAN = {
    "intent": "refund_discrepancy",
    "entities": {"transaction_ids": ["TX-2096"], "refund_ids": [], "amounts": [], "currencies": [], "dates": []},
    "urgency": "normal",
    "plan": [{"id": "S1", "goal": "read the ledger", "tool": "query_ledger", "depends_on": []}],
    "needs_clarification": False,
    "clarification_question": None,
}

# The same plan with a step that asks for no tool, so the run asks the agent once and the follow-up does not run.
PLAN_WITHOUT_TOOLS = {**PLAN, "plan": [{"id": "S1", "goal": "read the ledger", "tool": None, "depends_on": []}]}


class Failing(BaseChatModel):
    """A model whose provider fails on every call, and that says which model it is."""

    model_name: str = "gpt-4.1-mini"
    calls: list[str] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "failing"

    def bind_tools(self, tools: Any, **kwargs: Any) -> Failing:  # type: ignore[override]
        """The tools of the graph bind to the model, and a model that refuses them never runs."""
        return self

    def _generate(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append(self.model_name)
        raise RuntimeError("the provider is out")


class Answering(BaseChatModel):
    """A model that answers, and that says which model it is."""

    model_name: str = "gpt-4.1"
    reply: str = "the answer of the retry"
    calls: list[str] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "answering"

    def bind_tools(self, tools: Any, **kwargs: Any) -> Answering:  # type: ignore[override]
        """The tools of the graph bind to the model, and a model that refuses them never runs."""
        return self

    def _generate(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append(self.model_name)
        return ChatResult(
            generations=[
                ChatGeneration(
                    message=AIMessage(
                        content=self.reply,
                        usage_metadata={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
                    )
                )
            ]
        )


class Runtime:
    """The runtime of a call, with the ceiling of the turn in it."""

    def __init__(self, turn: TurnBudget | None) -> None:
        self.context = turn


class Request:
    """The request of a model, with the model that runs it and the turn that holds the ceiling."""

    def __init__(self, model: Any, turn: TurnBudget | None = None) -> None:
        self.model = model
        self.messages: list[Any] = []
        self.runtime = Runtime(turn)

    def override(self, **kwargs: Any) -> Any:
        other = Request(self.model, self.runtime.context)
        other.model = kwargs.get("model", self.model)
        other.messages = self.messages
        return other


def _handler(request: Any) -> Any:
    """The call of the model, the way the graph calls it."""
    return request.model.invoke(request.messages)


def _triage_that_answers() -> Any:
    """A triage that reads the question and answers with the plan."""
    return build_triage_declarative(ScriptedChatModel(script=[text_message(json.dumps(PLAN))]))


def _triage_that_fails() -> Any:
    """A triage whose model fails on the first call: the script of the model has no message."""
    return build_triage_declarative(ScriptedChatModel(script=[]))


def _runner(**kwargs: Any) -> FallbackRunner:
    """A runner of the retry, with the factory of the triage of a model."""
    return FallbackRunner(
        cascade=CASCADE,
        strategy=STRATEGY,
        factory=lambda name: _triage_that_answers(),
        **kwargs,
    )


def _turn(caps: RunBudget | None = None, registry: ProviderRegistry | None = None) -> TurnBudget:
    """The ceiling of a turn, with the registry that prices the models of the cascade."""
    caps = caps or RunBudget(max_model_calls=8, max_tool_calls=8)
    return TurnBudget(caps=caps, coordinator=BudgetCoordinator(caps, registry or ProviderRegistry(ALLOWLIST)))


def _priced_registry() -> ProviderRegistry:
    """A registry that prices the two models of the cascade, so the money tells which model spent it.

    Why the price of the retry model is a different one: the tokens of the retry are booked under the model of
    the retry, and a registry that prices the two models differently is the only way to see it in the money.
    """
    return ProviderRegistry(
        [
            ModelProfile(
                profile_id="openai-gpt-4.1-mini",
                provider="openai",
                model_id="gpt-4.1-mini",
                display_name="GPT-4.1 mini",
                capabilities=("chat",),
                status="tested",
                enabled_in_public_demo=True,
                pricing=Pricing(
                    source="manual",
                    last_verified=date(2026, 11, 8),
                    input_per_1m_usd=Decimal("0.40"),
                    output_per_1m_usd=Decimal("1.60"),
                ),
            ),
            ModelProfile(
                profile_id="openai-gpt-4.1",
                provider="openai",
                model_id="gpt-4.1",
                display_name="GPT-4.1",
                capabilities=("chat",),
                status="tested",
                enabled_in_public_demo=True,
                pricing=Pricing(
                    source="manual",
                    last_verified=date(2026, 11, 8),
                    input_per_1m_usd=Decimal("2.00"),
                    output_per_1m_usd=Decimal("8.00"),
                ),
            ),
        ]
    )


def _consent(monkeypatch: pytest.MonkeyPatch, attempts: int = 1, cascade: str = "gpt-4.1-mini,gpt-4.1") -> None:
    """The consent of a deployment: how many retries and the cascade they go through."""
    monkeypatch.setenv("LEDGERLENS_FALLBACK_ATTEMPTS", str(attempts))
    monkeypatch.setenv("LEDGERLENS_FALLBACK_DIRECTION", "up")
    monkeypatch.setenv("LEDGERLENS_MODEL", "gpt-4.1-mini")
    monkeypatch.setenv("LEDGERLENS_MODEL_CASCADE", cascade)


def _usage_of(spans: list[Any]) -> dict[str, Any]:
    """The usage the turn recorded, read from the trace of the investigation."""
    for span in reversed(spans):
        if span.name == "investigate" and isinstance(span.outputs, dict):
            usage = span.outputs.get("usage")
            if usage:
                return dict(usage)
    return {}


# --- the triage of the run -------------------------------------------------------------------------------


def test_the_triage_that_failed_is_retried_with_the_next_model_of_the_cascade() -> None:
    """A failure of the triage with a consent and a budget is retried, and the run answers with the plan."""
    triage = run_triage(
        _triage_that_fails(),
        "the customer says the refund never arrived",
        runner=_runner(),
        model="openai:gpt-4.1-mini",
    )

    assert triage is not None
    assert triage.intent == "refund_discrepancy"
    assert triage.plan


def test_the_model_that_failed_is_not_called_again_by_the_retry() -> None:
    """The call that failed already happened and the money of it is already spent.

    Why it matters: a retry that answers the same model spends the budget of the run twice for the same failure,
    and the count of the calls of the run stops being the count of the calls that happened.
    """
    called: list[str] = []

    def attempt(model: Any) -> Any:
        called.append(model.model_name)
        raise RuntimeError("the provider is out")

    def factory(name: str) -> Any:
        return Answering(model_name=name.split(":", 1)[-1])

    runner = FallbackRunner(cascade=CASCADE, strategy=STRATEGY, factory=factory)
    turn = _turn()

    with pytest.raises(FallbackStopped):
        runner.retry(attempt, failed_model="gpt-4.1-mini", turn=turn)

    assert "gpt-4.1-mini" not in called  # the runner never called the model that failed again
    assert called == ["gpt-4.1"]  # and the retry went to the neighbour of the cascade


def test_the_triage_of_the_run_is_retried_when_the_integrator_carries_the_names_of_the_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The seam of the triage is alive: the integrator names the model of the triage and the run retries it.

    Why it matters: a seam that no caller reaches is a seam that does not exist, and the retry of the triage would
    be a promise that nothing delivers.
    """
    _consent(monkeypatch)
    agent = build_integrator(
        ScriptedChatModel(script=[text_message("the answer")]),
        triage_model=ScriptedChatModel(script=[]),
        model_names={"triage": "openai:gpt-4.1-mini"},
        fallback_factory=lambda name: ScriptedChatModel(script=[text_message(json.dumps(PLAN))]),
    )

    assert agent.triage_model == "openai:gpt-4.1-mini"
    assert agent.triage_fallback is not None
    assert agent.fallback is not None


def test_the_triage_of_the_run_is_retried_with_the_model_of_the_cascade(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The triage of a real integrator fails and the run answers with the plan of the retry.

    Why it matters: the retry of the triage is the piece that saves a run whose plan never arrived, and a piece
    that only the unit test exercises is a piece nobody can rely on.
    """
    _consent(monkeypatch)
    agent = build_integrator(
        ScriptedChatModel(script=[text_message("the answer")]),
        triage_model=ScriptedChatModel(script=[]),
        model_names={"triage": "openai:gpt-4.1-mini"},
        fallback_factory=lambda name: ScriptedChatModel(script=[text_message(json.dumps(PLAN))]),
        verifier=lambda result, *, nli=None: result,
    )

    result = investigate(agent, "Where is my refund?", thread_id="t-triage")

    assert result.triage is not None
    assert result.triage.intent == "refund_discrepancy"


def test_the_name_of_the_model_of_the_triage_is_the_name_of_the_model_when_the_deployment_named_nothing() -> None:
    """A caller that routed nothing still names a model, and the retry of the triage has to know it."""
    agent = build_integrator(ScriptedChatModel(script=[]), triage_model=ScriptedChatModel(script=[]))

    assert agent.triage_model == "ScriptedChatModel"


def test_a_deployment_that_consented_to_no_retry_keeps_the_behaviour_it_had() -> None:
    """Without a runner the triage failure leaves the run without a plan, as it always did."""
    triage = run_triage(
        _triage_that_fails(),
        "the customer says the refund never arrived",
        model="openai:gpt-4.1-mini",
    )

    assert triage is None


def test_a_budget_with_no_room_stops_the_retry_and_the_run_answers_without_a_plan() -> None:
    """The retry that the budget does not cover never happens, and the run answers without a plan."""
    turn = _turn(RunBudget(max_model_calls=1, max_tool_calls=1))

    triage = run_triage(
        _triage_that_fails(),
        "the customer says the refund never arrived",
        runner=_runner(),
        model="openai:gpt-4.1-mini",
        turn=turn,
    )

    assert triage is None
    assert turn.cut_by() == "max_model_calls"


def test_the_retry_of_the_triage_is_reserved_against_the_budget_of_the_turn() -> None:
    """The retry of the triage is a call of a model, and the budget of the turn knows about it."""
    turn = _turn()

    triage = run_triage(
        _triage_that_fails(),
        "the customer says the refund never arrived",
        runner=_runner(),
        model="openai:gpt-4.1-mini",
        turn=turn,
    )

    assert triage is not None
    assert turn.coordinator.report().model_calls == 2
    assert turn.coordinator.report().calls_by_model == {"triage": 1, "gpt-4.1": 1}


def test_a_cap_of_the_tokens_stops_the_retry_of_the_triage_that_does_not_fit() -> None:
    """The plan of the retry of the triage reaches the cap of the tokens, and a retry that does not fit never happens.

    Why it matters: the system message of the triage is the largest part of the call, and a plan built from the
    complaint alone would let a cap of the tokens pass a call that sends it (FR-009). The cap below is below the
    system message of the triage and above the complaint, so it refuses the retry only when the plan is the
    whole call.
    """
    caps = RunBudget(max_model_calls=8, max_tool_calls=8, max_input_tokens=500)
    turn = _turn(caps, _priced_registry())
    answering = ScriptedChatModel(script=[text_message(json.dumps(PLAN))])

    triage = run_triage(
        _triage_that_fails(),
        "the customer says the refund never arrived",
        runner=FallbackRunner(cascade=CASCADE, strategy=STRATEGY, factory=lambda name: answering),
        model="openai:gpt-4.1-mini",
        turn=turn,
    )

    assert triage is None
    assert turn.cut_by() == "max_input_tokens"


# --- the model of the graph ------------------------------------------------------------------------------


def test_the_middleware_of_the_graph_retries_a_failed_call_of_a_model() -> None:
    """A call of a model that fails is run again with the model of the decision.

    Why it matters: the graph of the agent is where the answer of the run is made, and a provider that fails
    once is a provider that fails again.
    """
    failing = Failing()
    answering = Answering()
    middleware = FallbackMiddleware(FallbackRunner(cascade=CASCADE, strategy=STRATEGY, factory=lambda name: answering))

    result = middleware.wrap_model_call(Request(failing), _handler)

    assert result.content == "the answer of the retry"
    assert failing.calls == ["gpt-4.1-mini"]
    assert answering.calls == ["gpt-4.1"]


def test_the_usage_of_the_retry_is_booked_under_the_model_of_the_retry() -> None:
    """The tokens of the retry belong to the model of the retry.

    Why it matters: the coordinator prices the tokens under the model that made them, and a retry booked under
    the model that failed would be priced as another model and would leave the reservation of the retry pending.

    Why the registry of the test prices the two models differently: the price is the only place where the model
    that spent the tokens shows, and the two prices are far enough apart to tell them apart.
    """
    turn = _turn(registry=_priced_registry())
    answering = Answering()
    middleware = FallbackMiddleware(FallbackRunner(cascade=CASCADE, strategy=STRATEGY, factory=lambda name: answering))
    reservation = BudgetReservationMiddleware()

    def reserved_handler(request: Any) -> Any:
        return reservation.wrap_model_call(request, _handler)

    middleware.wrap_model_call(Request(Failing(), turn), reserved_handler)

    report = turn.coordinator.report()
    assert report.calls_by_model == {"gpt-4.1-mini": 1, "gpt-4.1": 1}
    assert report.input_tokens == 100  # the tokens of the retry
    assert report.usage_without_reservation == ()
    # The money of the run is the money of the model of the retry: 100 input and 50 output of gpt-4.1.
    assert report.observed_cost_usd == Decimal("0.000600")


def test_the_retry_of_the_graph_is_reserved_against_the_budget_of_the_turn() -> None:
    """The retry of the graph is a call of a model, and the budget of the turn knows about it.

    Why it matters: a retry that nobody reserved spends the money of the run outside the caps of the run.
    """
    turn = _turn()
    answering = Answering()
    middleware = FallbackMiddleware(FallbackRunner(cascade=CASCADE, strategy=STRATEGY, factory=lambda name: answering))
    reservation = BudgetReservationMiddleware()

    def reserved_handler(request: Any) -> Any:
        return reservation.wrap_model_call(request, _handler)

    middleware.wrap_model_call(Request(Failing(), turn), reserved_handler)

    assert turn.coordinator.report().model_calls == 2
    assert turn.coordinator.report().calls_by_model == {"gpt-4.1-mini": 1, "gpt-4.1": 1}


def test_the_plan_of_the_retry_reaches_the_caps_of_the_money() -> None:
    """A retry whose money does not fit the cap never happens, and the run says which cap stopped it.

    Why it matters: a cap of the money that cannot refuse a retry is a cap that does not hold the run, and the
    money of a retry the run may not spend is the money of a visitor (FR-009).

    Why the retry goes down the cascade: the price of `gpt-4.1` was never verified, and a cap of the money only
    refuses a retry whose price the registry knows (ADR-084).
    """
    caps = RunBudget(max_model_calls=8, max_tool_calls=8, max_estimated_usd=Decimal("0.00000001"))
    turn = _turn(caps)
    answering = Answering(model_name="gpt-4.1-mini")
    downwards = FallbackStrategy(name="one retry downwards", max_attempts=1, direction=DIRECTION_DOWN)
    middleware = FallbackMiddleware(
        FallbackRunner(cascade=CASCADE, strategy=downwards, factory=lambda name: answering)
    )

    with pytest.raises(FallbackStopped) as stopped:
        middleware.wrap_model_call(Request(Failing(model_name="gpt-4.1"), turn), _handler)

    assert answering.calls == []  # the retry never happened
    assert turn.cut_by() == "max_estimated_usd"
    assert "max_estimated_usd" in stopped.value.decision.reason


def test_a_cap_that_the_coordinator_recorded_is_the_cap_the_result_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The turn that stops because the budget refused the retry names the cap that the coordinator recorded.

    Why it matters: a result that says "the retry did not happen" when the budget said "the cap of the calls was
    reached" sends the reader after the wrong problem.
    """
    _consent(monkeypatch)
    answering = Answering()
    built: list[str] = []

    def factory(name: str) -> Any:
        built.append(name)
        return answering

    agent = build_integrator(
        Failing(),
        triage_model=ScriptedChatModel(script=[text_message(json.dumps(PLAN_WITHOUT_TOOLS))]),
        fallback_factory=factory,
        verifier=lambda result, *, nli=None: result,
    )
    # The triage is one call and the model of the graph is the second: the retry would be the third one.
    turn = shipped_turn_budget(RunBudget(max_model_calls=2, max_tool_calls=2))

    result = investigate(agent, "Where is my refund?", thread_id="t-cap", budget=turn)

    assert built == ["openai:gpt-4.1"]  # the retry was reached and the budget refused the call
    assert answering.calls == []  # and the model of the retry never ran
    assert result.recommended_action == "escalate_to_human"
    # The cap that the coordinator recorded is the cap the result names, and not the sentence of a fallback.
    assert any(cap_sentence("max_model_calls", turn.caps) == item for item in result.missing_information)
    assert not any("the retry did not happen" in item for item in result.missing_information)


def test_a_turn_that_stopped_because_the_retry_did_not_happen_names_the_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The result of a turn that stopped says why the retry did not happen.

    Why it matters: a turn that stopped and a model that failed look the same from the outside, and the reader
    of the result has to know which one happened.
    """
    _consent(monkeypatch, cascade="gpt-4.1-mini")  # the cascade holds no other model for the task
    agent = build_integrator(
        Failing(),
        triage_model=ScriptedChatModel(script=[text_message(json.dumps(PLAN))]),
        fallback_factory=lambda name: Answering(),
        verifier=lambda result, *, nli=None: result,
    )

    result = investigate(agent, "Where is my refund?", thread_id="t-stop")

    assert result.recommended_action == "escalate_to_human"
    assert any("the retry did not happen" in item for item in result.missing_information)
    assert any("no other model" in item for item in result.missing_information)


def test_the_graph_answers_with_the_model_of_the_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    """The model of the graph fails and the run answers with the answer of the model of the retry.

    Why it matters: the wiring of the retry is only real when the run answers, and a run that stops with the
    reason of a failure that never happened proves nothing.
    """
    _consent(monkeypatch)
    failing = Failing()
    answering = Answering()
    turn = _turn()
    agent = build_integrator(
        failing,
        triage_model=ScriptedChatModel(script=[text_message(json.dumps(PLAN_WITHOUT_TOOLS))]),
        fallback_factory=lambda name: answering,
        verifier=lambda result, *, nli=None: result,
    )

    result = investigate(agent, "Where is my refund?", thread_id="t-retry", budget=turn)

    assert failing.calls == ["gpt-4.1-mini"]  # the model that failed was called once
    assert answering.calls == ["gpt-4.1"]  # and the retry answered with the model of the cascade above it
    assert result.answer == "the answer of the retry"
    assert result.missing_information == []
    # And the budget of the turn counted both calls under their own model.
    report = turn.coordinator.report()
    assert report.calls_by_model == {"triage": 1, "gpt-4.1-mini": 1, "gpt-4.1": 1}
    assert report.usage_without_reservation == ()


def test_the_decision_of_the_retry_is_in_the_trace(monkeypatch: pytest.MonkeyPatch) -> None:
    """A reader of the trace of a run that retried sees the model of the retry and the reason of it.

    Why it matters: the decision is a value and it is the only thing that carries the model of the retry, and a
    trace without it cannot say what ran.
    """
    _consent(monkeypatch)
    agent = build_integrator(
        Failing(),
        triage_model=ScriptedChatModel(script=[text_message(json.dumps(PLAN))]),
        fallback_factory=lambda name: Answering(),
        verifier=lambda result, *, nli=None: result,
    )
    spans: list[Any] = []

    investigate(agent, "Where is my refund?", thread_id="t-trace", on_event=spans.append)

    usage = _usage_of(spans)
    assert usage.get("fallbacks"), "the trace carries no decision of the retry"
    assert usage["fallbacks"][0]["model"] == "openai:gpt-4.1"
    assert usage["fallbacks"][0]["action"] == "fallback"


def test_the_consent_of_the_deployment_counts_the_retries_of_a_task_and_not_of_the_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A task that fails gets the retries the deployment consented to, and the next task gets its own.

    Why it matters: a consent that is spent by the first task of a session would take the retry away from every
    task that comes after it.
    """
    _consent(monkeypatch, attempts=1)
    agent = build_integrator(
        Failing(),
        triage_model=ScriptedChatModel(script=[text_message(json.dumps(PLAN))]),
        fallback_factory=lambda name: Answering(),
        verifier=lambda result, *, nli=None: result,
    )
    spans: list[Any] = []

    investigate(agent, "Where is my refund?", thread_id="t-one", on_event=spans.append)
    first = _usage_of(spans).get("fallbacks", [])
    spans.clear()
    investigate(agent, "Where is my refund?", thread_id="t-two", on_event=spans.append)
    second = _usage_of(spans).get("fallbacks", [])

    assert first, "the first turn retried nothing"
    assert second, "the second turn did not get its own retry"


def test_the_model_that_keeps_failing_is_retried_as_many_times_as_the_consent_allows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A provider that fails on every call does not get more retries than the deployment consented to.

    Why it matters: a consent that does not bound the retries of a task is not a consent.
    """
    _consent(monkeypatch, attempts=1)
    failing = Failing()
    retrying = Failing()
    agent = build_integrator(
        failing,
        triage_model=ScriptedChatModel(script=[text_message(json.dumps(PLAN_WITHOUT_TOOLS))]),
        fallback_factory=lambda name: retrying,
        verifier=lambda result, *, nli=None: result,
    )

    result = investigate(agent, "Where is my refund?", thread_id="t-failing")

    assert failing.calls == ["gpt-4.1-mini"]  # the model of the graph was called once
    assert retrying.calls == ["gpt-4.1-mini"]  # and the model of the retry once, and no more
    assert result.recommended_action == "escalate_to_human"
    # And the reason of the stop says that the consent of one retry was spent.
    assert any("the run already made 1" in item for item in result.missing_information)


def test_a_signal_of_the_graph_is_not_a_model_that_failed() -> None:
    """An interrupt of the graph goes up and is not retried.

    Why it matters: a signal of the graph is the control of the run and not a failure of a provider, and a retry
    of it would swallow the control and spend the budget of the run for nothing.
    """
    answering = Answering()
    middleware = FallbackMiddleware(FallbackRunner(cascade=CASCADE, strategy=STRATEGY, factory=lambda name: answering))

    def handler(request: Any) -> Any:
        raise GraphBubbleUp("the graph asks a person")

    with pytest.raises(GraphBubbleUp):
        middleware.wrap_model_call(Request(Failing()), handler)

    assert answering.calls == []  # no retry of a signal of the graph


# --- the deployment that says nothing ---------------------------------------------------------------------


def test_a_deployment_that_says_nothing_has_no_retry_in_its_run() -> None:
    """Without the consent of the deployment the integrator carries no runner and no middleware."""
    agent = build_integrator()

    assert agent.fallback is None
    assert agent.triage_fallback is None


def test_the_model_of_the_triage_is_named_even_when_the_caller_named_no_triage_model() -> None:
    """The retry of the triage reads the name of the model of the triage, and a caller that named none still has one.

    Why it matters: a caller that routes nothing still runs a triage, and a triage whose model has no name is a
    triage that can never be retried (ADR-085).
    """
    agent = build_integrator(ScriptedChatModel(script=[]))

    assert agent.triage_model == "ScriptedChatModel"


def test_the_caller_that_holds_no_provider_builds_no_runner_of_the_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The runner is built by the caller that holds the provider, and a caller without one has no runner.

    Why it matters: a runner built out of the global key of the server would spend the money of the server in a
    run that belongs to somebody else (ADR-037, ADR-034).
    """
    _consent(monkeypatch)
    agent = build_integrator(ScriptedChatModel(script=[]))

    assert agent.fallback is None
    assert agent.triage_fallback is None


# --- the budget that says no ------------------------------------------------------------------------------


def test_a_deployment_that_could_not_build_the_model_of_the_retry_is_not_charged_for_it() -> None:
    """A model that cannot be built is not a call, and the budget of the turn does not pay for it.

    Why it matters: the factory of a deployment is `get_chat_model`, and it refuses a model that the provider
    does not have. A reservation of a call that never happens is money that the run of a visitor does not owe.
    """
    turn = _turn()
    runner = FallbackRunner(
        cascade=CASCADE,
        strategy=STRATEGY,
        factory=lambda name: (_ for _ in ()).throw(RuntimeError("the provider does not have that model")),
    )

    with pytest.raises(FallbackStopped) as stopped:
        runner.retry(lambda model: "an answer", failed_model="gpt-4.1-mini", turn=turn)

    assert turn.coordinator.report().model_calls == 0
    assert "could not build the model of the retry" in stopped.value.decision.reason


def test_the_failure_of_the_provider_is_in_the_reason_of_the_stop() -> None:
    """A run that stops because a provider failed says what the provider said.

    Why it matters: the exception of the provider is the only thing that knows what went wrong, and a reader
    that gets a reason without it is left guessing.
    """
    turn = _turn()
    runner = FallbackRunner(cascade=CASCADE, strategy=STRATEGY, factory=lambda name: Answering())

    def attempt(model: Any) -> Any:
        raise RuntimeError("the provider is out of credit")

    with pytest.raises(FallbackStopped) as stopped:
        runner.retry(attempt, failed_model="gpt-4.1-mini", turn=turn, failure=RuntimeError("the provider is out"))

    assert "the provider said: RuntimeError: the provider is out" in stopped.value.decision.reason


def test_a_cascade_that_holds_the_same_model_twice_stops_the_retry() -> None:
    """The neighbour of the failed model cannot be the failed model.

    Why it matters: a retry that answers the same model spends the budget of the run twice for the same failure.
    """
    cascade = ("openai:gpt-4.1-mini", "openai:gpt-4.1-mini")
    runner = FallbackRunner(cascade=cascade, strategy=STRATEGY, factory=lambda name: Answering())
    turn = _turn()

    with pytest.raises(FallbackStopped) as stopped:
        runner.retry(lambda model: "an answer", failed_model="openai:gpt-4.1-mini", turn=turn)

    assert "is the model that failed" in stopped.value.decision.reason


def test_a_cascade_that_holds_the_same_model_again_stops_the_retry_of_the_task() -> None:
    """A model that already failed in this task is not run again, not even from further up the cascade.

    Why it matters: the cascade may hold the same model at two levels, and a retry that walks back onto it
    spends the money of the failure twice for the same task.
    """
    cascade = ("openai:gpt-4.1-mini", "openai:gpt-4.1", "openai:gpt-4.1-mini")
    runner = FallbackRunner(
        cascade=cascade,
        strategy=FallbackStrategy(name="two retries upwards", max_attempts=2, direction=DIRECTION_UP),
        factory=lambda name: Answering(),
    )
    turn = _turn()

    with pytest.raises(FallbackStopped) as stopped:
        runner.retry(
            lambda model: (_ for _ in ()).throw(RuntimeError("the provider is out")),
            failed_model="openai:gpt-4.1-mini",
            turn=turn,
        )

    assert "already failed in this task" in stopped.value.decision.reason


def test_a_turn_that_does_not_own_the_counting_does_not_retry() -> None:
    """The side that holds the provider is the one that reserves, and a turn that does not count refuses the retry.

    Why it matters: a retry that nobody reserves spends the money of the run outside the caps of the run
    (ADR-054).
    """
    turn = shipped_turn_budget(RunBudget(max_model_calls=8, max_tool_calls=8), owner="caller")
    runner = FallbackRunner(cascade=CASCADE, strategy=STRATEGY, factory=lambda name: Answering())

    with pytest.raises(FallbackStopped) as stopped:
        runner.retry(lambda model: "an answer", failed_model="gpt-4.1-mini", turn=turn)

    assert "does not own the counting" in stopped.value.decision.reason


def test_the_decision_of_a_stop_is_in_the_trace() -> None:
    """A turn that stopped because the retry did not happen carries the decision of the stop.

    Why it matters: the decision is the only thing that says which model the retry would have used and why it
    did not happen (ADR-084).
    """
    turn = _turn()
    runner = FallbackRunner(cascade=CASCADE, strategy=STRATEGY, factory=lambda name: Answering())

    with pytest.raises(FallbackStopped):
        # The model that failed is the last of the cascade: the retry has no model to run with.
        runner.retry(lambda model: "an answer", failed_model="openai:gpt-4.1", turn=turn)

    assert turn.state.fallbacks
    assert turn.state.fallbacks[-1]["action"] == "stop"
    assert turn.state.fallbacks[-1]["reason"]


def test_the_plan_of_the_retry_carries_the_system_message_of_the_run() -> None:
    """The plan of the retry is the whole call and not only the messages of the request.

    Why it matters: the system message of the run is the largest part of the call, and a plan that leaves it out
    would let a cap of the tokens pass a call that sends it (FR-009).
    """
    request = Request(Failing())
    request.system_message = SystemMessage(content="x" * 400)

    assert planned_input_of_request(request) >= 100


def test_the_plan_of_the_retry_of_the_triage_carries_the_system_message_of_the_triage() -> None:
    """The plan of the retry of the triage is the whole prompt of the triage, system message included.

    Why it matters: the system message of the triage is the largest part of the call, and a plan that left it
    out would let a cap of the tokens pass a call that sends it (FR-009). The complaint alone is a small part
    of the call, and a plan built from it alone undercounts the call by two orders of magnitude.
    """
    complaint = "Where is my refund of 17.48 dollars?"

    plan = planned_input_of(triage_input_of(complaint))
    complaint_only = planned_input_of([HumanMessage(content=complaint)])

    # The system message of the triage is 4518 characters, and the complaint is a few dozen.
    assert plan > 1000
    assert plan > complaint_only * 10


def test_the_asynchronous_path_of_the_retry_awaits_the_call() -> None:
    """The asynchronous path of the middleware retries and awaits the answer of the retry.

    Why it matters: a path that awaits a tuple raises a TypeError and the run breaks instead of retrying.
    """

    async def scenario() -> Any:
        answering = Answering()
        middleware = FallbackMiddleware(
            FallbackRunner(cascade=CASCADE, strategy=STRATEGY, factory=lambda name: answering)
        )

        async def handler(request: Any) -> Any:
            return await request.model.ainvoke(request.messages)

        return await middleware.awrap_model_call(Request(Failing()), handler)

    result = asyncio.run(scenario())

    assert result.content == "the answer of the retry"


def test_the_usage_of_the_retry_of_the_triage_answers_its_reservation() -> None:
    """The retry of the triage is a call of a model and the budget of the turn counts it.

    Why it matters: a call that the budget of the run does not count is a call whose money nobody holds, and the
    money of the triage of the run is part of the bill of the run (FR-012).
    """
    turn = _turn()

    triage = run_triage(
        _triage_that_fails(),
        "the customer says the refund never arrived",
        runner=_runner(),
        model="openai:gpt-4.1-mini",
        turn=turn,
    )

    assert triage is not None
    assert turn.coordinator.report().calls_by_model == {"triage": 1, "gpt-4.1": 1}


def test_a_deployment_that_built_no_model_is_not_charged_for_the_retry() -> None:
    """A retry that cannot happen is not reserved, and the budget of the turn does not pay for it.

    Why it matters: a reservation of a call that never happens is money that the run of a visitor does not owe.
    """
    turn = _turn()
    runner = FallbackRunner(cascade=CASCADE, strategy=STRATEGY, factory=None)

    with pytest.raises(FallbackStopped) as stopped:
        runner.retry(lambda name: "an answer", failed_model="gpt-4.1-mini", turn=turn)

    assert turn.coordinator.report().model_calls == 0
    assert "built no model" in stopped.value.decision.reason


def test_a_plan_that_the_budget_cannot_count_stops_the_run_with_the_reason() -> None:
    """A plan with a negative count is not a plan, and the run stops with the reason instead of raising.

    Why it matters: an exception that nobody expected is not a result, and the reader of the run would see a
    crash where the truth is a refusal.
    """
    turn = _turn()
    runner = FallbackRunner(cascade=CASCADE, strategy=STRATEGY, factory=lambda name: "an answer")

    with pytest.raises(FallbackStopped) as stopped:
        runner.retry(
            lambda name: "an answer",
            failed_model="gpt-4.1-mini",
            turn=turn,
            planned_input_tokens=-1,
        )

    assert stopped.value.decision.action == "stop"
    assert "refused the plan" in stopped.value.decision.reason


def test_the_reason_of_a_stop_names_the_model_that_the_retry_would_have_used() -> None:
    """A stop that the budget caused says which model the budget refused.

    Why it matters: the decision of a stop carries no model, because no model ran the retry, and the reason is
    then the only thing that tells a reader which model the run would have used (ADR-085).
    """
    turn = _turn(caps=RunBudget(max_model_calls=0, max_tool_calls=1))
    runner = FallbackRunner(cascade=CASCADE, strategy=STRATEGY, factory=lambda name: Answering())

    with pytest.raises(FallbackStopped) as stopped:
        runner.retry(lambda name: "an answer", failed_model="openai:gpt-4.1-mini", turn=turn)

    assert stopped.value.decision.action == "stop"
    assert stopped.value.decision.model is None
    # The name of the model of the retry, and not the name of the model that failed.
    assert "with the model openai:gpt-4.1:" in stopped.value.decision.reason


def test_the_sentence_of_the_cut_names_the_retry_and_not_a_cap() -> None:
    """The cut of a fallback is not a cap, and the sentence of the result says what happened.

    Why it matters: a sentence that names a cap that was never reached sends the reader after the wrong problem.
    """
    sentence = cap_sentence(NO_FALLBACK)

    assert "the retry did not happen" in sentence
    assert "the consent of the deployment" in sentence
    assert "the remaining budget of the run" in sentence
    assert "the cap" not in sentence
