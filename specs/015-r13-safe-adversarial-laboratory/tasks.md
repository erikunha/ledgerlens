---
description: "Task list for the safe adversarial laboratory"
---

# Tasks: The safe adversarial laboratory

**Input**: Design documents from `specs/015-r13-safe-adversarial-laboratory/`

**Prerequisites**: plan.md (required), spec.md (required), the design package
(`docs/design/advanced-specs/R13-02-safe-adversarial-laboratory.md`) and the decisions that already bind:
`docs/decisions/ADR-005-guarded-text-to-sql.md` and
`docs/decisions/ADR-013-public-trace-as-a-versioned-contract.md`

**Tests**: Every task that changes the behaviour of the repository ships its test before its code, and the gate
of the Python side is green before the commit. The whole suite runs offline with `LEDGERLENS_OFFLINE=1` and no
key, and no test of the laboratory opens a socket, reads a key or writes to the ledger of the base. A task
that is delivered says so, with **DELIVERED** and the evidence of what it delivered.

**Organization**: Tasks are grouped by the three parts of the plan, and the tasks of a group touch disjoint
files so that they can be worked on in parallel. The ids of this milestone start above the ids of `specs/001-`
through `specs/006-` and they are continuous inside this milestone. The folder `tests/adversarial/` is
created by T220, and the tests of the layers that the laboratory exercises stay where they are:
`tests/tools/`, `tests/verify/`, `tests/sandbox/` and `tests/byok/`.

## Format: `[ID] [P?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[DELIVERED]**: the task is done, and the sentence names what it delivered
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `ledgerlens/`, `tests/`, `scripts/`, `data/`, `docs/` at repository root
- Paths shown below assume single project

## Part A, the list of the exercises and their fixtures

**Purpose**: the attacks are data, they are synthetic, and they are reproducible by their hash.

- [x] T220 [P] Create the package `ledgerlens/adversarial/` with the module `__init__.py` and the module
  `ledgerlens/adversarial/exercises.py`, whose docstring says what an exercise is and why the list of the
  exercises is data in the repository, and write the test in `tests/adversarial/test_canned_exercises_only.py`
  that expects the refusal of an unknown exercise id and the refusal of a request that carries an extra field
  - **DELIVERED**: the package is in `ledgerlens/adversarial/` with the module `exercises.py`: the list of the exercises is data in the repository, a request accepts an exercise id and nothing else, and an unknown exercise id and a request with an extra field are refused. The test is in `tests/adversarial/test_canned_exercises_only.py`.
- [x] T221 [P] Write the fixtures of the exercises in `data/adversarial/fixtures/`, one file per exercise, with
  the synthetic payload and the surface it attacks, and write the test in
  `tests/adversarial/test_fixtures_hold_no_secret.py` that reads every fixture and expects no value of a key,
  no address of a real service and no personal data
  - **DELIVERED**: the fixtures of the exercises are in `data/adversarial/fixtures/`, one file per exercise, with the synthetic payload and the surface it attacks. The test is in `tests/adversarial/test_fixtures_hold_no_secret.py`: it reads every fixture and expects no value of a key, no address of a real service and no personal data.
- [x] T222 [P] Write the test in `tests/adversarial/test_s09_stays_data.py` that runs the case of S09 of
  `data/scenarios.json` through the agent of `ledgerlens/agents/integrator.py` and expects the tools and the
  system prompt of the agent to be unchanged and the case to be escalated
  - **DELIVERED**: the test is in `tests/adversarial/test_s09_stays_data.py`: the case of S09 of `data/scenarios.json` runs through the agent of `ledgerlens/agents/integrator.py`, the tools and the system prompt of the agent are unchanged and the case is escalated.
- [x] T223 [P] Write the module `ledgerlens/adversarial/hashes.py` with the docstring saying that the hash of a
  fixture is what makes an exercise reproducible, and write the test in `tests/adversarial/test_fixture_hash.py`
  that expects the hash of every fixture of the list to be recorded and to change when the fixture changes

## Part B, the run of an exercise and the layers that answer

