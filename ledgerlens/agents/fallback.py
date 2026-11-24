"""The fallback of a run: the retry of a task with another model of the cascade, under a consent and a budget.

Why it exists: the router of ADR-078 chooses the model of each slot by the task the slot does, and the lightest
model that fits a task is the one that fails first when the task turns out to be harder than it looked. A
fallback is the retry of that task with another model of the cascade, and it is the one place of a run where a
call happens that the plan of the run did not ask for, so it is the one place where the consent of the deployment
and the remaining budget have to be read before the call.

The rules, in words, and they are the rules of FR-008 and of SC-008:
- a fallback happens only when a pre-consented strategy of the deployment allows it;
- the remaining budget has to cover it, and the check happens before the call, so the money of a retry the budget
  does not allow is never spent;
- the router never raises the spend of a run by itself: the retry uses the budget that is left and the caps of
  the run are never changed here;
- a failure with no retry left stops the run with an explicit reason and with no further call.

Why the decision and the reservation are two things: the decision is a value, so a reader of the trace can see
which model ran the retry and why, and a decision that moved the counters of the budget in the middle of the run
would be a decision nobody could reason about. The reservation happens after the decision and before the call,
and it is the reservation that checks the caps.

Why the reservation carries the name the coordinator counts under: the coordinator counts a call of a model
under the identifier of the model and the registry prices it under the same identifier, and a reservation under
another name would leave the call of the retry outside the money of the run and outside the caps.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import Any, Literal

from ledgerlens.agents.budget import TurnBudget
from ledgerlens.byok.budget import BudgetExceededError
from ledgerlens.config import Settings, get_settings

__all__ = [
    "ACTION_FALLBACK",
    "ACTION_STOP",
    "DIRECTION_DOWN",
    "DIRECTION_UP",
    "FallbackDecision",
    "FallbackStopped",
    "FallbackStrategy",
    "decide",
    "next_model_of",
    "reserve_retry",
    "strategy_of",
    "with_fallback",
]

# What a decision says the run does.
ACTION_FALLBACK = "fallback"
ACTION_STOP = "stop"

# The direction of a retry in the cascade, which goes from the lightest model to the most capable one.
DIRECTION_UP = "up"
DIRECTION_DOWN = "down"


def _bare(name: str) -> str:
    """The identifier of a model, without the provider that serves it.

    Why: the coordinator counts a call under the identifier of the model and the registry prices it under the
    same identifier, and the name of the deployment carries the provider on top of it.
    """
    return name.split(":", 1)[-1]


@dataclass(frozen=True)
class FallbackStrategy:
    """The pre-consented rule of the deployment about the retries of a task.

    Why it is a value with a shape and not a flag: the consent of a deployment is a rule, and a reader of the
    trace has to see how many retries it allowed and in which direction they go. A deployment that consents to
    nothing is a strategy with zero attempts, and not the absence of a strategy: the absence means that nobody
    said anything about the retries, and the run stops in both cases, with different reasons.
    """

    name: str = "the strategy of the deployment"
    max_attempts: int = 1
    direction: Literal["up", "down"] = DIRECTION_UP

    def __post_init__(self) -> None:
        if self.max_attempts < 0:
            raise ValueError("a strategy of fallback cannot allow a negative number of attempts")
        if self.direction not in (DIRECTION_UP, DIRECTION_DOWN):
            raise ValueError(
                f"the direction of a fallback is {DIRECTION_UP!r} or {DIRECTION_DOWN!r}, not {self.direction!r}"
            )

    def allows(self, attempts: int) -> bool:
        """Whether the strategy allows one more attempt after the ones that happened.

        Why a negative count is read as none: a count that nobody made is a bug of the caller, and the rule that
        matters is the rule of the strategy, so the count of the attempts that happened is never below zero.
        """
        return max(attempts, 0) < self.max_attempts

    def to_dict(self) -> dict[str, Any]:
        """The strategy as a dictionary, for the trace."""
        return {"name": self.name, "max_attempts": self.max_attempts, "direction": self.direction}


@dataclass(frozen=True)
class FallbackDecision:
    """What the run does after a model failed: try another model, or stop with the reason.

    Why the reason is always there: a run that stops without saying why is a run that a reader cannot tell from
    a run that broke, and the run of a visitor is worth more when it says what stopped it.
    """

    action: str
    model: str | None
    reason: str
    attempts: int
    strategy: str

    @property
    def is_fallback(self) -> bool:
        """Whether the decision is to try another model."""
        return self.action == ACTION_FALLBACK

    def to_dict(self) -> dict[str, Any]:
        """The decision as a dictionary, for the trace."""
        return {
            "action": self.action,
            "model": self.model,
            "reason": self.reason,
            "attempts": self.attempts,
            "strategy": self.strategy,
        }


class FallbackStopped(Exception):
    """The run stops, because a failure had no retry left, and the reason is in the message.

    Why it is an exception and not a return value: a run that continues without an answer is a run that lies
    about what it did, and the caller has to handle the stop.
    """

    reason = "the run stopped: a failure had no retry left"

    def __init__(self, decision: FallbackDecision) -> None:
        super().__init__(decision.reason)
        self.decision = decision


def strategy_of(settings: Settings | None = None) -> FallbackStrategy | None:
    """The strategy of the deployment, or None when the deployment consented to no fallback.

    Why None and not a strategy with zero attempts: a deployment that consented to nothing is not a deployment
    that said nothing, and the two stop the run with different reasons. The default of the settings is zero
    attempts, and a deployment that says nothing gets no retry at all.
    """
    settings = settings or get_settings()
    if settings.fallback_attempts <= 0:
        return None
    return FallbackStrategy(
        name=f"the deployment allows {settings.fallback_attempts} retries",
        max_attempts=settings.fallback_attempts,
        direction=settings.fallback_direction,
    )


def next_model_of(
    cascade: Sequence[str],
    failed_model: str,
    direction: str = DIRECTION_UP,
    *,
    position: int | None = None,
) -> str | None:
    """The model of the cascade that the retry of a failed model uses, or None when there is none.

    Why the names are compared with the provider and not without it: two providers may know a model by the same
    name, and a retry that answers the name of the model that just failed is not a retry.

    Why the position is an argument: the cascade of a deployment may hold the same model at two levels, and the
    router decides by the position and not by the name. A caller that knows the position of the model that
    failed says so, and the neighbour of that position is the model of the retry.

    Why upwards is the default: the cascade goes from the lightest model to the most capable one, and a model
    that failed a task is a model that was not capable enough for it, so the retry asks for more and not for
    less. A deployment that wants the other direction says so in its strategy.
    """
    if direction not in (DIRECTION_UP, DIRECTION_DOWN):
        raise ValueError(f"the direction of a fallback is {DIRECTION_UP!r} or {DIRECTION_DOWN!r}, not {direction!r}")
    index = position if position is not None else _position_of(cascade, failed_model)
    if index is None or index < 0 or index >= len(cascade):
        return None
    if direction == DIRECTION_DOWN:
        return cascade[index - 1] if index > 0 else None
    return cascade[index + 1] if index + 1 < len(cascade) else None


def _position_of(cascade: Sequence[str], failed_model: str) -> int | None:
    """The position of the model that failed in the cascade, or None when the cascade does not hold it.

    Why the exact name is looked for before the bare one: two providers may know a model by the same name, and the
    name with the provider is the name of the model that failed.
    """
    for index, model in enumerate(cascade):
        if model == failed_model:
            return index
    for index, model in enumerate(cascade):
        if _bare(model) == _bare(failed_model):
            return index
    return None


def decide(
    *,
    failed_model: str,
    cascade: Sequence[str],
    strategy: FallbackStrategy | None,
    attempts: int = 0,
    position: int | None = None,
) -> FallbackDecision:
    """What the run does after a model failed, with the reason in words.

    Why the decision changes nothing: the reservation of the retry is what checks the caps, and it happens after
    the decision and before the call. A decision that moved the counters of the budget would be a decision that
    changed the run it described (FR-008).
    """
    if strategy is None:
        return FallbackDecision(
            action=ACTION_STOP,
            model=None,
            reason="the deployment consented to no fallback",
            attempts=attempts,
            strategy="no strategy declared",
        )
    if not strategy.allows(attempts):
        return FallbackDecision(
            action=ACTION_STOP,
            model=None,
            reason=(
                f"the strategy {strategy.name!r} allows {strategy.max_attempts} retries and the run already made "
                f"{attempts}"
            ),
            attempts=attempts,
            strategy=strategy.name,
        )
    model = next_model_of(cascade, failed_model, strategy.direction, position=position)
    if model is None:
        return FallbackDecision(
            action=ACTION_STOP,
            model=None,
            reason=(
                f"the cascade holds no other model for the task of {failed_model!r} in the direction "
                f"{strategy.direction!r} that the strategy {strategy.name!r} declares"
            ),
            attempts=attempts,
            strategy=strategy.name,
        )
    return FallbackDecision(
        action=ACTION_FALLBACK,
        model=model,
        reason=(
            f"the strategy {strategy.name!r} allows the retry and the cascade holds {model} for it, so the model "
            f"{model} runs the task that {failed_model} failed"
        ),
        attempts=attempts + 1,
        strategy=strategy.name,
    )


def reserve_retry(
    budget: TurnBudget | None,
    decision: FallbackDecision,
    *,
    planned_input_tokens: int | None = None,
    planned_output_tokens: int | None = None,
) -> FallbackDecision:
    """The decision after the budget of the run was asked about the retry, and the reservation of the retry.

    Why the reservation comes here and not in the decision: the reservation moves the counters of the budget, and
    a decision that is a value does not move anything. The reservation carries the identifier of the model the
    way the coordinator counts it, and it carries the tokens the caller plans, because a cap of the tokens and a
    cap of the money are caps of a planned call and not of a call without a plan.

    Why a budget that nobody owns the counting of does not refuse the retry: the side that holds the provider is
    the one that reserves the call (ADR-054), and a second counter would count the same call twice. The caller
    that owns the provider refuses the retry when its own budget does not cover it.
    """
    if budget is None or not decision.is_fallback:
        return decision
    model = str(decision.model)
    try:
        budget.reserve_model_call(
            _bare(model),
            planned_input_tokens=planned_input_tokens,
            planned_output_tokens=planned_output_tokens,
        )
    except BudgetExceededError as exc:
        return replace(
            decision,
            action=ACTION_STOP,
            model=None,
            reason=f"the remaining budget of the run does not cover the retry: {exc.cap}",
        )
    return replace(
        decision,
        reason=(
            f"the strategy {decision.strategy!r} allows the retry and {_budget_covers(budget)}, so the model "
            f"{model} runs the task that failed"
        ),
    )


def _budget_covers(budget: TurnBudget | None) -> str:
    """The words that say who holds the budget of the retry, in the way the owner of the counting says.

    Why the words and not a boolean: a budget that nobody owns the counting of is not a budget that covers
    anything, it is a budget whose enforcement is somewhere else, and a reason that says "the budget covers it"
    would be a claim the module did not check (ADR-054).
    """
    if budget is None:
        return "no budget of the run was given to check"
    if budget.owner != "integrator":
        return (
            "the caller that holds the provider is the one that refuses the retry when its own budget does not "
            "cover it"
        )
    return "the budget of the run covers it"


def with_fallback[T](
    attempt: Callable[[str], T],
    *,
    failed_model: str,
    cascade: Sequence[str],
    strategy: FallbackStrategy | None,
    attempts: int = 0,
    position: int | None = None,
    budget: TurnBudget | None = None,
    planned_input_tokens: int | None = None,
    planned_output_tokens: int | None = None,
) -> tuple[T, FallbackDecision]:
    """Runs the task again with the model of the decision, or stops the run with the reason.

    Why the call is a parameter and not the module doing it: the caller holds the provider, the client and the
    trace, and a module that called the provider itself would be a second way of calling a model. The module
    decides, reserves and stops, and the caller calls.
    """
    decision = decide(
        failed_model=failed_model,
        cascade=cascade,
        strategy=strategy,
        attempts=attempts,
        position=position,
    )
    decision = reserve_retry(
        budget,
        decision,
        planned_input_tokens=planned_input_tokens,
        planned_output_tokens=planned_output_tokens,
    )
    if not decision.is_fallback:
        raise FallbackStopped(decision)
    return attempt(str(decision.model)), decision
