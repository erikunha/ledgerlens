"""The route that serves the evidence graph of a run.

Why the facade reads the domain and the domain never imports the facade: the route reads the run, applies the
scope of the account and assembles the graph with the builder of the domain. The builder knows nothing about
the route, because a domain that imported the facade would be a domain that depends on its caller.

Why the scope of the account is applied when the data is read: the graph of a run is the graph of the account
of the run, and a reader who asks for the run of another account is refused without a word about the run. A
refusal that named the run would confirm the run exists, and the existence of a run of another account is
already a disclosure.

Why the route publishes the count of the nodes it filtered: the graph is scoped, and a reader who cannot see
the scope cannot tell a graph of the whole run from a graph of the account. The count of the filtered nodes is
the scope, in a number.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException

from ledgerlens.replay.verdict import published_result_with_claims
from ledgerlens.schemas import InvestigationResult
from ledgerlens.verify.graph import EvidenceGraph, build_graph


def _result_of(bundle_dir: Path) -> InvestigationResult:
    """The result of the run of the bundle, with the claims and the verdicts of the spans of the verifier."""
    return published_result_with_claims(bundle_dir)


def _bundle_of(bundle_root: Path, run_id: str) -> Path | None:
    """The bundle of the run, or None when no published bundle carries the run."""
    for manifest_path in sorted(bundle_root.glob("*/manifest.json")):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if manifest.get("run_id") == run_id:
            return manifest_path.parent
    return None


def _account_of(bundle_dir: Path) -> str | None:
    """The account of the run of the bundle, as the artifact of the ledger names it."""
    ledger_path = bundle_dir.parent / "ledger" / f"{bundle_dir.name}.json"
    if not ledger_path.is_file():
        return None
    try:
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    accounts = ledger.get("accounts", [])
    return str(accounts[0]["id"]) if accounts else None


def _records_of_the_account(bundle_dir: Path, account: str) -> set[str]:
    """The records of the account, as the rows of the artifact of the ledger name them.

    Why the rows and not the reads: the rows of the account are the records the account holds, and the reads
    are what the run read. A read that names a record the account does not hold is a read out of the scope of
    the account, and the scope is judged against the rows.
    """
    ledger_path = bundle_dir.parent / "ledger" / f"{bundle_dir.name}.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    records: set[str] = set()
    for entry in ledger.get("accounts", []):
        if entry.get("id") != account:
            continue
        for row in entry.get("rows", []):
            records.add(str(row.get("id")))
    return records


def _records_of_each_read(bundle_dir: Path) -> dict[str, set[str]]:
    """The records each read of the ledger named, by the citation of the read, as the artifact names them."""
    ledger_path = bundle_dir.parent / "ledger" / f"{bundle_dir.name}.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    reads: dict[str, set[str]] = {}
    for entry in ledger.get("accounts", []):
        for read in entry.get("reads", []):
            reads[str(read.get("evidence_id"))] = {str(record) for record in read.get("records", [])}
    return reads


def _graph_dict(graph: EvidenceGraph) -> dict[str, Any]:
    """The graph as the route publishes it, with sorted keys so that two reads are byte identical."""
    return {
        "nodes": [
            {
                "id": node.id,
                "kind": node.kind,
                "label": node.label,
                "digest": node.digest,
                "hypothesis": node.hypothesis,
            }
            for node in graph.nodes
        ],
        "edges": [{"source": edge.source, "target": edge.target, "kind": edge.kind} for edge in graph.edges],
        "verdicts": dict(sorted(graph.verdicts.items())),
        "orphans": list(graph.orphans),
        "conflicts": list(graph.conflicts),
        "coverage": {
            "claims": graph.coverage.claims,
            "reached": graph.coverage.reached,
            "share": str(graph.coverage.share),
        },
        "snapshot_hash": graph.snapshot_hash,
    }


def create_app(bundle_root: Path) -> FastAPI:
    """The application of the evidence graph, over the published bundles of the runs."""
    app = FastAPI(title="LedgerLens evidence graph")
    index_meta = bundle_root.parents[2] / "index" / "policies_fastembed" / "index_meta.json"

    @app.get("/evidence/{run_id}")
    def evidence_graph(run_id: str, account: str) -> dict[str, Any]:
        bundle_dir = _bundle_of(bundle_root, run_id)
        if bundle_dir is None:
            raise HTTPException(status_code=404, detail="the run was not found")
        # The scope of the account is applied when the data is read: a run of another account is refused with
        # a reason that says nothing about the run.
        if _account_of(bundle_dir) != account:
            raise HTTPException(status_code=404, detail="the run was not found")

        result = _result_of(bundle_dir)
        # The scope of the account: an evidence of the ledger is in the graph when every record it names
        # belongs to the account, and an evidence that names a record of another account is out of the graph.
        # The count of the nodes it filtered is published.
        records = _records_of_the_account(bundle_dir, account)
        reads = _records_of_each_read(bundle_dir)
        in_scope = []
        filtered = 0
        for evidence in result.evidence:
            if evidence.source_type in ("sql", "ledger_api"):
                named = reads.get(evidence.id, set())
                if named and not named <= records:
                    filtered += 1
                    continue
            in_scope.append(evidence)
        result.evidence = in_scope

        corpus_digest = ""
        if index_meta.is_file():
            corpus_digest = str(json.loads(index_meta.read_text(encoding="utf-8")).get("corpus_sha256", ""))
        manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
        graph = build_graph(
            result,
            corpus_digest=corpus_digest,
            snapshot_hash=str(manifest.get("snapshot_sha256", "")),
        )
        body = _graph_dict(graph)
        body["filtered"] = filtered
        return body

    return app
