"""The evidence graph of a run: the relation between the claims, the evidence and the sources.

Why the graph is a read over the evidence of the run and never a second verdict: the graph is built from what
the run published, the claims, the evidence and the verdicts, and it relates them. The verdict of a claim of
the graph is the verdict of the run, read and never recomputed, because a graph that decided again would be a
second verifier, and two verifiers of the same run would disagree one day.

Why a citation that resolves to nothing is an orphan and never a near match: the citation names one piece of
evidence, and a citation that names nothing the run carries says something about the run, and the graph says it
with the orphan. A near match would connect the claim to a piece it did not cite, and a connection the run did
not make is a connection that proves nothing.

Why a sentence of the model is a hypothesis: a claim with no evidence behind it is a sentence of the model, and
the graph holds it as a hypothesis. A hypothesis supports nothing, because a sentence that nothing backs is a
sentence that proves nothing.

Why the coverage is a fraction of counts and not a float: the coverage is the share of the claims that reach a
source, and a share is a count over a count. A float would round the share, and the rounded share of a count is
not the count. The coverage names the hash of the snapshot the graph was built from, so a reader knows which
ledger the graph read.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from ledgerlens.schemas import InvestigationResult

# The four kinds of node of the graph.
NODE_CLAIM = "claim"
NODE_EVIDENCE = "evidence"
NODE_SOURCE = "source"
NODE_POLICY = "policy"
NODE_KINDS = frozenset({NODE_CLAIM, NODE_EVIDENCE, NODE_SOURCE, NODE_POLICY})

# The six kinds of edge of the graph.
EDGE_SUPPORTS = "supports"
EDGE_CONTRADICTS = "contradicts"
EDGE_DERIVED_FROM = "derived_from"
EDGE_RETRIEVED_FROM = "retrieved_from"
EDGE_SUPERSEDES = "supersedes"
EDGE_IN_SCOPE_OF = "in_scope_of"
EDGE_KINDS = frozenset(
    {EDGE_SUPPORTS, EDGE_CONTRADICTS, EDGE_DERIVED_FROM, EDGE_RETRIEVED_FROM, EDGE_SUPERSEDES, EDGE_IN_SCOPE_OF}
)


class GraphError(Exception):
    """The graph cannot be built, and the message says why."""


@dataclass(frozen=True)
class GraphNode:
    """One node of the graph: the identifier, the kind, the label, and the marks of the kind."""

    id: str
    kind: str
    label: str
    digest: str | None = None
    hypothesis: bool = False


@dataclass(frozen=True)
class GraphEdge:
    """One edge of the graph: the source, the target and the kind."""

    source: str
    target: str
    kind: str


@dataclass(frozen=True)
class Coverage:
    """The coverage of the graph: the share of the claims that reach a source, as a fraction of counts."""

    claims: int
    reached: int

    @property
    def share(self) -> Decimal:
        """The share of the claims that reach a source, as a Decimal and never as a float."""
        if self.claims == 0:
            return Decimal(0)
        return Decimal(self.reached) / Decimal(self.claims)


@dataclass(frozen=True)
class EvidenceGraph:
    """The graph of a run: the nodes, the edges, the verdicts, the orphans, the conflicts and the coverage."""

    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]
    verdicts: dict[str, str]
    orphans: tuple[str, ...]
    conflicts: tuple[str, ...]
    coverage: Coverage
    snapshot_hash: str


def _source_id_of(evidence_id: str, source_type: str, ref: str) -> str:
    """The identifier of the source of one piece of evidence.

    The source of a read of the ledger is the ledger, the source of a rate is the rate of the day and of the
    pair, and the source of a calculation is the calculation. The policy evidence has a node of its own, and it
    never comes here.
    """
    if source_type in ("sql", "api"):
        return "ledger"
    if source_type == "fx":
        return f"fx:{ref}"
    if source_type == "calc":
        return "calculation"
    if source_type == "case":
        return "case-memory"
    return f"source:{evidence_id}"


def build_graph(
    result: InvestigationResult,
    *,
    corpus_digest: str,
    snapshot_hash: str,
    historical_digests: Mapping[str, str] | None = None,
) -> EvidenceGraph:
    """Builds the graph of a run from what the run published.

    The claims, the evidence and the verdicts of the run are the input, and the graph relates them. The
    `historical_digests` names the digest of the corpus of the generation of a policy a historical case cited,
    so that a policy of a historical case that names another digest is linked to the current one with an
    explicit cross version edge.
    """
    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []
    orphans: list[str] = []
    conflicts: list[str] = []
    historical_digests = historical_digests or {}

    snapshot_id = f"snapshot:{snapshot_hash}"
    nodes[snapshot_id] = GraphNode(id=snapshot_id, kind=NODE_SOURCE, label=f"the snapshot {snapshot_hash[:12]}")

    evidence_ids = {evidence.id for evidence in result.evidence}

    # The nodes of the evidence: a policy evidence is a policy node with the digest of the corpus, and the
    # other evidence is an evidence node with a source node and a `retrieved_from` edge.
    policy_chunks: dict[str, list[str]] = {}
    for evidence in result.evidence:
        if evidence.source_type == "policy":
            digest = historical_digests.get(evidence.id, corpus_digest)
            nodes[evidence.id] = GraphNode(id=evidence.id, kind=NODE_POLICY, label=evidence.ref, digest=digest)
            policy_chunks.setdefault(evidence.ref, []).append(evidence.id)
            continue
        nodes[evidence.id] = GraphNode(id=evidence.id, kind=NODE_EVIDENCE, label=evidence.id)
        source_id = _source_id_of(evidence.id, evidence.source_type, evidence.ref)
        if source_id not in nodes:
            nodes[source_id] = GraphNode(id=source_id, kind=NODE_SOURCE, label=source_id)
        edges.append(GraphEdge(source=evidence.id, target=source_id, kind=EDGE_RETRIEVED_FROM))

    # The cross version edge: two policy nodes of the same chunk with two digests are two versions of the
    # chunk, and the current one supersedes the historical one explicitly.
    for node_ids in policy_chunks.values():
        digests = {nodes[node_id].digest for node_id in node_ids}
        if len(digests) > 1:
            current = next((node_id for node_id in node_ids if nodes[node_id].digest == corpus_digest), None)
            for node_id in node_ids:
                if node_id != current and current is not None:
                    edges.append(GraphEdge(source=current, target=node_id, kind=EDGE_SUPERSEDES))

    # The nodes of the claims, the hypothesis of the ones with no evidence, and the orphans of the citations
    # that resolve to nothing.
    verdicts = {verdict.claim_id: verdict.label for verdict in result.verdicts}
    for claim in result.claims:
        hypothesis = not claim.evidence_ids
        nodes[claim.id] = GraphNode(id=claim.id, kind=NODE_CLAIM, label=claim.text[:80], hypothesis=hypothesis)
        for evidence_id in claim.evidence_ids:
            if evidence_id not in evidence_ids:
                # A citation that resolves to nothing is an orphan, and it is never connected to a node.
                if claim.id not in orphans:
                    orphans.append(claim.id)
                continue
            edges.append(GraphEdge(source=evidence_id, target=claim.id, kind=EDGE_SUPPORTS))
        if claim.numeric is not None and claim.numeric.calc_evidence_id in evidence_ids:
            edges.append(GraphEdge(source=claim.id, target=claim.numeric.calc_evidence_id, kind=EDGE_DERIVED_FROM))

    # The verdicts of the run: a contradicted claim has a `contradicts` edge, and a claim with both marks is a
    # conflict the graph names.
    for verdict in result.verdicts:
        if verdict.label == "contradicted":
            for evidence_id in verdict.evidence_ids:
                if evidence_id in evidence_ids:
                    edges.append(GraphEdge(source=evidence_id, target=verdict.claim_id, kind=EDGE_CONTRADICTS))
    for claim in result.claims:
        kinds = {edge.kind for edge in edges if edge.target == claim.id}
        if EDGE_SUPPORTS in kinds and EDGE_CONTRADICTS in kinds:
            conflicts.append(claim.id)

    # The derivation of a piece of evidence: the reference of a calculation names what it was computed from,
    # and when the reference names a claim or another piece of evidence, the derivation is an edge.
    claim_ids = {claim.id for claim in result.claims}
    for evidence in result.evidence:
        if evidence.source_type != "calc":
            continue
        if evidence.ref in claim_ids or evidence.ref in evidence_ids:
            edges.append(GraphEdge(source=evidence.id, target=evidence.ref, kind=EDGE_DERIVED_FROM))

    # The scope: every node is in the scope of the snapshot the graph was built from.
    for node_id in list(nodes):
        if node_id != snapshot_id:
            edges.append(GraphEdge(source=node_id, target=snapshot_id, kind=EDGE_IN_SCOPE_OF))

    _refuse_a_cycle(edges)

    # The coverage: the claims that reach a source, over the claims the run verified.
    reached = 0
    for claim_id in verdicts:
        supported = [edge.source for edge in edges if edge.target == claim_id and edge.kind == EDGE_SUPPORTS]
        if any(nodes[source].kind in (NODE_SOURCE, NODE_POLICY) for source in supported) or any(
            any(
                edge2.target == source or edge2.source == source
                for edge2 in edges
                if edge2.kind == EDGE_RETRIEVED_FROM and edge2.source == source
            )
            for source in supported
        ):
            reached += 1
    coverage = Coverage(claims=len(verdicts), reached=reached)

    return EvidenceGraph(
        nodes=tuple(nodes.values()),
        edges=tuple(edges),
        verdicts=verdicts,
        orphans=tuple(orphans),
        conflicts=tuple(conflicts),
        coverage=coverage,
        snapshot_hash=snapshot_hash,
    )


def _refuse_a_cycle(edges: list[GraphEdge]) -> None:
    """Refuses a cycle in the derivation: a derivation that goes in a circle derives nothing."""
    derivation: dict[str, list[str]] = {}
    for edge in edges:
        if edge.kind == EDGE_DERIVED_FROM:
            derivation.setdefault(edge.source, []).append(edge.target)

    visited: set[str] = set()
    stack: set[str] = set()

    def walk(node: str) -> None:
        if node in stack:
            raise GraphError(f"the derivation of the graph goes in a circle at {node}")
        if node in visited:
            return
        stack.add(node)
        for target in derivation.get(node, []):
            walk(target)
        stack.discard(node)
        visited.add(node)

    for node in list(derivation):
        walk(node)
