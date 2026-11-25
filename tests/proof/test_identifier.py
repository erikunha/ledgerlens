"""The identifier of the artifact: the digest of the bundle, unguessable by construction.

What they guarantee, and why: the identifier of the artifact is the digest of the bundle, and two artifacts of
two commits have two identifiers, because the digest of the bundle is unguessable by construction and no
private artifact exists: every artifact is built from a published bundle of the two catalogs.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from ledgerlens.proof.provenance import provenance_of
from ledgerlens.replay.bundle import bundle_digest


def test_the_identifier_of_the_artifact_is_the_digest_of_the_bundle(bundle_replay, dataset, root) -> None:
    """The identifier is the digest of the bundle, and no private artifact exists."""
    provenance = provenance_of(bundle_replay, catalog="replay", dataset_path=dataset, root=root)

    assert provenance.artifact_id == bundle_digest(bundle_replay)
    assert len(provenance.artifact_id) == 64


def test_two_artifacts_of_two_bundles_have_two_identifiers(bundle_replay, bundle_replay_real, dataset, root) -> None:
    """Two bundles have two digests, so two artifacts have two identifiers."""
    first = provenance_of(bundle_replay, catalog="replay", dataset_path=dataset, root=root)
    second = provenance_of(bundle_replay_real, catalog="replay-real", dataset_path=dataset, root=root)

    assert first.artifact_id != second.artifact_id
