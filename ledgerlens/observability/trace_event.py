"""The public trace contract: the `TraceEvent`, the adapter for the current `Span` and the sinks that receive events.

Why it exists: today's trace is a tree of `Span` that Streamlit draws while the investigation happens. That format is
internal: it changes with LangChain and it does not serve a client that needs to read the trace afterwards, from the
outside, or to repeat the same execution. The `TraceEvent` is the public, stable shape that the design contract
`trace-event.schema.json` defines: `schema_version`, `run_id`, `seq`, `at`, `event_type`, `span_id`, `parent_span_id`,
`payload`, `snapshot_sha256` and `mode`.

The piece that bridges the two is the adapter: the `Span` that already exists becomes a public event without duplicating
a single listener and without touching what the product does. A running `Span` becomes `span.started`; a finished `Span`
becomes `span.ended`, carrying the error when there was one.

Who numbers is the coordinator, `TraceEventStream`, and not the caller: the sequence number comes out of a lock, so
`seq` always grows, even when the agent tools run on different threads. The delivery to the sink happens inside that
same lock, so the order of the numbers and the order of arrival are the same order. Delivering outside the lock would
let the sink receive events out of order, and a client that reconnects by number would lose an event without ever
seeing the gap.

The same pair (event, span) does not produce two events, which protects the interface from a repeated callback. The key
carries the span stamp and not only the identifier: a span that restarts with the same id is a new attempt, not a
repeated callback.

The sinks, `TraceSink`, are the exchange boundary. Today there are memory and the JSON lines file, which is the same
format the replay bundle uses. Tomorrow there can be an HTTP sink without the event producer changing: the producer only
knows that `append` exists.

The three contract modes say where the event came from: `live_agent` is a real execution, with a real model and real
exchange rates; `deterministic_sandbox` is the deterministic execution, with the scripted model and the recorded rate;
and `recorded_replay` is a recorded trace, which is repeated and must never be called a live execution. The mode
travels with the event so that nobody has to guess later, and no event is labelled live by accident: an event
constructed without a mode is a deterministic execution (`deterministic_sandbox`), and an event read back from a dict
without a mode is a recording (`recorded_replay`). A live execution has to declare itself.

The second defence against secrets happens at the boundary, in `to_dict`: even with the `Span` already sanitized and
even if the event was assembled outside the coordinator, the payload goes through `redact` and loses keys like
`api_key`, `authorization` and `cookie`, and a key that shows up as a field name is redacted in place. Whoever writes
the file never sees the key.
"""

from __future__ import annotations

import json
import re
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol

from ledgerlens.config import offline
from ledgerlens.observability.callbacks import redact
from ledgerlens.observability.trace import Span

SCHEMA_VERSION = "1"
MAX_EVENTS_PER_RUN = 2000

EventType = Literal[
    "run.started",
    "plan.created",
    "span.started",
    "span.ended",
    "evidence.added",
    "claim.verdict",
    "run.status",
    "run.completed",
    "run.failed",
    "run.cancelled",
    "heartbeat",
]
TraceMode = Literal["recorded_replay", "deterministic_sandbox", "live_agent"]
RunStatus = Literal["completed", "failed", "cancelled"]

# The keys that never leave an event, no matter where they came from.
FORBIDDEN_KEYS = frozenset({"api_key", "apikey", "authorization", "cookie", "set-cookie", "x-api-key"})

# The schema demands a sha256 in lowercase hex, and this module does not deliver anything else.
SNAPSHOT_PATTERN = re.compile(r"^[a-f0-9]{64}$")

# The mode is part of the contract, so an unknown one is refused here instead of travelling to the sink and breaking
# the schema validation on the other side.
TRACE_MODES = frozenset({"recorded_replay", "deterministic_sandbox", "live_agent"})

# The same refusal for the event type: the schema lists exactly these eleven values, and an event outside the list is
# not a trace event of this contract.
EVENT_TYPES = frozenset(
    {
        "run.started",
        "plan.created",
        "span.started",
        "span.ended",
        "evidence.added",
        "claim.verdict",
        "run.status",
        "run.completed",
        "run.failed",
        "run.cancelled",
        "heartbeat",
    }
)


def default_mode() -> TraceMode:
    """The mode the execution actually is: deterministic when the product is offline, live when it is not.

    The label does not come from the caller, it comes from the process configuration. The caller may declare a mode, but
    the default value is what the machine is doing.
    """
    return "deterministic_sandbox" if offline() else "live_agent"


