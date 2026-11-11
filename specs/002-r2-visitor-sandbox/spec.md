# Feature Specification: Isolated visitor sandbox branches

**Feature Branch**: `feature/v3`

**Created**: 2026-11-11

**Status**: Draft

**Input**: User description: "A visitor of the public demo must be able to open any published scenario, fork the immutable base snapshot into a private branch, apply typed mutations such as an FX rate adjustment on a refund or a duplicated charge, see a deterministic before and after diff with the verdict of the case, reset the branch to the original state and recover the original canonical hash, and never observe the work of another visitor. The sandbox never touches a real payment path, the published snapshot stays byte identical, and every change is an event that a projector replays deterministically."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fork an immutable base snapshot into a private branch (Priority: P1)

A visitor opens scenario S01, the FX markup case, and asks the system for a private working copy. The
system allocates an opaque branch id bound to the visitor session, records the canonical hash of the
published base snapshot, and hands the visitor a branch at revision 0 with the base contents. The
published snapshot file itself is never written, so a second visitor forking the same scenario gets
exactly the same starting bytes and the same base hash.

**Why this priority**: Every other sandbox capability depends on a branch existing. Without an
immutable base and a private fork there is nothing to mutate, no isolation to prove and nothing to
diff. This is the smallest slice that already delivers visible value, because the visitor can open a
case and read the account scoped ledger.

**Independent Test**: Fork S01 in a fresh session, then read the branch ledger and the branch status.
The test passes when the status endpoint returns revision 0, the base canonical hash and a branch id
that does not exist for any other session, and when the hash of the published snapshot file on disk
is byte identical before and after the fork.

**Acceptance Scenarios**:

1. **Given** a published scenario with canonical hash `h` and no branch for the session, **When** the
   visitor asks for a fork, **Then** the system returns a branch id of the form `sb_` plus 24
   hexadecimal characters, revision 0, base hash `h` and an expiry timestamp, and the published
   snapshot file hash on disk is unchanged.
2. **Given** two different visitor sessions on the same scenario, **When** both fork the scenario,
   **Then** each branch reports the same base canonical hash `h` and each session sees only its own
   branch id.
3. **Given** a branch that already exists for the session on that scenario, **When** the visitor
   forks again, **Then** the system returns the existing branch id and revision instead of creating a
   second branch, and the number of branches for the session does not grow.

---

### User Story 2 - Preview a typed mutation and then commit it (Priority: P1)

A visitor edits one field of one record, for example the applied FX rate of refund `R-0203` on
transaction `TX-2048`, and asks what would happen before anything is written. The system validates
the typed command against the branch state and the business invariants, and answers with a preview
that carries no write. Only when the visitor commits does the system append events to the branch
event store and recompute the projection.

**Why this priority**: A sandbox that writes before it explains is a sandbox that destroys evidence
and confuses visitors. The preview is the safety promise of the feature and it is also the fastest
path to value, because the visitor immediately sees the numeric consequence of the edit.

**Independent Test**: Send a preview request for `refund.apply_fx_adjustment` on a known refund of
S01, then compare the branch status before and after the preview. The test passes when the preview
returns the computed before and after amounts as decimal strings, the branch revision and the
branch canonical hash are unchanged after the preview, and a commit of the same command raises the
revision by exactly one.

**Acceptance Scenarios**:

1. **Given** a branch at revision 0 with refund `R-0203` refunded at BRL 549.31, **When** the visitor
   previews `refund.apply_fx_adjustment` with rate `5.41250000` and a valid effective date, **Then**
   the response carries `valid: true`, the before and the after payout as decimal strings with the
   currency code, and the branch revision and canonical hash are unchanged.
2. **Given** a valid preview, **When** the visitor commits the same command with an `Idempotency-Key`
   and the expected revision, **Then** the system appends the sandbox events atomically, returns
   revision 1 and the new canonical hash, and the branch ledger shows the new refund amount.
