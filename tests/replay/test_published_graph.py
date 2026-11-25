"""The published graph of a bundle: the artifact, its hash and the refusal of a bundle that moved.

What they guarantee, and why: (a) the export of the graph is byte identical when it runs twice, because the
artifact is a publication and a publication whose bytes move is not a publication; (b) the artifact carries the
hash of the snapshot it was built from and the hash of the bundle, so a reader checks the artifact against the
bundle and the bundle against the ledger; (c) the export refuses a bundle whose digest moved, because a bundle
that is not the recording the artifact names is a bundle the artifact cannot be built from.

Everything here runs offline, with no key and with no network. The fixture is the published bundle of the
scenario S01 under `data/eval/replay/s01/`.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from ledgerlens.replay.bundle import BundleError
from ledgerlens.replay.graph_artifact import build_graph_artifact, render_graph_artifact

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "data" / "eval" / "replay" / "s01"
INDEX_META = ROOT / "data" / "index" / "policies_fastembed" / "index_meta.json"


def _corpus_digest() -> str:
    return str(json.loads(INDEX_META.read_text(encoding="utf-8"))["corpus_sha256"])


def test_the_export_of_the_graph_is_byte_identical_when_it_runs_twice() -> None:
    """The artifact is a publication, and a publication whose bytes move is not a publication."""
    first = render_graph_artifact(build_graph_artifact(BUNDLE, corpus_digest=_corpus_digest()))
    second = render_graph_artifact(build_graph_artifact(BUNDLE, corpus_digest=_corpus_digest()))

    assert first == second


def test_the_artifact_carries_the_hash_of_the_snapshot_and_of_the_bundle() -> None:
    """A reader checks the artifact against the bundle and the bundle against the ledger."""
    artifact = build_graph_artifact(BUNDLE, corpus_digest=_corpus_digest())

    manifest = json.loads((BUNDLE / "manifest.json").read_text(encoding="utf-8"))
    assert artifact["snapshot_hash"] == manifest["snapshot_sha256"]
    assert artifact["bundle_digest"]
    assert artifact["corpus_digest"] == _corpus_digest()
    assert artifact["graph"]["nodes"]


def test_the_export_refuses_a_bundle_whose_digest_moved(tmp_path: Path) -> None:
    """A bundle that is not the recording the artifact names is a bundle the artifact cannot be built from."""
    moved = tmp_path / "s01"
    shutil.copytree(BUNDLE, moved)
    events = moved / "events.jsonl"
    events.write_text(events.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(BundleError):
        build_graph_artifact(moved, corpus_digest=_corpus_digest())
