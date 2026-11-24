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

Why the retry never repeats the model that failed: the call that failed already happened and the money of it is
already spent, and a retry that answered the same model would spend the budget of the run twice for the same
failure (ADR-084).
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, replace
from typing import Any, Literal

from langchain.agents.middleware import AgentMiddleware, ModelRequest
from langgraph.errors import GraphBubbleUp

from ledgerlens.agents.budget import (
    CHARS_PER_TOKEN,
    PLANNED_OUTPUT_TOKENS,
    TurnBudget,
    model_id_of,
    turn_of,
)
from ledgerlens.byok.budget import BudgetExceededError, BudgetRefused
from ledgerlens.config import Settings, get_settings

__all__ = [
    "ACTION_FALLBACK",
    "ACTION_STOP",
    "DIRECTION_DOWN",
    "DIRECTION_UP",
    "FallbackDecision",
    "FallbackMiddleware",
    "FallbackRunner",
    "FallbackStopped",
    "FallbackStrategy",
    "decide",
    "next_model_of",
    "planned_input_of",
    "planned_input_of_request",
    "reserve_retry",
    "strategy_of",
    "with_fallback",
]

log = logging.getLogger(__name__)

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
    if model == failed_model or _bare(model) == _bare(failed_model):
        # The neighbour of the failed model is the failed model: a cascade that holds the same model twice would
        # make the retry answer the model that just failed, and the money of the failure would be spent twice
        # (ADR-084).
        return FallbackDecision(
            action=ACTION_STOP,
            model=None,
            reason=(
                f"the neighbour of {failed_model!r} in the cascade is the model that failed, so the retry would "
                f"spend the budget of the run twice for the same failure"
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

    Why the reason of a refusal names the model: the decision carries no model when the run stops, because no model
    ran, and the model that the retry would have used is then the only thing that tells a reader which model the
    budget refused.
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
            reason=(
                f"the remaining budget of the run does not cover the retry with the model {model}: {exc.cap}"
            ),
        )
    except BudgetRefused as exc:
        # A plan that cannot be counted is a plan the caps cannot hold, and the run stops with the reason of the
        # refusal instead of raising an exception nobody expected (FR-009).
        return replace(
            decision,
            action=ACTION_STOP,
            model=None,
            reason=(
                f"the budget of the run refused the plan of the retry with the model {model}: {exc}"
            ),
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


@dataclass(frozen=True)
class FallbackRunner:
    """The retry of a failed call of a model: the consent, the cascade of the deployment and the factory of the
    model of a retry.

    Why it holds no counter: the consent of the deployment says how many retries a task may get, and a task is a
    call of a model, so the count of the retries is the count of the call and it lives with the call (ADR-084).
    A runner that carried the count would be shared by the calls of a session, and the second call of a session
    would find the retries of the first one already spent.

    Why it is frozen: the consent and the cascade of a deployment do not change while a run goes on, and a run
    whose rules changed in the middle is a run nobody could read.
    """

    cascade: tuple[str, ...] = ()
    strategy: FallbackStrategy | None = None
    factory: Callable[[str], Any] | None = None

    def retry[T](
        self,
        attempt: Callable[[Any], T],
        *,
        failed_model: str,
        turn: TurnBudget | None = None,
        planned_input_tokens: int | None = None,
        planned_output_tokens: int | None = None,
        failure: Exception | None = None,
    ) -> tuple[T, FallbackDecision]:
        """The answer of the retry, and the decision that produced it.

        Why the call takes the model and not the name: the caller holds the provider, and the model of the
        retry is built before the reservation, so a model that cannot be built is not a call that the budget of
        the run pays for. The model that failed is never called again: the call that failed already happened, and
        the money of it is already spent.

        Why the budget is asked before the call: the reservation of the retry carries the plan of the retry, so
        the cap of the money and the cap of the tokens are checked against what the retry is about to spend
        (FR-009). The reservation happens after the decision, and a decision that moved a counter would be a
        decision nobody could reason about.

        Why a cap is not a failure of a model: a refusal of the budget is the ceiling of the run and not a model
        that failed, so it goes up and the turn stops with the cap named (ADR-054).

        Why the failure of the provider is kept: a run that stops because a provider failed has to say which
        provider and what it said, and the exception of the provider is the only thing that knows.
        """
        model = failed_model
        attempts = 0
        # The models that this task already tried: a cascade that holds the same model twice would make the retry
        # answer a model that already failed in this task, and the money of that failure would be spent twice.
        tried = {_bare(failed_model)}
        while True:
            decision, built = self._next(
                failed_model=model,
                attempts=attempts,
                turn=turn,
                planned_input_tokens=planned_input_tokens,
                planned_output_tokens=planned_output_tokens,
                failure=failure,
                tried=tried,
            )
            attempts += 1
            tried.add(_bare(str(decision.model)))
            if turn is not None:
                turn.record_fallback(decision.to_dict())
                # The reservation of the retry is the one of the turn, and the reservation of the graph must not
                # reserve it a second time (ADR-084).
                turn.mark_reserved(_bare(str(decision.model)))
            try:
                value = attempt(built)
            except (BudgetExceededError, BudgetRefused, GraphBubbleUp):
                raise
            except Exception as exc:
                # The model of the retry failed too: the decision is taken again with the model that failed, and
                # the consent of the deployment says how many retries are left.
                failure = exc
                model = str(decision.model)
                continue
            finally:
                if turn is not None:
                    turn.clear_reserved()
            return value, decision

    async def aretry[T](
        self,
        attempt: Callable[[Any], Awaitable[T]],
        *,
        failed_model: str,
        turn: TurnBudget | None = None,
        planned_input_tokens: int | None = None,
        planned_output_tokens: int | None = None,
        failure: Exception | None = None,
    ) -> tuple[T, FallbackDecision]:
        """The asynchronous path of the retry: the same rules, awaited.

        Why it is a method and not the synchronous one with an awaited attempt: the decision of the next retry
        depends on whether the call failed, and a coroutine that nobody awaited says nothing about it.
        """
        model = failed_model
        attempts = 0
        tried = {_bare(failed_model)}
        while True:
            decision, built = self._next(
                failed_model=model,
                attempts=attempts,
                turn=turn,
                planned_input_tokens=planned_input_tokens,
                planned_output_tokens=planned_output_tokens,
                failure=failure,
                tried=tried,
            )
            attempts += 1
            tried.add(_bare(str(decision.model)))
            if turn is not None:
                turn.record_fallback(decision.to_dict())
                turn.mark_reserved(_bare(str(decision.model)))
            try:
                value = await attempt(built)
            except (BudgetExceededError, BudgetRefused, GraphBubbleUp):
                raise
            except Exception as exc:
                failure = exc
                model = str(decision.model)
                continue
            finally:
                if turn is not None:
                    turn.clear_reserved()
            return value, decision

    def _next(
        self,
        *,
        failed_model: str,
        attempts: int,
        turn: TurnBudget | None,
        planned_input_tokens: int | None,
        planned_output_tokens: int | None,
        failure: Exception | None,
        tried: frozenset[str] | set[str] = frozenset(),
    ) -> tuple[FallbackDecision, Any]:
        """The decision of the next retry and the model of it, or the stop with the reason.

        Why the model is built here and not in the attempt: a deployment that cannot build the model of the retry
        must not be charged for a call that never happens.

        Why the models that the task already tried are refused: a cascade that holds the same model twice would
        make the retry answer a model that already failed in this task, and the money of that failure would be
        spent twice (ADR-084).
        """
        decision = decide(
            failed_model=failed_model,
            cascade=self.cascade,
            strategy=self.strategy,
            attempts=attempts,
        )
        if not decision.is_fallback:
            raise self._stop(decision, failure, turn)
        if turn is not None and turn.owner != "integrator":
            # The side that holds the provider is the one that reserves the call (ADR-054), and a turn that does
            # not own the counting cannot reserve a call: a retry that nobody reserves spends the money of the
            # run outside the caps of the run.
            raise self._stop(
                replace(
                    decision,
                    action=ACTION_STOP,
                    model=None,
                    reason=(
                        f"{decision.reason}, and the side that holds the provider is the one that reserves the call, "
                        "and this turn does not own the counting of it"
                    ),
                ),
                failure,
                turn,
            )
        if self.factory is None:
            raise self._stop(
                replace(
                    decision,
                    action=ACTION_STOP,
                    model=None,
                    reason=f"{decision.reason}, and the deployment built no model for it",
                ),
                failure,
                turn,
            )
        try:
            built = self.factory(str(decision.model))
        except Exception as exc:
            raise self._stop(
                replace(
                    decision,
                    action=ACTION_STOP,
                    model=None,
                    reason=(
                        f"{decision.reason}, and the deployment could not build the model of the retry: "
                        f"{type(exc).__name__}: {exc}"
                    ),
                ),
                failure,
                turn,
            ) from exc
        if _bare(str(decision.model)) in tried:
            raise self._stop(
                replace(
                    decision,
                    action=ACTION_STOP,
                    model=None,
                    reason=(
                        f"{decision.reason}, and the model of the retry already failed in this task, so the money of "
                        "that failure would be spent twice"
                    ),
                ),
                failure,
                turn,
            )
        decision = reserve_retry(
            turn,
            decision,
            planned_input_tokens=planned_input_tokens,
            planned_output_tokens=planned_output_tokens,
        )
        if not decision.is_fallback:
            raise self._stop(decision, failure, turn)
        return decision, built

    def _stop(
        self,
        decision: FallbackDecision,
        failure: Exception | None,
        turn: TurnBudget | None,
    ) -> FallbackStopped:
        """The stop of the run, with the reason of the decision, and the decision in the trace of the turn.

        Why the decision is kept even when the run stops: a reader of the trace of a run that stopped because the
        retry did not happen has to see the model of the retry that was refused and the reason of it (ADR-084).
        """
        if turn is not None:
            turn.record_fallback(decision.to_dict())
        return _stopped(decision, failure)


def _stopped(decision: FallbackDecision, failure: Exception | None) -> FallbackStopped:
    """The stop of the run, with the reason of the decision and the failure of the provider when there was one.

    Why the failure of the provider is in the reason: a run that stops because a provider failed has to say
    which provider and what it said, and the exception of the provider is the only thing that knows (ADR-084).
    """
    if failure is not None:
        decision = replace(
            decision,
            reason=f"{decision.reason}; the provider said: {type(failure).__name__}: {failure}",
        )
    return FallbackStopped(decision)


class FallbackMiddleware(AgentMiddleware):
    """The retry of a call of a model of the graph, when the deployment consented to it and the budget covers it.

    Why it sits outside the reservation and not inside: the reservation books the usage of a call under the model
    of that call, and a retry that ran inside the reservation would book the tokens of the model of the retry
    under the model that failed (ADR-084). Outside, every attempt of the turn is reserved under its own model,
    and the retry is reserved by the fallback itself, with the plan of the retry, so the caps of the money are
    checked before the call (FR-009).

    Why it does not retry a refusal of the budget: a cap that is reached is the ceiling of the run and not a
    model that failed, so the turn stops with the cap named (ADR-054).

    Why a signal of the graph goes up: an interrupt or a command of the graph is not a model that failed, and a
    retry of it would swallow the control of the run.

    Why the runner is built by the caller: the middleware holds no consent and no cascade of its own, so a
    deployment that consented to no retry has no middleware at all and the behaviour of the run does not move.
    """

    def __init__(self, runner: FallbackRunner) -> None:
        self._runner = runner

    def wrap_model_call(self, request: ModelRequest, handler: Callable[[ModelRequest], Any]) -> Any:
        """Runs the call of the model, and runs it again with another model when it fails."""
        turn = turn_of(request.runtime)
        model_id = model_id_of(request.model)
        try:
            return handler(request)
        except (BudgetExceededError, BudgetRefused, GraphBubbleUp):
            raise
        except Exception as exc:
            return self._retry(request, handler, turn, model_id, exc)

    async def awrap_model_call(
        self, request: ModelRequest, handler: Callable[[ModelRequest], Awaitable[Any]]
    ) -> Any:
        """The asynchronous path of the retry: the same rules, awaited."""
        turn = turn_of(request.runtime)
        model_id = model_id_of(request.model)
        try:
            return await handler(request)
        except (BudgetExceededError, BudgetRefused, GraphBubbleUp):
            raise
        except Exception as exc:
            return await self._aretry(request, handler, turn, model_id, exc)

    def _retry(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Any],
        turn: TurnBudget | None,
        model_id: str,
        failure: Exception,
    ) -> Any:
        """The call of the model of the decision, with the plan of the retry."""
        runner = self._runner

        def attempt(model: Any) -> Any:
            return handler(request.override(model=model))

        value, _ = runner.retry(
            attempt,
            failed_model=model_id,
            turn=turn,
            planned_input_tokens=planned_input_of_request(request),
            planned_output_tokens=PLANNED_OUTPUT_TOKENS,
            failure=failure,
        )
        return value

    async def _aretry(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[Any]],
        turn: TurnBudget | None,
        model_id: str,
        failure: Exception,
    ) -> Any:
        """The asynchronous path of the retry of the model of the decision."""
        runner = self._runner

        async def attempt(model: Any) -> Any:
            return await handler(request.override(model=model))

        value, _ = await runner.aretry(
            attempt,
            failed_model=model_id,
            turn=turn,
            planned_input_tokens=planned_input_of_request(request),
            planned_output_tokens=PLANNED_OUTPUT_TOKENS,
            failure=failure,
        )
        return value