3. **Given** a commit whose expected revision is stale, **When** the request reaches the server,
   **Then** the system answers `409` with code `REVISION_CONFLICT`, appends no event, and the branch
   canonical hash stays exactly as it was.
4. **Given** a command with an unknown kind, **When** the visitor sends it, **Then** the system
   answers `422` with code `UNKNOWN_MUTATION_TYPE` and a readable reason that names the accepted
   kinds, and no event is appended.

---

### User Story 3 - Read the deterministic diff and the verdict of the case (Priority: P1)

After a mutation, the visitor wants to know exactly what changed and what the case now says. The
system computes the diff between the projected state before the mutation and the projected state
after it, listing every affected record with its value before and its value after, and it runs the
deterministic case checks of the scenario over the new projection so the visitor sees the verdict of
the case, for example that the refund is no longer below the FX reference.

**Why this priority**: The diff and the verdict are the entire reason the feature exists. A mutation
without a readable consequence teaches nothing and would leave the visitor reading a changed ledger
without knowing why.

**Independent Test**: Fork S01, commit one `refund.apply_fx_adjustment`, then request the diff for
the branch. The test passes when the diff lists the affected refund and the transaction, each value
is a decimal string or an explicit non monetary field, the ordering of the entries is stable across
two consecutive reads, and the verdict is one of the declared outcome labels of the scenario.

**Acceptance Scenarios**:

1. **Given** a branch at revision 1 with one committed FX adjustment, **When** the visitor reads the
   diff, **Then** the response lists each affected record with its before value and its after value,
   the before values equal the values of the base snapshot, and the after values equal the values of
   the current projection.
2. **Given** the same branch and the same revision, **When** the visitor reads the diff twice, **Then**
   the two payloads are identical, byte for byte, including the ordering of the entries.
3. **Given** a branch whose projection was recomputed from its events alone, **When** the canonical
   hash is computed, **Then** it equals the hash reported after the commit, which proves the diff and
   the verdict are reproducible.
4. **Given** a recorded answer that referred to the amount before the mutation, **When** the visitor
   reads the case after the mutation, **Then** that answer is marked stale and points at the
   original snapshot hash, and it is never presented as the current result.

---

### User Story 4 - Reset the branch and get the original canonical hash back (Priority: P2)

A visitor changes their mind, or wants to compare two variations from the same starting point. The
reset action drops every event of the branch and returns the branch to the published base, with the
same canonical hash the branch had at fork time and the revision back at 0.

**Why this priority**: Reset is the escape hatch that makes experimentation safe and is the base of
any comparison between two variations. It comes after the mutation loop because it is only
meaningful once mutations exist.

**Independent Test**: Fork S01, commit two mutations, then reset. The test passes when the branch
status reports revision 0, the canonical hash equals the base hash recorded at fork time, the branch
ledger equals the base ledger row for row, and every answer produced before the reset is marked stale.

**Acceptance Scenarios**:

1. **Given** a branch at revision 2 with two committed mutations, **When** the visitor resets the
   branch, **Then** the response carries the base canonical hash, the revision is 0 and the branch
   event count is 0.
2. **Given** a branch that was reset, **When** the visitor forks the same scenario again or reads
   the branch ledger, **Then** the ledger rows are byte identical to the rows of the published base
   snapshot.
3. **Given** answers and traces produced before the reset, **When** the visitor reads them
   afterwards, **Then** each one is marked stale against the original snapshot and none of them is
   shown as the current answer.

---

### User Story 5 - Work on the same scenario without seeing another visitor work (Priority: P2)

Two visitors open the same scenario at the same time. Each one applies a different mutation, for
example two different FX rates. Each visitor sees only the effect of their own mutation, and each
one gets a clean refusal when they try to read or write the branch of the other.

**Why this priority**: Isolation is the safety property of the whole feature. If it fails, the
feature must not ship, but it can be proven after the mutation loop works, so it sits right after the
core loop.

