# Feature Specification: Isolated sandbox mutations

**Feature Branch**: `feature/v3`

**Created**: 2026-11-23

**Status**: Draft

**Input**: Design documents: [ADR-018](../../docs/decisions/ADR-018-branch-layer-and-store-interface.md),
[ADR-019](../../docs/decisions/ADR-019-sandbox-facade-contract.md),
[ADR-020](../../docs/decisions/ADR-020-postgres-store-and-container.md),
[ADR-021](../../docs/decisions/ADR-021-typed-mutation-and-atomic-commit.md),
[ADR-022](../../docs/decisions/ADR-022-reset-and-staleness.md),
[ADR-025](../../docs/decisions/ADR-025-a-failed-write-loses-nothing.md),
[ADR-026](../../docs/decisions/ADR-026-the-store-serialises-the-writes-of-a-branch.md),
[ADR-028](../../docs/decisions/ADR-028-the-diff-and-the-history-are-reads.md),
[ADR-029](../../docs/decisions/ADR-029-the-expiry-and-the-cleanup-job.md),
[ADR-030](../../docs/decisions/ADR-030-case-memory-scoped-to-the-session.md),
[ADR-031](../../docs/decisions/ADR-031-the-catalog-grows-with-the-round-trip-test.md),
[ADR-032](../../docs/decisions/ADR-032-the-state-of-the-branch-and-the-hash.md),
[ADR-047](../../docs/decisions/ADR-047-the-lifecycle-and-the-limits-of-the-branch.md) and the design package
[LL-V3-R2-03, isolated sandbox mutations](../../docs/v3/advanced-specs/R2-03-isolated-sandbox-mutations.md). The
milestone that built the branch layer is [specs/002](../002-r2-visitor-sandbox/spec.md).

The package was written for a greenfield plan. The repository has since built the branch layer, the typed mutations,
the preview, the reset, the undo, the expiry and the facade that serves them. This specification covers the part of
the package that is still missing: the conformance of the acceptance scenarios of the package over the seeded
scenarios, the property tests that hold the invariants of the branch, and the published diff that shows what one
mutation did.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A visitor edits a value and reads the exact consequence (Priority: P1)

A visitor opens the scenario S01, edits the applied rate of a refund and asks what would happen. The system answers
with a preview that carries the value before and the value after, the branch revision and the hash of the branch,
and it writes nothing. When the visitor commits the same command, the branch moves by one revision, the diff lists
the affected rows with their two values, and the case ends in a decision that the code computed.

**Why this priority**: the preview is the promise of the feature and the diff is the reason it exists. Without the
preview a sandbox destroys evidence, and without the diff a visitor sees a changed ledger and no reason.

**Independent test**: fork S01, preview `refund.apply_fx_adjustment`, read the branch status, commit the same
command and read the diff. The preview leaves the revision and the hash untouched, the commit raises the revision by
exactly one, the diff lists the affected rows with the exact `Decimal` strings of their values before and after,
and the decision is one of the declared outcome labels of the scenario.

### User Story 2 - Two sessions that edit the same transaction never see each other (Priority: P1)

Two visitors open the same scenario at the same time. The first one applies a mutation. The second one still reads
the base values, and a direct request for the branch of the first one is refused without disclosing that the branch
exists.

**Why this priority**: isolation is the safety property of the whole feature. If it fails, the feature must not
ship, and the proof has to exist before the sandbox is exposed to the public.

**Independent test**: run two sessions against the same scenario, mutate in the first one and read the ledger and
the diff of the second one. The second session sees the base values, its canonical hash did not move, and a direct
read of the branch of the first session is refused with a generic answer that does not disclose the existence of
the branch.

### User Story 3 - The same mutation sent twice commits at most one event (Priority: P1)

A client retries a commit because the network failed after the server answered. The branch carries one event, the
revision moved by one, and the second delivery returns the identical revision, the identical hash and the
identical diff. The same idempotency key with a different payload is refused, and nothing is appended.

**Why this priority**: a retry that appends twice corrupts the branch and breaks the promise that the branch is
rebuilt from its events.

**Independent test**: send the same commit twice with the same idempotency key and the same payload, then send the
key again with a different payload. The count of the events of the branch moves by one and never by two, the two
deliveries answer with the same revision and the same hash, and the third delivery is refused with a conflict and
appends nothing.

### User Story 4 - A wrong precision is refused and the hash does not move (Priority: P1)

A visitor sends an amount with more decimals than the schema of the command accepts, or a currency that does not
match the record. The system answers `422`, names the rule that failed, and the hash of the branch is exactly what
it was.

