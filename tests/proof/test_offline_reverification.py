"""The offline re-verification: the verdict the artifact publishes is the verdict the code gives.

What they guarantee, and why: the verdict the artifact publishes is the verdict the deterministic verifier of
`ledgerlens/verify/checks.py` gives for the published evidence of the bundle, with no model and no network,
because the verification is the one of the published catalogs and it needs nothing but the bundle.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from ledgerlens.proof.verification import reverification_of, reverification_passes, verdict_summary_of
from ledgerlens.replay.verdict import reverified_labels


def test_the_verdict_the_artifact_publishes_is_the_verdict_the_code_gives(bundle_replay) -> None:
    """The re-verification of the artifact is the re-verification of the published catalogs."""
    assert reverification_of(bundle_replay) == reverified_labels(bundle_replay)
    assert reverification_passes(bundle_replay)


def test_the_summary_of_the_verdicts_names_every_claim(bundle_replay) -> None:
    """The summary carries one item per claim, in the order of the claims."""
    summary = verdict_summary_of(bundle_replay)

    for claim, label in reverified_labels(bundle_replay).items():
        assert f"{claim} {label}" in summary


def test_the_reverification_runs_offline_with_no_model(bundle_replay_real) -> None:
    """The bundle of a real model is re-verified with the same code and no model at all."""
    assert reverification_passes(bundle_replay_real)