**Independent Test**: Run two sessions against the same scenario, mutate in the first one, then read
the diff and the ledger of the second one. The test passes when the second session sees the base
values, when a direct read of the first branch from the second session is refused with a generic
`404` that does not disclose that the branch exists, and when the canonical hash of the second
branch did not move.

**Acceptance Scenarios**:

1. **Given** two sessions with one branch each on the same scenario, **When** the first session
   commits a mutation, **Then** the second session still reads the base values and the base
   canonical hash, and the event count of the second branch stays 0.
2. **Given** a branch that belongs to another session, **When** the second session requests that
   branch, its diff or its ledger, **Then** the system answers `404` with a generic message and
   never returns the contents of the branch, its owner or its existence.
3. **Given** two sessions, **When** the second session sends a mutation that names the branch of the
   first session, **Then** the system answers `404`, no event is appended anywhere and the canonical
   hash of the first branch is unchanged.
4. **Given** a case memory written by the first session, **When** the second session runs the same
   scenario, **Then** the second session finds no case written by the first session.

---

### User Story 6 - Meet an expired branch with a clear message (Priority: P3)

A visitor leaves a tab open and comes back the next morning. The branch is gone because its time to
live ended, and the system says so plainly instead of pretending the branch still exists or
returning a broken page.

**Why this priority**: Expiry is a resource guard, not a user value. It has to exist for the feature
to be safe to expose publicly, but the visitor impact is small and the behaviour is only visible
after a long pause.

**Independent Test**: Fork a branch with a short time to live, wait for it, then read the branch.
The test passes when the answer is `410` with code `BRANCH_EXPIRED`, when the stored rows and the
stored events of that branch are gone, and when the published base snapshot is still intact.

**Acceptance Scenarios**:

1. **Given** a branch whose expiry timestamp has passed, **When** the visitor reads it or sends a
   mutation to it, **Then** the system answers `410` with code `BRANCH_EXPIRED` and the message
   offers to fork the scenario again.
2. **Given** an expired branch, **When** the cleanup job runs, **Then** the branch rows and its
   events are deleted and no row of the published snapshot changes.
3. **Given** the same visitor session after the expiry, **When** the visitor forks the scenario
   again, **Then** the new branch starts at revision 0 with the base canonical hash.

---

### User Story 7 - Undo the last mutation on the branch (Priority: P3)

A visitor applies a mutation and sees immediately that it was a mistake. The undo action returns the
branch to the state it had before that mutation, with the revision back to the previous value.

**Why this priority**: Undo is a convenience on top of reset. Reset already covers the need of
returning to the original, so undo is a refinement and not a blocker for the first release.

**Independent Test**: Fork S01, commit one mutation, then undo it. The test passes when the
canonical hash after the undo equals the canonical hash before the mutation, the revision returns to
the previous value, and the branch event log keeps the undone event as a recorded undo event instead
of deleting history.

**Acceptance Scenarios**:

1. **Given** a branch at revision 1, **When** the visitor undoes the last mutation, **Then** the
   canonical hash equals the hash the branch had at revision 0 and the revision is back at 0.
2. **Given** a branch at revision 0 with no mutation, **When** the visitor asks for an undo, **Then**
   the system answers `409` with code `NOTHING_TO_UNDO` and the branch stays untouched.
3. **Given** an undone mutation, **When** the visitor reads the branch history, **Then** the
   original event is still listed and marked as undone, because the history is append only.

### Edge Cases

- Two visitors send a mutation on the same branch with the same expected revision at the same
  instant: exactly one is applied, the other receives `409` with code `REVISION_CONFLICT`, no event
  is appended by the loser and the canonical hash does not move.
- A mutation breaks a business invariant, for example an FX rate of zero, a negative refund, a refund
  above the captured amount or a chargeback deadline before the opening date: the system answers
  `422` with code `INVARIANT_VIOLATION`, the reason names the invariant, the event append is rolled
  back and the canonical hash stays as it was.
