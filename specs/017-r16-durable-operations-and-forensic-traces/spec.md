# Feature Specification: The durable operations and the forensic traces

**Feature Branch**: `feature/v3`

**Created**: 2026-11-23

**Status**: Draft

**Input**: Design documents: `docs/v3/advanced-specs/R16-02-idempotent-durable-operations-and-forensic-traces.md`,
`docs/v3/ai/01-MULTIAGENT-ORCHESTRATION.md`, and the decisions already in force:
`docs/decisions/ADR-021-typed-mutation-and-atomic-commit.md`,
`docs/decisions/ADR-025-a-failed-write-loses-nothing.md`,
`docs/decisions/ADR-026-the-store-serialises-the-writes-of-a-branch.md`,
`docs/decisions/ADR-029-the-expiry-and-the-cleanup-job.md`,
`docs/decisions/ADR-032-the-state-of-the-branch-and-the-hash.md`,
`docs/decisions/ADR-013-public-trace-as-a-versioned-contract.md`,
`docs/decisions/ADR-073-the-published-bundle-carries-the-evidence-its-verdict-was-computed-on-and-it-is-reproducible.md`.
User description: "The package proposes a run that restarts without losing evidence and without doing the same
work twice, and a trace that can be read as a forensic record. The repository already has the durable side of
the sandbox: the idempotent command, the atomic commit and the projection that is a pure function of the base
and the log. It has no journal for a run of the agent and no restart of one. This specification ports the
journal, the restart and the forensic export, and says plainly that the durable side of the sandbox is not
rebuilt."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Read that the durable side of the sandbox already exists (Priority: P1)

A reader asks what is durable today. The answer is the branch of a visitor: the command of the sandbox carries
an idempotency key and the digest of its payload, the store is idempotent on the identifier of the event, the
commit is atomic and a write that fails leaves the branch exactly where it was, and the state of the branch is
a pure function of the base and of the log. The reader is told that this milestone does not rebuild any of
that and that the new work is the run of the agent, which today is not durable at all.

**Why this priority**: the package proposes idempotent durable operations as if they were new, and they are not
new for the sandbox. A port that rebuilt them would be a port that broke working code.

**Independent test**: commit the same command of `ledgerlens/sandbox/mutation.py` twice with the same
idempotency key and expect one event in the log of the branch and an unchanged projection.

### User Story 2 - Read the journal of a run (Priority: P1)

A run of the agent writes a journal. Before a step runs, the journal carries the intent of the step: its
identifier, its attempt, the hash of its inputs and the snapshot it read. After it ran, the journal carries the
result: the reference of the output, the status and what it spent. The numbers of the journal grow by one and
never go back, so the order of the steps of a run is readable after the fact.

**Why this priority**: the journal is the whole of the durability of a run, and a journal whose order is not
readable is a log without a history.

**Independent test**: run a case and read the journal of the run, and expect an intent and a result for every
step, with the numbers growing monotonically.

### User Story 3 - Restart a run that died and change nothing (Priority: P1)

A run dies in the middle of a step. It restarts and finds the steps that completed in the journal. Those
steps are not run again, the outputs of the steps that completed are reused, and the updates of the projection
of the branch are not duplicated: the branch of the visitor is exactly where the crash left it. A step that
was interrupted before it committed is run again with the same idempotency key, so the commit of the branch
is the one that happens and not two.

**Why this priority**: a restart that duplicates an effect corrupts the branch of a visitor, and the durable
side of the sandbox exists precisely so that this cannot happen. The run of the agent has to reach the same
guarantee.

**Independent test**: kill a run after the commit of the branch and before the journal wrote the result,
restart it, and expect one event of the branch, an unchanged projection and the same answer of the case.

### User Story 4 - Say that the status of a provider call is uncertain (Priority: P1)

A provider call is sent and the process dies before the answer arrives. The run does not know whether the
provider did the work. It says so: the status of that call is unknown, the cost of that call is unknown and is
not counted as zero, and the run does not silently charge the visitor twice and does not report a success it
cannot prove.

**Why this priority**: the package names it, and it is the one case where a system must admit that it does not
know. A run that guesses is worse than a run that stops.

**Independent test**: kill a run during a call of the provider and expect the result to carry an unknown
status for that call, with no dollar amount for it and no second call of the provider.

### User Story 5 - Read the forensic export and find no secret in it (Priority: P1)

