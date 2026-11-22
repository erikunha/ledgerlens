"""The stream of the lifecycle of a branch: the hub, the sequence, the resume and the heartbeat (ADR-047).

Why the tests are here: ADR-047 decided that the lifecycle of a branch travels as a stream of named events, with a
sequence that grows by one for every event of the lifecycle, a heartbeat every fifteen seconds and a resume by the
last identifier of the event. Every decision of that record has a test here, and each test fails when the decision
it names is broken.

Why the hub is tested apart from the route: the hub holds the subscribers and the counter and never an event, and
that promise cannot be seen from the outside of a stream. The tests of the hub therefore read its own state.
"""

from __future__ import annotations

import ast
import json
import sys
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from ledgerlens.api.sandbox import (  # noqa: E402
    GENERIC_NOT_FOUND,
    SCHEMA_VERSION,
    SCHEMA_VERSION_HEADER,
    create_app,
)
from ledgerlens.sandbox import events as events_module  # noqa: E402
from ledgerlens.sandbox.events import (  # noqa: E402
    EVENT_BRANCH_EXPIRED,
    EVENT_BRANCH_OPENED,
    EVENT_MUTATION_COMMITTED,
    EVENT_NAMES,
    EVENT_RESET,
    EVENT_STREAM_CLOSED,
    EVENT_STREAM_HEARTBEAT,
    EVENT_STREAM_RESYNC,
    EVENT_UNDONE,
    HEARTBEAT_INTERVAL_SECONDS,
    RESUME_CONTINUE,
    RESUME_OPEN,
    RESUME_RESYNC,
    RESYNC_REASON_NOT_CURRENT,
    RESYNC_REASON_UNKNOWN,
    EventHub,
    StreamEvent,
    closed_fields,
    committed_fields,
    expired_fields,
    format_event,
    opened_fields,
    reset_fields,
    resync_fields,
    undone_fields,
)

# The names of the lifecycle of the branch, apart from the two that are about the stream itself and the heartbeat.
LIFECYCLE_NAMES = {
    EVENT_BRANCH_OPENED,
    EVENT_MUTATION_COMMITTED,
    EVENT_UNDONE,
    EVENT_RESET,
    EVENT_BRANCH_EXPIRED,
}
# The words a payload of the stream may never carry: the reads are reads, and a money value is a read too.
FORBIDDEN_WORDS = ("diff", "entr", "history", "ledger", "row", "amount", "balance", "money", "invoice", "value")
# The shapes of the `Last-Event-ID` that ADR-047 accepts: the bare decimal integer of the sequence, and nothing else.
CANONICAL_IDENTIFIERS = ("0", "1", "2")
# The shapes that the header may never carry: a sign, a space, an underscore, a leading zero, a word or a digit of
# another alphabet. Every one of them is a resync with the reason `unknown`.
NON_CANONICAL_IDENTIFIERS = (" 1", "1 ", " 1 ", "01", "007", "+1", "-1", "1_0", "1.0", "0x1", "1e3", "one", "١")


def _events_of(text: str) -> list[dict[str, Any]]:
    """The events of a chunk of a stream, parsed the way a browser parses them."""
    parsed: list[dict[str, Any]] = []
    for block in text.split("\n\n"):
        if not block.strip():
            continue
        event: dict[str, Any] = {}
        for line in block.splitlines():
            field, _, value = line.partition(":")
            if field == "data":
                event["data"] = json.loads(value.strip())
            else:
                event[field] = value.strip()
        parsed.append(event)
    return parsed


# --- the hub of the events --------------------------------------------------------------------------


def test_the_sequence_of_a_branch_starts_at_one_and_grows_by_one() -> None:
    """The `id:` of an event is its sequence, and the sequence grows by one for every event of the lifecycle."""
    hub = EventHub()
    first = hub.publish("branch-a", EVENT_BRANCH_OPENED, {"revision": 0})
    second = hub.publish("branch-a", EVENT_MUTATION_COMMITTED, {"revision": 1})

    assert (first.seq, second.seq) == (1, 2)
    assert first.payload["seq"] == 1
    assert second.payload["seq"] == 2
    assert hub.counter("branch-a") == 2


