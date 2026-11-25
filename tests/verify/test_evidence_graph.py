"""The evidence graph of a run: the relation between the claims, the evidence and the sources.

What they guarantee, and why: (a) a node of an unknown kind and an edge of an unknown type are refused, and the
six types of the edge are the six of the contract; (b) a cycle in the derivation is refused, because a
derivation that goes in a circle derives nothing; (c) a node of a policy carries the digest of the corpus, and
a policy of a historical case that names another digest is linked to the current one with an explicit
cross version edge; (d) a citation that resolves to nothing makes an orphan and never a near match, and a
sentence of the model is held as a hypothesis and supports no claim; (e) the verdict of a claim of the graph is
the verdict of the bundle, because the graph is a read and never a second verdict; (f) the coverage is a
fraction of counts with `Decimal`, and the graph names the hash of the snapshot it was built from; (g) no
module of the repository imports a graph library, and no module of the verifier imports the facade.

Everything here runs offline, with no key and with no network. The fixture is the published bundle of the
scenario S01 under `data/eval/replay/s01/`.
"""

from __future__ import annotations

import ast
import json
import re
from decimal import Decimal
from pathlib import Path

import pytest

from ledgerlens.replay.verdict import published_result
from ledgerlens.schemas import Claim, Verdict
from ledgerlens.verify.graph import (
    EDGE_KINDS,
    NODE_KINDS,
    GraphError,
    build_graph,
)

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "data" / "eval" / "replay" / "s01"
INDEX_META = ROOT / "data" / "index" / "policies_fastembed" / "index_meta.json"


def _corpus_digest() -> str:
    return str(json.loads(INDEX_META.read_text(encoding="utf-8"))["corpus_sha256"])


def _snapshot_hash() -> str:
    manifest = json.loads((BUNDLE / "manifest.json").read_text(encoding="utf-8"))
    return str(manifest["snapshot_sha256"])


