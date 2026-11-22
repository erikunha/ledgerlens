"""The events of the lifecycle of a branch: the hub that publishes them and the shape of the stream.

Why it exists: ADR-047 decided that the lifecycle of a branch travels as a stream of named events, with a sequence
that grows by one for every event of the lifecycle, a heartbeat every fifteen seconds and a resume by the last
identifier of the event. This module holds the two halves of that decision: the shape of the events (the eight
names, the four fields that every payload carries and the text of the server sent events) and the hub that publishes
them.

Why the hub keeps the counter and never the event: the truth of a branch is the answer of
`GET /v1/sandboxes/{sandbox_id}` and never the stream (ADR-047, ADR-044). A second copy of the log of the branch in
the memory of the process would die at the restart of the process and would not be shared between the workers of a
deployment with more than one worker. The hub therefore keeps the subscribers of a branch and the counter of the
sequence of a branch, and a resume that cannot be proven answers with `stream.resync`, so the client re-reads the
branch instead of receiving an event that never happened.

Why the hub is plain Python and knows nothing about asyncio: the events are published from the routes of the
facade, which run in the threadpool of the server, and a subscriber is a callable that takes the event and hands it
over. A hub with a queue of its own would have to know about the loop of the server, and the loop belongs to the
layer that writes the stream. The hub therefore knows nothing about the transport, and the route owns the queue of
its own stream.

Why the sequence is per branch and lives in the memory of the process: the counter is the state of the process,
exactly like the worker of the cleanup of ADR-029, and it starts again when the process starts. The sequence is NOT
the revision of the branch: the revision moves only on a commit, the undo moves it back, and a number that goes back
is not a sequence.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, TypedDict

from ledgerlens.sim.events import canonical_json

# The version of the shape of the payload of an event. It is the text "1", like the header of the answers of the
# facade, and it travels inside the payload because the payload of an event is not a resource of the contract.
SCHEMA_VERSION = "1"

# The eight names of the stream. Six of them are the lifecycle of the branch, one of them is the resync of a
# reconnection that cannot be proven and one of them is the end of the stream.
EVENT_BRANCH_OPENED = "branch.opened"
EVENT_MUTATION_COMMITTED = "branch.mutation.committed"
EVENT_UNDONE = "branch.undone"
EVENT_RESET = "branch.reset"
EVENT_BRANCH_EXPIRED = "branch.expired"
EVENT_STREAM_RESYNC = "stream.resync"
EVENT_STREAM_CLOSED = "stream.closed"
EVENT_STREAM_HEARTBEAT = "stream.heartbeat"

EVENT_NAMES: tuple[str, ...] = (
    EVENT_BRANCH_OPENED,
    EVENT_MUTATION_COMMITTED,
    EVENT_UNDONE,
    EVENT_RESET,
    EVENT_BRANCH_EXPIRED,
    EVENT_STREAM_RESYNC,
    EVENT_STREAM_CLOSED,
    EVENT_STREAM_HEARTBEAT,
)

# The cadence of the heartbeat: fifteen seconds, the number the design package names for the idle heartbeat of the
# trace transport, so the two streams of the deployment share one number (ADR-047).
HEARTBEAT_INTERVAL_SECONDS = 15

# The three answers of a resume: the header is absent, the header is the counter of the hub, or the header is
# anything else and the client missed events.
RESUME_OPEN = "open"
RESUME_CONTINUE = "continue"
RESUME_RESYNC = "resync"

# The two reasons of a resync: the identifier is behind the counter of the hub, or the hub does not know it at all.
RESYNC_REASON_NOT_CURRENT = "not_current"
RESYNC_REASON_UNKNOWN = "unknown"

# The reasons of the end of a stream. There are only two: the row of the branch is not there any more and the
# branch died. The disconnect of a client is not an event: the client that left is gone and the other connections of
# the branch are not affected by it.
CLOSED_REASON_EXPIRED = "branch_expired"
CLOSED_REASON_GONE = "branch_gone"

# A subscriber of the branch: a callable that takes the event and hands it over. The hub never waits for it.
Subscriber = Callable[["StreamEvent"], None]


class EventPayload(TypedDict):
    """The four fields that every payload of an event carries, over and above the fields of the event itself.

    Why the same four: a client reads one shape, and the sequence travels next to the revision so that the two are
    never confused (ADR-047).
    """

    schema_version: str
    branch_id: str
    seq: int
    at: str


class OpenedPayload(EventPayload):
    """The payload of `branch.opened`: the facts of the creation and the state of the branch at the opening."""

    scenario_id: str
    base_snapshot_id: str
    base_canonical_hash: str
    current_canonical_hash: str
    revision: int
    created_at: str
    expires_at: str
    state: str


class CommittedPayload(EventPayload):
    """The payload of `branch.mutation.committed`: what moved and under which command."""

    revision: int
    canonical_hash: str
    command_id: str
    kind: str


class UndonePayload(EventPayload):
    """The payload of `branch.undone`: the undo of a command and the event it took back."""

    revision: int
    canonical_hash: str
    command_id: str
    kind: str
    undone_event_uid: str


class ResetPayload(EventPayload):
    """The payload of `branch.reset`: the branch back at the published base."""

    revision: int
    canonical_hash: str
    base_canonical_hash: str


class ExpiredPayload(EventPayload):
    """The payload of `branch.expired`: the deadline that passed and the state of the branch."""

    expires_at: str
    state: str


class ResyncPayload(EventPayload):
    """The payload of `stream.resync`: the identifier the client sent and the reason it cannot be proven."""

    last_event_id: str
    reason: str


class ClosedPayload(EventPayload):
    """The payload of `stream.closed`: the reason the stream ended."""

    reason: str


class HeartbeatPayload(EventPayload):
    """The payload of `stream.heartbeat`: the moment and the sequence of the last event of the lifecycle.

    The heartbeat carries no change of the branch: it says that the connection is alive and nothing else, and the
    client that acts on the six names of the lifecycle cannot be confused by it (ADR-047).
    """

    last_seq: int


@dataclass(frozen=True)
class StreamEvent:
    """One event of the stream: its name, its payload and the sequence the `id:` line carries.

    `seq` is None for the heartbeat, because the heartbeat carries no `id:` line: the `Last-Event-ID` of the
    browser never moves because of a heartbeat and the counter of the hub never moves either (ADR-047).
    """

    name: str
    payload: Mapping[str, Any]
    seq: int | None = None


@dataclass(frozen=True)
class ResumeDecision:
    """The answer of the hub to the `Last-Event-ID` that a client sent.

    `kind` is one of the three answers of the resume, `last_event_id` echoes the identifier that the client sent and
    `reason` says why the reconnection cannot be proven.
    """

    kind: str
    last_event_id: str | None = None
    reason: str | None = None


def opened_fields(
    *,
    scenario_id: str,
    base_snapshot_id: str,
    base_canonical_hash: str,
    current_canonical_hash: str,
    revision: int,
    created_at: datetime,
    expires_at: datetime,
    state: str,
) -> dict[str, Any]:
    """The fields of the event of the opening, over and above the four common ones.

    Why the event of the opening carries the facts of the creation AND the state of the branch at the moment of the
    opening: a stream that opens on a branch that was created a minute ago did not witness the creation, so the
    event is true about the branch as it stands and not only about the branch as it was born (ADR-047).
    """
    return {
        "scenario_id": scenario_id,
        "base_snapshot_id": base_snapshot_id,
        "base_canonical_hash": base_canonical_hash,
        "current_canonical_hash": current_canonical_hash,
        "revision": revision,
        "created_at": created_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "state": state,
    }


def committed_fields(*, revision: int, canonical_hash: str, command_id: str, kind: str) -> dict[str, Any]:
    """The fields of the event of a commit: what moved and under which command."""
    return {
        "revision": revision,
        "canonical_hash": canonical_hash,
        "command_id": command_id,
        "kind": kind,
    }


def undone_fields(
    *, revision: int, canonical_hash: str, command_id: str, kind: str, undone_event_uid: str
) -> dict[str, Any]:
    """The fields of the event of an undo: the undo of a command and the event it took back."""
    return {
        "revision": revision,
        "canonical_hash": canonical_hash,
        "command_id": command_id,
        "kind": kind,
        "undone_event_uid": undone_event_uid,
    }


def reset_fields(*, revision: int, canonical_hash: str, base_canonical_hash: str) -> dict[str, Any]:
    """The fields of the event of a reset: the branch back at the published base."""
    return {
        "revision": revision,
        "canonical_hash": canonical_hash,
        "base_canonical_hash": base_canonical_hash,
    }


def expired_fields(*, expires_at: datetime, state: str = "expired") -> dict[str, Any]:
    """The fields of the event of the expiry: the deadline that passed and the state of the branch."""
    return {"expires_at": expires_at.isoformat(), "state": state}


def resync_fields(*, last_event_id: str, reason: str) -> dict[str, Any]:
    """The fields of the event of the resync: the identifier of the client and the reason it cannot be proven."""
    return {"last_event_id": last_event_id, "reason": reason}


def closed_fields(*, reason: str) -> dict[str, Any]:
    """The fields of the event of the close: the reason the stream ended."""
    return {"reason": reason}


def format_event(event: StreamEvent) -> str:
    """The text of an event of the stream: the `id:` line, the `event:` line, the `data:` line and the blank line.

    Why the three lines and the blank one: it is the shape of the server sent events, and the browser reads the
    `id:` line as the `Last-Event-ID` of the next reconnection, so the text of the `id:` line has to be the bare
    decimal integer of the sequence (ADR-047).
    """
    lines: list[str] = []
    if event.seq is not None:
        lines.append(f"id: {event.seq}")
    lines.append(f"event: {event.name}")
    lines.append(f"data: {canonical_json(event.payload)}")
    return "\n".join(lines) + "\n\n"


class EventHub:
    """The hub of the events of the lifecycle: the subscribers of a branch and the counter of its sequence.

    Why the hub keeps no event: the hub is a counter and a list of subscribers, and nothing else. The truth of a
    branch is the answer of `GET /v1/sandboxes/{sandbox_id}`, and a hub that kept the events would be a second copy
    of the log of the branch, a copy that dies at the restart of the process and that the workers of a deployment do
    not share (ADR-047, ADR-044).

    Why the counter is per branch: the sequence of a branch is the sequence of that branch, and two branches of two
    sessions never share one (ADR-047).

    Why the hub is synchronous: the events are published from the routes of the facade, which run in the threadpool
    of the server, and a subscriber hands the event over without waiting. The queue that a stream waits on belongs to
    the route that writes it (ADR-047).

    Why the hub locks its counter: two routes of the threadpool may publish at the same moment, and the counter of the
    branch has to give a different sequence to every event of the lifecycle. The lock is re-entrant, because a
    subscriber may publish while the hub delivers an event to it.
    """

    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        """The hub of the process, with the clock of the server that the moments of the payloads carry.

        Why the clock is injected: the moment of an event is the moment of the server and never a moment that comes
        from a visitor (FR-031).
        """
        self._clock = clock or (lambda: datetime.now(UTC))
        self._subscribers: dict[str, list[Subscriber]] = {}
        self._counters: dict[str, int] = {}
        self._lock = threading.RLock()

    def now(self) -> datetime:
        """The moment of the server, the one the payload of an event carries (FR-031)."""
        return self._clock()

    def subscribe(self, branch_id: str, subscriber: Subscriber) -> None:
        """Adds a subscriber of the branch, so that it receives every event published for that branch.

        Why a list and not a set: two streams of the same branch are two subscribers, and both of them have to
        receive the events (ADR-047).
        """
        self._subscribers.setdefault(branch_id, []).append(subscriber)

    def unsubscribe(self, branch_id: str, subscriber: Subscriber) -> None:
        """Removes a subscriber of the branch, when its stream ends.

        Why the removal is silent when the subscriber is not there: the end of a stream may be seen twice, and a
        double end must not fail the route that is closing (ADR-047).
        """
        subscribers = self._subscribers.get(branch_id)
        if not subscribers:
            return
        try:
            subscribers.remove(subscriber)
        except ValueError:
            return
        if not subscribers:
            del self._subscribers[branch_id]

    def publish(self, branch_id: str, name: str, fields: Mapping[str, Any]) -> StreamEvent:
        """Publishes an event of the lifecycle to every subscriber of the branch and returns it.

        Why the hub owns the sequence and the moment: the two are the facts of the server and not of the caller, so
        the sequence of a branch is the same for every stream of that branch (ADR-047).

        Why the counter moves under the lock: two routes of the threadpool may publish at the same moment, and the
        branch that received the same sequence twice would make a client believe that it missed nothing while it
        missed an event (ADR-047).

        Why the delivery happens under the lock as well: the order of the events of a branch must be the order of
        their sequences, and a stream that received them in another order would carry a `Last-Event-ID` behind the
        counter of the hub.

        Why the event is not kept: the hub hands the event over and forgets it, and a resume that cannot be proven
        answers with a resync instead of repeating an event (ADR-047).
        """
        with self._lock:
            seq = self._counters.get(branch_id, 0) + 1
            self._counters[branch_id] = seq
            payload: dict[str, Any] = {
                "schema_version": SCHEMA_VERSION,
                "branch_id": branch_id,
                "seq": seq,
                "at": self.now().isoformat(),
                **fields,
            }
            event = StreamEvent(name=name, payload=payload, seq=seq)
            for subscriber in list(self._subscribers.get(branch_id, ())):
                subscriber(event)
        return event

    def counter(self, branch_id: str) -> int:
        """The sequence last given to the branch, and zero when the hub never published anything for it."""
        with self._lock:
            return self._counters.get(branch_id, 0)

    def heartbeat(self, branch_id: str) -> StreamEvent:
        """The heartbeat of a stream of the branch: it carries no `id:` line and it moves no counter.

        Why the heartbeat is not published: it is not an event of the lifecycle, and a client that counts the
        heartbeats must not move the `Last-Event-ID` of the browser (ADR-047).
        """
        last_seq = self.counter(branch_id)
        payload: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "branch_id": branch_id,
            "seq": last_seq,
            "at": self.now().isoformat(),
            "last_seq": last_seq,
        }
        return StreamEvent(name=EVENT_STREAM_HEARTBEAT, payload=payload, seq=None)

    def resync(self, branch_id: str, *, last_event_id: str, reason: str) -> StreamEvent:
        """The event of the resync of ONE connection: it carries no `id:` line and it moves no counter.

        Why the resync belongs to the connection and not to the branch: the three events of the stream are not events
        of the lifecycle, and the counter of the branch exists so that a client can prove that it missed nothing. A
        resync that moved the counter would make every reconnection look stale, because the event that moved it was
        never received by the client that disconnected (ADR-047).
        """
        last_seq = self.counter(branch_id)
        payload: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "branch_id": branch_id,
            "seq": last_seq,
            "at": self.now().isoformat(),
            "last_event_id": last_event_id,
            "reason": reason,
        }
        return StreamEvent(name=EVENT_STREAM_RESYNC, payload=payload, seq=None)

    def closed(self, branch_id: str, *, reason: str) -> StreamEvent:
        """The event of the close of ONE connection: it carries no `id:` line and it moves no counter.

        Why the close belongs to the connection and not to the branch: the server ends a connection when the row of
        the branch is gone or when the branch died, and the other connections of the branch are not affected by it
        (ADR-047).
        """
        last_seq = self.counter(branch_id)
        payload: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "branch_id": branch_id,
            "seq": last_seq,
            "at": self.now().isoformat(),
            "reason": reason,
        }
        return StreamEvent(name=EVENT_STREAM_CLOSED, payload=payload, seq=None)

    def resume(self, branch_id: str, last_event_id: str | None) -> ResumeDecision:
        """The answer of the hub to the `Last-Event-ID` that a client sent.

        The three answers of ADR-047: the header is absent and the stream opens, the header is the counter of the
        hub and the stream continues without a resync, and the header is anything else and the stream answers with a
        resync that says why. The identifier the client sent is echoed back in the resync, and the reason is
        `not_current` when the identifier is behind the counter and `unknown` when the hub does not know it (ADR-047).

        Why the header is read strictly: the header is the bare decimal integer of the sequence, with no sign, no
        space, no underscore and no leading zero. Anything else cannot be proven, so the stream answers with a resync
        with the reason `unknown` instead of guessing what the client meant (ADR-047).
        """
        text = last_event_id or ""
        if not text:
            return ResumeDecision(kind=RESUME_OPEN)
        identifier = _canonical_sequence(text)
        if identifier is None:
            return ResumeDecision(kind=RESUME_RESYNC, last_event_id=text, reason=RESYNC_REASON_UNKNOWN)
        if branch_id not in self._counters:
            # The hub never published anything for this branch, so it cannot prove the identifier.
            return ResumeDecision(kind=RESUME_RESYNC, last_event_id=text, reason=RESYNC_REASON_UNKNOWN)
        current = self._counters[branch_id]
        if identifier == current:
            return ResumeDecision(kind=RESUME_CONTINUE, last_event_id=text)
        if identifier < current:
            return ResumeDecision(kind=RESUME_RESYNC, last_event_id=text, reason=RESYNC_REASON_NOT_CURRENT)
        # The identifier is ahead of the counter, so the hub never gave it to anybody.
        return ResumeDecision(kind=RESUME_RESYNC, last_event_id=text, reason=RESYNC_REASON_UNKNOWN)


def _canonical_sequence(text: str) -> int | None:
    """The sequence of a `Last-Event-ID` that is the bare decimal integer, and None for every other shape.

    Why the digits of the ascii alphabet only: a digit of another alphabet is a digit for `int()` and is not the bare
    decimal integer that ADR-047 names, and a header that a client cannot write by accident is a header that proves
    nothing.
    """
    if not text.isascii() or not text.isdigit():
        return None
    if len(text) > 1 and text.startswith("0"):
        # A leading zero is not the canonical text of a number, and two texts of one number are two identifiers.
        return None
    return int(text)


__all__ = [
    "CLOSED_REASON_EXPIRED",
    "CLOSED_REASON_GONE",
    "EVENT_BRANCH_EXPIRED",
    "EVENT_BRANCH_OPENED",
    "EVENT_MUTATION_COMMITTED",
    "EVENT_NAMES",
    "EVENT_RESET",
    "EVENT_STREAM_CLOSED",
    "EVENT_STREAM_HEARTBEAT",
    "EVENT_STREAM_RESYNC",
    "EVENT_UNDONE",
    "HEARTBEAT_INTERVAL_SECONDS",
    "RESUME_CONTINUE",
    "RESUME_OPEN",
    "RESUME_RESYNC",
    "RESYNC_REASON_NOT_CURRENT",
    "RESYNC_REASON_UNKNOWN",
    "SCHEMA_VERSION",
    "ClosedPayload",
    "CommittedPayload",
    "EventHub",
    "EventPayload",
    "ExpiredPayload",
    "HeartbeatPayload",
    "OpenedPayload",
    "ResetPayload",
    "ResyncPayload",
    "ResumeDecision",
    "StreamEvent",
    "Subscriber",
    "UndonePayload",
    "closed_fields",
    "committed_fields",
    "expired_fields",
    "format_event",
    "opened_fields",
    "resync_fields",
    "reset_fields",
    "undone_fields",
]
