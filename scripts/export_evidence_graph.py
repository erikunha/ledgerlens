#!/usr/bin/env python3
"""Exports the evidence graph of a published bundle as an artifact, beside the bundle it was built from.

Why it exists: the graph of a run is the relation between the claims, the evidence and the sources, and the
graph of a published bundle is published as an artifact with a manifest and a hash, so a reader checks the
graph against the bundle and the bundle against the ledger. The export copies, hashes and labels and never
changes the recorded content, and it refuses a bundle whose digest moved.

Usage:

```bash
uv run python scripts/export_evidence_graph.py --bundle data/eval/replay/s01 [--out data/eval/replay/graph]
```

Exit code 0 when the artifact was written, 1 when it could not be.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ledgerlens.replay.bundle import BundleError  # noqa: E402
from ledgerlens.replay.graph_artifact import artifact_digest, build_graph_artifact, render_graph_artifact  # noqa: E402

INDEX_META = ROOT / "data" / "index" / "policies_fastembed" / "index_meta.json"


def main() -> int:
    """Runs the command and returns the exit code of the answer."""
    parser = argparse.ArgumentParser(description="Exports the evidence graph of a published bundle.")
    parser.add_argument("--bundle", required=True, help="the folder of the bundle")
    parser.add_argument("--out", default=None, help="the folder of the artifact (by default <bundles>/graph)")
    args = parser.parse_args()

    bundle_dir = Path(args.bundle)
    corpus_digest = ""
    if INDEX_META.is_file():
        corpus_digest = str(json.loads(INDEX_META.read_text(encoding="utf-8")).get("corpus_sha256", ""))

    try:
        artifact = build_graph_artifact(bundle_dir, corpus_digest=corpus_digest)
    except BundleError as exc:
        print(f"export_evidence_graph: the bundle was refused: {exc}", file=sys.stderr)
        return 1

    out_dir = Path(args.out) if args.out else bundle_dir.parent / "graph"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{bundle_dir.name}.json"
    path.write_bytes(render_graph_artifact(artifact))
    print(f"the graph of the bundle was written: {path}")
    print(f"sha256 of the artifact: {artifact_digest(artifact)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