**Why this priority**: the money of the sandbox is exact. A float that enters the branch corrupts every number
computed from it, and a refusal that moves the hash is a refusal that is not a refusal.

**Independent test**: send a rate with nine decimals and an amount in the wrong currency, one after the other. The
two are refused with `422`, the codes name the rule that failed, and the canonical hash of the branch is unchanged
after each refusal.

### User Story 5 - A reset returns the branch to the base (Priority: P2)

A visitor changes their mind. The reset drops the events of the branch, the revision goes back to zero and the
canonical hash is the hash of the base snapshot, row for row. The answers that were computed before the reset stay
marked stale.

**Why this priority**: the reset is the escape hatch that makes the experimentation safe, and it is the base of any
comparison between two variations of the same case.

**Independent test**: fork S01, commit two mutations, reset, and read the status, the ledger and the hash. The
revision is zero, the event count is zero, the canonical hash equals the base hash recorded at fork time and the
ledger of the branch equals the ledger of the base row for row.

### User Story 6 - The source events cannot be touched from the outside (Priority: P2)

A visitor tries to change the identity of an event, its origin or the content of the published base. The request is
refused and the branch does not move. The published base file and the sample of the repository are byte identical
before and after the whole suite.

**Why this priority**: the sandbox is a laboratory over a fictional ledger. A write that reaches the source would
change the evidence of every published scenario.

**Independent test**: send a mutation that names a read only field, then read the hash of the published base file
and the bytes of `data/sample/` before and after the whole mutation suite. The mutation is refused, the hash does not
move and the files are byte identical.

### User Story 7 - A mutated rate invalidates the old answer and never re-labels it (Priority: P2)

A visitor changes the rate of a refund and reads the answer that was published for the case. The answer is marked
stale against the original snapshot, and it is never presented as the current result nor as a live run.

**Why this priority**: an answer that was computed on data that no longer exists is wrong, and an answer that is
presented as current is worse than an answer that was never published.

**Independent test**: fork S01, commit one mutation of a rate, then read the case. The answer of the original
recording is marked stale against the hash of the base, and the mode that the reader shows is the mode of the
recording and not the mode of a live run.

### User Story 8 - The engineer reads the diff of a mutation as a published artifact (Priority: P3)

An engineer who wants to show what one mutation did publishes the diff of the branch: the rows that changed, the
value before and the value after, the hash of the branch and the hash of the base, and a command that reproduces it.
The artifact is a file with a hash, so a third party can confirm it.

**Why this priority**: the package asks for a precise diff screenshot and for the source paths of the change. The
repository publishes artifacts with a manifest and a hash, and the diff of a branch is the same kind of thing.

**Independent test**: export the diff of a branch with one committed mutation into the folder of the published
artifacts, and run the export twice. The two exports are byte identical, the artifact carries the hashes of the
branch and of the base, and the command that reproduces the mutation is inside it.

### Edge Cases

- Two visitors send a mutation on the same branch with the same expected revision at the same instant: exactly one
  is applied, the other is refused with a conflict, and the hash of the branch does not move.
- A mutation breaks a business invariant of the scenario: the whole mutation is rolled back, the reason names the
  invariant, and the hash of the branch is the hash it had before.
- The time to live of the branch has passed: reads and writes are refused with `410`, and the cleanup job removes
  the rows and the events of the branch.
- A payload that is too large, too deep or too long: it is refused before the rules of the business run.
- The client clock is ahead or behind the server: the server clock is the only authority, and a timestamp outside
  the accepted window is refused.
- A branch whose projection was recomputed from its events alone does not reproduce the hash that the commit
  returned: the branch is not served as valid.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The preview of a mutation computes the projected outcome without writing an event, and it leaves the
  revision, the hash and the count of the events of the branch untouched.
  - Test: `tests/sandbox/test_mutation_preview.py` fails while the preview moves the revision or the hash.
- **FR-002**: A commit appends one event and raises the revision by exactly one, and the projection of the branch is
  rebuilt from the events of the branch alone.
  - Test: `tests/sandbox/test_mutation_commit.py` fails while a commit appends no event or appends two.
- **FR-003**: The diff is a read of the branch as it is, its order is stable across two reads of the same revision,
  and every value of the diff is an exact `Decimal` string.
  - Test: `tests/sandbox/test_branch_reads.py` fails while the order of the diff moves between two reads.
- **FR-004**: Two sessions never see the branch of each other, and a refusal does not disclose that the branch
  exists.
  - Test: `tests/sandbox/test_isolation.py` fails while the second session reads a row of the branch of the first
    session.
