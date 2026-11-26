# Feature Specification: Evidence graph and provenance

**Feature Branch**: `feature/v3`

**Created**: 2026-11-23

**Status**: Draft

**Input**: Design documents: [ADR-013](../../docs/decisions/ADR-013-public-trace-as-a-versioned-contract.md),
[ADR-017](../../docs/decisions/ADR-017-export-contract-and-provenance.md),
[ADR-055](../../docs/decisions/ADR-055-the-policy-index-carries-the-hash-of-the-corpus.md),
[ADR-073](../../docs/decisions/ADR-073-the-published-bundle-carries-the-evidence-its-verdict-was-computed-on-and-it-is-reproducible.md),
[ADR-074](../../docs/decisions/ADR-074-a-case-ends-in-a-decision-and-the-decision-belongs-to-the-code.md),
[ADR-076](../../docs/decisions/ADR-076-the-answer-of-the-run-is-published-whole-because-the-claims-are-extracted-from-it.md),
[ADR-077](../../docs/decisions/ADR-077-the-published-bundle-is-verified-against-the-answer-the-run-verified.md) and the
design package [LL-V3-R8-02, evidence graph and provenance](../../docs/design/advanced-specs/R8-02-evidence-graph-and-provenance.md).
The milestone that published the evidence of the verdict is
[specs/001](../001-r1-public-replay/spec.md).

The package was written for a greenfield plan. The repository has since built the evidence of the claims, the verdict
that cites it, the bundle that carries it, the provenance of the published artifact and the panel that shows it. This
specification covers the part of the package that is still missing: the graph that says how one piece of evidence
stands behind another, the resolution of a cited identifier against the source, the marking of the orphan and of the
conflict, and the coverage number that says how much of the answer the evidence holds.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The reviewer follows a claim back to the row that supports it (Priority: P1)

A reviewer reads an answer and wants to know what stands behind a claim. The graph shows the claim, the evidence it
cites, the row of the ledger or the passage of the policy or the value of the calculation behind that evidence, and
the link that says how the derivation came to be. The reviewer ends at a source they can read.

**Why this priority**: the answer of the run is published whole and its claims are extracted from it, and the
verdict of every claim names the evidence it was computed on. A claim that cannot be followed to a source is a claim
that nobody can check.

**Independent test**: build the graph of the published scenario S01 and walk it from the first claim to a leaf.
Every step of the walk is a typed edge, every leaf is a source with a reference, and every claim of the answer
reaches at least one leaf or is marked as an orphan.

### User Story 2 - A citation that names nothing is unsupported (Priority: P1)

A claim cites an identifier that no tool ever returned. The graph marks the claim as an orphan with the identifier
it names, and it does not attach the claim to the record whose text is the closest. The reviewer sees the gap
instead of a plausible neighbour.

**Why this priority**: a near match is a fabricated citation that looks right. The repository already refuses to
resolve a claim without evidence into a verdict that supports it, and the graph must not be the place where that
discipline is lost.

**Independent test**: build a graph over a run in which one claim cites an identifier that no tool returned, and
assert that the claim is marked as an orphan with that identifier, that it has no edge of support, and that no node
of the graph carries the text of the claim.

### User Story 3 - The reviewer sees the conflict between two sources (Priority: P1)

The reference rate of a case and the rate that the run used are not the same rate on the same day. The graph shows
the two nodes and the edge that says they conflict, and the reviewer sees the conflict instead of a verdict that
hides it.

**Why this priority**: a conflict that is visible is a fact a reader can act on, and a conflict that is hidden
becomes a wrong answer that looks verified.

**Independent test**: build the graph over a run whose reference rate came from a date other than the date of the
refund, and assert that the two rate nodes carry an edge of conflict, that the edge names the two sources, and that
the conflict is not folded into the verdict of the claim.

### User Story 4 - The reviewer sees the version of the policy a historical case used (Priority: P1)

