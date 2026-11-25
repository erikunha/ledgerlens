"""The deterministic gate: the verdict of a record is a decision of the code and never a proposal of a model.

Why the gate is the only door to the tier gold: a record is promoted by the verdict of the deterministic
verifier of `ledgerlens/verify/checks.py` over the published evidence of the bundle, computed offline, with no
model and no network, exactly as ADR-073 re-verifies a published bundle. The label of the NLI model may travel
with the record, and when it disagrees with the deterministic verdict the deterministic verdict is the one that
is written down, because a verdict of a model is a proposal and the verdict of the record is a decision.
"""

from __future__ import annotations

from pathlib import Path

from ledgerlens.feedback.record import FeedbackRecord
from ledgerlens.replay.verdict import reverified_labels

__all__ = ["PROJECT_ROOT", "verdict_of"]

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def verdict_of(record: FeedbackRecord, *, root: Path = PROJECT_ROOT) -> str:
    """The verdict of the record: the label the deterministic verifier gives for the published evidence.

    The label is read from the re-verification of the bundle of the record, which runs offline with the
    stand-in of the NLI model. A claim the bundle does not publish is a claim the evidence does not carry, and
    the verdict is `not_enough_evidence`.
    """
    labels = reverified_labels(root / record.bundle)
    return labels.get(record.claim_id, "not_enough_evidence")
