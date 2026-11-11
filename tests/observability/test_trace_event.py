"""The public trace contract: the `TraceEvent`, the adapter for the `Span` and the event sinks.

What they guarantee, and why: (a) every event the code produces satisfies the public schema of the design package, field
by field, so whoever consumes the trace does not have to guess the format; (b) a running span becomes `span.started`
and a finished span becomes `span.ended`, with the error when there was one; (c) the sequence number always grows,
even with spans arriving from different threads, because the coordinator is who numbers and it numbers under a
lock; (d) the parent of the span appears in the event, so the hierarchy survives the format change; (e) a repeated
callback of the same span does not produce two events, which protects the interface from duplicating a row; (f) a fake
key in a tool error reaches neither the event nor the file, because the second defence happens at the boundary;
(g) a real investigation becomes events with a growing sequence and a preserved hierarchy; (h) whoever reads the
events later gets only what is after the number they asked for, which is what a client that reconnects needs;
(i) memory has a ceiling per execution; (j) the file gives back exactly what was written; (k) a mode outside the
contract never reaches the sink; (l) the labels that arrive without a declaration are the safe ones, because an event
constructed without a mode is a deterministic sandbox, a dict read back without a mode is a recorded replay, and
neither is ever called live by accident.
"""

from __future__ import annotations

import json
import sys
import threading
from datetime import datetime
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from ledgerlens.agents.integrator import investigate
from ledgerlens.observability.trace import Span
from ledgerlens.observability.trace_event import (
    InMemoryTraceSink,
    JsonlTraceSink,
    SpanTraceAdapter,
    TraceEvent,
    TraceEventDraft,
    TraceEventStream,
)
from tests.agents.test_integrator import (  # noqa: F401  (fixtures reused)
    S01,
    cases,
    embeddings,
    index_root,
    integrator_for,
    ledger_db,
    s01_script,
    supporting_verifier,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "docs" / "v3" / "contracts" / "schemas" / "trace-event.schema.json"
FAKE_KEY = "sk-fakefake1234"


def _validator() -> Draft202012Validator:
    """The validator of the public schema, read from the versioned file in the repository."""
    return Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))


def _span(
    run_id: str = "s1",
    *,
    parent: str | None = None,
    name: str = "chain",
    status: str = "running",
    error: str | None = None,
) -> Span:
    """A minimal span, with the same shape as the current trace."""
    return Span(
        run_id=run_id,
        parent_run_id=parent,
        name=name,
        run_type="chain",
        start_time="2026-11-11T12:00:00.000+00:00",
        end_time=None if status == "running" else "2026-11-11T12:00:01.000+00:00",
        latency_ms=None if status == "running" else 1000,
        inputs={"question": "why was the refund lower"},
        outputs=None,
        error=error,
        metadata={},
        status=status,
    )


def test_the_event_follows_the_public_schema():
    """Every event the code produces satisfies the public schema, field by field."""
    validator = _validator()
    sink = InMemoryTraceSink()
    stream = TraceEventStream("run-1", sink, mode="deterministic_sandbox", snapshot_sha256="a" * 64)
    stream.on_span(_span("s1"))
    stream.on_span(_span("s1", status="ok"))
    stream.on_span(_span("s2", parent="s1", name="tool", status="error", error="boom"))
    stream.finish("completed", {"summary": "ok"})

    events = sink.read_from("run-1", after_seq=0, limit=100)
    assert len(events) == 4
    for event in events:
        errors = sorted(validator.iter_errors(event.to_dict()), key=lambda error: error.path)
        assert not errors, f"{event.event_type} outside the schema: {[error.message for error in errors]}"
        # The schema declares the shape of `at`, but the datetime validator does not come with jsonschema: the check
        # happens here, so the timestamp does not pass as a datetime only because nobody looked.
        assert datetime.fromisoformat(event.at).tzinfo is not None


def test_a_mode_outside_the_contract_is_refused():
    """A mode that is not in the schema never reaches the sink, because the schema does not allow it."""
    with pytest.raises(ValueError):
        TraceEvent(
            run_id="run-1",
            seq=1,
            at="2026-11-11T12:00:00.000+00:00",
            event_type="span.started",
            mode="banana",  # type: ignore[arg-type]
        )


def test_an_event_constructed_without_a_mode_is_a_deterministic_execution():
    """An event with no declared mode is the deterministic execution: the safe label, never a claim of live."""
    event = TraceEvent(
        run_id="run-1",
        seq=1,
        at="2026-11-11T12:00:00.000+00:00",
        event_type="span.started",
    )
    assert event.mode == "deterministic_sandbox"


