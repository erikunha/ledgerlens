# SPEC LL-R2-02 - Isolated event-sourced sandbox branches

**Status:** implementation planning, P0 for editable mode. **Primary safety invariant:** no visitor can change the committed ledger, other visitor's branch or real payment state.

## Data model and storage

```text
SandboxBranch(id, owner_session_id, base_snapshot_id, revision,
              projection_sha256, created_at, expires_at, state)
SandboxCommand(id, branch_id, idempotency_key, expected_revision,
               kind, normalized_payload_json, created_at)
SandboxEvent(event_uid, branch_id, event_type, occurred_at,
             payload_json, origin='sandbox', command_id)
```

Use per-session sandbox SQLite file or SQLite attached to scoped private temp dir (not global cache). The baseline is immutable. New events must satisfy current event whitelist or an explicit versioned sandbox domain interpreter. `projector.rebuild_database` operates under bounded transaction/lock with deterministic canonical hash. Clean up expired resources.

## Concurrency and transaction algorithm

```python
def apply_mutation(branch_id, cmd, if_match, idem_key, session):
    branch = authorize_owner(branch_id, session)
    with exclusive_branch_transaction(branch):
        if previous := idempotency_lookup(branch, idem_key):
            return previous if previous.payload_hash == hash(cmd) else Conflict()
        assert branch.revision == if_match, Conflict()
        normalized = validate_domain_command(branch, cmd)
        preview = calculate_impact_without_write(branch, normalized)
        events = synthesize_valid_events(branch, normalized)
        append_events(events)              # branch only, atomically
        project_and_verify_invariants()
        branch.revision += 1
        branch.projection_sha256 = canonical_hash()
        commit()
    invalidate_branch_scoped_cache(branch_id)
    return new_revision_and_diff
```

The sketch omits persistence details and exception handling. Actual implementation must guarantee atomic rollback, handle restart/duplicate requests, avoid filesystem path injection and provide bounded allocation.

## Permitted edits

Start with `tool.fx_outage` and `record.inject_untrusted_note` (fault overlays that do not mutate financial projections). Then add event-consistent payment duplicate and refund FX adjustment; deadline change requires projector-supported event semantics and business date validation. Do not promise all controls until each has round-trip tests.

## Validation matrix

- All amounts use integer minor/Decimal strings; invalid currency, negative amount, over-refund or impossible deadline gets 422 with explanatory code.
- Every `SandboxBranch` has owner session, TTL, immutable source hash and monotonic revision.
- On 409 revision conflict, no event applied, no revision bump, canonical hash stable.
- On same idempotency key and identical command, repeated submit returns identical response; different command conflicts.
- After commit, account-specific copy regenerated from branch revision; all cache and memory that referred to old revision invalidated.
- Sandbox `source/origin` visible in UI so visitor knows what is altered.
- Reset returns original base hash and makes old branch run comparisons visibly stale.
- No arbitrary SQL/SQL UPDATE/PRAGMA reachable by exposed editor.

## Tests

Run original event projector invariants; property-based generation of valid/invalid event sequences; two-session cross access, concurrent mutation, branch expiry, crash between append and projection, replay stale mismatch, S01 numeric before/after diff. Nonzero cross-visitor access in test is a release blocker.

## Rollback

Turn off mutation POSTs and set UI read-only; leave published replay operational. Never perform destructive base migration simply to recover branch availability.