**Purpose**: the laboratory measures the boundaries of the repository and adds none of its own.

  - **DELIVERED**: the module is in `ledgerlens/adversarial/hashes.py`: the hash of a fixture is what makes an exercise reproducible, the record of the hashes is in `data/adversarial/fixtures/hashes.json`. The test is in `tests/adversarial/test_fixture_hash.py`: the hash of every fixture of the list is recorded and changes when the fixture changes.
- [x] T224 [P] Write the module `ledgerlens/adversarial/runner.py` with the docstring saying that an exercise
  runs the agent of the repository unchanged, in the offline mode with the scripted model, and that the
  laboratory never weakens a layer to let an attack through, and write the test in
  `tests/adversarial/test_runner_uses_the_shipped_agent.py` that expects the tools and the prompt of the run
  to be the ones of the shipped path
  - **DELIVERED**: the module is in `ledgerlens/adversarial/runner.py`: an exercise runs the agent of the repository unchanged, in the offline mode with the scripted model, and the laboratory never weakens a layer to let an attack through. The test is in `tests/adversarial/test_runner_uses_the_shipped_agent.py`.
- [x] T225 [P] Write the test in `tests/adversarial/test_layers_answer.py` that runs the exercises of the write,
  of the table outside the allowlist and of the tool that does not exist, and expects the refusal of
  `ledgerlens/tools/sql_guard.py`, of the read-only connection of `ledgerlens/tools/sql.py` and of the
  allowlist of the tools of `ledgerlens/api/live_case.py`, and expects the reason of each refusal in the trace
  - **DELIVERED**: the test is in `tests/adversarial/test_layers_answer.py`: the exercises of the write, of the table outside the allowlist and of the tool that does not exist are stopped by the guard of `ledgerlens/tools/sql_guard.py`, by the read-only connection of `ledgerlens/tools/sql.py` and by the allowlist of the tools of `ledgerlens/api/live_case.py`, and the reason of each refusal is in the trace.
- [x] T226 [P] Write the test in `tests/adversarial/test_scope_of_the_session.py` that runs the exercise of the
  row of another visitor and expects the store of the branch and the session folder of
  `ledgerlens/sandbox/memory.py` to refuse the read of a branch of another session
  - **DELIVERED**: the test is in `tests/adversarial/test_scope_of_the_session.py`: the exercise of the row of another visitor is stopped by the store of the branch and the session folder of `ledgerlens/sandbox/memory.py` refuses the read of a branch of another session.
- [x] T227 [P] Write the test in `tests/adversarial/test_budget_of_the_run.py` that runs the exercise of the
  call that passes the cap and expects the coordinator of `ledgerlens/byok/budget.py` to stop the run with the
  name of the cap
  - **DELIVERED**: the test is in `tests/adversarial/test_budget_of_the_run.py`: the exercise of the call that passes the cap is stopped by the coordinator of `ledgerlens/byok/budget.py` with the name of the cap.
- [x] T228 [P] Write the module `ledgerlens/adversarial/result.py` with the docstring saying that the result of
  an exercise carries the surface that was attacked, the boundary that was expected, the reference of the
  trace, the actions that were blocked with their reasons and the risk that is still open, and write the test
  in `tests/adversarial/test_result_of_exercise.py` that expects the six fields and that the blocked actions
  carry the reason of the layer that stopped them
  - **DELIVERED**: the module is in `ledgerlens/adversarial/result.py`: the result of an exercise carries the surface, the boundary, the reference of the trace, the blocked actions with their reasons and the open risk. The test is in `tests/adversarial/test_result_of_exercise.py`.
- [x] T229 [P] Write the test in `tests/adversarial/test_no_unauthorized_actions.py` that counts the
  unauthorized actions over every exercise of the list and expects zero, and that the count is computed by the
  test and not written by hand
  - **DELIVERED**: the test is in `tests/adversarial/test_no_unauthorized_actions.py`: the count of the unauthorized actions over every exercise of the list is zero, and the count is computed by the test and not written by hand.
- [x] T230 [P] Write the test in `tests/adversarial/test_trace_of_the_lab.py` that reads the events of
  `ledgerlens/observability/trace_event.py` produced by an exercise and expects one event per attempt with the
  reason of the refusal

## Part C, the flag, the rollback and the publication

