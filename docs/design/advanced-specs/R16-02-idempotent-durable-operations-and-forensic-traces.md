# LL-V3-R16-02 - Idempotent durable operations and forensic traces

**Status:** design proposed; not yet implemented. **Strategic lens:** Theory of Constraints and Compounding. **Audience:** SRE and platform engineer. **Dependencies:** R11 checkpoints, R15 gateway.

## User outcome

Restart agent processes without losing evidence or executing duplicate work in a visitor branch.

## Ownership and compatibility

Use Python checkpointer, run journal and typed events; instrument trace spans to align with OpenTelemetry semantic conventions where applicable, redacted on export.

## Typed interfaces and persisted state

Each worker step carries `{run_id,step_id,attempt,idempotency_key,snapshot_hash,state_version,output_ref,token_cost_provenance}`; event offsets monotonic.

## Algorithm and execution contract

Write intent→execute bounded tool→record result→commit completion; on restart inspect journal, reuse complete outputs, retry only safe read operations, mark unknown status for provider requests where cost confirmation unavailable; preserve partial spans.

## Security, invalid states and recovery

Do not rehydrate expired BYOK; never log raw prompt content by default; no cross-session cache. Replaying an event is not permission to mutate original ledger.

## Acceptance scenarios (Given / When / Then)

- Worker killed mid-run: restart does not duplicate projector updates.
- Provider 429: retry policy respects deadline.
- Trace exporter fails: agent still finishes and error recorded locally.
- Cancellation: no more tool start events after barrier.

## Metrics, evidence and regression gates

Lost-event count, duplicate effects, restart recovery p95, error taxonomy, trace gap ratio, spend uncertainty.

## Definition of done and rollback

Chaos test fixture with repeated terminations; OTEL redaction verification and rollback runbook.

No claim of implementation is made by this spec. Shipped status requires passing exact executable tests, a source revision, a sanitized replay/trace, and known limitations in release notes.
