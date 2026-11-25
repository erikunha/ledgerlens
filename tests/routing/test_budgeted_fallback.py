"""The fallback of a run: the retry of a task with another model, only with a consent and only with a budget.

What they guarantee, and why: (a) a fallback happens only when a pre-consented strategy of the deployment allows
it, and a deployment that consented to none stops the run with the reason (FR-008); (b) the fallback happens only
when the remaining budget covers it, and the check happens before the call, so the money of a retry the budget
does not allow is never spent (FR-009); (c) the router never raises the spend of a run by itself, and the caps of
the run are the same before and after the decision; (d) a failure with no retry left stops the run with an
explicit reason and with no further call (SC-008); (e) the decision is a value and the reservation is a separate
step, so a decision never moves the counters of the budget; (f) the retry is never the model that just failed.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ledgerlens.agents.budget import TurnBudget, shipped_turn_budget
from ledgerlens.agents.fallback import (
    ACTION_FALLBACK,
    ACTION_STOP,
    DIRECTION_DOWN,
    DIRECTION_UP,
    FallbackStopped,
    FallbackStrategy,
    decide,
    next_model_of,
    reserve_retry,
    strategy_of,
    with_fallback,
)
from ledgerlens.byok.budget import BudgetCoordinator
from ledgerlens.byok.registry import ALLOWLIST, ProviderRegistry
from ledgerlens.run_context import RunBudget

# The cascade of the deployment, from the lightest model to the most capable one.
CASCADE = ("openai:gpt-4.1-mini", "openai:gpt-4.1")

# The strategy of a deployment that consented to one retry, upwards.
STRATEGY = FallbackStrategy(name="one retry upwards", max_attempts=1, direction=DIRECTION_UP)


def test_the_fallback_runs_the_task_again_with_the_next_model_of_the_cascade() -> None:
    """A failure with a strategy and a budget is retried with the model above the one that failed."""
    called: list[str] = []

    def attempt(model: str) -> str:
        called.append(model)
        return f"the answer of {model}"

    answer, decision = with_fallback(
        attempt,
        failed_model="openai:gpt-4.1-mini",
        cascade=CASCADE,
        strategy=STRATEGY,
    )

    assert decision.action == ACTION_FALLBACK
    assert decision.model == "openai:gpt-4.1"
    assert decision.attempts == 1
    assert called == ["openai:gpt-4.1"]
    assert answer == "the answer of openai:gpt-4.1"


def test_the_direction_of_the_strategy_reaches_the_decision() -> None:
    """A deployment that consented to go down the cascade retries with the lighter model.

    Why it matters: the direction is the consent itself, and a decision that ignored it would retry with the
    model above whatever the deployment said.
    """
    decision = decide(
        failed_model="openai:gpt-4.1",
        cascade=CASCADE,
        strategy=FallbackStrategy(name="downwards", max_attempts=1, direction=DIRECTION_DOWN),
    )

    assert decision.action == ACTION_FALLBACK
    assert decision.model == "openai:gpt-4.1-mini"


def test_a_deployment_that_consented_to_no_fallback_stops_the_run_with_the_reason() -> None:
    """No strategy, no retry: the run stops and says why."""
    called: list[str] = []

    def attempt(model: str) -> str:
        called.append(model)
        return "an answer"

    with pytest.raises(FallbackStopped) as stopped:
        with_fallback(attempt, failed_model="openai:gpt-4.1-mini", cascade=CASCADE, strategy=None)

    assert called == []
    assert "consented to no fallback" in stopped.value.decision.reason
    assert stopped.value.decision.action == ACTION_STOP
    assert str(stopped.value) == stopped.value.decision.reason


def test_a_strategy_that_ran_out_of_attempts_stops_the_run_with_the_reason() -> None:
    """A strategy of one retry does not allow a second one."""
    called: list[str] = []

    def attempt(model: str) -> str:
        called.append(model)
        return "an answer"

    with pytest.raises(FallbackStopped) as stopped:
        with_fallback(
            attempt,
            failed_model="openai:gpt-4.1-mini",
            cascade=CASCADE,
            strategy=STRATEGY,
            attempts=1,
        )

    assert called == []
    assert "allows 1 retries" in stopped.value.decision.reason


def test_a_negative_number_of_attempts_does_not_open_a_consent_of_nothing() -> None:
    """A count of attempts that nobody made cannot buy a retry that the deployment refused."""
    decision = decide(
        failed_model="openai:gpt-4.1-mini",
        cascade=CASCADE,
        strategy=FallbackStrategy(name="no retries", max_attempts=0),
        attempts=-1,
    )

    assert decision.action == ACTION_STOP
    assert decision.model is None


def test_the_cascade_that_holds_no_other_model_stops_the_run_with_the_reason() -> None:
    """The most capable model of the cascade has nobody above it."""
    decision = decide(
        failed_model="openai:gpt-4.1",
        cascade=CASCADE,
        strategy=STRATEGY,
    )

    assert decision.action == ACTION_STOP
    assert decision.model is None
    assert "no other model" in decision.reason


def test_the_retry_is_never_the_model_that_just_failed() -> None:
    """Two providers may know a model by the same name, and the retry is not the model that failed.

    Why it matters: a retry that answers the same model is a call that spends the budget of the run for the same
    answer, and ADR-084 refuses that.
    """
    cascade = ("anthropic:gpt-4.1", "openai:gpt-4.1")

    assert next_model_of(cascade, "anthropic:gpt-4.1") == "openai:gpt-4.1"
    assert next_model_of(cascade, "openai:gpt-4.1") is None
    assert next_model_of(cascade, "openai:gpt-4.1") != "openai:gpt-4.1"


def test_the_cascade_that_holds_the_same_model_twice_uses_the_position() -> None:
    """The router decides by the position and not by the name, and so does the neighbour of the retry."""
    cascade = ("openai:gpt-4.1-mini", "openai:gpt-4.1", "openai:gpt-4.1-mini")

    assert next_model_of(cascade, "openai:gpt-4.1-mini", position=0) == "openai:gpt-4.1"
    assert next_model_of(cascade, "openai:gpt-4.1-mini", position=2) is None


def test_an_empty_budget_stops_the_run_with_the_reason_and_no_further_call() -> None:
    """A budget with no room left stops the run before the call, and the call never happens.

    Why it matters: the reservation happens before the provider is called, so the money of a retry the budget does
    not cover is never spent, and the run says which cap stopped it.
    """
    budget = shipped_turn_budget(RunBudget(max_model_calls=0, max_tool_calls=1))
    called: list[str] = []

    def attempt(model: str) -> str:
        called.append(model)
        return "an answer"

    with pytest.raises(FallbackStopped) as stopped:
        with_fallback(
            attempt,
            failed_model="openai:gpt-4.1-mini",
            cascade=CASCADE,
            strategy=STRATEGY,
            budget=budget,
        )

    assert called == []
    assert "budget" in stopped.value.decision.reason
    assert budget.cut_by() == "max_model_calls"


def test_the_cap_of_the_money_refuses_a_retry_that_does_not_fit() -> None:
    """A retry with a plan that passes the cap of the money stops the run before the call.

    Why it matters: a cap of the money that cannot refuse a retry is a cap that does not hold the run, and the
    money of a retry the run may not spend is the money of a visitor.
    """
    caps = RunBudget(max_model_calls=4, max_tool_calls=4, max_estimated_usd=Decimal("0.00000001"))
    budget = TurnBudget(caps=caps, coordinator=BudgetCoordinator(caps, ProviderRegistry(ALLOWLIST)))
    called: list[str] = []

    def attempt(model: str) -> str:
        called.append(model)
        return "an answer"

    with pytest.raises(FallbackStopped) as stopped:
        with_fallback(
            attempt,
            failed_model="openai:gpt-4.1",
            cascade=CASCADE,
            strategy=FallbackStrategy(name="downwards", max_attempts=1, direction=DIRECTION_DOWN),
            budget=budget,
            planned_input_tokens=1000,
            planned_output_tokens=500,
        )

    assert called == []
    assert budget.cut_by() == "max_estimated_usd"
    assert "max_estimated_usd" in stopped.value.decision.reason


def test_a_budget_with_room_lets_the_fallback_happen_and_counts_the_retry() -> None:
    """The retry is reserved against the budget of the turn, so the budget knows about it."""
    budget = shipped_turn_budget(RunBudget(max_model_calls=2, max_tool_calls=2))

    decision = decide(
        failed_model="openai:gpt-4.1-mini",
        cascade=CASCADE,
        strategy=STRATEGY,
    )
    decision = reserve_retry(budget, decision)

    assert decision.action == ACTION_FALLBACK
    assert budget.coordinator.report().model_calls == 1


def test_the_retry_is_reserved_under_the_name_the_coordinator_counts() -> None:
    """The reservation carries the identifier of the model, and not the name with the provider on top of it.

    Why it matters: the coordinator counts a call under the identifier of the model and the registry prices it
    under the same identifier, and a reservation under another name would leave the retry outside the money of
    the run and outside the caps.
    """
    budget = shipped_turn_budget(RunBudget(max_model_calls=2, max_tool_calls=2))

    decision = reserve_retry(
        budget,
        decide(failed_model="openai:gpt-4.1-mini", cascade=CASCADE, strategy=STRATEGY),
    )

    assert decision.action == ACTION_FALLBACK
    assert budget.coordinator.report().calls_by_model == {"gpt-4.1": 1}


def test_the_decision_moves_no_counter_of_the_budget() -> None:
    """The decision is a value, and the reservation is the step that moves the counters.

    Why it matters: a decision that moved the counters of the budget in the middle of the run would be a
    decision that changed the run it described, and a caller that inspects a decision and then acts on it would
    be charged twice.
    """
    budget = shipped_turn_budget(RunBudget(max_model_calls=2, max_tool_calls=2))

    decide(failed_model="openai:gpt-4.1-mini", cascade=CASCADE, strategy=STRATEGY)

    assert budget.coordinator.report().model_calls == 0


def test_the_fallback_never_raises_the_spend_of_the_run_by_itself() -> None:
    """The caps of the run are the same before and after the retry, and the retry fits inside them.

    Why it matters: a fallback that enlarges the budget of the run is a router that spends money nobody approved,
    and the whole point of the consent is that the run may only spend what it was given.
    """
    caps = RunBudget(max_model_calls=1, max_tool_calls=1, max_estimated_usd=Decimal("0.01"))
    budget = shipped_turn_budget(caps)

    decision = reserve_retry(
        budget,
        decide(failed_model="openai:gpt-4.1-mini", cascade=CASCADE, strategy=STRATEGY),
    )

    assert decision.action == ACTION_FALLBACK
    assert budget.caps == caps
    assert budget.caps.max_model_calls == 1
    assert budget.caps.max_estimated_usd == Decimal("0.01")
    assert budget.coordinator.report().model_calls == 1


def test_a_budget_that_nobody_owns_the_counting_of_says_who_refuses_the_retry() -> None:
    """The reason of the retry says who holds the budget, because the module did not check it (ADR-054).

    Why it matters: a reason that says "the budget of the run covers it" when nobody checked it is a claim the
    module did not make, and the caller that holds the provider is the one that refuses the retry.
    """
    budget = shipped_turn_budget(RunBudget(max_model_calls=2, max_tool_calls=2), owner="caller")

    decision = reserve_retry(
        budget,
        decide(failed_model="openai:gpt-4.1-mini", cascade=CASCADE, strategy=STRATEGY),
    )

    assert decision.action == ACTION_FALLBACK
    assert "the caller that holds the provider" in decision.reason
    assert budget.coordinator.report().model_calls == 0


def test_the_direction_of_the_retry_is_the_one_the_strategy_declares() -> None:
    """A deployment that consented to go down the cascade retries with the lighter model."""
    assert next_model_of(CASCADE, "openai:gpt-4.1-mini", DIRECTION_UP) == "openai:gpt-4.1"
    assert next_model_of(CASCADE, "openai:gpt-4.1", DIRECTION_DOWN) == "openai:gpt-4.1-mini"
    assert next_model_of(CASCADE, "openai:gpt-4.1-mini", DIRECTION_DOWN) is None
    assert next_model_of(CASCADE, "openai:gpt-4.1", DIRECTION_UP) is None


def test_a_direction_that_does_not_exist_is_refused() -> None:
    """The direction of a retry is upwards or downwards, and a reader of the trace has to see which."""
    with pytest.raises(ValueError, match="direction of a fallback"):
        next_model_of(CASCADE, "openai:gpt-4.1-mini", "sideways")


def test_a_strategy_that_allows_nothing_is_a_strategy_that_allows_nothing() -> None:
    """A deployment that consented to no retry says so in the decision, and the run stops."""
    decision = decide(
        failed_model="openai:gpt-4.1-mini",
        cascade=CASCADE,
        strategy=FallbackStrategy(name="no retries", max_attempts=0),
    )

    assert decision.action == ACTION_STOP
    assert decision.model is None
    assert "allows 0 retries" in decision.reason


def test_a_strategy_that_allows_a_negative_number_of_attempts_is_refused() -> None:
    """A consent with a negative number of retries is not a consent."""
    with pytest.raises(ValueError, match="negative number of attempts"):
        FallbackStrategy(name="broken", max_attempts=-1)


def test_a_strategy_with_a_direction_that_does_not_exist_is_refused() -> None:
    """The direction of a retry is upwards or downwards, and a reader of the trace has to see which."""
    with pytest.raises(ValueError, match="direction of a fallback"):
        FallbackStrategy(name="broken", direction="sideways")


def test_the_decision_carries_what_the_trace_needs() -> None:
    """The decision is a value, so a reader of the trace sees the model, the reason and the strategy."""
    decision = decide(
        failed_model="openai:gpt-4.1-mini",
        cascade=CASCADE,
        strategy=STRATEGY,
    )
    published = decision.to_dict()

    assert published["action"] == ACTION_FALLBACK
    assert published["model"] == "openai:gpt-4.1"
    assert published["reason"]
    assert published["strategy"] == "one retry upwards"
    assert published["attempts"] == 1


def test_a_deployment_that_declares_no_retry_has_no_strategy() -> None:
    """Nobody said anything about the retries, so the run has no strategy and no retry."""
    from ledgerlens.config import Settings

    assert strategy_of(Settings()) is None


def test_the_strategy_of_the_deployment_comes_from_the_settings() -> None:
    """The consent of the deployment is a setting, and it says how many retries and in which direction."""
    from ledgerlens.config import Settings

    strategy = strategy_of(Settings(fallback_attempts=2, fallback_direction=DIRECTION_DOWN))

    assert strategy is not None
    assert strategy.max_attempts == 2
    assert strategy.direction == DIRECTION_DOWN


def test_the_consent_of_the_deployment_is_read_from_the_environment() -> None:
    """The consent comes from the environment of the deployment, and not only from a setting of the code."""
    from ledgerlens.config import get_settings

    settings = get_settings(env={"LEDGERLENS_FALLBACK_ATTEMPTS": "2", "LEDGERLENS_FALLBACK_DIRECTION": "down"})
    strategy = strategy_of(settings)

    assert settings.fallback_attempts == 2
    assert strategy is not None
    assert strategy.max_attempts == 2
    assert strategy.direction == DIRECTION_DOWN


def test_the_settings_refuse_a_number_of_attempts_that_is_not_a_number() -> None:
    """A consent that is not a number is not a consent, and the settings say so."""
    from ledgerlens.config import ConfigError, get_settings

    with pytest.raises(ConfigError, match="LEDGERLENS_FALLBACK_ATTEMPTS"):
        get_settings(env={"LEDGERLENS_FALLBACK_ATTEMPTS": "many"})


def test_the_settings_refuse_a_negative_number_of_attempts() -> None:
    """A consent with a negative number of retries is refused at the door."""
    from ledgerlens.config import ConfigError, get_settings

    with pytest.raises(ConfigError, match="LEDGERLENS_FALLBACK_ATTEMPTS"):
        get_settings(env={"LEDGERLENS_FALLBACK_ATTEMPTS": "-1"})


def test_the_settings_refuse_a_direction_of_the_fallback_that_does_not_exist() -> None:
    """The direction of a retry is upwards or downwards, and a deployment that says otherwise is refused."""
    from ledgerlens.config import ConfigError, get_settings

    with pytest.raises(ConfigError, match="LEDGERLENS_FALLBACK_DIRECTION"):
        get_settings(env={"LEDGERLENS_FALLBACK_DIRECTION": "sideways"})