def planned_input_of_request(request: Any) -> int:
    """The number of input tokens a call with this request would send, as an estimate.

    Why the system message is in the plan: the messages of the request are not the whole call, and the system
    message of the run is the largest part of it. A plan that leaves it out would let a cap of the tokens pass
    a call that sends it (FR-009).
    """
    characters = sum(len(_text_of(message)) for message in getattr(request, "messages", []) or [])
    system = getattr(request, "system_message", None)
    if system is not None:
        characters += len(_text_of(system))
    return max(1, characters // CHARS_PER_TOKEN)


def planned_input_of(messages: Sequence[Any]) -> int:
    """The number of input tokens a call that sends these messages would send, as an estimate.

    Why the estimate and not a count: the repository has no tokenizer that runs offline, and the rule of four
    characters per token is the one the live path uses to plan its calls. The estimate is a plan and never a
    report: the observed tokens are the ones the provider counted (FR-010).

    Why it is never zero: a call that sends nothing is a call that sends at least a token, and a plan of zero
    would let a cap of the tokens pass a call that is not free.
    """
    characters = sum(len(_text_of(message)) for message in messages)
    return max(1, characters // CHARS_PER_TOKEN)


def _text_of(message: Any) -> str:
    """The text of a message, whatever shape its content has."""
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, (list, tuple)):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                parts.append(str(part.get("text", "")))
        return "".join(parts)
    return str(content)

