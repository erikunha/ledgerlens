---
type: adr
status: accepted
date: 2026-11-11
---

# ADR-013: The public trace is a versioned contract

Status: accepted. Date: 2026-11-11.

## Context

The trace of an investigation today is a tree of `Span` that Streamlit draws while the investigation happens. It is
internal: it changes with LangChain, and it does not serve a client that needs to read the trace afterwards, from the
outside, or to repeat the same execution.

The design package defines a public shape for it, in `contracts/schemas/trace-event.schema.json`: `schema_version`,
`run_id`, `seq`, `at`, `event_type`, `span_id`, `parent_span_id`, `payload`, `snapshot_sha256` and `mode`. The public
replay of the R1 release has to consume that shape, and it has to do so without the internal format leaking into the
interface.

## Decision

The public trace lives in `ledgerlens/observability/trace_event.py`, and it is the `TraceEvent` of the schema, field by
field.

The piece that bridges the two is the adapter: the `Span` that already exists becomes a public event without
duplicating a single listener and without touching what the product does. A running `Span` becomes `span.started`; a
finished one becomes `span.ended`, carrying the error when there was one.

Who numbers is the coordinator, `TraceEventStream`, and not the caller. The sequence number comes out of a lock, so
`seq` always grows, even when the agent tools run on different threads. The delivery to the sink happens inside that
same lock, so the order of the numbers and the order of arrival are the same order. Delivering outside the lock would
let the sink receive the events out of order, and a client that reconnects by number would lose an event without ever
seeing the gap. When the sink fails, the number goes back, because no event was delivered.

The same pair of event and span does not produce two events, which protects the interface from a repeated callback. The
dedupe key carries the span stamp and not only the identifier: a span that restarts with the same id is a new attempt,
not a repeated callback.

The mode is part of the contract, so an unknown one is refused when the event is built, not when a client reads it. The
three modes say where the event came from: `live_agent` is a real execution, `deterministic_sandbox` is the
deterministic one with the scripted model and the recorded rate, and `recorded_replay` is a trace that was recorded and
is repeated. A replay that says it is live is the worst failure this repository can have, so the label travels with the
event and cannot be set by accident.

The sinks, `TraceSink`, are the exchange boundary. Today there are the memory and the JSON lines file, which is the same
format the replay bundle uses. Tomorrow there can be an HTTP sink without the event producer changing: the producer only
knows that `append` exists.

The second defence against secrets happens at the boundary, in `to_dict`. Even with the `Span` already sanitized and
even if the event was assembled outside the coordinator, the payload goes through `redact` and loses keys like
`api_key`, `authorization` and `cookie`. Whoever writes the file never sees the key.

The schema version is checked when the event is read back: a file of a different version is not read as if it were this
one.

## Alternatives considered

- **Expose the `Span` tree as it is.** The shape changes with LangChain, and the interface would have to follow. The
  public interface cannot be allowed to change every time a dependency changes.
- **Let the caller number the events.** Two callers that both start at one would produce two events with the same
  number, and a client that reconnects by number would not know which it got.
- **Deliver to the sink outside the lock.** It is faster. It is also the bug that loses an event without a hole in the
  sequence, which is the failure a client cannot detect.
- **Validate the mode only on the client.** The contract would be checked by whoever reads it, and the first reader
  might not be the one that checks.

## Consequences

- The public interface consumes a stable contract and never sees the internal format.
- The internal trace can change shape without breaking anything that reads the public one.
- A mode outside the contract cannot leave the process.
- The redaction happens twice: once in the span and once at the boundary, and the boundary is the one that holds.
- The event carries the snapshot hash and the mode, so a client can tell a fresh run from a stale one.
- The number of events per execution is bounded in memory, and the sink says what it no longer has, so a client that
  reconnects can tell that there was a discard instead of following on with a silent hole.
