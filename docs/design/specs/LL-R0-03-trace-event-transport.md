# SPEC LL-R0-03 - Stable trace event protocol and adapter

**Status:** ready for implementation planning; **priority P0**. Owner boundary: `ledgerlens/observability` → `ledgerlens/demo_api` and `apps/web/features/agent-trace`. No change to observed business actions.

## Intent

Make a `TraceEvent` stable across LangChain upgrades and streamable to a React UI while preserving source identifiers, run hierarchy, timing, verifier decisions, sanitizer and schema evolution.

## Preconditions and files

Read `ledgerlens/observability/trace.py`, `ledgerlens/agents/integrator.py`, `ledgerlens/schemas.py`, `tests/agents/test_trace.py`, `docs/architecture.md`. Existing Span events use IDs and parent relationships, callback handlers, compacting and token extraction; do not duplicate listeners or leak hidden trace nodes. Proposed public JSON schema: `contracts/schemas/trace-event.schema.json`.

## Proposed interface

```python
class TraceEventAdapter(Protocol):
    def normalize(self, span: Span, context: RunContext) -> list[TraceEvent]: ...

class TraceSink(Protocol):
    def append(self, event: TraceEvent) -> None: ...
    def read_from(self, run_id: str, after_seq: int, limit: int) -> list[TraceEvent]: ...
```

Normalize `Span.running` to `span.started`, `Span.ok/error` to `span.ended`, plus separate `evidence.added`, `claim.verdict`, terminal `run.completed`/`run.failed`. Do not infer a new event if there is no observed event; promote application events explicitly. Each `TraceEvent` has `(run_id, seq, at, event_type, span_id, parent_span_id, payload, snapshot_sha256, mode)`.

## Ordering, idempotency and retention

A single run coordinator assigns sequence numbers after acquiring an event-stream lock or atomic counter, not the caller thread. In concurrent callbacks, nesting is by `span_id` rather than event delivery order. `run.completed` is emitted only after verification finalizes; a downstream error produces `run.failed`. Bounded ring buffer retains at most N events/bytes per run (N configured; start at 2,000 events), with oldest offset advertised. Reconnect uses `Last-Event-ID`, returns catch-up if available or explicit resync-required status if evicted. Stream end closes after terminal event and flush.

## Transport

FastAPI `GET /v1/runs/{run_id}/events` returns `text/event-stream`, ownership checked before subscription. Each SSE event carries `id=<seq>`, `event=<event_type>`, `data=<JSON>`. Idle heartbeat every configurable interval (e.g., 15s). Cancellation/stall handled server-side; not reliant on browser connection. Backpressure: bounded queue; if over limit, terminal error or summary + resync indicator, never OOM.

## Redaction

Normalize from already sanitized fields but enforce a second defense at transport boundary. Reject token-like strings in names/headers/`api_key`, `authorization`, `cookie`. Tool output may include benign simulated IDs, but no raw session/auth. For model call content, default to truncation or omission; show metadata and sanitized excerpts. Never render provider SDK exception bodies raw.

## Tests (Given/When/Then)

- Given nested triage/model/tool spans on separate threads, when normalized, then seq strictly increases and hierarchy preserves parent relationships.
- Given callback duplicate, when appended with same event dedupe key, then viewer displays one event.
- Given fake key marker in tool exception, then serialized SSE and stored replay contain no marker.
- Given provider timeout before verifier, then `run.failed` appears and no `run.completed` or supported result is fabricated.
- Given SSE reconnect after five events, when `Last-Event-ID: 5`, then receive only later events.
- Given another visitor's run ID, then SSE must not reveal event count, tool names or data.
- Given `verification_status=unavailable`, no claim is displayed as newly verified.

## Quality and rollback

No architecture metrics regression; existing Python trace unit tests pass. Benchmarks must compare callback overhead before/after on 30 cases, with p95 measured not guessed. Feature flag `TRACE_V1`; Streamlit continues using old Span directly until Next UI shipping. Rollback disables v1 transport but keeps original trace.
