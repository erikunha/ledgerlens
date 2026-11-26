---
description: "Task list for the durable operations and the forensic traces"
---

# Tasks: The durable operations and the forensic traces

**Input**: Design documents from `specs/017-r16-durable-operations-and-forensic-traces/`

**Prerequisites**: plan.md (required), spec.md (required), the design package
(`docs/design/advanced-specs/R16-02-idempotent-durable-operations-and-forensic-traces.md`) and the decisions that
already bind: `docs/decisions/ADR-021-typed-mutation-and-atomic-commit.md`,
`docs/decisions/ADR-025-a-failed-write-loses-nothing.md`,
`docs/decisions/ADR-032-the-state-of-the-branch-and-the-hash.md` and
`docs/decisions/ADR-013-public-trace-as-a-versioned-contract.md`

**Tests**: Every task that changes the behaviour of the repository ships its test before its code, and the gate
of the Python side is green before the commit. The whole suite runs offline with `LEDGERLENS_OFFLINE=1` and no
key, the provider is the fake of the repository and the clock is injected, so that a deadline is proved by
moving the clock. A task that is delivered says so, with **DELIVERED** and the evidence of what it
delivered.

**Organization**: Tasks are grouped by the four parts of the plan, and the tasks of a group touch disjoint
files so that they can be worked on in parallel. The ids of this milestone start above the ids of `specs/001-`
through `specs/006-` and they are continuous inside this milestone. The folder `tests/durability/` is created by
T261, and the tests of the sandbox stay where they are, in `tests/sandbox/`.

## Format: `[ID] [P?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[DELIVERED]**: the task is done, and the sentence names what it delivered
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `ledgerlens/`, `tests/`, `scripts/`, `data/`, `docs/` at repository root
- Paths shown below assume single project

## Part A, the durable side of the sandbox, which is not rebuilt

**Purpose**: the branch of a visitor is already durable, and this milestone does not touch it.

- [x] T260 [P] Write the test in `tests/durability/test_sandbox_durability_is_kept.py` that commits the same
  command of `ledgerlens/sandbox/mutation.py` twice with the same idempotency key and expects one event in the
  log of the branch and an unchanged projection of `ledgerlens/sandbox/projector.py`, so that a change of the
  sandbox in a later task of this milestone fails here
  - **DELIVERED**: the test is in `tests/durability/test_sandbox_durability_is_kept.py`: a commit of `ledgerlens/sandbox/mutation.py` sent twice with the same idempotency key leaves one event of the branch and an unchanged projection of `ledgerlens/sandbox/projector.py`, so a change of the sandbox in a later task fails here.
- [x] T261 [P] Write the test in `tests/durability/test_projection_is_pure.py` that expects the same hash of
  the projection for the same base and the same log, whatever the order of the events was, beside the check
  of `tests/sandbox/test_branch_projection.py`
  - **DELIVERED**: the test is in `tests/durability/test_projection_is_pure.py`: the same base and the same log give the same hash of the projection, a rebuild of the projector gives the same hash, and two branches with the same events in the same order project to the same hash.
- [x] T262 [P] Write the test in `tests/durability/test_replay_writes_nothing.py` that replays a published bundle
  of `ledgerlens/replay/bundle.py` and expects the digest of the ledger of the base to be the same before and
  after the replay

## Part B, the journal of a run

**Purpose**: a run that writes nothing durable cannot be restarted.

  - **DELIVERED**: the test is in `tests/durability/test_replay_writes_nothing.py`: a replay of a published bundle of `ledgerlens/replay/bundle.py` writes nothing, and the digest of the ledger of the base is the same before and after the replay.
- [x] T263 [P] Create the package `ledgerlens/durability/` with the module `__init__.py` and the module
  `ledgerlens/durability/journal.py`, whose docstring says what the journal of a run is and why the intent of
  a step is written before the step runs, and write the test in `tests/durability/test_run_journal.py` that
  expects an intent and a result for every step of a run and that the numbers of the journal grow monotonically
  - **DELIVERED**: the package is in `ledgerlens/durability/` with the module `journal.py`: the intent of a step is written before the step runs and the result after it ran, and the numbers of the journal grow monotonically. The test is in `tests/durability/test_run_journal.py`.
