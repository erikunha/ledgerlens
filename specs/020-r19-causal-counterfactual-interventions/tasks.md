---
description: "Task list for causal counterfactual interventions"
---

# Tasks: Causal counterfactual interventions

**Input**: Design documents from `specs/020-r19-causal-counterfactual-interventions/`

**Prerequisites**: plan.md (required), spec.md (required), the design package of the release
(`docs/v3/advanced-specs/R19-02-causal-counterfactual-interventions.md`), ADR-013, ADR-028, ADR-032 and ADR-074 of
`docs/decisions/`, ADR-P007 and ADR-P009 of `docs/v3/adrs/`, and the code the registry describes: `ledgerlens/sim/fx.py`,
`ledgerlens/sim/pipeline.py`, `ledgerlens/sim/gaps.py`, `ledgerlens/sim/calendars.py`, `ledgerlens/tools/calculator.py`,
`ledgerlens/tools/fx.py`, `ledgerlens/retrieval.py`, `ledgerlens/verify/escalation.py` and `ledgerlens/verify/checks.py`.
The arrival stream of the world comes from the twin of `specs/018-r17-operations-digital-twin/`, and the parts of
this list that need it wait for it

**Tests**: Every task that changes the behaviour of the repository ships its test before its code, and the gate of
the Python side is green before the commit. The tests of the causal engine live in `tests/causal/` and run offline
with `LEDGERLENS_OFFLINE=1`. Every test of this list is written to fail before the code of its task and to pass
after it. No test of this list writes into `data/eval/replay/` or into `data/eval/replay-real/`, and no test of
this list claims anything about a real merchant

**Organization**: Tasks are grouped by the layer of the engine that they build, from the decision that starts it to
the documentation that closes it. The ids of this list start at T601 and are unique in the repository; the ids of
the specifications `001` to `006` end at T172, and the blocks of the lists that run in parallel are kept apart, so
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

**Purpose**: the registry is the only source of a dependency, a change without a declared edge is unknown, and a
result never speaks about a real outcome.

- [ ] T601 Write the record of the decision in
  `docs/decisions/ADR-081-the-registry-of-the-structural-functions-is-the-only-source-of-a-dependency.md`, with the
  number the index shows as free at the time of writing, saying that the registry is written by hand over the code
  of the repository, that a node that is not in the registry is never a descendant, that a change without a declared
  edge is reported as `unknown` with the missing edge named, that no cause is learned from an observation and that
  every statement of the report is a statement about the simulation. Run
  `uv run python scripts/build_docs_index.py` to regenerate `docs/decisions/README.md` and commit the result. The
  record does not change any accepted record

## The registry of the structural functions

**Purpose**: the dependency between the nodes of the world is declared, and the declaration names the code.

- [ ] T602 Write `ledgerlens/causal/__init__.py` with the docstring of the package, which says that the registry
  declares the dependencies of the synthetic world and that nothing of it is learned from an observation
- [ ] T603 Write `tests/causal/test_registry.py` first, expecting the nodes of the four families of the registry,
  expecting that every edge names the two nodes it connects, the function that implements it and the reason of the
  edge, and expecting that a node outside the registry has no edge at all. Then write `ledgerlens/causal/registry.py`
  with the declaration over `ledgerlens/sim/fx.py`, `ledgerlens/sim/pipeline.py`, `ledgerlens/sim/gaps.py`,
  `ledgerlens/sim/calendars.py`, `ledgerlens/tools/calculator.py`, `ledgerlens/tools/fx.py`,
  `ledgerlens/retrieval.py`, `ledgerlens/verify/escalation.py` and `ledgerlens/verify/checks.py`, with a docstring
  that says what an edge is and why the reason of the edge is part of it
- [ ] T604 [P] Extend `tests/causal/test_registry.py` with the expectation that every function named by an edge
  exists in the code of the repository, so that an edge whose function was renamed fails the test. The registry is
  a declaration of the code and not a picture of it

## The intervention

**Purpose**: an intervention is a typed record, and an invalid one is refused before anything is written.

