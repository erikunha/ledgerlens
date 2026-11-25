"""The comparison and the promotion: a candidate worse on the holdout is not promoted, and the loss is kept.

What they guarantee, and why: a candidate that is worse on the holdout is not promoted, the negative result is
kept in the report, and the report names the set, the denominator, the role of the set and the digest of the
dataset, because a loop that keeps only the wins is a loop that publishes a tendency and calls it a
significance.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from decimal import Decimal

from ledgerlens.feedback.promotion import compare_on_holdout, render_report


def _comparison(candidate: str, baseline: str = "0.75"):
    return compare_on_holdout(
        dataset_id="verification_heldout",
        role="held_out",
        denominator=48,
        dataset_digest="a" * 64,
        baseline_score=Decimal(baseline),
        candidate_score=Decimal(candidate),
    )


def test_a_candidate_that_is_worse_on_the_holdout_is_not_promoted() -> None:
    """A candidate that is worse is not promoted, whatever the size of the loss."""
    comparison = _comparison("0.70")

    assert not comparison.promoted
    assert comparison.difference == Decimal("-0.05")


def test_the_negative_result_is_kept_in_the_report() -> None:
    """The report of a loss has the same fields as the report of a win."""
    report = render_report(_comparison("0.70"))

    assert "not promoted" in report
    assert "0.70" in report
    assert "-0.05" in report


def test_the_report_names_the_set_the_denominator_the_role_and_the_digest() -> None:
    """A reader of the report can find the run and check the numbers."""
    report = render_report(_comparison("0.80"))

    assert "verification_heldout" in report
    assert "48" in report
    assert "held_out" in report
    assert "a" * 64 in report


def test_a_candidate_that_is_strictly_better_is_promoted() -> None:
    """The promotion is the exception, and the tie is not a win."""
    assert _comparison("0.80").promoted
    assert not _comparison("0.75").promoted