- [x] T264 [P] Extend the module `ledgerlens/durability/journal.py` with the typed intent and the typed result
  of a step, with the docstring of each class saying what it carries and why, and write the test in
  `tests/durability/test_journal_records.py` that expects the hash of the inputs, the snapshot, the attempt,
  the idempotency key, the reference of the output and the spend of a step
  - **DELIVERED**: the typed intent and the typed result of a step are in `ledgerlens/durability/journal.py`. The test is in `tests/durability/test_journal_records.py`: the hash of the inputs, the snapshot, the attempt, the idempotency key, the reference of the output and the spend of a step.
- [x] T265 [P] Write the module `ledgerlens/durability/store.py` with the docstring saying that the journal of a
  run lives in the folder of the session that owns the run, beside the folder of the branch, and that the
  numbers of the journal grow by one under a lock, and write the test in
  `tests/durability/test_journal_store.py` that expects the numbers of two writers to grow without a gap
  - **DELIVERED**: the module is in `ledgerlens/durability/store.py`: the journal of a run lives in the folder of the session that owns the run, and the numbers of the journal grow by one under a lock. The test is in `tests/durability/test_journal_store.py`: the numbers of two writers grow without a gap.
- [x] T266 [P] Write the test in `tests/durability/test_journal_failure.py` that makes the write of the
  journal fail and expects the run to stop with the reason, because a run that continues without a journal is a
  run that cannot be restarted

## Part C, the restart and the unknown status

**Purpose**: a run that died comes back, and a run that does not know says so.

  - **DELIVERED**: the test is in `tests/durability/test_journal_failure.py`: a run whose write of the journal fails stops with the reason, because a run that continues without a journal is a run that cannot be restarted.
- [x] T267 [P] Write the module `ledgerlens/durability/restart.py` with the docstring saying that a restart
  reuses the output of a step that completed, runs again only a step that is idempotent and read only and
  refuses a step whose snapshot changed, and write the test in `tests/durability/test_restart_recovery.py` that
  kills a run between the commit of the branch and the journal, restarts it, and expects one event of the
  branch, an unchanged projection and the same answer of the case
  - **DELIVERED**: the module is in `ledgerlens/durability/restart.py`. The test is in `tests/durability/test_restart_recovery.py`: a run killed between the commit of the branch and the journal restarts, the commit does not happen twice, the projection is unchanged and the answer of the case is the same.
- [x] T268 [P] Write the module `ledgerlens/durability/unknown.py` with the docstring saying that a provider
  call whose answer never arrived carries an unknown status, that its cost is unknown and never zero, and that
  the run neither repeats the call nor claims a success it cannot prove, and write the test in
  `tests/durability/test_unknown_status.py` that expects the unknown status, the absence of a dollar amount
  and the absence of a second call of the provider
  - **DELIVERED**: the module is in `ledgerlens/durability/unknown.py`: a provider call whose answer never arrived carries the unknown status, its cost is unknown and never zero, and the run neither repeats the call nor claims a success. The test is in `tests/durability/test_unknown_status.py`.
- [x] T269 [P] Write the module `ledgerlens/durability/cancellation.py` with the docstring saying that a
  cancelled run starts no tool after the barrier of the cancellation, closes its spans and marks the claims
  that were not verified as incomplete, and write the test in
  `tests/durability/test_cancellation_barrier.py` that expects no tool to start after the cancellation and the
  incomplete claims to be marked
  - **DELIVERED**: the module is in `ledgerlens/durability/cancellation.py`: a cancelled run starts no tool after the barrier, closes its spans and marks the claims that were not verified as incomplete. The test is in `tests/durability/test_cancellation_barrier.py`.
