"""The rate of the requests of one session: the counter, the sliding window and the wait of a refusal.

Why it exists: ADR-047 decides that the facade refuses the requests of a session over the rate with the status
`429`, with the code `RESOURCE_LIMIT_EXCEEDED` and with the header `Retry-After`, and that the header carries the
number of seconds until the oldest request of the window falls out of it. The counter is here, in a module of its
own, so that the rule of the rate is in one place and not in the body of a route.

Why the counter lives in the memory of the process, and what that means: THE LIMIT IS PER PROCESS. A deployment that
runs the facade with more than one worker allows that many times the quota, because every worker counts the requests
of the session on its own and the counters are not shared between them. The number of workers is a decision of the
deployment and the documentation of the API says so in words (ADR-047).

Why the counter is not in the store of the branches: the store has two implementations, the file backed one has no
place to hold a counter, and a rule of the facade inside the persistence is what ADR-018 forbids. The limit of the
branches of a session is the opposite: it is read from the store, so it is global between the processes of a
deployment.

Why the window slides: the resources of the server are spent at the moment of the request, so the counter holds the
moments of the requests of the session and drops the ones that fell out of the window. A fixed window would let a
visitor spend the whole quota at the last second of one window and at the first second of the next one, and the
limit exists to bound the work of the server.

Why the clock is injected: the rate is decided by the server and never by the visitor (FR-031), and a test moves the
clock by hand instead of waiting for a minute.

What is measured is the requests of ONE session and never the address of the client: the facade has no trusted
address of the visitor, because the repository has no policy of the headers of a proxy, and the session is the only
identity the facade can trust (ADR-047).
"""

from __future__ import annotations

import math
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

# The ceiling of the requests of one session in the window, and the length of the window in seconds. The two are the
# defaults of the decision and the deployment changes them with the settings of the configuration.
DEFAULT_REQUESTS = 120
DEFAULT_WINDOW_SECONDS = 60


@dataclass(frozen=True)
class RateDecision:
    """The answer of the counter: the request is allowed or it is refused, and how long the caller waits.

    Why the wait is a number of seconds and not a moment: the front never computes a wait with the clock of the
    browser, and it shows the number of seconds the server wrote (ADR-047).
    """

    allowed: bool
    retry_after_seconds: int = 0
    remaining: int = 0


class RateLimiter:
    """The counter of the requests of every session, in the memory of the process.

    Why the counter is per session and not per address: the facade has no trusted address of the visitor, and a limit
    per address would be a limit that a visitor escapes by asking for a new session (ADR-047).

    Why the moments are kept and not a number: the window slides, so the counter has to know when every request of the
    session happened to know which ones fell out of the window.

    Why the counter drops the sessions that said nothing: a session that the visitor abandoned kept its key in the
    counter for ever, and the memory of a visitor dies with the visitor (ADR-030).

    Why the lock is here: the routes of the facade run in the thread pool of the server, and two requests of the same
    session may be counted at the same moment.
    """

    def __init__(
        self,
        *,
        limit: int = DEFAULT_REQUESTS,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        """The counter with the ceiling of the requests of a session and the length of the window.

        Why the clock is an argument: the rate is decided by the server, and the test moves the clock by hand.
        """
        self.limit = limit
        self.window_seconds = window_seconds
        self._clock = clock or (lambda: datetime.now(UTC))
        self._moments: dict[str, list[datetime]] = {}
        self._lock = threading.Lock()

    def now(self) -> datetime:
        """The moment of the server, taken from the same clock the counter uses."""
        return self._clock()

    def acquire(self, session_id: str) -> RateDecision:
        """Counts one request of the session and answers whether it is allowed.

        Why the refused request is not counted: the request was not served, and the work of the server was not spent
        on it. The counter keeps the moments of the requests that were served.

        Why the window sweeps every session and not only the one that asks: a session that the visitor abandoned kept
        its key in the counter for ever, and the memory of a visitor dies with the visitor (ADR-030).

        What the wait of a refusal is: the number of seconds until the oldest request of the window falls out of it,
        which is the shortest wait that can work.
        """
        with self._lock:
            now = self._clock()
            window_start = now - timedelta(seconds=self.window_seconds)
            self._sweep(window_start)
            moments = self._moments.get(session_id, [])
            if len(moments) >= self.limit:
                oldest = min(moments)
                wait = (oldest + timedelta(seconds=self.window_seconds) - now).total_seconds()
                return RateDecision(allowed=False, retry_after_seconds=max(1, math.ceil(wait)), remaining=0)
            moments.append(now)
            self._moments[session_id] = moments
            return RateDecision(allowed=True, retry_after_seconds=0, remaining=self.limit - len(moments))

    def _sweep(self, window_start: datetime) -> None:
        """Drops the sessions that have no request inside the window.

        Why the sweep is its own method: the counter has no timer of its own, and the request that comes is the
        moment where the dead sessions are found and dropped (ADR-030).
        """
        for session_id in list(self._moments):
            alive = [moment for moment in self._moments[session_id] if moment > window_start]
            if alive:
                self._moments[session_id] = alive
            else:
                del self._moments[session_id]

    def forget(self, session_id: str) -> None:
        """Drops the counter of the session.

        Why: the counter of a session that ended is dead, and the memory of an anonymous visitor dies with the
        visitor (ADR-030).
        """
        with self._lock:
            self._moments.pop(session_id, None)


__all__ = [
    "DEFAULT_REQUESTS",
    "DEFAULT_WINDOW_SECONDS",
    "RateDecision",
    "RateLimiter",
]
