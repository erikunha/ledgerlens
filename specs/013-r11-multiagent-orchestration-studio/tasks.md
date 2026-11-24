---
description: "Task list for the multi-agent orchestration studio"
---

# Tasks: The multi-agent orchestration studio

**Input**: Design documents from `specs/013-r11-multiagent-orchestration-studio/`

**Prerequisites**: plan.md (required), spec.md (required), the decision that draws the red line
(`docs/v3/adrs/ADR-P007-no-multiagent-by-default.md`), the design package
(`docs/v3/advanced-specs/R11-02-budgeted-specialist-dispatch.md` and
`docs/v3/advanced-specs/R11-05-graph-checkpoint-and-resume.md`), the decision that fixes the one model of a
run (`docs/decisions/ADR-037-the-case-of-the-demo-runs-on-a-bridge-over-the-caller.md`) and the decision that
fixes the budget (`docs/decisions/ADR-034-the-registry-the-budget-and-the-endpoint.md`)

**Tests**: Every task that changes the behaviour of the repository ships its test before its code, and the gate
of the Python side is green before the commit. The whole suite runs offline with `LEDGERLENS_OFFLINE=1` and no
key, and the provider is a fake in the tests. A task that is delivered says so, with **DELIVERED** and the
evidence of what it delivered.

**Organization**: Tasks are grouped by the four parts of the plan, and the tasks of a group touch disjoint files
so that they can be worked on in parallel. The ids of this milestone start above the ids of `specs/001-` through
`specs/006-` and they are continuous inside this milestone. The folder `tests/orchestration/` is created by
T183, and the tests of the sandbox that the studio touches stay in `tests/sandbox/`.

## Format: `[ID] [P?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[DELIVERED]**: the task is done, and the sentence names what it delivered
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `ledgerlens/`, `tests/`, `scripts/`, `data/`, `docs/` at repository root
- Paths shown below assume single project

## Part A, the baseline that is frozen before anything is measured

**Purpose**: the reference arm of the comparison is the shipped code, and a reference that moves is not a
reference.

- [x] T180 [P] Record the behavior of the shipped path in `docs/orchestration/baseline.md`: the agent of
  `ledgerlens/agents/integrator.py`, its six tools, the verifier of `ledgerlens/verify/`, the snapshot of the
  branch it reads and the commit of the code, so that the studio is measured against a named reference and not
  against a memory of one - **DELIVERED**: the page `docs/orchestration/baseline.md` names the commit
  `77a9a2c9ba9665619290dc3875e81169f3256cac`, the agent of `ledgerlens/agents/integrator.py` with the six tools
  `query_ledger`, `get_ledger_record`, `search_policies`, `get_reference_fx`, `calculate` and `recall_cases`, the
  verifier of `ledgerlens/verify/` with its thresholds, and the snapshot of the comparison with the digest of the set
  of 31 cases and the digest of the canonical ledger.
- [x] T181 [P] Write the test in `tests/orchestration/test_baseline_is_frozen.py` that reads
  `docs/orchestration/baseline.md` and expects the commit of the baseline, the tools of the shipped agent and
  the name of the snapshot of the comparison, and that fails while the file does not exist - **DELIVERED**: the
  test is in `tests/orchestration/test_baseline_is_frozen.py`: it fails with a sentence while the page does not
  exist, it expects a commit that the repository holds and that is an ancestor of the head, it expects the six
  tools of the contract and it checks that the source of the repository still declares them, and it expects the
  digests of the set and of the ledger to be the digests of the files of the disk.
- [x] T182 [P] Write the manifest of the comparison in `data/runtime/orchestration/comparison.json` with the
  set of the comparison, the denominator, the two arms, the measures and the rule that decides the result, and
  register it in `data/eval/datasets.json` with the role the manifest of the datasets gives it, so that the set
  of the comparison is never read by anything but the final scoring - **DELIVERED**: the manifest is in
  `data/runtime/orchestration/comparison.json`, with one record per line so that the manifest of the datasets can
  count its records and pin its digest. It names the set of the 31 cases with its digest, the denominator, the
  snapshot of the ledger, the two arms, the four measures with their direction, the rule that decides the result
  and the uncertainty of the measurement. It is registered in `data/eval/datasets.json` with the role `held_out`,
  the path is reserved in the code of the guard of the tuning, and the sentence of the contamination policy that
  counts the datasets with that role was corrected in the seven entries and republished in the two reports of the
  held out set.

