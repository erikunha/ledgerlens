---
description: "Task list for isolated sandbox mutations"
---

# Tasks: Isolated sandbox mutations

**Input**: Design documents from `specs/008-r2-isolated-sandbox-mutations/`

**Prerequisites**: plan.md (required), spec.md (required), the branch layer that already exists
(`ledgerlens/sandbox/branch.py`, `ledgerlens/sandbox/mutation.py`, `ledgerlens/sandbox/events.py`,
`ledgerlens/sandbox/store.py`) and the decisions
[ADR-018](../../docs/decisions/ADR-018-branch-layer-and-store-interface.md),
[ADR-021](../../docs/decisions/ADR-021-typed-mutation-and-atomic-commit.md),
[ADR-022](../../docs/decisions/ADR-022-reset-and-staleness.md),
[ADR-028](../../docs/decisions/ADR-028-the-diff-and-the-history-are-reads.md) and
[ADR-032](../../docs/decisions/ADR-032-the-state-of-the-branch-and-the-hash.md)

**Tests**: Every task that changes the behaviour of the repository ships its test before its code, and the gate of
the Python side `scripts/gate.sh` is green before the commit. A test that must fail before the change names the
file it lives in and what it refuses.

**Organization**: Tasks are grouped by the milestone that delivers them, and the tasks of a milestone touch disjoint
files so that they can be worked on in parallel. The ids of this specification start at T741, above the highest id
used by `specs/001-*` through `specs/006-*`, and they never collide with them.

## Format: `[ID] [P?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[DELIVERED]**: the task is done, and the sentence names what it delivered
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `ledgerlens/`, `tests/`, `scripts/`, `data/`, `docs/` at repository root
- Paths shown below assume single project

## Milestone A, the conformance suite of the acceptance scenarios

**Purpose**: the six sentences of the design package, gathered in one suite and run over the three seeded
scenarios.

- [x] T741 Write the suite in `tests/sandbox/test_acceptance_conformance.py` that runs the acceptance scenarios of
  the design package over the seeded scenarios S01, S02 and S03: two sessions that edit the same transaction, a
  mutation that is retried with the same idempotency key, a wrong precision and a wrong currency, a reset that
  returns the base hash, a request that names a read only field, and a mutated rate that marks the published answer
  stale. Every case names the scenario it ran and the number of the commands it sent, and the suite fails while a
  case runs no scenario
  - **DELIVERED**: `tests/sandbox/test_acceptance_conformance.py`: the six sentences of the package over S01, S02 and S03, every case naming the scenario and the commands it sent.
- [x] T742 [P] Extend the suite in `tests/sandbox/test_acceptance_conformance.py` so that it checks the two
  properties that hold over the three scenarios: the revision of the branch is the count of its events, and the
  canonical hash of the branch is the hash of its projected state and is reproduced from the events alone. The
  suite fails while a scenario is missing from the parameterisation
  - **DELIVERED**: `tests/sandbox/test_acceptance_conformance.py`: the revision is the count of the events and the canonical hash is reproduced from the events alone, over the three scenarios.

## Milestone B, the property tests of the branch

**Purpose**: the invariants of the branch over a sequence of commands that nobody wrote by hand.

- [x] T743 Decide how the generator of the sequences of commands is written: the repository carries no property
  testing library, and the choice is between adding one to `pyproject.toml` and writing a seeded generator inside
  `tests/sandbox/`. Write the decision down in the record of the milestone of T748, with the reason and the
  dependency it adds to the suite of the repository
  - **DELIVERED**: the decision is in ADR-101: a seeded generator inside `tests/sandbox/`, and no property testing library added to the suite.
- [x] T744 Write the test in `tests/sandbox/test_branch_properties.py` that fails while a generated sequence of
  commands breaks the property that the revision is the count of the events, the property that the hash of the
  branch is reproduced from the events alone, or the property that a refused command changes neither the revision
  nor the hash. The test names the seed of every case it runs, and the seed of a failure is in the message
  - **DELIVERED**: `tests/sandbox/test_branch_properties.py`: the generated sequences never break the revision, the hash or the refusal, and the seed of every case is in the message.
- [x] T745 Write the generator of the sequences of commands in `tests/sandbox/sequences.py`, seeded and
  deterministic, that produces the previews, the commits, the refused commands and the resets over the temporary
  store of the tests, with the docstring of the module saying why the generator never touches
  `data/runtime/sandbox-bases/`
  - **DELIVERED**: `tests/sandbox/sequences.py`: the seeded and deterministic generator of the previews, the commits, the refused commands and the resets, and it never touches `data/runtime/sandbox-bases/`.

## Milestone C, the published diff of a mutation

**Purpose**: the diff of a branch published as data, with a hash and with the command that reproduces it.

- [x] T746 Write the test in `tests/sandbox/test_diff_artifact.py` that fails while the export of a diff moves the
  revision or the hash of the branch, that fails while two exports of the same branch differ by a byte, and that
  fails while the artifact carries no hash of the branch, no hash of the base and no command that reproduces the
  mutation
  - **DELIVERED**: `tests/sandbox/test_diff_artifact.py`: the export moves neither the revision nor the hash, two exports are byte identical, and the artifact carries the two hashes and the commands.
- [x] T747 Write the reader of the diff in `ledgerlens/sandbox/diff_artifact.py` and the export
  `scripts/export_sandbox_diff.py`, with the docstring of the module saying that the diff is a read of the branch
  under ADR-028, that the export copies and hashes and never writes, and that the domain never imports the facade
  - **DELIVERED**: `ledgerlens/sandbox/diff_artifact.py` and `scripts/export_sandbox_diff.py`: the diff of the branch as data, a read under ADR-028, and the domain never imports the facade.
- [x] T748 Write the record of the milestone in `docs/decisions/` with the next number after ADR-077, which states
  that the conformance suite of the acceptance scenarios runs over the three seeded scenarios, that the generator
  of the sequences of commands is seeded, and that the diff of a branch is published as data with a hash and not
  as a picture, and link it from `docs/decisions/README.md` with
  `uv run python scripts/build_docs_index.py`
  - **DELIVERED**: `docs/decisions/ADR-101-the-conformance-of-the-sandbox-runs-over-the-seeded-scenarios-and-the-diff-is-published-as-data.md`: the suite, the seeded generator and the diff as data.