def test_an_event_read_back_without_a_mode_is_a_recorded_replay():
    """A dict without the mode key is a recording read back, so it comes out a replay and never a live run.

    The deserialization default is deliberately not the construction default: an event assembled in code is a
    deterministic sandbox, a dict read back from a file is a replay, and neither is labelled live by accident.
    """
    data = {
        "schema_version": "1",
        "run_id": "run-1",
        "seq": 2,
        "at": "2026-11-11T12:00:00.000+00:00",
        "event_type": "span.ended",
        "payload": {},
        "span_id": None,
        "parent_span_id": None,
    }
    assert "mode" not in data
    assert TraceEvent.from_dict(data).mode == "recorded_replay"


def test_an_event_type_outside_the_schema_is_refused():
    """An event type the schema does not list never reaches the sink: it is refused at the construction."""
    with pytest.raises(ValueError):
        TraceEvent(
            run_id="run-1",
            seq=1,
            at="2026-11-11T12:00:00.000+00:00",
            event_type="banana",  # type: ignore[arg-type]
        )


def test_an_empty_run_id_is_refused():
    """The schema demands a non empty run id: an event without one never reaches the sink."""
    with pytest.raises(ValueError):
        TraceEvent(
            run_id="",
            seq=1,
            at="2026-11-11T12:00:00.000+00:00",
            event_type="span.started",
        )


def test_a_running_span_becomes_span_started_and_a_finished_one_becomes_span_ended():
    """The adapter turns the span of the current trace into the public event, without inventing an event."""
    adapter = SpanTraceAdapter()

    started = adapter.normalize(_span("s1"))
    assert [draft.event_type for draft in started] == ["span.started"]
    assert started[0].payload["name"] == "chain"

    ended = adapter.normalize(_span("s1", status="ok"))
    assert [draft.event_type for draft in ended] == ["span.ended"]
    assert ended[0].payload["status"] == "ok"

    failed = adapter.normalize(_span("s1", status="error", error="boom"))
    assert failed[0].event_type == "span.ended"
    assert failed[0].payload["error"] == "boom"