The corpus of the policies has moved since the case was recorded. The graph of the historical case still points at
the document of its generation, and the edge to the current document is an explicit cross version reference, not a
silent substitution.

**Why this priority**: the index of the policies carries the digest of the corpus it was built from, and a case
that was verified against one corpus must keep pointing at that corpus.

**Independent test**: build the graph of a case recorded against one version of the corpus and read the node of the
policy, then read the graph again after the corpus moved. The node of the historical case still names the digest of
its generation, and the edge to the other version carries the kind `supersedes` or `cross_version` and names both
digests.

### User Story 5 - The reviewer reads how much of the answer the evidence holds (Priority: P2)

The graph carries a coverage number: the share of the claims that reach a source, and the share of the claims that
do not. A reader sees the number before the detail, because a graph of a case that is mostly unsupported is a
different thing from a graph of a case that is fully supported.

**Why this priority**: the coverage is the number that a reader of a public artifact needs first, and it is the
number that says whether the case is worth reading.

**Independent test**: build the graph over a run with a known number of claims and a known number of orphans, and
assert that the coverage is the exact fraction, that it is a `Decimal` and not a float, and that it names the
number of the claims it was computed over.

### User Story 6 - The graph refuses to cross an account (Priority: P2)

A visitor asks for the graph of a run that belongs to another account. The request is refused before the graph is
assembled, and the refusal says nothing about the run. The scope is applied when the data is read and not when it
is drawn.

**Why this priority**: the scope of an account is a rule of the query and not of the presentation. A graph that is
filtered at the interface shows the rows of one account inside the shape of another.

**Independent test**: ask for the graph of a run of another account and assert that the request is refused with a
code, that no node of the run appears in the answer, and that the same rule is applied by a test that reads the
graph without the interface.

### User Story 7 - The rationale of the model is a hypothesis and the graph says so (Priority: P2)

The answer of the run carries sentences that explain why. The graph holds them as what they are, a hypothesis of the
model, and never as an edge that supports a claim. A reader who follows the edges sees only the edges that the
tools and the code produced.

**Why this priority**: the numbers come from the tool and the label comes from the evidence. A graph that mixes a
sentence of the model with a row of the ledger would break that rule in the place where the reader is looking.

**Independent test**: build the graph over a run whose answer carries explanatory sentences, and assert that no
sentence of the model is a node that supports a claim, and that the nodes that carry a sentence are marked as
hypotheses.

### Edge Cases

- A claim that cites the same evidence twice: the graph holds one node for the evidence and one edge.
- An evidence that no claim cites: the node is held as an orphan of the answer and the coverage says so.
- A circular derivation: the graph refuses to build it and names the cycle, because a cycle in a derivation is not a
  proof.
- A claim whose evidence was redacted: the node says that it was redacted and why, and it never shows the original.
- A run that was never recorded: the graph is empty and says that there is nothing to trace.
- A node that belongs to another account: it is filtered when the data is read, and the count of the filtered
  nodes is published so that a reader knows that the graph is smaller than the run.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The graph is built from the trace of the run and from the evidence of the claims, and it holds nodes
  of four kinds: a claim, a piece of evidence, a source and a derived value.
  - Test: `tests/verify/test_evidence_graph.py` fails while the graph holds a node of an unknown kind.
- **FR-002**: Every edge is typed, and the types are `supports`, `contradicts`, `derived_from`, `retrieved_from`,
  `supersedes` and `in_scope_of`.
  - Test: `tests/verify/test_evidence_graph.py` fails while an edge carries a type that is not one of the six.
- **FR-003**: A cited identifier that no tool returned makes the claim an orphan, and the graph never attaches the
  claim to a record by the similarity of its text.
  - Test: `tests/verify/test_evidence_graph.py` fails while an unresolved citation is connected to a node.