- A visitor replays a request against a stale snapshot, that is a request built on a branch revision
  that is no longer current: the system answers `409`, never applies the event to the newer state and
  never silently rebases the request.
- The branch time to live has passed: reads and writes answer `410` with code `BRANCH_EXPIRED` and
  the cleanup job removes the stored rows and the stored events of that branch.
- The same mutation is delivered twice with the same idempotency key and the same payload: at most
  one event is committed and the second delivery returns the identical revision, the identical
  canonical hash and the identical diff.
- The same idempotency key arrives with a different payload: the system answers `409` with code
  `IDEMPOTENCY_MISMATCH` and nothing is appended.
- The visitor sends a mutation kind that the catalog does not accept, or a kind that is not enabled
  for that scenario: the system answers `422` with code `UNKNOWN_MUTATION_TYPE` and lists the
  accepted kinds.
- The visitor tries to change a read only field, for example the event identity, the origin, the
  branch owner or the published snapshot content: the system answers `422` with code
  `READ_ONLY_FIELD` and the projection is unchanged.
- The visitor sends a payload with a wrong numeric precision, a non decimal amount or a currency
  that does not match the record: the system answers `422` with code `INVALID_AMOUNT` or code
  `CURRENCY_MISMATCH`, the unchanged canonical hash is returned, and no float arithmetic is used
  anywhere on the path.
- The client clock is ahead or behind the server clock: the server clock is the only authority for
  expiry and for the recorded timestamp, a client supplied timestamp outside the allowed window is
  refused with code `INVALID_EFFECTIVE_DATE`, and two branches forked from the same snapshot in the
  same second carry the same base hash.
- The canonical hash after a reset does not equal the base hash: the system detects the mismatch,
  refuses to serve the branch, reports code `HASH_MISMATCH` and offers a fresh fork, because a
  branch that cannot prove its own state is never shown as valid.
- A visitor sends an oversized payload, a nested object deeper than the accepted depth or a note
  longer than the accepted length: the system answers `413` or `422` before any validation of the
  business rules runs.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST keep the published base snapshot immutable. A fork, a mutation, a
  preview, a reset and a cleanup job MUST leave the bytes of the published snapshot unchanged, and a
  test MUST compare the file hash before and after a full mutation suite.
- **FR-002**: Every visitor MUST receive a base snapshot that is byte identical to every other
  visitor of the same scenario, and the canonical hash reported at fork time MUST be the same for all
  of them.
- **FR-003**: The system MUST allocate an opaque branch identifier of the form `sb_` plus 24
  hexadecimal characters, and the identifier MUST NOT encode the session, the scenario or any
  filesystem path.
- **FR-004**: The system MUST bind every branch to exactly one owner session and MUST refuse any read
  or write of a branch whose owner does not match the calling session.
- **FR-005**: The system MUST answer `404` with a generic message when a session asks for a branch it
  does not own, and the answer MUST NOT disclose whether that branch exists.
- **FR-006**: The system MUST record every mutation as an append only sandbox event in the event
  store of the branch, and MUST NEVER update a domain row directly as a result of a visitor action.
- **FR-007**: The system MUST never write to `data/ledger.db`, to `data/scenarios.json` or to any
  other published artifact, and MUST NEVER invoke a payment processor, send a message or reach an
  external system as a result of a sandbox mutation.
- **FR-008**: The system MUST attach the origin label `sandbox` to every event appended by a
  mutation, and the branch events MUST be distinguishable from the events of the published
  snapshot.
- **FR-009**: The system MUST recompute the projected state from the event log with a deterministic
  projector, so that replaying the same events on the same base produces the same canonical hash.
- **FR-010**: The system MUST compute the canonical hash with a canonical serialisation of the
  projected rows, and the same implementation MUST be used for the base snapshot and for every
  branch, so that the two hashes are comparable.
