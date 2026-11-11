# Scenario sandbox: safely edit financial facts

## Goal and constraints

Allow anonymous visitors to experiment with a financial-world simulation and observe causal, reproducible effects, without creating a real-money system or undermining the repo's append-only/event-sourced guarantees. **The visitor edits domain events and tool faults, not the original tables or deployed fixtures.**

## Existing foundation

`ledgerlens/sim/events.py` implements append-only event storage with unique IDs; `sim/projector.py` applies events and can reconstruct a canonical hash; `sim/scenarios.py` plants 12 named anomalies; `data/scenarios.json` carries seed 42 and ground truth. `docs/contracts/ledger_schema.sql` defines event types and guarded projection tables.

This is the substrate, not something to rewrite as client-side JavaScript objects.

## Core concepts

- `BaseSnapshot`: immutable published version of ledger + simulator manifest, with content SHA256, seed, source mix, simulator version, canonical DB hash and licenses.
- `SandboxBranch`: random opaque visitor-owned ID, `base_snapshot_id`, `owner_session_id`, creation/expiry times, `branch_revision`, mutation limit, state. **No user-origin filesystem path.**
- `ScenarioMutation`: typed command describing a permitted event or injection in the visitor's branch. Also carries reason, invariant policy and idempotency key.
- `ProjectedLedger`: isolated SQLite database rebuilt from base snapshot plus branch's appended events; never a mutable global cached database.
- `RunContext`: binds `branch_id`, `branch_revision`, `snapshot_hash`, account ID, policy version, model profile and fixture version. Every trace/result contains this context.

## Deterministic lifecycle

```text
Published immutable base snapshot
    └─ POST /v1/sandboxes                  create branch
        └─ copy to owned bounded temp dir, or COW SQLite in one backend process
            └─ POST /v1/sandboxes/:id/mutations/preview (no writes)
                └─ validate typed command + business invariants
                    └─ POST .../mutations (idempotent; atomic event append)
                        └─ projector.rebuild and canonical_hash
                            └─ session-specific scoped ledger
                                └─ deterministic case checks / optional live agent
                                    └─ compare run and evidence against prior snapshot
```

Never mutate `data/ledger.db`, `data/scenarios.json` or `@st.cache_resource` paths. Never allow a browser to specify an arbitrary SQLite path or query target. Store sandbox TTL and maximum storage; cleanup on expiry, cancellation and maintenance. On every mutation, invalidate affected cached account statements, session case memory, expected facts and all trace/replay correlations from previous revision.

## Mutation catalog (v1)

| Command | Supported input | Event/reconstruction strategy | Invariants / flags |
|---|---|---|---|
| `refund.apply_fx_adjustment` | refund ID, rate, effective date | Sandbox FX event + recomputed refund amount or explicit adjusted record depending on event model | Positive finite rate, compatible currencies, refund must exist |
| `payment.simulate_duplicate` | source TX, elapsed seconds | New payment authorized/captured events with distinct ID, same merchant/card fingerprint/amount | Account ownership, valid dates, no collision |
| `chargeback.change_deadline` | chargeback ID, date | New versioned domain command/event, not direct update; extend projector with explicit sandbox-only type if necessary | Deadline cannot precede opening; escalation recalculated |
| `refund.simulate_rejection` | refund ID, authorized reason | State transition event (`refund.rejected`), may require new branch scenario starting requested | Only valid from requested, no double settlement |
| `merchant.change_refund_window` | merchant ID, window days, effective date | Versioned sandbox policy override referenced by rules; not silent overwrite of past policy | Positive bounded days, explicit effective date |
| `tool.fx_outage` | fault on/off, error code | Tool fault injection in run context, **not a financial event** | Effect scoped to branch and run |
| `record.inject_untrusted_note` | target record, harmless attack text | Test-only untrusted metadata overlay, never trusted instruction | Length bounded, redacted, no sensitive real content |
| `transaction.adjust_amount` | amount in minor units, reason | Only when an event-consistent reissue/adjustment path is implemented | No direct update of settled amounts; derived records consistent |

