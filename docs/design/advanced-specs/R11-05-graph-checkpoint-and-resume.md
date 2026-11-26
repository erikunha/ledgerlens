# LL-V3-R11-05 - Graph checkpoint and resume

**Status:** design proposed; not yet implemented. **Strategic lens:** Compounding and Reliability. **Audience:** Platform engineer. **Dependencies:** R11 dispatcher, R16 durability.

## User outcome

A suspended case resumes from durable state without replaying unsafe effects or losing provenance.

## Ownership and compatibility

Persist run journal `{run_id,step_id,attempt,inputs_hash,result_ref,status}`; graph backend can remain LangGraph checkpointer initially, evaluate Temporal later only with evidence.

## Typed interfaces and persisted state

`POST /runs/{id}/resume` checks authorization, resume token, snapshot hash, TTL. Replay uses already persisted completed step outputs; new operations get idempotency key and span parent linking.

## Algorithm and execution contract

On restart load terminal/completed steps, validate snapshot and agent config versions, only re-run unfinished idempotent tools; invalidated steps require new run. No hidden paid model retry if budget already spent.

## Security, invalid states and recovery

Do not store BYOK across restart: request re-authorization or stop; never automatically rehydrate expired secret.

## Acceptance scenarios (Given / When / Then)

- Kill between FX result and verifier; FX result reused if valid.
- Kill during provider call; uncertain charge status reported and not charged twice by us silently.
- Modified sandbox branch invalidates resume.
- Key expired -> no model call.

## Metrics, evidence and regression gates

Duplicate effects 0, replay consistency, resume p95 and lost-event rate.

## Definition of done and rollback

Fault injection in CI, restart replay manifest, documented state migration and rollback.

No claim of implementation is made by this spec. Shipped status requires passing exact executable tests, a source revision, a sanitized replay/trace, and known limitations in release notes.