- **FR-011**: The system MUST be idempotent on append. The same event identity appended twice MUST
  be stored once, and the second append MUST be reported as a duplicate rather than as an error.
- **FR-012**: The system MUST be idempotent on request. The same idempotency key with the same
  payload MUST return the identical revision, the identical canonical hash and the identical diff,
  and MUST NOT append a second event.
- **FR-013**: The system MUST answer `409` with code `IDEMPOTENCY_MISMATCH` when the same idempotency
  key arrives with a different payload.
- **FR-014**: The system MUST require an expected revision on every mutation and MUST answer `409`
  with code `REVISION_CONFLICT` when the expected revision does not match the current revision.
- **FR-015**: The system MUST validate the typed command against the current branch state BEFORE any
  write, and MUST reject an invalid command with `422` and a reason that names the failed rule in
  readable English.
- **FR-016**: The system MUST offer a preview endpoint that validates the command and computes the
  projected outcome WITHOUT writing an event, and the preview MUST NOT change the revision, the
  canonical hash or the event count of the branch.
- **FR-017**: The system MUST compute all monetary values with integer minor units or `Decimal`
  strings, and MUST NOT use floating point arithmetic anywhere on the mutation path.
- **FR-018**: The system MUST check the declared business invariants of the scenario after the
  projection of a mutation, and MUST roll back the whole mutation when any invariant fails.
- **FR-019**: The system MUST return a diff that lists every affected record with its value before
  and its value after, and the ordering of the entries MUST be stable across repeated reads of the
  same revision.
- **FR-020**: The system MUST return the verdict of the case computed by the deterministic checks of
  the scenario over the current projection, and the verdict MUST be one of the declared outcome
  labels of that scenario.
- **FR-021**: The system MUST reset a branch by dropping every event of that branch and MUST return
  the canonical hash of the published base snapshot, which MUST equal the hash recorded at fork time.
- **FR-022**: After a reset, the system MUST mark every answer, trace and replay produced before the
  reset as stale against the original snapshot, and MUST NOT present any of them as the current
  result.
- **FR-023**: The system MUST give every branch a hard time to live, MUST reject every access to a
  branch after the expiry with `410` and code `BRANCH_EXPIRED`, and MUST delete the stored rows and
  the stored events of the expired branch.
- **FR-024**: The system MUST clean expired branches automatically, with a delay of at most 60
  seconds between the expiry moment and the deletion.
- **FR-025**: The system MUST enforce per branch resource limits: at most 20 committed mutations, at
  most 200 stored events, a payload of at most 32 kilobytes and a note of at most 300 characters, and
  MUST answer `429` when the limit is reached.
- **FR-026**: The system MUST scope every read to the account of the branch, and MUST NOT return a
  row of another account.
- **FR-027**: The system MUST NOT expose any cross visitor read of branch data, of the event log or
  of the case memory, and a case memory written in one session MUST NOT be visible in another
  session.
- **FR-028**: The system MUST expose the origin of the data in the interface, so that the visitor
  sees that the values come from a simulation and not from a real payment system.
- **FR-029**: The system MUST refuse any attempt to change a read only field, including the event
  identity, the event origin, the branch owner, the base snapshot and the event log itself, with
  `422` and code `READ_ONLY_FIELD`.
- **FR-030**: The system MUST refuse a mutation kind that is not in the accepted catalog, and a kind
  that is not enabled for the scenario, with `422` and code `UNKNOWN_MUTATION_TYPE`.
- **FR-031**: The system MUST use the server clock as the only authority for the expiry and for the
  recorded timestamps, and MUST refuse a client supplied effective date outside the accepted window
  with `422` and code `INVALID_EFFECTIVE_DATE`.
- **FR-032**: The system MUST detect a canonical hash that does not match the recomputed value after
  a reset, MUST refuse to serve that branch and MUST report code `HASH_MISMATCH`.