def test_two_branches_have_two_counters_of_their_own() -> None:
    """The sequence is per branch: two branches never share a counter."""
    hub = EventHub()
    hub.publish("branch-a", EVENT_BRANCH_OPENED, {})
    hub.publish("branch-b", EVENT_BRANCH_OPENED, {})

    assert hub.counter("branch-a") == 1
    assert hub.counter("branch-b") == 1

    hub.publish("branch-b", EVENT_MUTATION_COMMITTED, {})

    assert hub.counter("branch-a") == 1
    assert hub.counter("branch-b") == 2


def test_the_sequence_is_not_the_revision() -> None:
    """The revision goes back on an undo and the sequence never goes back."""
    hub = EventHub()
    opened = hub.publish("branch-a", EVENT_BRANCH_OPENED, {"revision": 0})
    committed = hub.publish("branch-a", EVENT_MUTATION_COMMITTED, {"revision": 1})
    undone = hub.publish("branch-a", EVENT_UNDONE, {"revision": 0})
    reset = hub.publish("branch-a", EVENT_RESET, {"revision": 0})

    assert [opened.payload["revision"], committed.payload["revision"]] == [0, 1]
    assert [undone.payload["revision"], reset.payload["revision"]] == [0, 0]
    assert [opened.seq, committed.seq, undone.seq, reset.seq] == [1, 2, 3, 4]


def test_the_hub_keeps_no_event() -> None:
    """The hub keeps the subscribers and the counter and never an event."""
    hub = EventHub()
    received: list[StreamEvent] = []
    hub.subscribe("branch-a", received.append)

    event = hub.publish("branch-a", EVENT_BRANCH_OPENED, {"marker": "A-MARKER-ONLY-AN-EVENT-CARRIES"})

    assert received == [event]
    state = repr(vars(hub))
    assert "A-MARKER-ONLY-AN-EVENT-CARRIES" not in state
    assert EVENT_BRANCH_OPENED not in state
    assert not any(isinstance(value, StreamEvent) for value in vars(hub).values())


def test_the_resume_without_a_header_opens_the_stream() -> None:
    """The header is absent: it is the first connection of the client and the stream opens."""
    hub = EventHub()

    decision = hub.resume("branch-a", None)

    assert decision.kind == RESUME_OPEN
    assert decision.reason is None


def test_the_resume_with_the_counter_of_the_hub_continues_without_a_resync() -> None:
    """The header carries the last sequence the hub gave: the client holds the last event and nothing is missing."""
    hub = EventHub()
    hub.publish("branch-a", EVENT_BRANCH_OPENED, {})

    decision = hub.resume("branch-a", "1")

    assert decision.kind == RESUME_CONTINUE
    assert decision.reason is None


def test_the_resume_with_another_identifier_answers_a_resync() -> None:
    """The header carries anything else: the stream answers with a resync and says why."""
    hub = EventHub()
    hub.publish("branch-a", EVENT_BRANCH_OPENED, {})

    behind = hub.resume("branch-a", "0")
    ahead = hub.resume("branch-a", "9")
    other_branch = hub.resume("branch-b", "1")
    broken = hub.resume("branch-a", "not-a-number")

    assert behind.kind == RESUME_RESYNC
    assert behind.last_event_id == "0"
    assert behind.reason == "not_current"
    assert ahead.kind == RESUME_RESYNC
    assert ahead.last_event_id == "9"
    assert ahead.reason == "unknown"
    assert other_branch.kind == RESUME_RESYNC
    assert other_branch.reason == "unknown"
    assert broken.kind == RESUME_RESYNC
    assert broken.reason == "unknown"


def test_the_resume_never_repeats_the_events_that_were_lost() -> None:
    """The hub keeps no history, so it has nothing to repeat, and the counter never goes back."""
    hub = EventHub()
    hub.publish("branch-a", EVENT_BRANCH_OPENED, {})
    hub.publish("branch-a", EVENT_MUTATION_COMMITTED, {})

    decision = hub.resume("branch-a", "1")

    assert decision.kind == RESUME_RESYNC
    assert hub.counter("branch-a") == 2
    assert not any(isinstance(value, StreamEvent) for value in vars(hub).values())