def _result():
    """The result of the run of the bundle, with the claims and the verdicts of the spans of the verifier."""
    result = published_result(BUNDLE)
    events = [
        json.loads(line)
        for line in (BUNDLE / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    for event in events:
        payload = event.get("payload", {})
        name = str(payload.get("name") or "")
        if not re.match(r"^CL\d+$", name) or event.get("event_type") != "span.ended":
            continue
        outputs = payload.get("outputs", {})
        claim_id = str(outputs["claim_id"])
        evidence_ids = [str(item) for item in outputs.get("evidence_ids", [])]
        result.claims.append(Claim(id=claim_id, text=claim_id, kind="fact", evidence_ids=evidence_ids))
        result.verdicts.append(
            Verdict(
                claim_id=claim_id,
                label=str(outputs["label"]),
                method=str(outputs.get("method") or "nli"),
                evidence_ids=evidence_ids,
            )
        )
    return result


def _graph():
    result = _result()
    return result, build_graph(result, corpus_digest=_corpus_digest(), snapshot_hash=_snapshot_hash())


def test_the_nodes_and_the_edges_are_of_the_kinds_of_the_contract() -> None:
    """A node of an unknown kind and an edge of an unknown type are refused."""
    _, graph = _graph()

    assert graph.nodes
    for node in graph.nodes:
        assert node.kind in NODE_KINDS, f"the node {node.id} is of the unknown kind {node.kind}"
    for edge in graph.edges:
        assert edge.kind in EDGE_KINDS, f"the edge {edge.source}->{edge.target} is of the unknown type {edge.kind}"
    assert EDGE_KINDS == frozenset(
        {"supports", "contradicts", "derived_from", "retrieved_from", "supersedes", "in_scope_of"}
    )


def test_a_node_of_a_policy_carries_the_digest_of_the_corpus() -> None:
    """A policy node without the digest of the corpus is a policy that cannot be checked."""
    _, graph = _graph()

    policies = [node for node in graph.nodes if node.kind == "policy"]
    assert policies, "the graph of S01 holds no policy node"
    for node in policies:
        assert node.digest == _corpus_digest()


def test_a_citation_that_resolves_to_nothing_makes_an_orphan_and_never_a_near_match() -> None:
    """An unresolved citation is an orphan, and it is never connected to a node."""
    result = _result()
    # A claim whose citation names an evidence the run does not carry.
    result.claims.append(
        Claim(
            id="CL99",
            text="a claim with a citation that resolves to nothing",
            kind="fact",
            evidence_ids=["sql:99"],
        )
    )
    graph = build_graph(result, corpus_digest=_corpus_digest(), snapshot_hash=_snapshot_hash())

    assert "CL99" in graph.orphans
    # The unresolved citation is connected to nothing: no edge names the missing evidence.
    assert all(edge.source != "sql:99" and edge.target != "sql:99" for edge in graph.edges)


def test_a_sentence_of_the_model_is_a_hypothesis_and_supports_no_claim() -> None:
    """A claim with no evidence behind it is held as a hypothesis, and it supports nothing."""
    result = _result()
    result.claims.append(
        Claim(id="CL98", text="a sentence of the model with no evidence", kind="fact", evidence_ids=[])
    )
    graph = build_graph(result, corpus_digest=_corpus_digest(), snapshot_hash=_snapshot_hash())

    hypothesis = next(node for node in graph.nodes if node.id == "CL98")
    assert hypothesis.kind == "claim"
    assert hypothesis.hypothesis is True
    # The hypothesis supports no claim: no edge leaves it but the scope.
    assert all(edge.source != "CL98" or edge.kind == "in_scope_of" for edge in graph.edges)


def test_the_verdict_of_a_claim_of_the_graph_is_the_verdict_of_the_bundle() -> None:
    """The graph is a read over the evidence of the run, and it never becomes a second verdict."""
    result, graph = _graph()
    labels = {verdict.claim_id: verdict.label for verdict in result.verdicts}

    assert graph.verdicts
    for claim_id, label in graph.verdicts.items():
        assert labels[claim_id] == label


def test_the_coverage_is_a_fraction_of_counts_and_names_the_snapshot() -> None:
    """The coverage is a fraction of counts with Decimal, and the graph names the snapshot it was built from."""
    _, graph = _graph()

    assert graph.coverage.claims == len(graph.verdicts)
    assert 0 <= graph.coverage.reached <= graph.coverage.claims
    assert graph.coverage.share == Decimal(graph.coverage.reached) / Decimal(graph.coverage.claims)
    assert graph.snapshot_hash == _snapshot_hash()


def test_a_cycle_in_the_derivation_is_refused() -> None:
    """A derivation that goes in a circle derives nothing."""
    result = _result()
    from ledgerlens.schemas import NumericClaim

    # Two claims whose calculations derive from each other: a cycle.
    result.claims.append(
        Claim(
            id="CL97",
            text="a amount that derives from CL96",
            kind="numeric",
            evidence_ids=[],
            numeric=NumericClaim(expected=Decimal("1"), unit="BRL", calc_evidence_id="calc:97"),
        )
    )
    result.claims.append(
        Claim(
            id="CL96",
            text="a amount that derives from CL97",
            kind="numeric",
            evidence_ids=[],
            numeric=NumericClaim(expected=Decimal("1"), unit="BRL", calc_evidence_id="calc:96"),
        )
    )
    from ledgerlens.schemas import Evidence

    result.evidence.append(
        Evidence(
            id="calc:97",
            source_type="calc",
            tool="calculate",
            content="a",
            ref="CL96",
            retrieved_at=result.evidence[0].retrieved_at,
        )
    )
    result.evidence.append(
        Evidence(
            id="calc:96",
            source_type="calc",
            tool="calculate",
            content="b",
            ref="CL97",
            retrieved_at=result.evidence[0].retrieved_at,
        )
    )

    with pytest.raises(GraphError):
        build_graph(result, corpus_digest=_corpus_digest(), snapshot_hash=_snapshot_hash())


def test_no_module_of_the_repository_imports_a_graph_library() -> None:
    """The graph is built in memory, and no graph database is added."""
    forbidden = {"networkx", "graphviz", "neo4j", "rdflib", "igraph"}
    for module in (ROOT / "ledgerlens").rglob("*.py"):
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] not in forbidden, f"{module} imports {alias.name}"
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] not in forbidden, f"{module} imports {node.module}"


def test_no_module_of_the_verifier_imports_the_facade() -> None:
    """The domain never imports the facade."""
    for module in (ROOT / "ledgerlens" / "verify").rglob("*.py"):
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("ledgerlens.api"), f"{module} imports {node.module}"
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("ledgerlens.api"), f"{module} imports {alias.name}"


def test_a_policy_of_a_historical_case_names_another_digest_with_an_explicit_cross_version_edge() -> None:
    """A policy of a historical case that names another digest of the corpus is linked to the current one."""
    from ledgerlens.schemas import Evidence

    result = _result()
    chunk = "cross-currency-refunds#overview"
    historical_id = "policy:cross-currency-refunds#overview:generation-of-the-case"
    result.evidence.append(
        Evidence(
            id=historical_id,
            source_type="policy",
            tool="search_policies",
            content="the chunk as the corpus of the case had it",
            ref=chunk,
            retrieved_at=result.evidence[0].retrieved_at,
        )
    )
    graph = build_graph(
        result,
        corpus_digest=_corpus_digest(),
        snapshot_hash=_snapshot_hash(),
        historical_digests={historical_id: "f" * 64},
    )

    historical = next(node for node in graph.nodes if node.id == historical_id)
    assert historical.digest == "f" * 64
    current = next(
        node for node in graph.nodes if node.kind == "policy" and node.label == chunk and node.id != historical_id
    )
    assert current.digest == _corpus_digest()
    assert any(
        edge.kind == "supersedes" and edge.source == current.id and edge.target == historical_id
        for edge in graph.edges
    ), "the policy of the historical case names another digest without an explicit cross version edge"
