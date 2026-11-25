"""The status of the artifact: draft with the name of the missing evidence, and verified when it is all there.

What they guarantee, and why: the status is `draft` with the name of the missing evidence when the digest of
the dataset is removed, a `draft` artifact carries no verified badge, and the status is `verified` for a
complete bundle, because no person promotes an artifact by hand and a badge that a missing digest does not
remove means nothing.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from dataclasses import replace

from ledgerlens.proof.provenance import provenance_of
from ledgerlens.proof.status import DRAFT, VERIFIED, status_of


def test_a_complete_bundle_is_verified(bundle_replay, dataset, root) -> None:
    """The four conditions of the verified status hold for a bundle of the published catalog."""
    provenance = provenance_of(bundle_replay, catalog="replay", dataset_path=dataset, root=root)
    status = status_of(provenance, reverified=True, root=root)

    assert status.value == VERIFIED
    assert status.is_verified
    assert status.missing == ()


def test_an_artifact_without_the_digest_of_the_dataset_is_a_draft_that_names_it(bundle_replay, dataset, root) -> None:
    """The digest of the dataset is one of the four conditions, and the draft names it."""
    provenance = provenance_of(bundle_replay, catalog="replay", dataset_path=dataset, root=root)
    without_dataset = replace(provenance, dataset_digest="")
    status = status_of(without_dataset, reverified=True, root=root)

    assert status.value == DRAFT
    assert not status.is_verified
    assert "the digest of the dataset" in status.missing


def test_an_artifact_without_the_reverification_is_a_draft_that_names_it(bundle_replay, dataset, root) -> None:
    """The offline re-verification is one of the four conditions, and the draft names it."""
    provenance = provenance_of(bundle_replay, catalog="replay", dataset_path=dataset, root=root)
    status = status_of(provenance, reverified=False, root=root)

    assert status.value == DRAFT
    assert "the offline re-verification" in status.missing


def test_an_artifact_whose_file_moved_is_a_draft_that_names_the_digest(bundle_replay, dataset, root, tmp_path) -> None:
    """A digest that does not match the disk is a missing evidence, and the draft names it."""
    provenance = provenance_of(bundle_replay, catalog="replay", dataset_path=dataset, root=root)
    moved = replace(provenance, file_digests={name: "0" * 64 for name in provenance.file_digests})
    status = status_of(moved, reverified=True, root=root)

    assert status.value == DRAFT
    assert any("does not match the disk" in name for name in status.missing)