- [x] T270 [P] Write the test in `tests/durability/test_rate_limit_retry.py` that makes the fake provider answer
  with a rate limit and expects the retry to stop at the deadline or at the budget of
  `ledgerlens/byok/budget.py`, and that expects the count of the attempts to be bounded

## Part D, the forensic export, the fault injection and the runbook

**Purpose**: a stranger can read the shape of a run, and the recovery is exercised.

  - **DELIVERED**: the module is in `ledgerlens/durability/retry.py`. The test is in `tests/durability/test_rate_limit_retry.py`: the retry of a call that the fake provider rate limits stops at the deadline or at the budget of `ledgerlens/byok/budget.py`, and the count of the attempts is bounded.
- [x] T271 [P] Write the module `ledgerlens/durability/export.py` with the docstring saying that the export
  carries the spans of the run, the parent of every span, the order of the events and the spend of every step,
  that it redacts what looks like a key and that it does not export the raw content of a prompt by default,
  and write the test in `tests/durability/test_forensic_export.py` that expects the parent of every span, the
  redaction of the value that looks like a key, the absence of the raw prompt and the sentence that says what
  was redacted
  - **DELIVERED**: the module is in `ledgerlens/durability/export.py`: the export carries the spans, the parent of every span, the order of the events and the spend of every step, it redacts what looks like a key and it does not export the raw content of a prompt by default. The test is in `tests/durability/test_forensic_export.py`.
- [x] T272 [P] Write the test in `tests/durability/test_exporter_failure.py` that makes the exporter fail and
  expects the run to finish with an answer and the error of the exporter to be recorded locally
  - **DELIVERED**: the test is in `tests/durability/test_exporter_failure.py`: the exporter that fails is recorded locally and the run finishes with an answer.
- [x] T273 [P] Write the fixture of the fault injection in `tests/durability/fixtures/kill_points.json` with
  the named points at which the continuous integration kills a run, and write the test in
  `tests/durability/test_fault_injection.py` that expects the same answer of the case over every named point and
  no duplicated event of the branch
  - **DELIVERED**: the fixture is in `tests/durability/fixtures/kill_points.json` with the named points at which the continuous integration kills a run. The test is in `tests/durability/test_fault_injection.py`: the same answer of the case over every named point and no duplicated event of the branch.
- [x] T274 [P] Add the fixture of the fault injection to the workflow of `.github/workflows/gate.yml`, so that
  the recovery of a run is exercised on every run of the continuous integration
  - **DELIVERED**: the workflow of `.github/workflows/gate.yml` has the step of the fault injection, so the recovery of a run is exercised on every run of the continuous integration.
- [x] T275 [P] Write the runbook `docs/runbook/durability.md` with the steps of a restart, the states that a
  run may be in, the unknown status and what a person has to do with it, and the way to roll the journal of a
  run back without touching the branch of a visitor
  - **DELIVERED**: the runbook is in `docs/runbook/durability.md`: the steps of a restart, the states of a run, the unknown status and what a person has to do with it, and the way to roll the journal of a run back without touching the branch of a visitor.
- [x] T276 [P] Write the record of the milestone in `docs/decisions/` with the next number after ADR-077, which
  writes down that the durable side of the sandbox was not rebuilt, that the journal of a run reuses the rule of
  idempotence of the branch, that a step that is not idempotent is not run again after a restart, that the
  trace keeps the shape of its own span and that the store of a deployment is a later decision, and link it
  from `docs/decisions/README.md`

  - **DELIVERED**: the record is `docs/decisions/ADR-092-the-journal-of-a-run-reuses-the-idempotence-of-the-branch-and-a-step-that-is-not-idempotent-is-not-run-again.md`: the durable side of the sandbox was not rebuilt, the journal reuses the rule of idempotence of the branch, a step that is not idempotent is not run again, the trace keeps the shape of its own span and the store of a deployment is a later decision. The index of the decisions was regenerated with `uv run python scripts/build_docs_index.py`.