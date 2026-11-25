"""The provenance of the artifact: the commit and the digests of the run it describes.

What they guarantee, and why: the artifact of a bundle of each catalog carries the commit, the digest of every
file of the bundle, the digest of the snapshot, the digest of the dataset, the catalog, the capture kind and
the model profiles, and every digest is the digest of the file on the disk, because the provenance of the
artifact is the provenance of the bundle and a digest copied from a manifest could be a digest of a file that
moved.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import hashlib

import pytest

from ledgerlens.proof.provenance import provenance_of


def test_the_artifact_of_a_bundle_of_the_scripted_catalog_carries_the_provenance(
    bundle_replay, dataset, root
) -> None:
    """The provenance of the bundle of the scripted model, with every digest read from the disk."""
    provenance = provenance_of(bundle_replay, catalog="replay", dataset_path=dataset, root=root)

    assert provenance.scenario_id == "S01"
    assert provenance.catalog == "replay"
    assert provenance.capture_kind == "scripted_fixture"
    assert provenance.git_commit
    assert provenance.source_commit
    assert provenance.snapshot_hash
    assert provenance.dataset_digest == hashlib.sha256(dataset.read_bytes()).hexdigest()
    assert provenance.model_profiles
    for name, digest in provenance.file_digests.items():
        assert digest == hashlib.sha256((bundle_replay / name).read_bytes()).hexdigest()


def test_the_artifact_of_a_bundle_of_the_real_catalog_carries_the_provenance(
    bundle_replay_real, dataset, root
) -> None:
    """The provenance of the bundle of a real model, with the profiles of the models of the run."""
    provenance = provenance_of(bundle_replay_real, catalog="replay-real", dataset_path=dataset, root=root)

    assert provenance.catalog == "replay-real"
    assert provenance.capture_kind == "real_model_recorded"
    assert provenance.mode == "live_provider"
    assert "agent" in provenance.model_profiles


def test_a_catalog_the_site_does_not_publish_is_refused(bundle_replay, dataset, root) -> None:
    """The catalogs are the two of the site, and a third one is a mistake of the caller."""
    with pytest.raises(ValueError, match="catalog"):
        provenance_of(bundle_replay, catalog="elsewhere", dataset_path=dataset, root=root)