A run is exported for a reader who wants to know what happened. The export carries the spans of the run, the
parent of every span, the order of the events and what each step spent. The export is redacted: a value that
looks like a key is replaced, the raw content of a prompt is not exported by default, and the export says
what it redacted and how many values it redacted.

**Why this priority**: the trace of the repository already redacts and already says what it cut, and the
export is read by strangers.

**Independent test**: export a run whose prompt carries a value that looks like a key and expect that value to
be replaced, the raw prompt to be absent, and the export to say what it redacted.

### User Story 6 - Reconstruct the order of a run and the parent of every step (Priority: P2)

A reader wants to know the shape of a run: which step asked for which, how long the critical path was and
where the run spent its time. The forensic trace answers it: the span of every step carries the parent of the
step that called it, and the times of the spans are in one clock.

**Why this priority**: the repository already emits a tree of spans and a public event with a sequence that
grows, and the forensic export is that tree with its provenance.

**Independent test**: export a run and expect every span to carry a parent that exists in the export, except
the root, and expect the sequence of the events to grow.

### User Story 7 - Stop the tools of a cancelled run (Priority: P2)

A visitor stops a run. No tool starts after the barrier of the cancellation, the spans close, and the claims
that were not verified are marked as incomplete rather than left as if they were answered.

**Why this priority**: the package names it, and the live path already raises the cancellation of the run
before the next call.

**Independent test**: cancel a run during a tool and expect no tool to start after the cancellation and the
incomplete claims to be marked.

### User Story 8 - Kill the run at a named point and see it recover (Priority: P2)

The continuous integration kills a run at named points of its life and restarts it. Each kill leaves the
branch of the visitor exactly where it was, the run recovers from the journal, and the answer of the case is
the same as the answer of a run that was never killed.

**Why this priority**: a recovery that is never exercised is a recovery that does not exist, and the package
asks for the fault injection in the continuous integration.

**Independent test**: run the fixture of the fault injection over the named points and expect the same answer
every time and no duplicated event.

### User Story 9 - Read that a replay of an event does not move the ledger (Priority: P2)

A reader replays the events of a published run. The replay reads the ledger of the base and the events of the
branch, and it never writes a row of the ledger of the base. The sandbox of a visitor is the only place where
a row is written, and a replay of a published recording writes nothing at all.

**Why this priority**: the package says it, and the repository writes to the ledger only through the sandbox
of a branch.

**Independent test**: replay a published bundle and expect the digest of the ledger of the base to be the same
before and after.

### Edge Cases

- A journal whose write fails: the run stops with the reason, because a run that continues without a journal
  is a run that cannot be restarted.
- A run that ends without a step: the journal carries the end of the run, so an abandoned run is visible.
- A trace exporter that fails: the run finishes anyway and the error is recorded locally, because the export
  is a convenience and the answer of the visitor is not.
- A provider that answers with a rate limit: the retry respects the deadline of the run and the budget of the
  run, and it is not an unlimited retry.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001** (the repository today): The durable side of the sandbox is not rebuilt: the command carries an
  idempotency key and the digest of its payload, the store is idempotent on the identifier of the event, the
  commit is atomic, a write that fails leaves the branch where it was, and the state of the branch is a pure
  function of the base and of the log.
  - Test: `tests/sandbox/test_mutation_duplicate.py` and `tests/sandbox/test_branch_projection.py` keep
    passing unchanged, and `tests/durability/test_sandbox_durability_is_kept.py` expects the idempotence of
    the commit and the purity of the projection.
- **FR-002** (the package): The journal of a run writes the intent of a step before it runs and its result
  after it ran, and the numbers of the journal grow by one and never go back.
  - Test: `tests/durability/test_run_journal.py` expects an intent and a result for every step of a run and
    that the numbers of the journal grow monotonically.
- **FR-003** (the package and ADR-021): A restart of a run reuses the output of a step that completed, does not
  duplicate the update of the projection of the branch, and runs again an interrupted step with the same
  idempotency key.
  - Test: `tests/durability/test_restart_recovery.py` expects one event of the branch after a kill between the
    commit and the journal, and an unchanged projection.
- **FR-004** (the package): A provider call whose answer never arrived is marked with an unknown status, its
  cost is unknown and is never zero, and the run does not repeat the call and does not report a success it
  cannot prove.
  - Test: `tests/durability/test_unknown_status.py` expects the unknown status, the absence of a dollar amount
    and the absence of a second call of the provider.