def _sanitize(value: Any) -> Any:
    """The payload without keys and without text that looks like a key: the second defence, at the transport."""
    if isinstance(value, dict):
        # The name position goes through `redact` as well: a key materialized as a field name does not escape.
        return {
            redact(str(key)): _sanitize(item) for key, item in value.items() if str(key).lower() not in FORBIDDEN_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_sanitize(item) for item in value]
    if isinstance(value, str):
        return redact(value)
    return value


@dataclass(frozen=True)
class TraceEvent:
    """One trace event in the public format, exactly what the schema defines.

    The two defaults are deliberately different: an event constructed in code without a mode is a deterministic
    execution, so the field default is `deterministic_sandbox`; an event read back from a dict without a mode is a
    recording, so the `from_dict` default is `recorded_replay`. Neither default is ever `live_agent`, because a live
    execution is a claim that has to be made explicitly.
    """

    run_id: str
    seq: int
    at: str
    event_type: EventType
    payload: dict[str, Any] = field(default_factory=dict)
    span_id: str | None = None
    parent_span_id: str | None = None
    snapshot_sha256: str | None = None
    mode: TraceMode = "deterministic_sandbox"

    def __post_init__(self) -> None:
        """Checks what the schema demands, so an invalid event never reaches the sink."""
        if self.snapshot_sha256 is not None and not SNAPSHOT_PATTERN.match(self.snapshot_sha256):
            raise ValueError(f"invalid snapshot_sha256: {self.snapshot_sha256!r}")
        if self.seq < 1:
            raise ValueError(f"invalid seq: {self.seq}")
        if not self.run_id:
            raise ValueError("run_id must not be empty")
        if self.event_type not in EVENT_TYPES:
            raise ValueError(f"invalid event_type: {self.event_type!r}")
        if self.mode not in TRACE_MODES:
            raise ValueError(f"invalid mode: {self.mode!r}")

    def to_dict(self) -> dict[str, Any]:
        """The event as a dictionary, in the exact shape of the public schema.

        The redaction happens here, at the boundary: whoever writes the file never sees the key, even if the event was
        assembled outside the coordinator.
        """
        data: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "seq": self.seq,
            "at": self.at,
            "event_type": self.event_type,
            "payload": _sanitize(self.payload),
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "mode": self.mode,
        }
        if self.snapshot_sha256:
            data["snapshot_sha256"] = self.snapshot_sha256
        return data

    def to_json(self) -> str:
        """The event as one line of JSON, with no line break in the middle."""
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TraceEvent:
        """The event back, from the dictionary or from the line of the file.

        The schema version is checked: a file of a different version is not read as if it were this one. A dict
        without the mode key is a recording read back, so the mode comes out `recorded_replay` and never
        `live_agent`: this default is the deserialization one, deliberately different from the construction default.
        """
        version = str(data.get("schema_version", SCHEMA_VERSION))
        if version != SCHEMA_VERSION:
            raise ValueError(f"unknown schema version: {version}")
        return cls(
            run_id=str(data["run_id"]),
            seq=int(data["seq"]),
            at=str(data["at"]),
            event_type=data["event_type"],
            payload=dict(data.get("payload") or {}),
            span_id=data.get("span_id"),
            parent_span_id=data.get("parent_span_id"),
            snapshot_sha256=data.get("snapshot_sha256"),
            mode=data.get("mode", "recorded_replay"),
        )


@dataclass(frozen=True)
class TraceEventDraft:
    """An event without a sequence number yet: the coordinator is who numbers, and it numbers under a lock."""

    event_type: EventType
    payload: dict[str, Any] = field(default_factory=dict)
    span_id: str | None = None
    parent_span_id: str | None = None
    dedupe_key: str | None = None


class SpanTraceAdapter:
    """Turns the current trace `Span` into the public event it represents."""

    def normalize(self, span: Span) -> list[TraceEventDraft]:
        """The public event of a span: `span.started` while it runs, `span.ended` when it finishes."""
        if span.status == "running":
            payload = {"name": span.name, "run_type": span.run_type, "inputs": span.inputs}
            return [
                TraceEventDraft(
                    "span.started",
                    payload,
                    span.run_id,
                    span.parent_run_id,
                    f"span.started:{span.run_id}:{span.start_time}",
                )
            ]
        payload = {
            "name": span.name,
            "run_type": span.run_type,
            "outputs": span.outputs,
            "error": span.error,
            "latency_ms": span.latency_ms,
            "status": span.status,
            "metadata": span.metadata,
        }
        return [
            TraceEventDraft(
                "span.ended",
                payload,
                span.run_id,
                span.parent_run_id,
                f"span.ended:{span.run_id}:{span.end_time}",
            )
        ]


class TraceWriter(Protocol):
    """What the producer needs: a place to deliver the event. Nothing else."""

    def append(self, event: TraceEvent) -> None: ...