def test_the_sequence_number_strictly_increases_with_spans_from_different_threads():
    """Who numbers and delivers is the coordinator, under a lock: the order in the sink and the order of the numbers
    come out equal."""
    sink = InMemoryTraceSink()
    stream = TraceEventStream("run-1", sink)

    def emit(index: int) -> None:
        stream.on_span(_span(f"s{index}"))

    threads = [threading.Thread(target=emit, args=(index,)) for index in range(12)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    events = sink.read_from("run-1", after_seq=0, limit=100)
    assert [event.seq for event in events] == list(range(1, len(events) + 1))


def test_the_order_in_the_sink_holds_under_forced_preemption():
    """With the system switching threads all the time, the sink still receives the events in order.

    The delivery happens inside the lock of the coordinator. Outside it, the sink received the events out of order, and
    a client that reconnects by number lost events without seeing the gap.
    """
    previous = sys.getswitchinterval()
    sys.setswitchinterval(1e-9)
    try:
        for attempt in range(5):
            sink = InMemoryTraceSink()
            stream = TraceEventStream("run-1", sink)

            def emit(index: int, target=stream, round_id=attempt) -> None:
                target.on_span(_span(f"s{round_id}-{index}"))

            threads = [threading.Thread(target=emit, args=(index,)) for index in range(10)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            events = sink.read_from("run-1", after_seq=0, limit=100)
            assert [event.seq for event in events] == list(range(1, len(events) + 1))
    finally:
        sys.setswitchinterval(previous)


def test_the_parent_relationship_is_preserved():
    """The parent of the span travels in the event, so the hierarchy survives the format change."""
    sink = InMemoryTraceSink()
    stream = TraceEventStream("run-1", sink)
    stream.on_span(_span("root"))
    stream.on_span(_span("child", parent="root", name="tool"))

    events = sink.read_from("run-1", after_seq=0, limit=100)
    assert events[0].parent_span_id is None
    assert events[0].span_id == "root"
    assert events[1].parent_span_id == "root"
    assert events[1].span_id == "child"


def test_a_repeated_callback_produces_one_event():
    """The same span does not produce two events, even when the callback repeats."""
    sink = InMemoryTraceSink()
    stream = TraceEventStream("run-1", sink)
    stream.on_span(_span("s1"))
    stream.on_span(_span("s1"))
    stream.on_span(_span("s1", status="ok"))
    stream.on_span(_span("s1", status="ok"))

    events = sink.read_from("run-1", after_seq=0, limit=100)
    assert [event.event_type for event in events] == ["span.started", "span.ended"]


def test_a_fake_key_marker_never_reaches_the_event_or_the_file(tmp_path: Path):
    """The second defence happens at the boundary: the key enters neither the event nor the file."""
    sink = JsonlTraceSink(tmp_path / "trace.jsonl")
    stream = TraceEventStream("run-1", sink)
    stream.on_span(_span("s1", status="error", error=f"401 unauthorized: {FAKE_KEY}"))

    event = sink.read_from("run-1", after_seq=0, limit=10)[0]
    assert FAKE_KEY not in event.to_json()
    assert FAKE_KEY not in (tmp_path / "trace.jsonl").read_text(encoding="utf-8")


def test_a_forbidden_key_is_dropped_from_the_payload():
    """An authentication key in the payload does not leave, even when it comes from outside."""
    sink = InMemoryTraceSink()
    stream = TraceEventStream("run-1", sink)
    stream.emit(TraceEventDraft("plan.created", {"api_key": FAKE_KEY, "question": "hello"}))

    payload = sink.read_from("run-1", after_seq=0, limit=10)[0].payload
    assert "api_key" not in payload
    assert payload["question"] == "hello"


def test_every_forbidden_key_is_dropped_from_the_payload():
    """None of the authentication keys leaves in the payload, and none of them becomes a field name of the event."""
    sink = InMemoryTraceSink()
    stream = TraceEventStream("run-1", sink)
    stream.emit(
        TraceEventDraft(
            "plan.created",
            {
                "api_key": FAKE_KEY,
                "authorization": f"Bearer {FAKE_KEY}",
                "cookie": "session=abc",
                "set-cookie": "session=abc",
                "x-api-key": FAKE_KEY,
                "apikey": FAKE_KEY,
                "headers": {"authorization": f"Bearer {FAKE_KEY}", "x-keep": "ok"},
            },
        )
    )

    payload = sink.read_from("run-1", after_seq=0, limit=10)[0].payload
    assert set(payload) == {"headers"}
    assert payload["headers"] == {"x-keep": "ok"}


def test_a_fake_key_in_a_name_position_is_redacted():
    """A key that shows up as a field name is redacted too, at any depth: the defence does not look only at values."""
    sink = InMemoryTraceSink()
    stream = TraceEventStream("run-1", sink)
    stream.emit(TraceEventDraft("plan.created", {FAKE_KEY: "value", "nested": {f"Bearer {FAKE_KEY}": "v"}}))

    event = sink.read_from("run-1", after_seq=0, limit=10)[0]
    assert FAKE_KEY not in event.to_json()
    assert event.payload["[REDACTED]"] == "value"
    assert event.payload["nested"] == {"[REDACTED]": "v"}


def test_a_secret_written_straight_to_the_sink_is_still_redacted(tmp_path: Path):
    """The second defence is at the boundary: whoever writes to the sink without going through the coordinator does
    not leak the key."""
    sink = JsonlTraceSink(tmp_path / "trace.jsonl")
    event = TraceEvent(
        run_id="run-1",
        seq=1,
        at="2026-11-11T12:00:00.000+00:00",
        event_type="span.ended",
        payload={"api_key": FAKE_KEY, "error": f"401 {FAKE_KEY}"},
    )
    sink.append(event)

    text = (tmp_path / "trace.jsonl").read_text(encoding="utf-8")
    assert FAKE_KEY not in text
    assert "api_key" not in text


def test_the_file_sink_returns_only_the_events_after_the_given_sequence(tmp_path: Path):
    """In the file, the reconnection by number also returns only what is after."""
    sink = JsonlTraceSink(tmp_path / "trace.jsonl")
    stream = TraceEventStream("run-1", sink)
    for index in range(5):
        stream.on_span(_span(f"s{index}"))

    later = sink.read_from("run-1", after_seq=3, limit=100)
    assert [event.seq for event in later] == [4, 5]


def test_the_memory_sink_says_what_it_no_longer_has():
    """The memory ceiling tells the oldest number that is left, so whoever reconnects knows there was a discard."""
    sink = InMemoryTraceSink(max_events=10)
    stream = TraceEventStream("run-1", sink)
    for index in range(30):
        stream.on_span(_span(f"s{index}"))

    assert sink.oldest_seq("run-1") == 21
    assert sink.read_from("run-1", after_seq=0, limit=100)[0].seq == 21


def test_read_from_returns_only_the_events_after_the_given_sequence():
    """Whoever reconnects receives only what comes after the number they asked for."""
    sink = InMemoryTraceSink()
    stream = TraceEventStream("run-1", sink)
    for index in range(5):
        stream.on_span(_span(f"s{index}"))

    later = sink.read_from("run-1", after_seq=3, limit=100)
    assert [event.seq for event in later] == [4, 5]


def test_the_memory_sink_keeps_a_ceiling_per_execution():
    """Memory has a ceiling per execution, so a long execution does not bring the process down."""
    sink = InMemoryTraceSink(max_events=10)
    stream = TraceEventStream("run-1", sink)
    for index in range(30):
        stream.on_span(_span(f"s{index}"))

    events = sink.read_from("run-1", after_seq=0, limit=100)
    assert len(events) == 10
    assert events[-1].seq == 30


def test_the_file_sink_gives_back_exactly_what_was_written(tmp_path: Path):
    """The file is the replay bundle: what was written comes back equal."""
    path = tmp_path / "trace.jsonl"
    sink = JsonlTraceSink(path)
    stream = TraceEventStream("run-1", sink, mode="deterministic_sandbox", snapshot_sha256="b" * 64)
    stream.on_span(_span("s1"))
    stream.on_span(_span("s1", status="ok"))
    stream.finish("completed")

    events = sink.read_from("run-1", after_seq=0, limit=100)
    assert [event.event_type for event in events] == ["span.started", "span.ended", "run.completed"]
    assert events[0].mode == "deterministic_sandbox"
    assert events[0].snapshot_sha256 == "b" * 64

    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3
    assert all(json.loads(line)["schema_version"] == "1" for line in lines)


def test_the_terminal_event_is_the_last_one():
    """The terminal event comes after everything, and an execution has only one."""
    sink = InMemoryTraceSink()
    stream = TraceEventStream("run-1", sink)
    stream.on_span(_span("s1"))
    stream.finish("completed")
    stream.finish("completed")

    events = sink.read_from("run-1", after_seq=0, limit=100)
    assert [event.event_type for event in events] == ["span.started", "run.completed"]


def test_a_real_investigation_becomes_events_with_hierarchy(ledger_db, index_root, cases):  # noqa: F811
    """A real investigation becomes a public event: growing sequence and preserved hierarchy."""
    agent = integrator_for(ledger_db, index_root, cases, s01_script(), verifier=supporting_verifier([]))
    sink = InMemoryTraceSink()
    stream = TraceEventStream("run-s01", sink, mode="deterministic_sandbox")

    investigate(agent, S01["questions"][0], thread_id="t-v1", on_event=stream.on_span)

    events = sink.read_from("run-s01", after_seq=0, limit=1000)
    assert events, "the investigation produced no event at all"
    assert [event.seq for event in events] == list(range(1, len(events) + 1))
    assert {event.event_type for event in events} == {"span.started", "span.ended"}

    started = {event.span_id for event in events if event.event_type == "span.started"}
    ended = {event.span_id for event in events if event.event_type == "span.ended"}
    assert started <= ended, "a span that started cannot stay without an end"

    span_ids = {event.span_id for event in events}
    assert any(event.parent_span_id in span_ids for event in events), "the hierarchy did not survive"


def test_a_real_investigation_writes_a_file_without_key_material(ledger_db, index_root, cases, tmp_path: Path):  # noqa: F811
    """In a real execution the file comes out with events and without key material.

    This is a smoke test of the full path: the S01 scenario has no secret at all, so what proves the redaction is the
    fake key test, not this one.
    """
    agent = integrator_for(ledger_db, index_root, cases, s01_script(), verifier=supporting_verifier([]))
    sink = JsonlTraceSink(tmp_path / "trace.jsonl")
    stream = TraceEventStream("run-s01", sink, mode="deterministic_sandbox")

    investigate(agent, S01["questions"][0], thread_id="t-v2", on_event=stream.on_span)

    text = (tmp_path / "trace.jsonl").read_text(encoding="utf-8")
    assert "sk-" not in text
    assert "Bearer " not in text
    assert len(text.strip().splitlines()) > 10


def test_the_event_survives_a_round_trip_through_the_dictionary():
    """The dictionary of the event gives the same event back: it is what the replay bundle uses."""
    event = TraceEvent(
        run_id="run-1",
        seq=3,
        at="2026-11-11T12:00:00.000+00:00",
        event_type="claim.verdict",
        payload={"label": "supported"},
        span_id="s1",
        parent_span_id="s0",
        snapshot_sha256="c" * 64,
        mode="recorded_replay",
    )

    again = TraceEvent.from_dict(event.to_dict())
    assert again == event
    assert again.mode == "recorded_replay"