- **FR-005** (the package and ADR-013): The forensic export carries the spans of the run, the parent of every
  span, the order of the events and the spend of every step, and it is redacted: a value that looks like a key
  is replaced, the raw content of a prompt is not exported by default, and the export says what it redacted.
  - Test: `tests/durability/test_forensic_export.py` expects the parent of every span, the redaction of the
    value that looks like a key, the absence of the raw prompt and the sentence that says what was redacted.
- **FR-006** (the package): A cancelled run starts no tool after the barrier of the cancellation, closes its
  spans and marks the claims that were not verified as incomplete.
  - Test: `tests/durability/test_cancellation_barrier.py` expects no tool to start after the cancellation and
    the incomplete claims to be marked.
- **FR-007** (the package): The continuous integration kills a run at named points and restarts it, and every
  kill leaves the branch where it was and the answer of the case the same.
  - Test: `tests/durability/test_fault_injection.py` expects the same answer over the named points and no
    duplicated event, and the fixture is read by the workflow of `.github/workflows/gate.yml`.
- **FR-008** (the package): Replaying the events of a run reads the ledger and writes nothing, and the digest
  of the ledger of the base is the same before and after the replay.
  - Test: `tests/durability/test_replay_writes_nothing.py` expects the digest of the ledger of the base to be
    unchanged after a replay of a published bundle.
- **FR-009** (the package): A retry of a provider that answered with a rate limit respects the deadline of the
  run and the budget of the run, and it is never an unlimited retry.
  - Test: `tests/durability/test_rate_limit_retry.py` expects the retry to stop at the deadline and at the
    budget, and expects the count of the attempts to be bounded.
- **FR-010** (the package): A trace exporter that fails does not take the run down: the run finishes and the
  error of the export is recorded locally.
  - Test: `tests/durability/test_exporter_failure.py` expects the run to finish with an answer and the error
    of the exporter to be recorded.
- **FR-011** (the package and ADR-032): The state of a branch is a pure function of the base and of the log,
  and the hash of the projection is the hash of the projector of the simulator, so the two hashes are
  comparable.
  - Test: `tests/durability/test_projection_is_pure.py` expects the same hash for the same base and the same
    log, whatever the order of the events was.

### Key Entities

- **Journal of a run**: the durable record of the steps of a run, their intents, their results and their
  numbers, with a number that grows by one.
- **Intent**: what a step is about to do, written before it runs, with the hash of its inputs and the snapshot
  it reads.
- **Attempt**: the number of times a step was tried, with the idempotency key that belongs to it.
- **Unknown status**: the state of a provider call whose answer never arrived, where the cost is unknown and
  the success is not claimed.
- **Forensic export**: the redacted record of a run: the spans, the parents, the order, the spend and the
  sentence that says what was redacted.
- **Cancellation barrier**: the point after which no tool of the run may start.
- **Fault injection fixture**: the named points at which the continuous integration kills a run.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The durable side of the sandbox is unchanged and its tests keep passing, and a repeated command
  with the same idempotency key leaves one event and one projection.
- **SC-002**: Every step of a run has an intent and a result in the journal, and the numbers of the journal
  grow by one.
- **SC-003**: A restart of a run leaves the branch of the visitor exactly where the crash left it, and the
  answer of the case is the same.
- **SC-004**: A provider call whose answer never arrived is marked unknown, shows no dollar amount and is not
  repeated.
- **SC-005**: The forensic export holds no value that looks like a key, no raw prompt by default, and says what
  it redacted.
- **SC-006**: Every span of the export carries a parent that exists in the export, except the root.
- **SC-007**: A cancelled run starts no tool after the barrier and marks its incomplete claims.
- **SC-008**: The fault injection fixture runs in the continuous integration and every kill recovers.
- **SC-009**: A replay of a published bundle writes nothing and the digest of the ledger of the base is the
  same before and after.
- **SC-010**: The retry of a provider that answered with a rate limit stops at the deadline or at the budget,
  and the number of the attempts is bounded.
- **SC-011**: A trace exporter that fails does not take the run down.

## Design documents

