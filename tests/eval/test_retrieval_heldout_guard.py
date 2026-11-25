"""The guard of the held out set of the retrieval: a tuning script that reads it is refused.

What they guarantee, and why: the held out set of the retrieval carries the role `held_out` in the manifest,
the guard of the tuning refuses a tuning against it, and the guard refuses the path of the set and the paths
of its sources, because a set that a tuning script may read is a set that a threshold may be chosen against,
and the held out set exists so that no decision is ever taken against it.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import pytest

from ledgerlens.eval.manifest import (
    TuningRefusal,
    load_manifests,
    may_be_tuned_against,
    require_tuning_dataset,
    require_tuning_path,
)


def test_the_held_out_set_of_the_retrieval_carries_the_role_held_out() -> None:
    """The set is declared in the manifest with the role that reserves it for the final scoring."""
    manifests = load_manifests()
    entry = next(manifest for manifest in manifests if manifest.dataset_id == "retrieval_heldout")

    assert entry.split_role == "held_out"
    assert entry.records_count == 16


def test_the_guard_refuses_a_tuning_against_the_held_out_set_of_the_retrieval() -> None:
    """A tuning script that asks for the set is refused, with a readable reason."""
    manifests = load_manifests()

    assert not may_be_tuned_against("retrieval_heldout", manifests)
    with pytest.raises(TuningRefusal):
        require_tuning_dataset("retrieval_heldout", manifests)


def test_the_guard_refuses_the_path_of_the_set_and_the_paths_of_its_sources() -> None:
    """The set and the files it is rebuilt from are reserved, whatever role a hand edit gives them."""
    manifests = load_manifests()

    for path in (
        "data/eval/retrieval_heldout.jsonl",
        "data/eval/heldout/retrieval_cases.jsonl",
        "data/eval/heldout/retrieval_recipes.jsonl",
        "data/eval/heldout/retrieval_labels_reader_a.jsonl",
        "data/eval/heldout/retrieval_labels_reader_b.jsonl",
        "data/eval/heldout/retrieval_labels_adjudicated.jsonl",
    ):
        with pytest.raises(TuningRefusal):
            require_tuning_path(path, manifests)