- **FR-033**: The system MUST append the events of a mutation, project them and update the revision
  and the canonical hash inside a single transaction, so that a crash between the append and the
  projection leaves the branch on the previous revision and never in a half applied state.
- **FR-034**: The system MUST expose the branch status, the branch ledger, the diff and the reset
  through a versioned HTTP facade, with the endpoint contract described in the interface document,
  and MUST answer with the documented status codes for each case.
- **FR-035**: The system SHOULD publish the branch lifecycle events over a server sent event stream
  with a monotonically increasing sequence, so that the interface can follow a long running
  projection without polling.
- **FR-036**: The system MUST treat the commit of a mutation as the only point where the revision
  moves, and MUST return the new revision, the new canonical hash and the diff of the mutation in
  the same response.
- **FR-037**: The system MUST support an undo of the last mutation, which returns the canonical hash
  and the revision of the previous state and records the undo as a new event instead of deleting
  history.
- **FR-038**: The system MUST answer `409` with code `NOTHING_TO_UNDO` when an undo is requested on a
  branch with no mutation to undo.
- **FR-039**: The system MUST run offline, with a scripted model, prebuilt fixtures and a fixed seed,
  so that every sandbox test passes with `LEDGERLENS_OFFLINE=1` and without any provider key.
- **FR-040**: The system MUST keep the branch store behind an interface, so that the Postgres
  implementation can be replaced by a file backed implementation without any change in the domain
  logic, and the two implementations MUST behave identically under the same test suite.
- **FR-041**: The system MUST NOT accept a file path, a SQL statement or a URL from the browser, and
  MUST NOT expose a route that writes to the published snapshot.
- **FR-042**: The system MUST attach the schema version to every sandbox response, and MUST attach
  the branch id, the branch revision and the base snapshot hash to every trace and to every answer
  produced inside a branch.

### Key Entities

- **Scenario**: a published case that a visitor can open, with an id, a title, the question, the
  account under analysis, the list of accepted mutation kinds, the expected invariants, the expected
  outcome labels and the version of the ground truth. A scenario references a base snapshot and
  never owns mutable data.
- **Snapshot**: the immutable published version of the simulated ledger, with a content hash, a
  seed, a source list, a simulator version, the canonical hash of the projected rows and the licence
  of every source. A snapshot is read only for every consumer and is never written by the sandbox.
- **Branch**: a private, short lived working copy owned by one session, with an opaque id, the owner
  session, the base snapshot id, the base canonical hash, a monotonic revision, the current canonical
  hash, the creation time, the expiry time, the state and the per branch resource counters.
- **Mutation**: a typed command that a visitor asks to apply, with a kind taken from the accepted
  catalog, a payload validated against the command schema, an optional reason of at most 200
  characters, an expected revision and an idempotency key. A mutation is a request, not a write.
- **MutationEvent**: the event that a committed mutation appends to the branch event store, with the
  event identity, the branch id, the event type, the aggregate it changes, the occurred timestamp, the
  payload, the origin label `sandbox`, the command id that produced it and the flag that marks an
  undone event. Mutation events are append only and are never updated in place.
- **ProjectedState**: the derived tables that the projector computes for a branch from the base
  snapshot plus the events of that branch, including the transactions, refunds, chargebacks, FX
  applications, settlements and the account scoped rows. The projected state is a pure function of
  the base and of the event log.
- **Invariant**: a named business rule of the scenario, with an id, a readable description, the
  predicate that checks it and the result of the check, which is pass or fail with the reason. The
  invariants are evaluated after the projection of every mutation.
- **Diff**: the ordered list of changes between the projected state before a mutation and the
  projected state after it, with the record identity, the field name, the value before, the value
  after and the kind of value, monetary or not. The diff also carries the verdict of the case and
  the canonical hashes of both sides.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero cross visitor reads in the adversarial test suite. A single successful read of a
  branch, of the branch event log or of the case memory of another session fails the release.