- [R16-02 Idempotent durable operations and forensic traces](../../docs/v3/advanced-specs/R16-02-idempotent-durable-operations-and-forensic-traces.md)
- [Multi-Agent Orchestration and Durable Runtime](../../docs/v3/ai/01-MULTIAGENT-ORCHESTRATION.md)
- [ADR-021: A mutation is a typed command and the commit is atomic](../../docs/decisions/ADR-021-typed-mutation-and-atomic-commit.md)
- [ADR-025: A write that fails leaves the branch exactly where it was](../../docs/decisions/ADR-025-a-failed-write-loses-nothing.md)
- [ADR-026: The store serialises the writes of a branch](../../docs/decisions/ADR-026-the-store-serialises-the-writes-of-a-branch.md)
- [ADR-029: The expiry has one home, and the cleanup is a job of the process](../../docs/decisions/ADR-029-the-expiry-and-the-cleanup-job.md)
- [ADR-032: The state of the branch and the hash](../../docs/decisions/ADR-032-the-state-of-the-branch-and-the-hash.md)
- [ADR-013: The public trace is a versioned contract](../../docs/decisions/ADR-013-public-trace-as-a-versioned-contract.md)
- [ADR-073: The published bundle carries the evidence its verdict was computed on](../../docs/decisions/ADR-073-the-published-bundle-carries-the-evidence-its-verdict-was-computed-on-and-it-is-reproducible.md)

## Status

**What exists in the repository today.** The branch of a visitor is durable: the command of the sandbox carries
an idempotency key and the digest of its payload (`ledgerlens/sandbox/mutation.py`), the store appends the
events idempotently on the identifier of the event (`ledgerlens/sandbox/store.py`), the commit is atomic
(ADR-021), a write that fails loses nothing (ADR-025), the writes of a branch are serialised (ADR-026), the
state of the branch is a pure function of the base and of the log and its hash is the hash of the projector of
the simulator (ADR-032), and the expiry of a session takes its folder with it (ADR-029). The trace is a tree
of spans and a public event whose sequence grows under a lock
(`ledgerlens/observability/trace_event.py`), and it redacts what looks like a key and says what it cut
(`ledgerlens/observability/trace.py`). The published bundle carries a manifest, a hash, the commit of the
code and the evidence of the verdict (ADR-014, ADR-017, ADR-073, ADR-077).

**What the package proposes.** A worker step that carries the run, the step, the attempt, the idempotency key,
the hash of the snapshot, the version of the state, the reference of the output and the provenance of the cost,
with monotonic event offsets, a write of the intent before the execution and of the result after it, a
restart that reuses the complete outputs and retries only the safe reads, an unknown status for a provider
request whose cost cannot be confirmed, spans that follow the conventions of OpenTelemetry where they apply and
are redacted on export, a chaos fixture with repeated terminations, and a rollback runbook.

**What this specification changes.** The durable side of the sandbox is not rebuilt and not renamed: it exists,
it is proven by its own tests, and this milestone adds to it rather than replacing it. The journal of the run
is the new part, and it writes to the same kind of store as the branch, so that the two share one rule about
idempotence. The conventions of OpenTelemetry are used where they apply and the repository keeps its own shape
of the span, because the trace of the repository is a published contract (ADR-013) and a contract that is
replaced by a standard is a contract that breaks.

**What is still to be built.** The journal of the run, the restart of a run, the unknown status, the forensic
export, the cancellation barrier of a run, the fault injection fixture and the rollback runbook. None of them
exists.

## Assumptions

- The store of the journal is the file backed store of the repository for a first version, beside the folder of
  the session. The durable store of a deployment is a decision of another milestone.
- The clock of the journal is the same injected clock of the budget, so that a test proves a deadline by
  moving a clock and not by waiting.
- The answer of the case after a restart is the same as the answer of a run that was never killed, because the
  verifier is deterministic and the journal reuses the outputs that completed.
- No number of this specification says that a restart is faster or cheaper than a run that never died. The
  measure is the count of the duplicated effects, which must be zero, and the rate of the lost events.

## Out of scope

- The temporal database as the backend of the durability. The package itself allows the checkpointer of
  LangGraph for a first version, and the decision of a durable store is a later milestone.
- The conformance of the trace to the conventions of OpenTelemetry as a whole. The repository keeps the shape
  of its own span, which is a published contract.
- The change of the sandbox, of its store and of its projector.
- The multi-agent runtime. The journal of the run serves the single agent of today, and the studio of
  `specs/013-r11-multiagent-orchestration-studio/` reads the same journal when it exists.
- The frontend of `apps/web/`. The interface of the durability is the published bundle and the trace.
