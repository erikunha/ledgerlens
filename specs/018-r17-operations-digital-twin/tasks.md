---
description: "Task list for operations digital twin"
---

# Tasks: Operations digital twin

**Input**: Design documents from `specs/018-r17-operations-digital-twin/`

**Prerequisites**: plan.md (required), spec.md (required), the design package of the release
(`docs/design/advanced-specs/R17-04-operations-digital-twin-simulation.md`), ADR-009
(`docs/decisions/ADR-009-public-data-first-simulation-for-gaps.md`), ADR-018, ADR-021, ADR-022 and ADR-032 of
`docs/decisions/`, ADR-P007 and ADR-P009 of `docs/design/adrs/`, and the generator that the twin builds on:
`ledgerlens/sim/config.py`, `ledgerlens/sim/events.py`, `ledgerlens/sim/projector.py`,
`ledgerlens/sim/scenarios.py` and the truth in `data/scenarios.json`

**Tests**: Every task that changes the behaviour of the repository ships its test before its code, and the gate of
the Python side is green before the commit. The tests of the twin live in `tests/sim/twin/` and run offline with
`LEDGERLENS_OFFLINE=1`. A test that passes before the change it proves proves nothing, so every test of this list
is written to fail before the code of its task and to pass after it. The twin runs with the network disabled, and
no task of this list writes into `data/eval/replay/` or into `data/eval/replay-real/`.

**Organization**: Tasks are grouped by the layer of the twin that they build, from the decision that starts it to
the documentation that closes it. The ids of this list start at T301 and are unique in the repository; the ids of
the specifications `001` to `006` end at T172 and the blocks of the lists that run in parallel are kept apart, so
that two people can work on this list and on another list at the same time. The tasks marked `[P]` touch disjoint
files and can run in parallel with each other.

## Format: `[ID] [P?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[DELIVERED]**: the task is done, and the sentence names what it delivered
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `ledgerlens/`, `tests/`, `scripts/`, `data/`, `docs/` at repository root
- Paths shown below assume single project

## The decision that starts the milestone

**Purpose**: the shape of the twin and the rule that a run of it is not a bundle of the agent.

- [x] T301 Write the record of the decision in
  `docs/decisions/ADR-079-the-simulation-of-the-twin-is-not-a-recording-of-a-run.md`, with the number the index
  shows as free at the time of writing, saying that the manifest of a simulation is canonical and carries the
  digest of the truth, the provenance, the assumptions, the digest of the arrival stream and the commit of the
  code, that the twin models slots and never people, and that a run of the twin is never a bundle of the agent and
  never goes into `data/eval/replay/` or into `data/eval/replay-real/`. Run
  `uv run python scripts/build_docs_index.py` to regenerate `docs/decisions/README.md` and commit the result. The
  record does not change any accepted record

## The configuration and its refusal

**Purpose**: a configuration that cannot be simulated is refused before anything is written.

  - **DELIVERED**: the record is `docs/decisions/ADR-093-the-simulation-of-the-twin-is-not-a-recording-of-a-run-and-the-twin-models-slots-and-never-people.md`: the manifest of a simulation is canonical and carries the digest of the truth, the provenance, the assumptions, the digest of the arrival stream and the commit, the twin models slots and never people, and a run of the twin is never a bundle of the agent. The index of the decisions was regenerated with `uv run python scripts/build_docs_index.py`.
- [x] T302 Write `tests/sim/twin/test_config.py` first, expecting that a negative capacity, a horizon of zero, a
  provider failure rate outside the interval of a rate, a merchant that is not in the ledger and an unknown field
  are each refused, that the message names the field that is wrong and that the output directory holds no manifest
  after a refusal. Then write `ledgerlens/sim/twin/config.py` with the typed record of the configuration, its
  validation and the refusal, with a docstring that says what the configuration is and why the refusal happens
  before any write
  - **DELIVERED**: the test is in `tests/sim/twin/test_config.py` and the module is in `ledgerlens/sim/twin/config.py`: a negative capacity, a horizon of zero, a rate outside the interval, a merchant that is not in the ledger and an unknown field are each refused with the name of the field, before anything is written.
- [x] T303 [P] Write `ledgerlens/sim/twin/__init__.py` with the docstring of the package, which says that the twin
  simulates the operations of a payment business over a modelled arrival process and never runs a model and never
  touches a payment network

## The arrival stream

**Purpose**: the arrivals are a modelled process with a declared distribution, generated once and read by every run
of a comparison.

  - **DELIVERED**: the package is in `ledgerlens/sim/twin/__init__.py`: the twin simulates the operations of a payment business over a modelled arrival process, never runs a model and never touches a payment network.
