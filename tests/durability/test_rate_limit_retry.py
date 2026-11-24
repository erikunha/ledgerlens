"""The retry of a rate limited call: it stops at the deadline or at the budget, and the attempts are bounded.

What they guarantee, and why: (a) the retry of a call that the provider rate limits stops at the deadline (the
wall clock cap of the budget of the run) or at the budget (the cap of the calls of the run), because a retry
that never stops is a run that spends the money and the time of the visitor on a provider that is not
answering; (b) the count of the attempts is bounded, because a retry that could try forever would spend
forever. The clock is injected, so the deadline is proved by moving the clock and not by waiting.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from ledgerlens.byok.budget import BudgetCoordinator
from ledgerlens.byok.registry import ProviderRegistry
from ledgerlens.durability.retry import RateLimited, retry_rate_limited
from ledgerlens.run_context import RunBudget


def _coordinator(max_model_calls: int = 12, max_wall_seconds: float = 120.0) -> BudgetCoordinator:
    """The coordinator of a run, with the caps of the test."""
    return BudgetCoordinator(
        RunBudget(max_model_calls=max_model_calls, max_wall_seconds=max_wall_seconds),
        ProviderRegistry([]),
    )


def test_the_retry_of_a_rate_limited_call_answers_within_the_bound() -> None:
    """The call that answers on the second attempt answers, and the attempts are counted."""
    attempts = 0

    def call() -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RateLimited("the provider asked for time")
        return "the answer"

    outcome = retry_rate_limited(call, coordinator=_coordinator(), model="openai:gpt-4.1-mini", max_attempts=3)

    assert outcome.answer == "the answer"
    assert outcome.attempts == 2
    assert outcome.stopped_by is None


def test_the_retry_stops_at_the_budget() -> None:
    """The budget of the run stops the retry, and the reason names the budget."""
    outcome = retry_rate_limited(
        lambda: (_ for _ in ()).throw(RateLimited("the provider asked for time")),
        coordinator=_coordinator(max_model_calls=2),
        model="openai:gpt-4.1-mini",
        max_attempts=10,
    )

    assert outcome.answer is None
    assert outcome.stopped_by == "budget"
    assert outcome.attempts <= 2


def test_the_retry_stops_at_the_deadline_proved_by_the_clock() -> None:
    """The deadline is proved by moving the clock, and the retry stops at it."""
    moments = iter([0.0, 0.0, 200.0, 200.0, 200.0, 200.0])
    outcome = retry_rate_limited(
        lambda: (_ for _ in ()).throw(RateLimited("the provider asked for time")),
        coordinator=_coordinator(max_wall_seconds=120.0),
        model="openai:gpt-4.1-mini",
        max_attempts=10,
        clock=lambda: next(moments),
    )

    assert outcome.answer is None
    assert outcome.stopped_by == "deadline"


def test_the_count_of_the_attempts_is_bounded() -> None:
    """A retry that could try forever would spend forever: the attempts have a bound."""
    outcome = retry_rate_limited(
        lambda: (_ for _ in ()).throw(RateLimited("the provider asked for time")),
        coordinator=_coordinator(max_wall_seconds=10_000.0),
        model="openai:gpt-4.1-mini",
        max_attempts=3,
    )

    assert outcome.attempts == 3
