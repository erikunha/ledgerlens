"""The time to live of a branch: the two deadlines, the check of the expiry and the cleanup of the expired branches.

Why it exists: ADR-029 moved the rule of the expiry out of the branch layer and into this module, and made the
cleanup of the expired branches a job of the process. There is one rule of the time to live and not two: the layer
asks this module for the expiry of a branch, and the job that deletes the expired branches asks it for the same
moments. Two copies of the rule would drift apart, and a branch that the layer refuses would never be deleted.

What the module holds:

* the two deadlines: the idle one of sixty minutes, counted from the last activity of the visitor, and the absolute
  one of four hours, counted from the creation of the branch;
* the computation of the expiry of a branch, which is the earlier of the two deadlines;
* the check of the expiry of a branch;
* the cleanup: the sweep that deletes the expired branches, the thread that runs it and the command that runs it.

Why the clock of the job is the clock of the server: the expiry is decided by the server and never by the visitor
(FR-031), and the branch that the job deletes and the branch that the layer refuses have to be the same branch at
the same moment.

Why the job names the owner of every branch it deletes: the isolation of the owner is a promise of the store, and the
deletion goes through the store like every other operation, so it is never bypassed. The listing of the expired
branches crosses the owners on purpose, and the deletion names the owner it found.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from ledgerlens.sandbox.store import BranchNotFound, BranchStore, SandboxBranchRow

log = logging.getLogger(__name__)

# The idle deadline of a branch: one hour of silence of the visitor (FR-023).
IDLE_TTL_SECONDS = 3600
# The absolute deadline of a branch: four hours from the creation, whatever the visitor does (FR-023).
ABSOLUTE_TTL_SECONDS = 14400
# The period of the sweep. Thirty seconds is half of the sixty seconds of FR-024, so the delay between the expiry of
# a branch and the deletion of its rows is inside the promise even when a sweep begins just before the expiry.
CLEANUP_INTERVAL_SECONDS = 30


def _server_clock() -> datetime:
    """The clock of the server: the moment of this process, in UTC.

    Why the clock is never taken from a caller of the job: the expiry is decided by the server and never by the
    visitor (FR-031), and a moment that comes from a request would let a visitor delete the branch of another one.
    """
    return datetime.now(UTC)


def expiry_of(
    last_activity_at: datetime,
    created_at: datetime,
    *,
    idle_ttl_seconds: int = IDLE_TTL_SECONDS,
    absolute_ttl_seconds: int = ABSOLUTE_TTL_SECONDS,
) -> datetime:
    """The expiry of a branch: the idle deadline from the last activity, never past the absolute deadline.

    Why the earlier of the two: a visitor that keeps working must not keep a branch forever, and a branch that
    nobody touches must not live longer than the day of the deployment. The idle deadline is counted from the last
    activity of the visitor and the absolute one from the creation of the branch, so the second one never moves.

    Why the deadlines are arguments: the configuration of the deployment decides them, and the rule itself is the
    same for every value of them.
    """
    idle = last_activity_at + timedelta(seconds=idle_ttl_seconds)
    absolute = created_at + timedelta(seconds=absolute_ttl_seconds)
    return min(idle, absolute)


def is_expired(row: SandboxBranchRow, now: datetime) -> bool:
    """True when the branch outlived its time to live.

    Why the row and the moment and not the clock: the caller decides which clock it uses, and the layer and the
    job of the cleanup use the same one, so they refuse and delete the same branches at the same moment (ADR-029).
    """
    return now >= row.expires_at


def cleanup_expired_branches(
    store: BranchStore, *, clock: Callable[[], datetime] | None = None
) -> list[str]:
    """One sweep of the cleanup: every branch whose expiry has passed is deleted, and nothing else is touched.

    Why the listing crosses the owners: the expired branch of a visitor that never comes back is the one the
    promise of FR-024 is about. The deletion names the owner it found, so the isolation of the owner is never
    bypassed and the deletion is an operation of the store like every other one.

    Why a branch that is already gone is not an error: two workers of the facade may sweep at the same time, and the
    branch that one of them deleted is not there when the other one reaches it.

    What it returns: the identifiers of the branches it deleted, in the order of the listing.
    """
    now = (clock or _server_clock)()
    deleted: list[str] = []
    for row in store.list_expired(now):
        try:
            store.delete_branch(row.branch_id, row.owner_session)
        except BranchNotFound:
            # The branch was already deleted by another sweep, so there is nothing left to delete.
            continue
        deleted.append(row.branch_id)
    if deleted:
        log.info("cleanup: %d expired branch(es) deleted", len(deleted))
    return deleted


class CleanupWorker:
    """The sweep of the expired branches, in a daemon thread of the process.

    Why a daemon thread: a process that is killed does not wait for the sweep, and the sweep never keeps the
    process alive. The thread is started by the lifespan of the app and stopped by it, so a test that builds the
    app without the lifespan has no thread at all (ADR-029).

    Why the thread waits on an event and not on a sleep: the thread stops at once when it is told to stop, and the
    process does not have to wait for the end of an interval.
    """

    def __init__(
        self,
        store: BranchStore,
        *,
        interval_seconds: float = CLEANUP_INTERVAL_SECONDS,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.store = store
        self.interval_seconds = interval_seconds
        self._clock = clock
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def thread(self) -> threading.Thread | None:
        """The thread of the worker, when it was started."""
        return self._thread

    def start(self) -> None:
        """Starts the thread of the sweep. Starting a worker that runs does nothing.

        Why the sweep runs at once: the promise of FR-024 counts from the expiry of the branch, and a worker that
        waits for its first interval would spend half of the promise before it starts to work.
        """
        if self._thread is not None:
            return
        thread = threading.Thread(target=self._loop, name="ledgerlens-cleanup", daemon=True)
        self._thread = thread
        thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Stops the thread of the sweep and waits for the sweep that is running to end.

        Why the wait: the thread of a facade that stops must not delete a branch after the app is down, so the
        process waits for the sweep in flight instead of killing it in the middle of a deletion.
        """
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout)

    def _loop(self) -> None:
        """The loop of the thread: one sweep, then the wait for the next one.

        Why the failure of a sweep does not stop the thread: a store that is unreachable for a moment must not take
        the cleanup of the deployment down with it, and the next sweep tries again.
        """
        while not self._stop.is_set():
            try:
                cleanup_expired_branches(self.store, clock=self._clock)
            except Exception:
                log.warning("cleanup: the sweep failed", exc_info=True)
            # The wait on the event is what makes the thread stop at once, and not at the end of the interval.
            self._stop.wait(self.interval_seconds)


__all__ = [
    "ABSOLUTE_TTL_SECONDS",
    "CLEANUP_INTERVAL_SECONDS",
    "CleanupWorker",
    "IDLE_TTL_SECONDS",
    "cleanup_expired_branches",
    "expiry_of",
    "is_expired",
]