- [x] T304 Write `tests/sim/twin/test_arrivals.py` first, expecting that the count of the arrivals follows the
  declared distribution over a long horizon, that the stream is the same for the same seed and that the digest of
  the stream is recorded in the manifest. Then write `ledgerlens/sim/twin/arrivals.py` with the sampler, the
  canonical form of the stream and its digest, with a docstring that says the distribution is a model of the
  repository and never a measurement of a real operation

## The manifest of a run

**Purpose**: the reader of a run knows which world the run measured and under which assumptions.

  - **DELIVERED**: the test is in `tests/sim/twin/test_arrivals.py` and the module is in `ledgerlens/sim/twin/arrivals.py`: the count of the arrivals follows the declared distribution, the stream is the same for the same seed and the digest of the stream is recorded in the manifest.
- [x] T305 Write `tests/sim/twin/test_manifest.py` first, expecting the four fields of the manifest, the change of
  the digest of the truth when the truth changes, the same bytes when the keys are written in a different order, and
  the absence of a timestamp and of a path of the machine in the bytes. Then write `ledgerlens/sim/twin/manifest.py`
  with the typed record, the canonical serialization and the digest, with a docstring that says why the bytes of the
  manifest do not depend on the machine that wrote them

## The run

**Purpose**: the run is deterministic in the seed and the state of the world does not depend on when the projector
was restarted.

  - **DELIVERED**: the test is in `tests/sim/twin/test_manifest.py` and the module is in `ledgerlens/sim/twin/manifest.py`: the manifest carries the digest of the truth, the provenance, the assumptions, the digest of the stream, the commit and the label, the bytes do not depend on the order of the keys and they hold no timestamp and no path of the machine.
- [x] T306 Write `tests/sim/twin/test_determinism.py` first, expecting that three runs of the same configuration,
  two of them with a different hash seed of the interpreter, produce byte for byte equal manifests. Then write
  `ledgerlens/sim/twin/run.py` with the run, the reading of the cases through the read-only surface of the domain
  and the writing of the manifest, with a docstring that says what a run of the twin is and that it is a simulation
  and not a recording of the agent
  - **DELIVERED**: the test is in `tests/sim/twin/test_determinism.py` and the module is in `ledgerlens/sim/twin/run.py`: three runs of the same configuration, two of them with a different hash seed of the interpreter, produce byte for byte equal manifests.
- [x] T307 Write `tests/sim/twin/test_projector_restart.py` first, expecting that the digest of the projected tables
  after a rebuild of the projector is the digest before the rebuild and that the order of the ids of the events is
  the same. Then extend `ledgerlens/sim/twin/run.py` with the rebuild, keeping the docstring of the module and
  adding a docstring to the function that says why the order of the events survives a restart

## The capacity and the condition of the queue

**Purpose**: a queue that never drains is a label and not a number.

  - **DELIVERED**: the test is in `tests/sim/twin/test_projector_restart.py` and the function `rebuild_projection` is in `ledgerlens/sim/twin/run.py`: the digest of the projected tables after a rebuild of the projector is the digest before the rebuild, and the order of the ids of the events is the same.
- [x] T308 Write `tests/sim/twin/test_queue.py` first, expecting the label `queue_never_drains` and the absence of
  the throughput for a capacity of one slot and an arrival rate above the service rate, a throughput number for a
  capacity that is large enough, and the refusal of a capacity of zero. Then write `ledgerlens/sim/twin/queue.py`
  with the capacity model, the service time and the label of the run, with a docstring that says that the slots are
  a capacity and never a number of people

## The paired comparison

**Purpose**: two policies are compared over one stream of arrivals, and every money figure is recomputable.

  - **DELIVERED**: the test is in `tests/sim/twin/test_queue.py` and the module is in `ledgerlens/sim/twin/queue.py`: a capacity of one slot and an arrival rate above the service rate carries the label `queue_never_drains` and publishes no throughput, a capacity that is large enough publishes a throughput, and a capacity of zero is refused.
- [x] T309 Write `tests/sim/twin/test_paired_comparison.py` first, expecting that the digest of the arrival stream
  of the second run is the digest of the first and that the second run refuses to generate a second stream, that the
  comparison names the cases whose decision changed, that the cost per case recomputed with `Decimal` is the number
  the comparison published and that the cost per case is undefined with a reason when the denominator is zero. Then
  write `ledgerlens/sim/twin/compare.py` with the comparison, the changed cases and the figures, with a docstring
  that says that a comparison is a difference inside the synthetic world and never a statement about a real
  operation

## The report