## Part B, the dispatcher, behind a flag

**Purpose**: the dispatcher validates, schedules and spends. It never widens the scope and it never decides an
amount.

- [x] T183 [P] Create the package `ledgerlens/orchestration/` with the module `__init__.py` and the module
  `ledgerlens/orchestration/plan.py`, whose docstring says what a plan is and why the plan of a case is
  validated before any step runs, and write the test in `tests/orchestration/test_plan_validation.py` that
  expects a plan with a cycle to be refused at the planning and expects that no step ran
  - **DELIVERED**: the package `ledgerlens/orchestration/` with the module `plan.py`, whose docstring says what a plan
    is and why the plan of a case is validated before any step runs. The test is in
    `tests/orchestration/test_plan_validation.py`: a plan with a cycle is refused at the planning, a step
    that waits for itself is refused, a step that waits for a step that does not exist is refused, two
    steps with the same id are refused, and the order of the steps is the order of the dependencies and
    not the order they were written down.
- [x] T184 [P] Add the typed plan and the typed result of a step to `ledgerlens/schemas.py`, with the docstring
  of each class saying what it carries and why, and write the test in `tests/orchestration/test_step_result.py`
  that expects the status, the evidence references, the spend and the error of a step to be present and to be
  typed
  - **DELIVERED**: the typed plan and the typed result of a step are in `ledgerlens/schemas.py`, with the docstring of
    each class saying what it carries and why. The test is in `tests/orchestration/test_step_result.py`:
    the status, the evidence references, the spend and the error are present and typed, the money of a
    step is a `Decimal` and a float is refused, an unknown spend is None and never a zero, and the plan
    forbids the fields that nobody wrote.
- [x] T185 [P] Write the module `ledgerlens/orchestration/specialists.py` with the versioned spec of a
  specialist, the docstring saying what a specialist may read, which tools it may call, what it may spend and
  what it must return, and the registry of the specialists, and write the test in
  `tests/orchestration/test_specialist_spec.py` that expects a specialist of the registry to refuse a tool
  that is not in its allowlist
  - **DELIVERED**: the module `ledgerlens/orchestration/specialists.py` holds the versioned spec of a specialist and the
    registry of the specialists. The docstring says what a specialist may read, which tools it may call,
    what it may spend and what it must return. The test is in
    `tests/orchestration/test_specialist_spec.py`: a specialist refuses a tool that is not in its
    allowlist, every spec of the registry carries a version and a return, the specialists call the six
    tools of the shipped path and no other, and a specialist that the registry does not hold is refused.
- [x] T186 Write the module `ledgerlens/orchestration/dispatcher.py` with the docstring saying that the
  dispatcher owns the policy and the registry of the tools and that the permissions of a specialist are the
  intersection of the permissions of its parent with the permissions of its own spec, and write the test in
  `tests/orchestration/test_dispatch_scope.py` that expects the refusal of a tool outside the allowlist and the
  refusal of an account outside the scope of the run, and that expects no tool call
  - **DELIVERED**: the module `ledgerlens/orchestration/dispatcher.py` owns the policy of the run and the registry of
    the tools, and the permissions of a specialist are the intersection of the permissions of its parent
    with the permissions of its own spec. The test is in `tests/orchestration/test_dispatch_scope.py`: a
    tool outside the allowlist is refused and no tool is called, an account outside the scope of the run
    is refused and nothing is read, and the permissions of a specialist never widen the scope of the run.