- [ ] T605 Write `tests/causal/test_intervention.py` first, expecting that an intervention on an unknown node, on
  a node with an invalid value and on a date outside the horizon are each refused with a readable reason that names
  the field that is wrong, and that the output directory holds no result after a refusal. Then write
  `ledgerlens/causal/intervention.py` with the typed record and its validation, with a docstring that says what an
  intervention is and why a refused intervention writes nothing

## The engine

**Purpose**: the descendants of the target are recomputed along the edges of the registry, and the history is not
rewritten.

- [ ] T606 Write `tests/causal/test_engine.py` first, expecting that two runs over the same base carry the same
  digest of the exogenous stream, that the changed nodes are the descendants of the target in the registry, that
  every applied rate of the ledger is unchanged after an intervention on the reference rate, and that an
  intervention on a merchant policy names the periods it covered and leaves every node outside them unchanged.
  Then write `ledgerlens/causal/engine.py` with the run, the recomputation of the descendants and the reading of
  the state, with a docstring that says that the engine changes one field and that the rest follows the registry
- [ ] T607 Write `tests/causal/test_unknown_links.py` first, expecting that a node that changes without a declared
  edge is reported with the status `unknown`, that the missing edge is named and that the claim is listed as an
  unsupported causal claim. Then extend `ledgerlens/causal/engine.py` with the check of the edges, keeping the
  docstring of the module and adding one that says why a change without a declared edge is never a cause
- [ ] T608 Write `tests/causal/test_compound.py` first, expecting that the compound intervention names both of its
  targets and that its result is not the sum of the results of the two single interventions. Then extend
  `ledgerlens/causal/intervention.py` and `ledgerlens/causal/engine.py` with the compound intervention, with a
  docstring that says why two changes at once are named one by one
- [ ] T609 Write `tests/causal/test_invariants.py` first, expecting that an intervention that breaks a money
  invariant of `ledgerlens/sandbox/invariants.py` is refused and that the state of the world is the one before the
  intervention. Then extend `ledgerlens/causal/engine.py` with the check of the invariants, with a docstring that
  says that an intervention that breaks the world is not applied

## The report

**Purpose**: the report separates what is known, what is unknown and what nobody can check.

- [ ] T610 Write `tests/causal/test_report.py` first, expecting that every amount of the report is a `Decimal`, that
  every difference recomputes exactly, that the amounts that did not change are named, that no sentence of the
  report says what a real merchant would have received and that every sentence of cause names the simulation. Then
  write `ledgerlens/causal/report.py` with the report, with a docstring that says that a difference without its two
  values is not a result
- [ ] T611 Write `tests/causal/test_sensitivity.py` first, expecting that the result carries its assumptions and the
  sensitivity to them, and that the two results under two assumptions carry the assumption that produced them.
  Then extend `ledgerlens/causal/engine.py` and `ledgerlens/causal/report.py` with the sensitivity, with a
  docstring that says that the sensitivity is a measurement of the assumption and not an interval of confidence

## The boundaries of the engine

**Purpose**: the engine stays inside the rules of the repository and outside the published catalogs.

- [ ] T612 [P] Write `tests/causal/test_not_a_replay_bundle.py` first, expecting that a run writes nothing under
  `data/eval/replay/` and nothing under `data/eval/replay-real/`, and that the export of the site still passes
  `uv run python scripts/export_replay_site.py --check`. A result of a simulation is not a bundle of the agent
- [ ] T613 [P] Write `tests/causal/test_domain_boundary.py` first, reading the modules of `ledgerlens/causal/` with
  `ast` and expecting that none of them carries a SQL string and that none of them imports `ledgerlens.api`. The
  engine reads the world through the simulator and the projector

## The documentation that closes the milestone

**Purpose**: a reader of a result knows what a dependency is and where it comes from.

- [ ] T614 [P] Write `docs/causal.md` with the four families of the registry, the nodes and the edges of each one,
  the reason of every edge and the function that implements it, the meaning of `unknown`, the meaning of an
  unsupported causal claim, and the statement that a result is a statement about a simulation and never a
  prediction for a real merchant. Link it from `docs/README.md` by running
  `uv run python scripts/build_docs_index.py`