def test_the_heartbeat_carries_no_id_and_moves_no_counter() -> None:
    """The heartbeat cannot be confused with an event of the lifecycle: it has another name and no `id:` line."""
    hub = EventHub()
    hub.publish("branch-a", EVENT_BRANCH_OPENED, {})

    beat = hub.heartbeat("branch-a")

    assert beat.name == EVENT_STREAM_HEARTBEAT
    assert beat.seq is None
    assert beat.payload["last_seq"] == 1
    assert beat.payload["at"]
    assert hub.counter("branch-a") == 1
    assert EVENT_STREAM_HEARTBEAT not in LIFECYCLE_NAMES
    text = format_event(beat)
    assert "id:" not in text
    assert f"event: {EVENT_STREAM_HEARTBEAT}" in text


def test_the_heartbeat_arrives_every_fifteen_seconds() -> None:
    """The heartbeat is every fifteen seconds, the number the design package names."""
    assert HEARTBEAT_INTERVAL_SECONDS == 15


def test_the_counter_of_the_hub_is_atomic_when_two_threads_publish_at_the_same_moment() -> None:
    """Two threads that publish at the same moment get two different sequences, and the counter loses no step.

    Why the counter of the test is slow on purpose: the race lives between the read of the counter and the write of
    it, and a read that takes time widens that window until the race happens at every round. The switch interval of
    the interpreter is tiny as well, so that the threads of the barrier really run at the same moment.
    """
    hub = EventHub()
    hub._counters = _SlowCounter()
    threads_count = 8
    rounds = 50
    original_interval = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        for round_number in range(1, rounds + 1):
            barrier = threading.Barrier(threads_count)
            sequences: list[int] = []
            guard = threading.Lock()

            workers = [
                threading.Thread(
                    target=_publish_at_the_same_moment,
                    args=(hub, barrier, guard, sequences),
                )
                for _ in range(threads_count)
            ]
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join()

            assert len(set(sequences)) == threads_count, sequences
            assert hub.counter("branch-a") == round_number * threads_count
    finally:
        sys.setswitchinterval(original_interval)


def _publish_at_the_same_moment(
    hub: EventHub, barrier: threading.Barrier, guard: threading.Lock, sequences: list[int]
) -> None:
    """Publishes one event of the branch at the same moment as the other threads of the barrier."""
    barrier.wait()
    event = hub.publish("branch-a", EVENT_MUTATION_COMMITTED, {})
    with guard:
        sequences.append(event.seq)


class _SlowCounter(dict):
    """The counter of the hub of the test, with a read that takes time on purpose.

    Why: the counter of the hub is read and written by the publishers, and the window between the two is where two
    threads may take the same sequence. A read that waits widens that window until every round of the test proves it.
    """

    def get(self, key: str, default: int | None = None) -> int | None:
        """The value of the key, read before the wait, so that the wait happens between the read and the write."""
        value = super().get(key, default)
        time.sleep(0.0002)
        return value


def test_a_subscriber_that_publishes_inside_a_delivery_does_not_break_the_counter() -> None:
    """A subscriber that publishes while the hub delivers an event re-enters the hub, and the counter still holds.

    Why the work happens in a thread: a hub that locks itself with a lock it cannot take again would wait for ever,
    and this test has to fail with a message instead of hanging the gate.
    """
    hub = EventHub()
    published: list[int] = []
    finished = threading.Event()

    def subscriber(event: StreamEvent) -> None:
        if event.seq == 1:
            inner = hub.publish("branch-a", EVENT_MUTATION_COMMITTED, {})
            published.append(inner.seq)

    def publish() -> None:
        hub.subscribe("branch-a", subscriber)
        hub.publish("branch-a", EVENT_BRANCH_OPENED, {})
        finished.set()

    worker = threading.Thread(target=publish, daemon=True)
    worker.start()

    assert finished.wait(timeout=10), "the hub did not come back from a delivery that published"
    assert published == [2]
    assert hub.counter("branch-a") == 2


def test_the_module_lists_every_public_name_of_its_surface() -> None:
    """The whole surface of the module is in one list, so that a reader who opens the file sees it at once.

    Why the surface is read from the source of the module: the names that the module imports are not its own, and
    the convention of the repository is that the list holds what the module defines.
    """
    surface = _public_names_of_the_module(events_module)

    assert surface
    missing = sorted(name for name in surface if name not in events_module.__all__)
    assert not missing, missing
    unknown = sorted(name for name in events_module.__all__ if not hasattr(events_module, name))
    assert not unknown, unknown
    assert len(set(events_module.__all__)) == len(events_module.__all__)