**Purpose**: the laboratory is off in the shipped configuration, and what it finds is published.

  - **DELIVERED**: the test is in `tests/adversarial/test_trace_of_the_lab.py`: the events of `ledgerlens/observability/trace_event.py` produced by an exercise carry one event per attempt with the reason of the refusal.
- [x] T231 [P] Read the flag of the laboratory in `ledgerlens/config.py` as `LEDGERLENS_ADVERSARIAL_LAB`, off by
  default, and write the test in `tests/adversarial/test_lab_flag.py` that expects the flag off in the shipped
  configuration and that expects the traces of the exercises to be readable offline with no key
  - **DELIVERED**: the flag of the laboratory is read in `ledgerlens/config.py` as `LEDGERLENS_ADVERSARIAL_LAB`, off by default. The test is in `tests/adversarial/test_lab_flag.py`: the flag is off in the shipped configuration and the traces of the exercises are readable offline with no key.
- [x] T232 [P] Write the test in `tests/adversarial/test_rollback.py` that builds the application of
  `ledgerlens/api/` with the flag off and expects that no route of the laboratory answers, and that the fixtures
  of `data/adversarial/fixtures/` stay readable as data
  - **DELIVERED**: the test is in `tests/adversarial/test_rollback.py`: the application of `ledgerlens/api/` built with the flag off has no route of the laboratory, and the fixtures of `data/adversarial/fixtures/` stay readable as data.
- [x] T233 [P] Write the script `scripts/run_adversarial_lab.py` that runs the list of the exercises in the
  offline mode and writes the result of each one under `data/adversarial/results/`, and write the test in
  `tests/adversarial/test_run_adversarial_lab.py` that expects the script to refuse to run with a key in the
  environment and that expects the results of every exercise to carry its six fields
  - **DELIVERED**: the script is in `scripts/run_adversarial_lab.py`: it runs the list of the exercises in the offline mode and writes the result of each one under `data/adversarial/results/`. The test is in `tests/adversarial/test_run_adversarial_lab.py`: the script refuses to run with a key in the environment and the results of every exercise carry the six fields.
- [x] T234 [P] Write the page `docs/adversarial-lab.md` with the list of the exercises, the surface of each
  one, the layer that answers it, the count of the unauthorized actions with the restriction it carries and the
  sentence that says the count says nothing about an attack that is not in the list
  - **DELIVERED**: the page is in `docs/adversarial-lab.md`: the list of the exercises, the surface of each one, the layer that answers it, the count of the unauthorized actions with the restriction it carries and the sentence that says the count says nothing about an attack that is not in the list.
- [x] T235 [P] Write the mapping in `docs/adversarial-lab.md` of every exercise to the reference of the
  taxonomy it belongs to, with the source of the taxonomy named, and write the test in
  `tests/adversarial/test_threat_mapping.py` that reads the mapping and expects every exercise to name its
  surface, its layer and its reference, and that expects the wording that the mapping is proposed and not a
  certification
  - **DELIVERED**: the mapping is in `docs/adversarial-lab.md`: every exercise names its surface, its layer and its reference of the OWASP Top 10 for LLM Applications 2025, with the source named and the wording that the mapping is proposed and not a certification. The test is in `tests/adversarial/test_threat_mapping.py`.
- [x] T236 [P] Write the record of the milestone in `docs/decisions/` with the next number after ADR-077, which
  writes down that the laboratory adds no defense of its own, that it accepts an exercise id and nothing else,
  that it runs offline with no key, that the count of the unauthorized actions says nothing about an attack
  that is not in the list and that the mapping of the taxonomy is proposed and not a certification, and link it
  from `docs/decisions/README.md`

  - **DELIVERED**: the record is `docs/decisions/ADR-091-the-adversarial-laboratory-adds-no-defense-of-its-own-and-its-count-says-nothing-about-an-attack-that-is-not-in-the-list.md`: the laboratory adds no defense of its own, it accepts an exercise id and nothing else, it runs offline with no key, the count says nothing about an attack that is not in the list and the mapping is proposed and not a certification. The index of the decisions was regenerated with `uv run python scripts/build_docs_index.py`.