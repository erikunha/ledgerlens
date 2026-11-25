---
description: "Task list for evidence graph and provenance"
---

# Tasks: Evidence graph and provenance

**Input**: Design documents from `specs/010-r8-evidence-graph-and-provenance/`

**Prerequisites**: plan.md (required), spec.md (required), the evidence and the verdict that already exist
(`ledgerlens/schemas.py`, `ledgerlens/verify/claims.py`, `ledgerlens/verify/checks.py`), the bundle
(`ledgerlens/replay/bundle.py`, `ledgerlens/replay/site_export.py`) and the decisions
[ADR-013](../../docs/decisions/ADR-013-public-trace-as-a-versioned-contract.md),
[ADR-055](../../docs/decisions/ADR-055-the-policy-index-carries-the-hash-of-the-corpus.md),
[ADR-073](../../docs/decisions/ADR-073-the-published-bundle-carries-the-evidence-its-verdict-was-computed-on-and-it-is-reproducible.md),
[ADR-074](../../docs/decisions/ADR-074-a-case-ends-in-a-decision-and-the-decision-belongs-to-the-code.md) and
[ADR-077](../../docs/decisions/ADR-077-the-published-bundle-is-verified-against-the-answer-the-run-verified.md)

**Tests**: Every task that changes the behaviour of the repository ships its test before its code, and the gate of
the Python side `scripts/gate.sh` is green before the commit. A test that must fail before the change names the
file it lives in and what it refuses.

**Organization**: Tasks are grouped by the milestone that delivers them, and the tasks of a milestone touch disjoint
files so that they can be worked on in parallel. The ids of this specification start at T821, above the highest id
used by `specs/001-*` through `specs/006-*`, and they never collide with them.

## Format: `[ID] [P?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[DELIVERED]**: the task is done, and the sentence names what it delivered
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `ledgerlens/`, `tests/`, `scripts/`, `data/`, `docs/` at repository root
- Paths shown below assume single project

## Milestone A, the graph in the domain

**Purpose**: the relation between the claims, the evidence and the sources, built in memory from what the run
published.

- [x] T821 Write the test in `tests/verify/test_evidence_graph.py` that fails while a node of an unknown kind is in
  the graph, while an edge carries a type that is not one of `supports`, `contradicts`, `derived_from`,
  `retrieved_from`, `supersedes` and `in_scope_of`, while a cycle in the derivation is built, and while a node of a
  policy carries no digest of the corpus. The fixture is the published bundle of the scenario S01 under
  `data/eval/replay/s01/`
  - **DELIVERED**: `tests/verify/test_evidence_graph.py`: a node of an unknown kind, an edge of an unknown type, a cycle in the derivation and a policy node with no digest of the corpus are refused, over the bundle of S01.
- [x] T822 Write the module `ledgerlens/verify/graph.py` with the builder of the graph, the four kinds of node, the
  six kinds of edge, the resolution of a cited identifier by identity, the marking of the orphans and the conflicts
  and the refusal of a cycle, with the docstring of the module saying that the graph is a read over the evidence of
  the run and that it never becomes a second verdict
  - **DELIVERED**: `ledgerlens/verify/graph.py`: the builder of the graph, the four kinds of node, the six kinds of edge, the orphans, the conflicts and the refusal of a cycle, and the graph is never a second verdict.
- [x] T823 [P] Write the test in `tests/verify/test_evidence_graph.py` that fails while an unresolved citation is
  connected to a node, that fails while a sentence of the model supports a claim, and that fails while the verdict of
  a claim of the bundle differs from the verdict that the graph carries
  - **DELIVERED**: `tests/verify/test_evidence_graph.py`: an unresolved citation is an orphan and never a near match, a sentence of the model is a hypothesis that supports nothing, and the verdict of the graph is the verdict of the bundle.