**Implementation caveat:** existing `events.type` CHECK whitelist does not include adjustment/deadline types. Introduce explicit versioned sandbox-only event types through migrations or a separate sandbox event interpreter; never insert unrecognized types and quietly bypass constraints. Some mutations are P1/P2 until coherent domain events are implemented.

## Precise example - FX refund

Original S01: `TX-2048` charged `BRL 566.79`, refunded `BRL 549.31`; reference and applied FX differ. A visitor may adjust the **sandbox applied FX** using a valid decimal string and date. The preview recalculates derived output from deterministic Decimal logic; the UI displays both original and new amount, and the explained reason. A prior recorded answer referring to BRL 549.31 is marked **stale - original snapshot**. With no key, show deterministic recalculation, not a new natural-language agent conclusion. With BYOK, evaluate the actual agent on the changed snapshot and compare evidence/verdicts.

## Data integrity

- Normalize all monetary fields as integer minor units or `Decimal` string with currency code; no JS floating-point calculation of money.
- Preserve source time zone and timestamps; no negative days/invalid transitions; hold `occurred_at`/`ingested_at` separately.
- Use optimistic concurrency: `If-Match: branch_revision` or explicit `expected_revision` on every mutation. Reject 409 on stale form.
- Use `Idempotency-Key` for mutation submission; same key+payload yields identical result; same key+different payload yields conflict.
- Validate state transitions through the existing projector or service-specific validators; never bypass event log for convenience.
- Add `fork_parent_hash` and `branch_revision` to trace and eval artifacts so stale comparisons are detected before rendering.
- Branch-specific FAISS memory must not reuse another visitor's cases; easiest default: no long-term writes in public sandbox, seed memory immutable and read-only per visitor.
- Live FX uses recorded fixtures in replay/sandbox by default. Explicit user action needed to opt into current external rate source; distinguish current market reference from historical applied acquirer rate.

## Generator and scenario versioning

`ScenarioDefinition` includes `id`, `title`, `question`, `seed`, `account`, `base_event_refs`, `mutation_actions_allowed`, `expected_invariants`, `expected_tools`, `expected_business_outcome`, `expected_escalation`, `ground_truth_version`, `license_and_origin`, `recorded_run_ids`.

Scenario stories (seeded core):

1. `S01` FX markup and rate movement: Decimal, policy, FX date.
2. `S02` duplicate charges 38 seconds apart: idempotency and duplicate detection.
3. `S03` chargeback deadline nearing: temporal policy and human escalation.
4. `S04` unknown ID: honest abstention.
5. `S05` ambiguous equal-amount transactions: clarification, not false duplicate.
6. `S06` refund outside window: policy reasoning.
7. `S07` control refund with no discrepancy: avoid false-positive issue.
8. `S08` settlement arithmetic and holidays: deterministic date math.
9. `S09` malicious text in refund note: prompt injection defense.
10. `S10` unsupported ARS reference rate: unsupported external dependency.
11. `S11` FX upstream unavailable: fault handling.
12. `S12` past case memory: retrieval with provenance.

## Guarded actions: never the same as real payments

A sandbox-only "simulate refund approved" operation appends a synthetic event and updates the simulated projection. It must not invoke payment processor APIs, send emails, or modify real external systems. The visitor must always see "simulated" badges on such actions. Real-customer data uploads are **out of scope** for the initial public portfolio release.

## API acceptance scenarios

- Two anonymous sessions fork S01 and apply different rates; each reads only its own derived result.
- Attempt to read another session's branch returns generic 404/403 without revealing its existence.
- Two concurrent mutations with same expected revision: exactly one succeeds, the other receives 409.
- Invalid refund amount/state transition rolls back event append and leaves canonical projection hash unchanged.
- Reset returns exactly the published base hash.
- Injected note with prompt-like text cannot invoke a forbidden tool or change another account's state.
- After mutation, the UI cannot replay an old trace as if it reflected changed data.
- Expired branch is unresolvable and temporary files are removed on expiry.
- Rebuild from events yields same canonical hash on identical seed, branch and configuration.
