# LL-V3-R2-03 - Isolated sandbox mutations

**Status:** design proposed; not yet implemented. **Strategic lens:** Reversibility and Systems Thinking. **Audience:** Engineer and researcher. **Dependencies:** R0 data baseline, original LL-R2-02.

## User outcome

Visitors can edit simulated FX/refunds/policy values and see exact causal input diff without corrupting other sessions.

## Ownership and compatibility

Python `ledgerlens/sim/` owns events/projector; FastAPI wraps branch service. Next.js only submits typed commands. Never change `data/scenarios.json` or canonical sample in place.

## Typed interfaces and persisted state

`POST /sandboxes` allocates `branch_id,revision,base_hash`. `POST /sandboxes/{id}/mutations` with `if_match_revision,command_type,payload,idempotency_key`. `GET /sandboxes/{id}/diff`, `POST /reset`.

## Algorithm and execution contract

Validate command and account scope, calculate projected event delta without commit, return preview; on accept append to private branch with unique idempotency key, project derived tables, compute new canonical hash and invalidate stale replay. Event order deterministic; exact Decimal rules.

## Security, invalid states and recovery

Per-session namespace, TTL, quota, no arbitrary SQL or file paths; double submit returns same revision or 409 conflict, never silent overwrite. Public visitor may only edit synthetic branches.

## Acceptance scenarios (Given / When / Then)

- Two sessions edit same transaction: isolation preserved.
- Same mutation retried: at most one event committed.
- Wrong precision: 422 with unchanged hash.
- Reset branch: hash equals base.
- Request to modify source events: denied.
- Mutated FX invalidates old answer, not re-labeled live.

## Metrics, evidence and regression gates

Event projection hash, branch isolation failures zero, status of old replay (stale/valid), mutation latency and validations.

## Definition of done and rollback

Tests on seeded S01/S02/S03 plus property tests. Provide precise diff screenshot, source paths, rollback by expiring branches and keeping original core unchanged.

No claim of implementation is made by this spec. Shipped status requires passing exact executable tests, a source revision, a sanitized replay/trace, and known limitations in release notes.