**Purpose**: every figure of the report carries the assumptions that produced it.

  - **DELIVERED**: the test is in `tests/sim/twin/test_paired_comparison.py` and the module is in `ledgerlens/sim/twin/compare.py`: the digest of the stream of the second run is the digest of the first, the comparison names the cases whose decision changed, the cost per case recomputed with `Decimal` is the number published and the cost is undefined with a reason when the denominator is zero.
- [x] T310 [P] Write `tests/sim/twin/test_report.py` first, expecting that every figure of the report carries the
  reference to the run it came from and that the report holds no sentence that claims a saving or a loss in a real
  operation. Then write `ledgerlens/sim/twin/report.py` with the report, with a docstring that says that the
  assumptions are part of the number and not a footnote of it

## The boundaries of the twin

**Purpose**: the twin stays inside the repository and outside the published catalogs.

  - **DELIVERED**: the test is in `tests/sim/twin/test_report.py` and the module is in `ledgerlens/sim/twin/report.py`: every figure of the report carries the reference to the run and the assumptions, and the report holds no sentence that claims a saving or a loss in a real operation.
- [x] T311 [P] Write `tests/sim/twin/test_no_external_calls.py` first, expecting that the twin finishes with the
  network disabled and that no module of `ledgerlens/sim/twin/` imports `ledgerlens.api`. Then keep the modules of
  the twin free of any provider client and any payment endpoint
  - **DELIVERED**: the test is in `tests/sim/twin/test_no_external_calls.py`: the twin finishes with the network disabled and no module of `ledgerlens/sim/twin/` imports `ledgerlens.api`.
- [x] T312 [P] Write `tests/sim/twin/test_domain_boundary.py` first, reading the modules of `ledgerlens/sim/twin/`
  with `ast` and expecting that none of them carries a SQL string and that none of them imports `ledgerlens.api`.
  The twin reads the ledger through the read-only surface of the domain, the same way `ledgerlens/tools/ledger_api.py`
  does, and the domain never speaks SQL
  - **DELIVERED**: the test is in `tests/sim/twin/test_domain_boundary.py`: no module of `ledgerlens/sim/twin/` carries a SQL string and none imports `ledgerlens.api`, read with `ast`.
- [x] T313 [P] Write `tests/sim/twin/test_not_a_replay_bundle.py` first, expecting that a run of the twin writes no
  directory under `data/eval/replay/` and none under `data/eval/replay-real/` and that the export of the site still
  passes `uv run python scripts/export_replay_site.py --check`. The two published catalogs hold the recordings of the
  agent and nothing else, under ADR-073, ADR-075 and ADR-077

## The command and the gate

**Purpose**: the twin is run by one command and the gate checks that it stays honest.

  - **DELIVERED**: the test is in `tests/sim/twin/test_not_a_replay_bundle.py`: a run of the twin writes no directory under `data/eval/replay/` and none under `data/eval/replay-real/`, and the export of the site still passes.
- [x] T314 Write `ledgerlens/sim/twin/cli.py` with the command that runs the twin and prints the manifest, and
  register it in `pyproject.toml` next to the existing `ledgerlens-sim` entry point, with the docstring of the
  module saying what the command does and what it refuses
  - **DELIVERED**: the module is in `ledgerlens/sim/twin/cli.py` and the command `ledgerlens-twin` is registered in `pyproject.toml` next to `ledgerlens-sim`: the command runs the twin and prints the manifest, and a configuration that cannot be simulated is refused.
- [x] T315 Add the check of the twin to `scripts/gate.sh`: a run with the seed 42 over a short horizon, the
  comparison of the manifest against the expected bytes and the check that the two published catalogs are untouched.
  The step writes nothing and fails the gate with a readable reason

## The documentation that closes the milestone

**Purpose**: a reader of the manifest finds the reasoning of the model and the limits of it.

  - **DELIVERED**: the check is in `scripts/check_twin.py` and in `scripts/gate.sh`: a run with the seed 42 over a short horizon is deterministic, and the two published catalogs are untouched. The step writes nothing and fails the gate with a readable reason.
- [x] T316 [P] Write `docs/twin.md` with the arrival distribution that the shipped configuration uses and why it was
  chosen, the vocabulary of the twin, the meaning of every label of a run, the difference between a measurement and
  a model, and the statement that a comparison is a comparison inside a synthetic world. Link it from
  `docs/README.md` by running `uv run python scripts/build_docs_index.py`

  - **DELIVERED**: the page is in `docs/twin.md`: the arrival distribution of the shipped configuration and the reasoning of it, the vocabulary of the twin, the meaning of every label of a run, the difference between a measurement and a model and the statement that a comparison is a comparison inside a synthetic world. The index was regenerated with `uv run python scripts/build_docs_index.py`.