class TraceSink(Protocol):
    """Where the events arrive and where they are read from. Today it is memory and a file; tomorrow it can be HTTP."""

    def append(self, event: TraceEvent) -> None: ...

    def read_from(self, run_id: str, after_seq: int, limit: int) -> list[TraceEvent]: ...


class InMemoryTraceSink:
    """Keeps the events of each execution in memory, with a ceiling per execution."""

    def __init__(self, max_events: int = MAX_EVENTS_PER_RUN) -> None:
        self._lock = threading.Lock()
        self._events: dict[str, deque[TraceEvent]] = {}
        self._max_events = max_events

    def append(self, event: TraceEvent) -> None:
        with self._lock:
            bucket = self._events.setdefault(event.run_id, deque(maxlen=self._max_events))
            bucket.append(event)

    def read_from(self, run_id: str, after_seq: int = 0, limit: int = 100) -> list[TraceEvent]:
        """The events of the execution after `after_seq`, at most `limit`."""
        with self._lock:
            bucket = list(self._events.get(run_id, ()))
        return [event for event in bucket if event.seq > after_seq][:limit]

    def oldest_seq(self, run_id: str) -> int | None:
        """The number of the oldest event still in memory, or `None` when there is none.

        A client that reconnects compares its number with this one: if its own is older, the middle was dropped and the
        client has to resynchronise instead of following on with a silent hole.
        """
        with self._lock:
            bucket = self._events.get(run_id)
            if not bucket:
                return None
            return bucket[0].seq


class JsonlTraceSink:
    """Writes the events as JSON lines: one line per event, the same format the replay bundle uses."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        """Where the file lives."""
        return self._path

    def append(self, event: TraceEvent) -> None:
        line = event.to_json() + "\n"
        with self._lock:
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(line)

    def read_from(self, run_id: str, after_seq: int = 0, limit: int = 100) -> list[TraceEvent]:
        """The events of the execution after `after_seq`, read back from the file."""
        if not self._path.exists():
            return []
        events: list[TraceEvent] = []
        with self._path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                event = TraceEvent.from_dict(json.loads(line))
                if event.run_id == run_id and event.seq > after_seq:
                    events.append(event)
        return events[:limit]


class TraceEventStream:
    """The coordinator of an execution: it gives the sequence number, the timestamp and the delivery, under a lock."""

    def __init__(
        self,
        run_id: str,
        sink: TraceWriter,
        *,
        mode: TraceMode | None = None,
        snapshot_sha256: str | None = None,
        adapter: SpanTraceAdapter | None = None,
    ) -> None:
        self.run_id = run_id
        self.mode = mode or default_mode()
        self._sink = sink
        self._snapshot_sha256 = snapshot_sha256
        self._adapter = adapter or SpanTraceAdapter()
        self._lock = threading.Lock()
        self._seq = 0
        self._seen: set[str] = set()

    def emit(self, draft: TraceEventDraft) -> TraceEvent | None:
        """Publishes an event and returns it. `None` when the same event had already been published.

        Number, timestamp and delivery come out together, under the same lock. Delivering outside the lock would let the
        sink receive the events out of order, and a client that reconnects by number would lose an event without ever
        seeing the gap. If the sink fails, the number goes back, because no event was delivered.
        """
        with self._lock:
            if draft.dedupe_key is not None:
                if draft.dedupe_key in self._seen:
                    return None
                self._seen.add(draft.dedupe_key)
            self._seq += 1
            seq = self._seq
            event = TraceEvent(
                run_id=self.run_id,
                seq=seq,
                at=datetime.now(UTC).isoformat(timespec="milliseconds"),
                event_type=draft.event_type,
                payload=_sanitize(draft.payload),
                span_id=draft.span_id,
                parent_span_id=draft.parent_span_id,
                snapshot_sha256=self._snapshot_sha256,
                mode=self.mode,
            )
            try:
                self._sink.append(event)
            except Exception:
                self._seq -= 1
                if draft.dedupe_key is not None:
                    self._seen.discard(draft.dedupe_key)
                raise
            return event

    def on_span(self, span: Span) -> None:
        """Receives a span of the current trace and publishes the matching public events."""
        for draft in self._adapter.normalize(span):
            self.emit(draft)

    def finish(self, status: RunStatus, payload: dict[str, Any] | None = None) -> TraceEvent | None:
        """The terminal event of the execution. It comes after the verification, never before.

        An execution has a single terminal event. Calling again does not publish another one.
        """
        return self.emit(TraceEventDraft(f"run.{status}", payload or {}, dedupe_key="run:terminal"))
