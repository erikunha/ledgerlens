"""The comparison and the promotion: a candidate is compared with the baseline once, over the holdout.

Why a comparison publishes no number that the run did not produce: the scores of the comparison are the scores
the run produced, and the report names the set, the denominator, the role of the set and the digest of the
dataset, so a reader can find the run and check the numbers. A candidate that is worse on the holdout is not
promoted, and the negative result is kept in the report, because a loop that keeps only the wins is a loop
that publishes a tendency and calls it a significance.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

__all__ = ["Comparison", "compare_on_holdout", "render_report"]


@dataclass(frozen=True)
class Comparison:
    """The comparison of a candidate with the baseline over the holdout, written down whatever the result."""

    dataset_id: str
    role: str
    denominator: int
    dataset_digest: str
    baseline_score: Decimal
    candidate_score: Decimal
    promoted: bool

    @property
    def difference(self) -> Decimal:
        """The difference of the candidate against the baseline, exact because the scores are `Decimal`."""
        return self.candidate_score - self.baseline_score


def compare_on_holdout(
    *,
    dataset_id: str,
    role: str,
    denominator: int,
    dataset_digest: str,
    baseline_score: Decimal,
    candidate_score: Decimal,
) -> Comparison:
    """The comparison of the candidate with the baseline, once, over the holdout.

    The candidate is promoted only when it is strictly better than the baseline: a tie is not a win, and a
    candidate that is worse is not promoted, whatever the size of the loss.
    """
    return Comparison(
        dataset_id=dataset_id,
        role=role,
        denominator=denominator,
        dataset_digest=dataset_digest,
        baseline_score=baseline_score,
        candidate_score=candidate_score,
        promoted=candidate_score > baseline_score,
    )


def render_report(comparison: Comparison) -> str:
    """The report of the comparison: the set, the denominator, the role, the digest and the two scores.

    The negative result is kept: a candidate that is worse is written down with the same fields as a candidate
    that is better, because the report of a loop that hides its losses is a report of a loop that cannot be
    trusted.
    """
    outcome = "promoted" if comparison.promoted else "not promoted"
    return "\n".join(
        [
            f"Comparison over the holdout {comparison.dataset_id} (role {comparison.role}).",
            f"Denominator: {comparison.denominator} cases.",
            f"Digest of the dataset: {comparison.dataset_digest}.",
            f"Baseline: {comparison.baseline_score}.",
            f"Candidate: {comparison.candidate_score}.",
            f"Difference: {comparison.difference}.",
            f"The candidate is {outcome}.",
        ]
    )