- **SC-002**: A reset returns the canonical hash of the published base in 100 percent of the runs of
  the reset test, and the hash equals the value recorded at fork time in every run.
- **SC-003**: The canonical hash of a branch rebuilt from its events alone equals the hash reported
  after the commit in 100 percent of the runs of the rebuild test, for the scenarios S01, S02 and
  S03.
- **SC-004**: The hash of `data/ledger.db` and of `data/scenarios.json` is unchanged after the whole
  mutation test suite runs.
- **SC-005**: Of two concurrent mutations sent with the same expected revision, exactly one succeeds
  and the other receives `409`, in 100 percent of the runs of the conflict test.
- **SC-006**: A repeated submission with the same idempotency key and the same payload returns the
  identical revision, the identical canonical hash and the identical diff in 100 percent of the runs
  of the idempotency test, and the branch event count grows by exactly one.
- **SC-007**: A rejected mutation, whatever the reason, leaves the canonical hash unchanged in 100
  percent of the runs of the rejection test, which covers an unknown kind, a broken invariant, a
  wrong precision, a read only field and a stale revision.
- **SC-008**: The preview endpoint performs zero writes. The branch revision, the canonical hash and
  the event count before and after a preview are equal in 100 percent of the runs of the preview
  test.
- **SC-009**: The diff of a given branch revision is byte identical across two consecutive reads,
  and the diff names every record whose values changed, with no missing entry in 100 percent of the
  runs of the diff test.
- **SC-010**: Every sandbox response carries the schema version and the branch identity, and every
  event appended by a mutation carries the origin label `sandbox`, in 100 percent of the runs of the
  labelling test.
- **SC-011**: An expired branch is refused with `410` and its stored rows and events are gone within
  60 seconds of the expiry, in 100 percent of the runs of the expiry test.
- **SC-012**: The preview of a mutation on scenario S01 answers in under 300 milliseconds at the
  95th percentile, and the commit of the same mutation answers in under 800 milliseconds at the 95th
  percentile, on the reference machine of the continuous integration run.
- **SC-013**: The whole sandbox suite runs offline with `LEDGERLENS_OFFLINE=1` and without any
  provider key, and the sandbox tests make zero network calls.
- **SC-014**: A recorded answer that predates a mutation is marked stale against the original
  snapshot hash in 100 percent of the runs of the staleness test, and no stale answer is presented
  as the current result.
- **SC-015**: The branch store interface has two implementations, the Postgres one and the file
  backed one, and both pass the same contract test suite with identical results.

## Assumptions

- The published scenario snapshots and the base ledger already exist in the repository, and this
  feature only reads them. Nothing in this feature writes to a published artifact.
- The visitor is anonymous. The owner of a branch is the opaque server side session that the
  facade already issues, and there is no account creation in this feature.
- The event store of the simulator, the projector and the canonical hash already exist and are
  reused. This feature adds the branch layer on top of them and does not rewrite them.
- The run context of the execution already carries the optional fields for the branch id, the
  branch revision and the snapshot hash, and this feature fills them when an execution runs inside
  a branch.
- The default time to live of a branch is 60 minutes of idleness with an absolute limit of 4 hours,
  following the retention defaults of the threat model, and both values are configurable.
- The accepted mutation catalog starts with the kinds listed in the published command schema, and a
  kind is added only when it has a round trip test and a coherent domain event.
- The branch data is held in Postgres for the deployment, and the same store is reachable through a
  local container for development and for the continuous integration run.
- The frontend is the Next.js application described in the architecture document. It submits typed
  commands and renders the responses. It never calculates money and never writes domain logic.
- No provider key is needed for any sandbox behaviour. The visitor sees a deterministic
  recalculation, never a generated natural language conclusion.
- The visitor sees a visible simulated label on every value that a mutation changed, and the
  interface states that the values are not financial advice and not a payment action.