- [x] T187 Write the module `ledgerlens/orchestration/scheduler.py` with the docstring saying that the scheduler
  runs the independent steps of a plan under a concurrency cap and that every step spends from the budget of
  the run, and write the test in `tests/orchestration/test_dispatch_budget.py` that expects the run to stop at
  the cap of `ledgerlens/byok/budget.py`, with the name of the cap and the partial result, and that expects no
  call outside the budget
  - **DELIVERED**: the module `ledgerlens/orchestration/scheduler.py` runs the independent steps of a plan under a
    concurrency cap and every step spends from the budget of the run, through the coordinator that
    enforces the caps. The test is in `tests/orchestration/test_dispatch_budget.py`: the run stops at the
    cap of `ledgerlens/byok/budget.py` with the name of the cap and the partial result, no call happens
    outside the budget, a plan with a cycle never runs a step and the money the run spent is published
    with the result.
- [x] T188 [P] Write the module `ledgerlens/orchestration/join.py` with the docstring saying that two results are
  joined only on a matching snapshot and on evidence identifiers that resolve to a record of the run, and write
  the test in `tests/orchestration/test_join_and_conflict.py` that expects the refusal of an invented evidence
  identifier and expects the value of the deterministic calculator, or a named abstention, over two results that
  disagree over an amount
  - **DELIVERED**: the module `ledgerlens/orchestration/join.py` joins two results only on a matching snapshot and on
    evidence identifiers that resolve to a record of the run. The test is in
    `tests/orchestration/test_join_and_conflict.py`: an invented evidence identifier is refused, two
    results that disagree over an amount end with the value of the deterministic calculator or with a
    named abstention, and a result of another snapshot is refused.
- [x] T189 [P] Read the flag of the studio in `ledgerlens/config.py` as `LEDGERLENS_ORCHESTRATION_STUDIO`, off by
  default, and write the test in `tests/orchestration/test_studio_flag.py` that expects the flag off in the
  shipped configuration and that expects the refusal of a run that asks for the studio without a registered
  experiment in `data/runtime/orchestration/comparison.json`
  - **DELIVERED**: the flag of the studio is read in `ledgerlens/config.py` as `LEDGERLENS_ORCHESTRATION_STUDIO`, off by
    default, and the module `ledgerlens/orchestration/studio.py` opens the studio only for an experiment
    that is registered before it runs. The test is in `tests/orchestration/test_studio_flag.py`: the flag
    is off in the shipped configuration, a run that asks for the studio with the flag off is refused, and
    a run that asks for it without a registered experiment in
    `data/runtime/orchestration/comparison.json` is refused and the refusal names what is missing.
- [x] T190 [P] Write the test in `tests/orchestration/test_trace_of_dispatch.py` that reads the events of
  `ledgerlens/observability/trace_event.py` produced by a run of the studio and expects one event per step
  with the budget it had and the reason it stopped, and that expects the trace to name the specialist that
  answered each part of the question
  - **DELIVERED**: the test is in `tests/orchestration/test_trace_of_dispatch.py`: it reads the events of
    `ledgerlens/observability/trace_event.py` produced by a run of the studio, expects one event per step
    with the budget it had and the reason it stopped, and expects the trace to name the specialist that
    answered each part of the question. The trace uses the event types of the public contract and does
    not extend it.

## Part C, the journal and the resume

**Purpose**: a suspended run continues from durable state without repeating an effect and without losing its
provenance.

- [x] T191 [P] Write the module `ledgerlens/orchestration/journal.py` with the docstring saying that the journal
  of a run records the steps, their attempts, their inputs and their outputs so that a run resumes from what
  it already did, and write the test in `tests/orchestration/test_journal.py` that expects the journal to
  refuse a step whose output does not match the digest of its inputs
  - **DELIVERED**: the module `ledgerlens/orchestration/journal.py` records the steps of a run, their attempts, their
                   inputs and their outputs, and the docstring says that a suspended run continues from what it already
                   did. The test is in `tests/orchestration/test_journal.py`: the journal refuses an entry whose output
                   does not match the digest it was given, the entry keeps the digest of the inputs of the step, the
                   attempts of a step are counted, the entry of a step that completed is found, a step that failed has
                   no completed entry and the journal survives the round trip of its records.