- **FR-004**: Two sources that disagree make an edge of conflict, and the conflict is not folded into the verdict of
  the claim.
  - Test: `tests/verify/test_evidence_graph.py` fails while a conflict is missing or while the verdict of the claim
    changed.
- **FR-005**: The node of a policy carries the digest of the corpus it came from, and a reference to another version
  of the corpus is an explicit cross version edge.
  - Test: `tests/verify/test_evidence_graph.py` fails while the node of a policy carries no digest.
- **FR-006**: The graph carries the hash of the snapshot it was built from and a coverage number computed with
  `Decimal` over the claims it holds.
  - Test: `tests/verify/test_evidence_graph.py` fails while the coverage is a float or while it names no number of
    claims.
- **FR-007**: The scope of the account is applied when the data is read, and a node of another account never
  reaches the graph.
  - Test: `tests/verify/test_evidence_graph.py` fails while a node of another account is in the graph.
- **FR-008**: A sentence of the model is held as a hypothesis and never as a support of a claim.
  - Test: `tests/verify/test_evidence_graph.py` fails while a sentence of the model supports a claim.
- **FR-009**: The graph refuses a cycle in the derivation and names it.
  - Test: `tests/verify/test_evidence_graph.py` fails while a cycle is built.
- **FR-010**: The graph is served by id of the run, it is immutable for a given run, and two reads of the same run
  return the same bytes.
  - Test: `tests/verify/test_evidence_graph.py` fails while two reads of the same run differ.
- **FR-011**: The graph is a read over the evidence of the run and it never becomes a second source of truth about
  the verdict, and the domain never imports the API.
  - Test: `tests/verify/test_evidence_graph.py` reads the modules with `ast` and fails while a module of
    `ledgerlens/verify/` imports `ledgerlens.api`.
- **FR-012**: No graph database is added. The graph is built in memory from the trace and the bundle, and it is
  published as an artifact with a hash when it is published at all.
  - Test: `tests/verify/test_evidence_graph.py` fails while a module of `ledgerlens/` imports a graph library.

### Key Entities

- **Node**: one element of the graph, of one of the four kinds, with its reference and its digest.
- **Edge**: a typed relation between two nodes.
- **Orphan**: a claim whose cited evidence resolves to nothing.
- **Conflict**: an edge between two sources that disagree.
- **Coverage**: the share of the claims that reach a source, computed with `Decimal`.
- **Snapshot hash**: the digest of the bundle the graph was built from.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every claim of the published scenario S01 reaches a source or is marked as an orphan, and no claim is
  connected to a record by the similarity of its text.
- **SC-002**: Every edge of the graph carries one of the six types, and the graph refuses a cycle and names it.
- **SC-003**: The coverage of the published scenario is published as an exact `Decimal` over the number of the
  claims it names.
- **SC-004**: A run whose reference rate came from another date shows the conflict of the two rate nodes.
- **SC-005**: A historical case still points at the digest of the corpus of its generation, and the reference to
  another version is an explicit edge.
- **SC-006**: The number of the nodes of another account that reached a graph is zero.
- **SC-007**: Two reads of the same run return the same bytes, and the hash of the snapshot is published with the
  graph.
- **SC-008**: The graph never becomes a second source of truth: the verdict of a claim is the one the run computed,
  and the domain never imports the API.

## Assumptions

- The evidence, the claims and the verdict exist and the published bundle carries them, under ADR-073 and
  ADR-076. The graph is a read over that evidence and it does not change it.
- The repository carries no graph database and this specification adds none, as the package itself asks.
- The scope of an account is a rule of the query. The graph is built after the scope of the data was applied, and a
  node that belongs to another account never enters it.
- The rationale of the model is a hypothesis. The graph holds it and marks it, and it never lets it support a claim.
- The number of the references that resolve is a measurement of the repository and not a promise about the quality
  of the agent. The graph publishes the number it measured and the specification says that a low number is a fact
  about the run and not a defect of the graph.

## Out of scope

