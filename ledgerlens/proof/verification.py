"""The offline re-verification of the artifact: the verdict the code gives for the published evidence.

Why the verification is the one of the published catalogs: the artifact publishes the verdict the
deterministic verifier of `ledgerlens/verify/checks.py` gives for the published evidence of the bundle,
computed offline, with no model and no network, exactly as ADR-073 re-verifies a published bundle. The
verification needs nothing but the bundle, so a reader can carry the check anywhere, and the artifact never
carries a verdict of the NLI model as if the code had given it.
"""

from __future__ import annotations

from pathlib import Path

from ledgerlens.replay.verdict import differences, reverified_labels

__all__ = ["reverification_of", "verdict_summary_of"]


def reverification_of(bundle_dir: Path) -> dict[str, str]:
    """The labels the deterministic verifier gives for the published evidence of the bundle."""
    return reverified_labels(bundle_dir)


def verdict_summary_of(bundle_dir: Path) -> str:
    """The summary of the verdicts of the bundle, one claim per item, in the order of the claims."""
    labels = reverified_labels(bundle_dir)
    return "; ".join(f"{claim} {label}" for claim, label in labels.items())


def reverification_passes(bundle_dir: Path) -> bool:
    """Whether the published labels and the labels the code gives are the same, claim by claim."""
    return not differences(bundle_dir)