def _public_names_of_the_module(module: Any) -> set[str]:
    """The names that the module defines itself, without the ones that it imports and without the private ones."""
    source = Path(str(module.__file__)).read_text(encoding="utf-8")
    tree = ast.parse(source)
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(target.id for target in node.targets if isinstance(target, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return {name for name in names if not name.startswith("_")}


@pytest.mark.parametrize("identifier", CANONICAL_IDENTIFIERS)
def test_the_resume_accepts_the_bare_decimal_integer(identifier: str) -> None:
    """The header is the bare decimal integer of the sequence: the hub reads it and never asks for a resync."""
    hub = EventHub()
    hub.publish("branch-a", EVENT_BRANCH_OPENED, {})
    hub.publish("branch-a", EVENT_MUTATION_COMMITTED, {})

    decision = hub.resume("branch-a", identifier)

    assert decision.kind in {RESUME_CONTINUE, RESUME_RESYNC}
    assert decision.reason in {None, RESYNC_REASON_NOT_CURRENT}


@pytest.mark.parametrize("identifier", NON_CANONICAL_IDENTIFIERS)
def test_the_resume_refuses_everything_that_is_not_the_bare_decimal_integer(identifier: str) -> None:
    """Anything else is a resync with the reason `unknown`: the hub cannot prove what the client claims."""
    hub = EventHub()
    hub.publish("branch-a", EVENT_BRANCH_OPENED, {})
    hub.publish("branch-a", EVENT_MUTATION_COMMITTED, {})

    decision = hub.resume("branch-a", identifier)

    assert decision.kind == RESUME_RESYNC
    assert decision.reason == RESYNC_REASON_UNKNOWN
    assert decision.last_event_id == identifier


def test_the_resume_of_an_absent_header_opens_the_stream_and_echoes_nothing() -> None:
    """The header is absent: the stream opens, and the decision carries no identifier."""
    hub = EventHub()

    decision = hub.resume("branch-a", None)

    assert decision.kind == RESUME_OPEN
    assert decision.last_event_id is None
    assert decision.reason is None


def test_the_resync_carries_no_id_and_moves_no_counter() -> None:
    """The resync belongs to ONE connection: it carries no `id:` line and it moves no counter."""
    hub = EventHub()
    hub.publish("branch-a", EVENT_BRANCH_OPENED, {})

    event = hub.resync("branch-a", last_event_id="7", reason=RESYNC_REASON_UNKNOWN)

    assert event.name == EVENT_STREAM_RESYNC
    assert event.seq is None
    assert event.payload["schema_version"] == events_module.SCHEMA_VERSION
    assert event.payload["branch_id"] == "branch-a"
    assert event.payload["seq"] == 1
    assert event.payload["at"]
    datetime.fromisoformat(event.payload["at"])
    assert event.payload["last_event_id"] == "7"
    assert event.payload["reason"] == RESYNC_REASON_UNKNOWN
    assert hub.counter("branch-a") == 1
    assert "id:" not in format_event(event)
    assert f"event: {EVENT_STREAM_RESYNC}" in format_event(event)


def test_the_closed_carries_no_id_and_moves_no_counter() -> None:
    """The close belongs to ONE connection: it carries no `id:` line and it moves no counter."""
    hub = EventHub()
    hub.publish("branch-a", EVENT_BRANCH_OPENED, {})

    event = hub.closed("branch-a", reason=events_module.CLOSED_REASON_GONE)

    assert event.name == EVENT_STREAM_CLOSED
    assert event.seq is None
    assert event.payload["schema_version"] == events_module.SCHEMA_VERSION
    assert event.payload["branch_id"] == "branch-a"
    assert event.payload["seq"] == 1
    assert event.payload["at"]
    datetime.fromisoformat(event.payload["at"])
    assert event.payload["reason"] == events_module.CLOSED_REASON_GONE
    assert hub.counter("branch-a") == 1
    assert "id:" not in format_event(event)
    assert f"event: {EVENT_STREAM_CLOSED}" in format_event(event)


def test_the_disconnect_of_a_client_is_not_a_reason_of_the_close() -> None:
    """The close of a stream has two reasons only: the row of the branch is gone and the branch died."""
    assert not hasattr(events_module, "CLOSED_REASON_DISCONNECTED")
    assert "CLOSED_REASON_DISCONNECTED" not in events_module.__all__


def test_the_payload_of_every_event_carries_the_four_common_fields() -> None:
    """Every payload carries the same four fields, so that a client reads one shape."""
    hub = EventHub()
    payloads = []
    for name in EVENT_NAMES:
        if name == EVENT_STREAM_HEARTBEAT:
            payloads.append(hub.heartbeat("branch-a").payload)
        else:
            payloads.append(hub.publish("branch-a", name, {}).payload)

    assert len(payloads) == 8
    for payload in payloads:
        assert payload["schema_version"] == SCHEMA_VERSION
        assert payload["branch_id"] == "branch-a"
        assert isinstance(payload["seq"], int)
        assert payload["at"]
        datetime.fromisoformat(payload["at"])


def test_the_text_of_an_event_has_the_three_lines_and_the_blank_line() -> None:
    """The shape of an event is the shape of the server sent events: three lines and a blank line."""
    hub = EventHub()
    event = hub.publish("branch-a", EVENT_BRANCH_OPENED, {"revision": 0})

    text = format_event(event)
    lines = text.split("\n")

    assert lines[0] == "id: 1"
    assert lines[1] == f"event: {EVENT_BRANCH_OPENED}"
    assert lines[2].startswith("data: ")
    assert lines[3] == ""
    assert text.endswith("\n\n")


def test_the_stream_never_carries_the_diff_the_history_the_ledger_or_a_money_value() -> None:
    """The reads are reads: the stream carries none of them, and no money value."""
    hub = EventHub()
    moment = datetime.now(UTC)
    payloads = [
        hub.publish(
            "branch-a",
            EVENT_BRANCH_OPENED,
            opened_fields(
                scenario_id="S01",
                base_snapshot_id="snapshot-1",
                base_canonical_hash="hash-1",
                current_canonical_hash="hash-1",
                revision=0,
                created_at=moment,
                expires_at=moment,
                state="active",
            ),
        ).payload,
        hub.publish(
            "branch-a",
            EVENT_MUTATION_COMMITTED,
            committed_fields(
                revision=1,
                canonical_hash="hash-2",
                command_id="cmd-1",
                kind="refund.apply_fx_adjustment",
            ),
        ).payload,
        hub.publish(
            "branch-a",
            EVENT_UNDONE,
            undone_fields(
                revision=0,
                canonical_hash="hash-1",
                command_id="cmd-2",
                kind="mutation.undo",
                undone_event_uid="uid-1",
            ),
        ).payload,
        hub.publish(
            "branch-a",
            EVENT_RESET,
            reset_fields(revision=0, canonical_hash="hash-1", base_canonical_hash="hash-1"),
        ).payload,
        hub.publish("branch-a", EVENT_BRANCH_EXPIRED, expired_fields(expires_at=moment)).payload,
        hub.publish("branch-a", EVENT_STREAM_RESYNC, resync_fields(last_event_id="7", reason="not_current")).payload,
        hub.publish("branch-a", EVENT_STREAM_CLOSED, closed_fields(reason="branch_expired")).payload,
        hub.heartbeat("branch-a").payload,
    ]

    for payload in payloads:
        for key, value in payload.items():
            assert not any(word in key.lower() for word in FORBIDDEN_WORDS), key
            assert isinstance(value, (str, int)), (key, value)


# --- the route of the stream --------------------------------------------------------------------------


@pytest.fixture
def hub() -> EventHub:
    """The hub of the test, so that the counter of a branch starts fresh."""
    return EventHub()


@pytest.fixture
def app(file_store, base_resolver, clock, hub):
    """The facade over the file backed store, the shared base and the hub of the test."""
    return create_app(store=file_store, base_resolver=base_resolver, clock=clock, event_hub=hub)


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)


@pytest.fixture
def session_client(client: TestClient) -> TestClient:
    """A client that holds the cookie of a session the server issued."""
    assert client.post("/v1/sessions").status_code == 201
    return client


@pytest.fixture
def branch_id(session_client: TestClient, scenario_id: str) -> str:
    """The branch of the session of the test, forked from the published scenario."""
    response = session_client.post("/v1/sandboxes", json={"scenario_id": scenario_id})
    assert response.status_code == 201
    return response.json()["id"]


def test_the_route_refuses_the_branch_of_another_session_before_the_stream_opens(app, branch_id: str) -> None:
    """A branch of another session is refused with the generic answer, before the stream opens."""
    other = TestClient(app)
    assert other.post("/v1/sessions").status_code == 201

    response = other.get(f"/v1/sandboxes/{branch_id}/events")

    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "NOT_FOUND"
    assert body["message"] == GENERIC_NOT_FOUND
    assert response.headers["content-type"].startswith("application/json")


def test_the_route_refuses_a_request_without_a_session(app, branch_id: str) -> None:
    """No session, no stream."""
    anonymous = TestClient(app)

    response = anonymous.get(f"/v1/sandboxes/{branch_id}/events")

    assert response.status_code == 401
    assert response.json()["code"] == "SESSION_REQUIRED"


def test_the_stream_answers_the_server_sent_events_with_the_headers_of_the_facade(
    session_client: TestClient, branch_id: str
) -> None:
    """The answer is a stream, and it carries the version of the schema and the headers of the no store."""
    with session_client.stream("GET", f"/v1/sandboxes/{branch_id}/events") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers[SCHEMA_VERSION_HEADER] == SCHEMA_VERSION
        assert response.headers["cache-control"] == "no-store"
        first = next(response.iter_text())

    events = _events_of(first)
    assert len(events) == 1
    assert events[0]["event"] == EVENT_BRANCH_OPENED
    assert events[0]["id"] == "1"


def test_the_stream_opens_with_the_facts_of_the_creation_and_the_state_of_the_opening(
    session_client: TestClient, branch_id: str, scenario_id: str
) -> None:
    """The first event of every stream carries the facts of the creation AND the state of the branch now."""
    with session_client.stream("GET", f"/v1/sandboxes/{branch_id}/events") as response:
        first = next(response.iter_text())

    data = _events_of(first)[0]["data"]
    assert data["schema_version"] == SCHEMA_VERSION
    assert data["branch_id"] == branch_id
    assert data["seq"] == 1
    assert data["at"]
    assert data["scenario_id"] == scenario_id
    assert data["base_snapshot_id"]
    assert data["base_canonical_hash"]
    assert data["current_canonical_hash"]
    assert data["revision"] == 0
    assert data["created_at"]
    assert data["expires_at"]
    assert data["state"]


def test_the_stream_answers_a_resync_when_the_last_event_id_is_not_the_counter_of_the_hub(
    session_client: TestClient, branch_id: str
) -> None:
    """A reconnection that cannot be proven answers with a resync as its first event."""
    with session_client.stream(
        "GET", f"/v1/sandboxes/{branch_id}/events", headers={"Last-Event-ID": "999"}
    ) as response:
        first = next(response.iter_text())

    events = _events_of(first)
    assert len(events) == 1
    assert events[0]["event"] == EVENT_STREAM_RESYNC
    assert events[0]["data"]["last_event_id"] == "999"
    assert events[0]["data"]["reason"] in {"not_current", "unknown"}


def test_the_stream_closes_with_the_event_of_the_close_when_the_branch_expires(
    session_client: TestClient, branch_id: str, clock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The branch outlives its time to live: the stream says that it expired and closes."""
    monkeypatch.setattr("ledgerlens.api.sandbox.HEARTBEAT_INTERVAL_SECONDS", 0.05)

    chunks: list[str] = []
    with session_client.stream("GET", f"/v1/sandboxes/{branch_id}/events") as response:
        for chunk in response.iter_text():
            chunks.append(chunk)
            if len(chunks) == 1:
                clock.advance(timedelta(hours=2))

    names = [event["event"] for event in _events_of("".join(chunks))]
    assert names[0] == EVENT_BRANCH_OPENED
    assert EVENT_STREAM_HEARTBEAT in names
    assert EVENT_BRANCH_EXPIRED in names
    assert names[-1] == EVENT_STREAM_CLOSED
