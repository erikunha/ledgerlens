---
description: "Task list for human review queue and approval state machine"
---

# Tasks: Human review queue and approval state machine

**Input**: Design documents from `specs/012-r10-human-review-and-approval/`

**Prerequisites**: plan.md (required), spec.md (required), the rule that escalates
(`ledgerlens/verify/escalation.py`), the numbers of the policy (`ledgerlens/policy_limits.py`), the branch that an
approval applies to (`ledgerlens/sandbox/branch.py`), the economics package that
[specs/011](../011-r9-cost-per-case-and-decision-utility/spec.md) creates, and the decisions
[ADR-019](../../docs/decisions/ADR-019-sandbox-facade-contract.md),
[ADR-021](../../docs/decisions/ADR-021-typed-mutation-and-atomic-commit.md),
[ADR-047](../../docs/decisions/ADR-047-the-lifecycle-and-the-limits-of-the-branch.md),
[ADR-074](../../docs/decisions/ADR-074-a-case-ends-in-a-decision-and-the-decision-belongs-to-the-code.md) and
[ADR-P007](../../docs/v3/adrs/ADR-P007-no-multiagent-by-default.md)

**Tests**: Every task that changes the behaviour of the repository ships its test before its code, and the gate of
the Python side `scripts/gate.sh` is green before the commit. A test that must fail before the change names the
file it lives in and what it refuses.

**Organization**: Tasks are grouped by the milestone that delivers them, and the tasks of a milestone touch disjoint
files so that they can be worked on in parallel. The ids of this specification start at T901, above the highest id
used by `specs/001-*` through `specs/006-*`, and they never collide with them. The file
`ledgerlens/economics/queue.py` lives in the package that
[specs/011](../011-r9-cost-per-case-and-decision-utility/spec.md) creates, and the export of that package in
`ledgerlens/economics/__init__.py` is touched by T911.

## Format: `[ID] [P?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[DELIVERED]**: the task is done, and the sentence names what it delivered
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `ledgerlens/`, `tests/`, `scripts/`, `data/`, `docs/` at repository root
- Paths shown below assume single project

## Milestone A, the domain of the review

**Purpose**: a typed task, a table of transitions and an append only history.

- [ ] T901 Write the test in `tests/review/test_review_task.py` that fails while a task carries no hash of its
  evidence, that reads the modules of `ledgerlens/review/` with `ast` and fails while a module imports
  `ledgerlens.api`, and that fails while a module of `ledgerlens/review/` imports a live run or a payment client
- [ ] T902 Create the package `ledgerlens/review/` with the module `ledgerlens/review/task.py` that holds the typed
  review task with the case it reviews, the evidence the reviewer read, the hash of that evidence, the state, the
  revision and the history, with the docstring of the module saying what a task is and why the hash of the evidence
  travels with it
- [ ] T903 [P] Write the test in `tests/review/test_review_state_machine.py` that fails while a transition that is
  not in the table of the states is applied, that fails while a transition appends no event, that fails while a
  decision that carries an identity of the model applies, that fails while a stale revision applies, that fails while
  a decision with a moved snapshot applies, that fails while a task with a missing evidence is approved, that fails
  while the task of a cancelled run is approved, and that fails while a replay advances a state
- [ ] T904 Write the module `ledgerlens/review/state_machine.py` with the six states, the table of the transitions,
  the append only events and the checks that run before a transition, with the docstring of the module saying that
  the agent prepares the evidence and never decides and that the identity of the reviewer comes from the session
- [ ] T905 [P] Write the service in `ledgerlens/review/service.py` that opens a task when the escalation flags a
  case, that takes the decisions and that appends the approval to the branch of the sandbox, with the docstring
  saying that an approval binds to an event of a branch and that it never reaches a live run

## Milestone B, the route that takes a decision

**Purpose**: one route, the session of the reviewer and the codes of the refusals.

- [ ] T906 Write the test in `tests/api/test_reviews_api.py` that fails while a decision of a session of another
  person is served, that fails while the refusal discloses something about the task, and that fails while a
  decision with a stale revision is accepted
- [ ] T907 Write the route in `ledgerlens/api/reviews.py` that takes a decision with the expected revision, the
  decision, the reason and the session, that answers a conflict with a code, and with the docstring of the module
  saying that the facade reads the domain and that the domain never imports the facade
- [ ] T908 [P] Write the test in `tests/review/test_review_state_machine.py` that fails while the number of the
  transitions applied without the permission of a reviewer is not zero over the fixture of the suite, and that
  expects the history of a task to be read only in the order of its events

## Milestone C, the queue simulator

**Purpose**: the capacity of a review queue, computed and not guessed.

- [ ] T909 Write the test in `tests/economics/test_queue.py` that fails while two runs of the same experiment with
  the same seed differ, that fails while a queue with no reviewer raises or publishes a utilization, that fails
  while an overloaded queue publishes a finite steady state wait, that fails while two policies are compared over
  different arrivals, that fails while the critical class is not named apart, and that fails while the queue holds
  an identifier of a visitor. The fixture holds two reviewers, four arrivals and a fixed review time, so that the
  schedule can be worked out by hand and written in the test
- [ ] T910 Write the module `ledgerlens/economics/queue.py` with the experiment, the stable priority queue of the
  events `(at, sequence, type)`, the service of the reviewers, the utilization, the throughput, the backlog, the
  distribution of the waiting time and the overload, with the docstring of the module saying that the waiting time
  is computed and never written by a model and that the simulator holds no identity of a visitor
- [ ] T911 [P] Extend the export in `ledgerlens/economics/__init__.py` so that it publishes the simulator of the
  queue next to the cost and the utility, and extend the test in `tests/economics/test_queue.py` so that it fails
  while the report of the simulation presents the capacity of the queue as a staffing plan or the latency of the
  interface as the work time of a reviewer
- [ ] T912 [P] Write the test in `tests/economics/test_queue.py` that fails while a class of cases that never
  reaches a reviewer is not reported as starved, and that expects the waiting time of the critical class to be
  published apart from the waiting time of the other classes

## Milestone D, the record of the milestone

**Purpose**: the decisions the milestone took are written down where the repository keeps them.

- [ ] T913 Write the record of the milestone in `docs/decisions/` with the next number after ADR-077, which states
  that the agent prepares the evidence and never decides, that the identity of the reviewer comes from the session,
  that an approval binds to an event of a branch and never to a live payment, that the history of a task is append
  only, that the queue simulator is a simulation whose defaults are fictional and marked as such, that the review
  never changes the model of a run under ADR-037, and that any specialist dispatch of the review stays behind a flag
  until a paired comparison measures a gain under ADR-P007, and link it from `docs/decisions/README.md` with
  `uv run python scripts/build_docs_index.py`