- **FR-005**: The same idempotency key with the same payload commits one event and returns the identical revision,
  the identical hash and the identical diff, and the same key with a different payload is refused.
  - Test: `tests/sandbox/test_mutation_duplicate.py` fails while the second delivery appends an event.
- **FR-006**: A wrong precision and a wrong currency are refused with `422`, the code names the rule that failed,
  and the hash of the branch does not move.
  - Test: `tests/sandbox/test_mutation_preview.py` fails while a wrong precision is accepted.
- **FR-007**: The reset returns the branch to the base hash and to the revision zero, and the answers computed
  before the reset stay marked stale.
  - Test: `tests/sandbox/test_reset.py` fails while the reset leaves an event of the branch.
- **FR-008**: A read only field cannot be changed, and the published base and the sample of the repository are byte
  identical before and after the whole suite.
  - Test: `tests/sandbox/test_mutation_commit.py` fails while a read only field is written, and
    `tests/test_sample_untouched.py` fails while a file of `data/sample/` moves.
- **FR-009**: A mutation that invalidates a published answer marks that answer stale against the hash of the base,
  and the mode of the recording is never changed to the mode of a live run.
  - Test: `tests/sandbox/test_reset.py` fails while a stale answer is presented as the current one.
- **FR-010**: The suite of the acceptance scenarios runs over the seeded scenarios S01, S02 and S03 and not over
  S01 alone, so that a rule that holds for one scenario and not for another is caught.
  - Test: `tests/sandbox/test_acceptance_conformance.py` fails while a rule of the suite is checked on one scenario
    only.
- **FR-011**: The properties of the branch hold over a generated sequence of commands: the hash of the branch is
  always the hash of its events, the revision is always the count of the events, and a refused command never
  changes either.
  - Test: `tests/sandbox/test_branch_properties.py` fails while a generated sequence breaks the property.
- **FR-012**: The export of a diff is a pure function of the branch and it carries the hashes of the branch and of
  the base and the command that reproduces the mutation.
  - Test: `tests/sandbox/test_diff_artifact.py` fails while two exports of the same branch differ.

### Key Entities

- **Branch**: a private copy of a published base, with a revision and a canonical hash.
- **Command**: a typed mutation with a kind, a payload and an idempotency key.
- **Event**: the append only record of an applied command, the only thing the projector replays.
- **Preview**: the projected outcome of a command, computed without writing.
- **Diff**: the read of the rows that a command changed, with the value before and the value after.
- **Staleness**: the mark that says that an answer was computed on a state that no longer exists.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The preview of a mutation writes nothing, and the commit that follows raises the revision by exactly
  one.
- **SC-002**: The number of the isolated failures of the suite is zero over the seeded scenarios S01, S02 and S03.
- **SC-003**: The same mutation sent twice commits one event, and the same key with a different payload commits
  nothing.
- **SC-004**: A wrong precision and a wrong currency are refused with `422` and the hash of the branch does not
  move.
- **SC-005**: The reset returns the hash of the base and the revision zero, and the answers of the branch stay
  marked stale.
- **SC-006**: The published base and the sample of the repository are byte identical before and after the whole
  suite.
- **SC-007**: The properties of the branch hold over the generated sequences of commands, and the suite that holds
  them is in the gate.
- **SC-008**: The export of a diff is byte identical when it runs twice, and it carries the hashes and the command
  that reproduces the mutation.

## Assumptions

- The branch layer, the typed mutations, the preview, the reset, the undo, the expiry and the facade already exist.
  This specification adds the conformance suite of the acceptance scenarios, the property tests and the published
  diff. It does not rewrite the branch layer.
- The store has two implementations, the file backed one and the Postgres one, and the tests of the suite run
  against the file backed one. The contract of the store is the same for the two, and the test of the contract
  covers it.
- The property tests use a generator of the sequences of commands written for the repository. The repository does
  not carry a property testing library today, and the first task of the milestone decides between adding one and
  writing a deterministic seeded generator.
- The diff of a branch is a read of the branch, as ADR-028 decided. The export of the diff does not change that:
  it copies a read and hashes it.
- No task of this milestone writes into the sample of the repository, and the published base of a scenario is never
  written.

## Out of scope

- The live mode, which reads the ledger of the branch of the visitor but does not mutate it.
- The multi agent work of the design package, which stays behind a flag and out of the runtime until a paired
  comparison measures a gain, under ADR-P007.
- The review of a case by a person, which belongs to
  [specs/012](../012-r10-human-review-and-approval/spec.md).
- The costs of a mutation, which belong to
  [specs/011](../011-r9-cost-per-case-and-decision-utility/spec.md).
