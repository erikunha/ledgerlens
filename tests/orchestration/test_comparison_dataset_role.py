"""The role of the set of the comparison: only the final scoring reads it.

What they guarantee, and why: (a) the set of the comparison carries the role that the manifest of the datasets gives
it, and the role is `held_out`, so a tuning script that reads it is refused; (b) the refusal names the dataset and
the rule it breaks, so the reader of the log knows what to do next; (c) the path of the manifest is reserved in the
code of the guard, so a copy of it under another name is refused too.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import pytest

from ledgerlens.eval.manifest import (
    HELD_OUT_RESERVED_PATHS,
    MANIFEST_PATH,
    TuningRefusal,
    load_manifests,
    may_be_tuned_against,
    require_tuning_dataset,
)

DATASET_ID = "orchestration_comparison"


def test_the_set_of_the_comparison_carries_the_role_the_manifest_gives_it() -> None:
    """The role of the set of the comparison is `held_out`, so only the final scoring reads it."""
    manifests = load_manifests(MANIFEST_PATH)
    entry = next(manifest for manifest in manifests if manifest.dataset_id == DATASET_ID)

    assert entry.split_role == "held_out"


def test_a_tuning_script_that_reads_the_set_of_the_comparison_is_refused() -> None:
    """The guard of the tuning refuses and the refusal names the dataset and the rule."""
    manifests = load_manifests(MANIFEST_PATH)

    assert may_be_tuned_against(DATASET_ID, manifests) is False
    with pytest.raises(TuningRefusal) as refusal:
        require_tuning_dataset(DATASET_ID, manifests)

    message = str(refusal.value)
    assert DATASET_ID in message
    assert "held_out" in message


def test_the_path_of_the_manifest_of_the_comparison_is_reserved_in_the_code() -> None:
    """A copy of the manifest under another name is refused: the reservation is of the path and of the digest."""
    assert "data/runtime/orchestration/comparison.json" in HELD_OUT_RESERVED_PATHS
