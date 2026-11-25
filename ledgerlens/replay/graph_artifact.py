"""The artifact of the evidence graph of a published bundle.

Why the export copies, hashes and labels and never changes the recorded content: the graph of a published
bundle is built from the bundle, and the bundle is the recording. The export reads the bundle, builds the
graph, and writes the artifact beside the bundle, and it never writes into the bundle. The artifact carries
the hash of the bundle it was built from and the hash of the snapshot the graph read, so a reader checks the
artifact against the bundle and the bundle against the ledger.

Why the export refuses a bundle whose digest moved: the digest of the bundle is the name of the recording, and
a bundle whose files moved is a bundle that is not the recording the artifact names. The loader of the bundle
verifies the digests of the files, and the export refuses the bundle the loader refuses.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ledgerlens.replay.bundle import bundle_digest, load_bundle
from ledgerlens.replay.verdict import published_result_with_claims
from ledgerlens.verify.graph import EvidenceGraph, build_graph

# The version of the schema of the artifact, so that a reader of a later version knows the artifact is not of
# its version.
ARTIFACT_SCHEMA_VERSION = "1"


def _graph_dict(graph: EvidenceGraph) -> dict[str, Any]:
    """The graph as the artifact carries it, with sorted keys so that two exports are byte identical."""
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


def build_graph_artifact(bundle_dir: Path, *, corpus_digest: str) -> dict[str, Any]:
    """The artifact of the graph of the bundle: the graph, the hash of the bundle and the hash of the snapshot.

    The loader of the bundle verifies the digests of the files, so a bundle whose digest moved is refused here,
    before the graph is built.
    """
    manifest, _events = load_bundle(bundle_dir)
    result = published_result_with_claims(bundle_dir)
    graph = build_graph(
        result,
        corpus_digest=corpus_digest,
        snapshot_hash=str(manifest.snapshot_sha256 or ""),
    )
    return {
        "artifact": "evidence_graph",
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "scenario": str(manifest.scenario),
        "run_id": str(manifest.run_id),
        "bundle_digest": bundle_digest(bundle_dir),
        "snapshot_hash": str(manifest.snapshot_sha256 or ""),
        "corpus_digest": corpus_digest,
        "graph": _graph_dict(graph),
    }


def render_graph_artifact(artifact: dict[str, Any]) -> bytes:
    """The bytes of the artifact, canonical: two exports of the same bundle are byte identical."""
    return (json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def artifact_digest(artifact: dict[str, Any]) -> str:
    """The hash of the artifact, over the canonical bytes."""
    return hashlib.sha256(render_graph_artifact(artifact)).hexdigest()