- [x] T192 [P] Write the module `ledgerlens/orchestration/resume.py` with the docstring saying that a resume
  reuses the output of a completed step, runs again only a step that is idempotent and read-only, refuses a
  step whose snapshot or whose configuration version changed and never rehydrates a credential, and write the
  test in `tests/orchestration/test_resume.py` that expects the reuse, the two refusals and the absence of any
  call of a provider in the resume
  - **DELIVERED**: the module `ledgerlens/orchestration/resume.py` reuses the output of a step that completed, runs
                   again only a step that is idempotent and read-only, refuses a step whose snapshot or whose
                   configuration version changed and never rehydrates a credential. The test is in
                   `tests/orchestration/test_resume.py`: the output of a step that completed is reused, a step that
                   never completed runs again, a step that writes is never run again, a step whose snapshot or whose
                   configuration version changed is refused, a step whose arguments changed runs again, and a step whose
                   arguments carry a credential is refused.
- [x] T193 Write the test in `tests/orchestration/test_restart_idempotency.py` that commits the same command of
  `ledgerlens/sandbox/mutation.py` twice with the same idempotency key and expects one event of the branch in
  `ledgerlens/sandbox/projector.py` and an unchanged projection
  - **DELIVERED**: the test is in `tests/orchestration/test_restart_idempotency.py`: it commits the same command of
                   `ledgerlens/sandbox/mutation.py` twice with the same idempotency key and expects one event of the
                   branch in `ledgerlens/sandbox/projector.py`, and it expects the projection of the branch to be the
                   same after the second commit.
- [x] T194 [P] Write the module `ledgerlens/orchestration/verify_stage.py` with the docstring saying that the
  verifier of `ledgerlens/verify/` runs on the claims of the joined steps before the summary and that it stays
  deterministic, and write the test in `tests/orchestration/test_verify_before_summary.py` that expects the
  summary of a run of the studio to exist only after the verdicts of the verifier
  - **DELIVERED**: the module `ledgerlens/orchestration/verify_stage.py` runs the verifier of `ledgerlens/verify/` on
                   the claims of the joined steps before the summary, and the docstring says that the studio never
                   replaces the verifier and that it stays deterministic. The test is in
                   `tests/orchestration/test_verify_before_summary.py`: the summary exists only after the verdicts, a
                   verification without a verdict is refused and publishes no summary, and the claims come from the
                   results of the steps.
- [x] T195 [P] Write the test in `tests/orchestration/test_comparison_dataset_role.py` that expects the set of
  `data/runtime/orchestration/comparison.json` to carry the role the manifest of `data/eval/datasets.json`
  gives it and that expects the refusal of `ledgerlens/eval/manifest.py` when a tuning script reads it
  - **DELIVERED**: the test is in `tests/orchestration/test_comparison_dataset_role.py`: the set of
                   `data/runtime/orchestration/comparison.json` carries the role that the manifest of
                   `data/eval/datasets.json` gives it, that role is `held_out`, a tuning script that reads it is refused
                   by `ledgerlens/eval/manifest.py` with the name of the dataset and of the rule, and the path of the
                   manifest is reserved in the code of the guard.

## Part D, the comparison and the publication

**Purpose**: the result is published, and the decision that follows it is published too.

- [ ] T196 [P] Write the script `scripts/measure_orchestration.py` that runs the two arms of the comparison over
  the set of the comparison with the same snapshot and writes the measures with their denominator, and write the
  test in `tests/orchestration/test_measure_orchestration.py` that expects the script to refuse to run when the
  manifest of the experiment was written after the first run
- [ ] T197 [P] Write the page `docs/orchestration/comparison.md` with the measures of the two arms, the
  denominator, the uncertainty of the difference and the decision that follows the result, and with the rule that
  a studio that costs more and answers the same is not a gain, and with the wording that the number was
  measured over the set it names and is not a generalization
- [ ] T198 [P] Write the test in `tests/orchestration/test_comparison_is_published.py` that reads
  `docs/orchestration/comparison.md` and expects the two arms, the denominator, the uncertainty and the decision,
  and that expects the page to exist even when the decision was that the flag stays off
- [ ] T199 [P] Write the record of the milestone in `docs/decisions/` with the next number after ADR-077, which
  writes down that the studio is off in the shipped configuration, that the comparison was registered before it
  ran, that the result was published with the decision that follows it and that the verifier stayed
  deterministic, and link it from `docs/decisions/README.md`