- [x] T824 [P] Write the coverage in `ledgerlens/verify/graph.py` with the share of the claims that reach a source,
  computed with `Decimal` over the number of the claims it names, together with the hash of the snapshot the graph
  was built from, and the docstring saying why the coverage is a fraction of counts and not a float
  - **DELIVERED**: `ledgerlens/verify/graph.py`: the coverage is a fraction of counts with `Decimal` over the claims it names, and the graph names the hash of the snapshot.
- [x] T825 [P] Write the test in `tests/verify/test_evidence_graph.py` that reads the modules of `ledgerlens/` with
  `ast` and fails while a module imports a graph library, and that reads the modules of `ledgerlens/verify/` with
  `ast` and fails while a module imports `ledgerlens.api`
  - **DELIVERED**: `tests/verify/test_evidence_graph.py`: no module of `ledgerlens/` imports a graph library, and no module of `ledgerlens/verify/` imports `ledgerlens.api`.

## Milestone B, the route that serves the graph

**Purpose**: one read of the graph by the identifier of the run, with the scope of the account applied before the
graph is assembled.

- [x] T826 Write the test in `tests/api/test_evidence_api.py` that fails while the graph of a run of another account
  is served, that fails while the refusal discloses something about the run, and that fails while two reads of the
  same run return different bytes
  - **DELIVERED**: `tests/api/test_evidence_api.py`: the graph of a run of another account is refused without a word about the run, and two reads of the same run return the same bytes.
- [x] T827 Write the route in `ledgerlens/api/evidence.py` that serves the graph of a run, that applies the scope of
  the account when it reads the run, that publishes the count of the nodes it filtered, and with the docstring of
  the module saying that the facade reads the domain and that the domain never imports the facade
  - **DELIVERED**: `ledgerlens/api/evidence.py`: the route serves the graph of a run, applies the scope of the account when it reads the run, and publishes the count of the nodes it filtered.
- [x] T828 [P] Write the test in `tests/verify/test_evidence_graph.py` that fails while the graph of a run that
  holds a sentence of the model explains something, that the sentence is held as a hypothesis and that it supports
  no claim, and that fails while the node of a policy of a historical case names another digest of the corpus
  without an explicit cross version edge
  - **DELIVERED**: `tests/verify/test_evidence_graph.py`: a sentence of the model is a hypothesis that supports no claim, and a policy of a historical case that names another digest is linked with an explicit cross version edge.

## Milestone C, the published graph

**Purpose**: the graph published as an artifact, with a manifest and a hash, beside the bundle it was built from.

- [x] T829 Write the test in `tests/replay/test_published_graph.py` that fails while the export of the graph is not
  byte identical when it runs twice, that fails while the artifact carries no hash of the snapshot it was built
  from, and that fails while the export refuses nothing when the bundle moved
  - **DELIVERED**: `tests/replay/test_published_graph.py`: the export of the graph is byte identical, the artifact carries the hash of the snapshot and of the bundle, and the export refuses a bundle whose digest moved.
- [x] T830 Write the export in `ledgerlens/replay/graph_artifact.py` and the script
  `scripts/export_evidence_graph.py`, with the docstring of the module saying that the export copies, hashes and
  labels and never changes the recorded content, and that it refuses a bundle whose digest moved
  - **DELIVERED**: `ledgerlens/replay/graph_artifact.py` and `scripts/export_evidence_graph.py`: the graph published as an artifact, and the export copies, hashes and labels and never changes the recorded content.
- [x] T831 Write the record of the milestone in `docs/decisions/` with the next number after ADR-077, which states
  that the graph is a read over the evidence of the run and never a second verdict, that a citation that resolves to
  nothing makes an orphan and never a near match, that the scope of an account is applied when the data is read,
  that no graph database is added, and link it from `docs/decisions/README.md` with
  `uv run python scripts/build_docs_index.py`
  - **DELIVERED**: `docs/decisions/ADR-103-the-evidence-graph-is-a-read-over-the-evidence-of-the-run-and-it-is-never-a-second-verdict.md`: the read, the orphan, the scope and no graph database.
