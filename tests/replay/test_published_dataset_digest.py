"""The digest of the dataset that every published bundle declares: the check the gate was missing.

What it proves, and why: the `dataset_sha256` of every published bundle is the sha256 of `data/scenarios.json`
of the repository now, so a bundle that was published against another dataset is refused by the gate. The
digest was in the published files and nothing compared it with the dataset, so it was a number that only the
export wrote.

Why the published set and not the export: the export copies the digest of the dataset it read, so a check of
the export proves that the export is honest and not that the published set is. The published set is what the
visitor downloads, and it is the one that can go stale without anybody noticing.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "data" / "scenarios.json"
PUBLISHED = ROOT / "site" / "replay"

# The nine scenarios the catalog publishes, in the order of the index.
SCENARIOS = ("s01", "s02", "s03", "s04", "s07", "s08", "s09", "s10", "s11")

__all__ = ["test_every_published_bundle_declares_the_digest_of_the_dataset_of_the_repository"]


def test_every_published_bundle_declares_the_digest_of_the_dataset_of_the_repository():
    """The digest of the dataset of every published bundle is the digest of the dataset of the repository.

    Why every scenario and not only the first one: the catalog publishes nine recordings, and a check that read
    one of them would let the other eight carry the digest of a dataset that is not the one of the repository.
    """
    digest = hashlib.sha256(DATASET.read_bytes()).hexdigest()

    for slug in SCENARIOS:
        provenance = json.loads((PUBLISHED / slug / "provenance.json").read_text(encoding="utf-8"))
        assert provenance["dataset_sha256"] == digest, (
            f"the bundle of {slug} declares the digest of another dataset"
        )