- The persistence of the branch in Postgres beyond the store that exists, and the deployment of the facade with
  more than one worker, which is a decision of the deployment.

## Design documents

| Document | What it decides for this specification |
|---|---|
| [ADR-018](../../docs/decisions/ADR-018-branch-layer-and-store-interface.md) | The branch layer sits behind a store interface, so the same rules run against the file backed store and against Postgres. |
| [ADR-019](../../docs/decisions/ADR-019-sandbox-facade-contract.md) | The facade follows the versioned contract and the session is a cookie, so the isolation is by session and not by a key the client carries. |
| [ADR-020](../../docs/decisions/ADR-020-postgres-store-and-container.md) | The branch data lives in Postgres and the file backed store is the fallback. |
| [ADR-021](../../docs/decisions/ADR-021-typed-mutation-and-atomic-commit.md) | A mutation is a typed command and the commit is atomic, so a refused command changes nothing. |
| [ADR-022](../../docs/decisions/ADR-022-reset-and-staleness.md) | The reset returns the base and a generation marks the answers that went stale. |
| [ADR-025](../../docs/decisions/ADR-025-a-failed-write-loses-nothing.md) | A write that fails leaves the branch exactly where it was, in the two stores alike. |
| [ADR-026](../../docs/decisions/ADR-026-the-store-serialises-the-writes-of-a-branch.md) | The store serialises the writes of a branch, so a lost update is impossible. |
| [ADR-028](../../docs/decisions/ADR-028-the-diff-and-the-history-are-reads.md) | The diff and the history are reads, so the export of a diff copies a read. |
| [ADR-029](../../docs/decisions/ADR-029-the-expiry-and-the-cleanup-job.md) | The expiry has one home and the cleanup is a job of the process. |
| [ADR-030](../../docs/decisions/ADR-030-case-memory-scoped-to-the-session.md) | The case memory of a session lives in the folder of the session, so it does not leak between the sessions. |
| [ADR-031](../../docs/decisions/ADR-031-the-catalog-grows-with-the-round-trip-test.md) | The catalog of the sandbox grows with the round trip test, so every accepted kind is exercised. |
| [ADR-032](../../docs/decisions/ADR-032-the-state-of-the-branch-and-the-hash.md) | The hash of the branch is the hash of its state, so the branch proves itself. |
| [ADR-047](../../docs/decisions/ADR-047-the-lifecycle-and-the-limits-of-the-branch.md) | The lifecycle of the branch travels as a stream and the limits answer with a code. |
| [LL-V3-R2-03](../../docs/v3/advanced-specs/R2-03-isolated-sandbox-mutations.md) | The design package this specification ports. |
| [specs/002](../002-r2-visitor-sandbox/spec.md) | The milestone that built the branch layer and the facade. |

## Status

| Part | State in the repository on 2026-11-23 |
|---|---|
| The branch layer, the store interface and the two stores | Built. `ledgerlens/sandbox/branch.py`, `store.py` and `postgres_store.py`. |
| The typed mutations and the atomic commit | Built. `ledgerlens/sandbox/mutation.py` and `events.py`, with the accepted kinds of the catalog. |
| The preview | Built. `tests/sandbox/test_mutation_preview.py` covers it and the facade serves it. |
| The reset, the undo and the staleness | Built. `tests/sandbox/test_reset.py` and `tests/sandbox/test_undo.py`. |
| The isolation between the sessions | Built. `tests/sandbox/test_isolation.py`. |
| The facade and the rate of the requests | Built. `ledgerlens/api/sandbox.py` and `ledgerlens/sandbox/rate_limit.py`. |
| The interface of the sandbox | Built. `apps/web/features/sandbox/` with the panel of the branch, the form of the mutation and the diff. |
| The conformance suite over the acceptance scenarios of the package | Not built as one suite. The rules are spread over the tests of the folder, and the seeded scenarios S02 and S03 are not exercised by all of them. |
| The property tests of the branch | Not built. The repository carries no property testing library and no generated sequence of commands. |
| The published diff of a mutation | Not built. The diff is served to the interface and is not published as an artifact with a hash. |
| The screenshot of the diff that the package asks for | Not built and not planned as an image. The repository publishes data with a manifest and a hash, and the diff is published as data. |

The package says that FastAPI wraps the branch service and that the Next.js interface only submits typed commands.
The repository does the same thing with other names: the facade is `ledgerlens/api/sandbox.py`, the session is a
cookie under ADR-019 and the store is behind an interface under ADR-018. This specification follows the repository
and does not rename the layer.
