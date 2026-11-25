"""The retry of a call that the provider rate limited: it stops at the deadline or at the budget, and it is bounded.

Why the retry stops at the deadline or at the budget: a provider that answers with a rate limit is a provider
that asks for time, and a retry that never stops is a run that spends the money and the time of the visitor on
a provider that is not answering. The deadline is the wall clock cap of the budget of the run, and the budget
is the cap of the calls of the run, and the retry stops at whichever comes first.

Why the count of the attempts is bounded: a retry that could try forever is a retry that would spend forever,
and the bound is the promise that the run ends.

Why the clock is injected: a deadline is proved by moving a clock, and not by waiting, so the test of the
deadline runs in the gate of the repository with no waiting.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ledgerlens.byok.budget import BudgetCoordinator, BudgetExceededError

__all__ = ["RateLimited", "RetryOutcome", "retry_rate_limited"]


class RateLimited(Exception):
    """The provider answered with a rate limit: the call may be retried, within the deadline and the budget."""


@dataclass(frozen=True)
class RetryOutcome:
    """The outcome of a retry: the answer, or the reason the retry stopped, and the count of the attempts."""

    answer: object | None
    attempts: int
    stopped_by: str | None  # "deadline", "budget" or None when the call answered


def retry_rate_limited(
    call: Callable[[], object],
    *,
    coordinator: BudgetCoordinator,
    model: str,
    max_attempts: int,
    clock: Callable[[], float] | None = None,
) -> RetryOutcome:
    """The retry of a call that the provider rate limits: bounded by the attempts, the deadline and the budget.

    Why every attempt reserves a call of the budget: the retry of a rate limited call is a call of the run, and
    a retry that ran outside the budget would spend money the run was not allowed to spend (FR-009).

    Why the deadline is the wall clock of the coordinator: the deadline of the retry is the wall clock cap of
    the budget of the run, and a retry that ran past it would spend the time the run was not allowed to spend.
    """
    import time

    now = clock or time.monotonic
    start = now()
    attempts = 0
    while attempts < max_attempts:
        try:
            coordinator.reserve_model_call(model)
        except BudgetExceededError:
            return RetryOutcome(answer=None, attempts=attempts, stopped_by="budget")
        attempts += 1
        try:
            return RetryOutcome(answer=call(), attempts=attempts, stopped_by=None)
        except RateLimited:
            if now() - start >= (coordinator.caps.max_wall_seconds or 0):
                return RetryOutcome(answer=None, attempts=attempts, stopped_by="deadline")
    return RetryOutcome(answer=None, attempts=attempts, stopped_by="deadline")