- The verifier and the checks of the claims, which belong to the verifier and are not changed here.
- The published bundle and the export of the site, which belong to
  [specs/001](../001-r1-public-replay/spec.md).
- The guided reader of the recording, which belongs to
  [specs/007](../007-r1-cold-start-guided-replay/spec.md).
- The review of a case by a person, which belongs to
  [specs/012](../012-r10-human-review-and-approval/spec.md).
- The cost of a run and the utility of a decision, which belong to
  [specs/011](../011-r9-cost-per-case-and-decision-utility/spec.md).
- The drawing of the graph. The first milestone serves the graph as data and the interface reads it later.

## Design documents

| Document | What it decides for this specification |
|---|---|
| [ADR-013](../../docs/decisions/ADR-013-public-trace-as-a-versioned-contract.md) | The trace of a run is a versioned contract, so the graph is built from a contract and not from a log. |
| [ADR-017](../../docs/decisions/ADR-017-export-contract-and-provenance.md) | The bundle declares its commit and the export publishes the artifacts the interface accepts, so the graph is published the same way. |
| [ADR-055](../../docs/decisions/ADR-055-the-policy-index-carries-the-hash-of-the-corpus.md) | The index carries the digest of the corpus, so a node of a policy names the corpus it came from. |
| [ADR-073](../../docs/decisions/ADR-073-the-published-bundle-carries-the-evidence-its-verdict-was-computed-on-and-it-is-reproducible.md) | The bundle carries the evidence the verdict was computed on, so the graph has its input. |
| [ADR-074](../../docs/decisions/ADR-074-a-case-ends-in-a-decision-and-the-decision-belongs-to-the-code.md) | The decision belongs to the code, so the graph shows the code and never a second verdict. |
| [ADR-076](../../docs/decisions/ADR-076-the-answer-of-the-run-is-published-whole-because-the-claims-are-extracted-from-it.md) | The answer of the run is published whole, so the claims of the graph are the claims of the answer. |
| [ADR-077](../../docs/decisions/ADR-077-the-published-bundle-is-verified-against-the-answer-the-run-verified.md) | The published bundle is verified against the answer the run verified, so the graph never contradicts the verdict. |
| [LL-V3-R8-02](../../docs/design/advanced-specs/R8-02-evidence-graph-and-provenance.md) | The design package this specification ports. |
| [specs/001](../001-r1-public-replay/spec.md) | The milestone that published the bundle with its evidence and its provenance. |

## Status

| Part | State in the repository on 2026-11-23 |
|---|---|
| The evidence of a claim | Built. `ledgerlens/schemas.py` holds `Evidence` with the pattern of its identifier, and `ledgerlens/verify/claims.py` extracts the claims and the citations. |
| The verdict and its evidence | Built. `ledgerlens/verify/checks.py` and `ledgerlens/schemas.py` hold the `Verdict` and its `evidence_ids`. |
| The published bundle with its evidence | Built. `ledgerlens/replay/bundle.py` and `ledgerlens/replay/site_export.py`, under ADR-073 and ADR-077. |
| The provenance of the published artifact | Built. `apps/web/features/shell/ProvenancePanel.tsx` and `apps/web/lib/replay/provenance.ts`. |
| The digest of the corpus of the policies | Built. `ledgerlens/retrieval.py` carries it in the meta of the index, under ADR-055. |
| The graph of the evidence | Not built. There is no relation between two pieces of evidence and no relation between a claim and the row behind it. |
| The resolution of a cited identifier against the source | Not built as a named step. The claims carry the identifiers and the tools return the evidence, but nothing resolves an identifier that resolves to nothing and marks the claim as an orphan. |
| The conflict between two sources | Not built. |
| The coverage number | Not built. |
| The endpoint that serves the graph | Not built. The facade of the sandbox and of the live run exist, and no route serves a graph. |
| A graph database | Not built and not planned. |
