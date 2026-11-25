"""The deterministic gate: the verdict of a record is the verdict of the verifier over the published evidence.

What they guarantee, and why: the verdict of a record is the one the deterministic verifier of
`ledgerlens/verify/checks.py` gives for the published evidence of the bundle, computed with no model and no
network, and a record whose NLI verdict disagrees with the deterministic one carries the deterministic one,
because the verdict of a record is a decision of the code and never a proposal of a model.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from pathlib import Path

from ledgerlens.feedback.gate import verdict_of
from ledgerlens.replay.verdict import reverified_labels


def test_the_verdict_of_a_record_is_the_verdict_of_the_deterministic_verifier(record) -> None:
    """The gate re-verifies the bundle of the record and reads the label of the claim of the record."""
    expected = reverified_labels(Path("data/eval/replay/s02"))["CL3"]

    assert verdict_of(record) == expected == "not_enough_evidence"


def test_a_record_whose_nli_verdict_disagrees_carries_the_deterministic_one(record_factory) -> None:
    """The label of the NLI model is a proposal, and the deterministic verdict is the decision."""
    disagreeing = record_factory(nli_label="supported")

    assert disagreeing.nli_label == "supported"
    assert verdict_of(disagreeing) == "not_enough_evidence"


def test_a_claim_the_bundle_does_not_publish_is_not_enough_evidence(record_factory) -> None:
    """A claim the bundle does not publish is a claim the evidence does not carry."""
    missing = record_factory(claim_id="CL99")

    assert verdict_of(missing) == "not_enough_evidence"
