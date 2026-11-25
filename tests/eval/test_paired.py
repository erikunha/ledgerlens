"""The paired comparison of two variants over a cohort: the difference, case by case.

What they guarantee, and why: (a) a comparison over two cohorts is refused, because a comparison over two
cohorts is a comparison over two questions; (b) a missing run of one case never lowers the mean of the variant
that ran it, because the case is excluded from the pairing and named with the reason; (c) a result never hides
an excluded case, and never carries an interval without naming the method that computed it; (d) the goal of the
experiment is checked against the measured score, and a score of 0.73 never meets a goal of 0.80; (e) a stratum
below the declared minimum carries no mean, every stratum names its count, and the totals of the strata add up
to the cohort.

Everything here runs offline, with no key and with no network: the comparison reads the results of the runs that
already happened and never calls a model.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ledgerlens.eval.paired import ComparisonError, compare, read_runs

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "paired_runs.json"
COHORT = "c0ffee00000000000000000000000000000000000000000000000000000000000000"
METHOD = "the paired difference, with the standard error of the differences and the normal approximation of 95 percent"


def _runs():
    return read_runs(FIXTURE)


def test_a_comparison_over_two_cohorts_is_refused() -> None:
    """A comparison over two cohorts is a comparison over two questions."""
    runs = list(_runs())
    runs[0] = runs[0].__class__(**{**runs[0].__dict__, "cohort_sha256": "f" * 64})

    with pytest.raises(ComparisonError):
        compare(runs, goal=0.80, method=METHOD)


def test_a_missing_run_never_lowers_the_mean_of_the_variant_that_ran() -> None:
    """The case EC-02 ran only in the first variant: it is excluded, and the mean of the first variant does not
    carry it as a zero."""
    comparison = compare(_runs(), goal=0.80, method=METHOD)

    # The paired cases are the ones both variants ran: EC-01 and EC-03.
    assert comparison.paired_cases == 2
    # The excluded cases are named with the reason: EC-02 (the second variant did not run it) and EC-04 (the
    # first variant failed it).
    excluded = {case.case_id: case.reason for case in comparison.excluded}
    assert set(excluded) == {"EC-02", "EC-04"}
    assert all(excluded.values())
    # The mean of the first variant over the paired cases is (1.0 + 0.0) / 2, and the missing run of EC-02
    # never lowered it.
    assert comparison.mean_of("single_agent") == pytest.approx(0.5)
    assert comparison.mean_of("studio") == pytest.approx(0.75)


def test_the_result_never_hides_an_excluded_case_and_names_the_method_of_the_interval() -> None:
    """The excluded cases are in the result, and the interval names the method that computed it."""
    comparison = compare(_runs(), goal=0.80, method=METHOD)

    assert comparison.excluded
    assert comparison.interval.method == METHOD
    assert comparison.interval.low <= comparison.mean_difference <= comparison.interval.high


def test_a_score_of_0_73_never_meets_a_goal_of_0_80() -> None:
    """The goal is checked against the measured score, and 0.73 does not meet 0.80."""
    comparison = compare(_runs(), goal=0.80, method=METHOD)

    assert comparison.goal == 0.80
    assert comparison.goal_met is False


def test_a_stratum_below_the_minimum_carries_no_mean_and_the_totals_add_up() -> None:
    """A stratum below the declared minimum carries no mean, every stratum names its count, and the totals of
    the strata add up to the cohort."""
    comparison = compare(_runs(), goal=0.80, method=METHOD, minimum_stratum=2)

    assert comparison.minimum_stratum == 2
    for stratum in comparison.strata:
        assert stratum.count > 0
        if stratum.count < comparison.minimum_stratum:
            assert stratum.mean is None
            assert stratum.marked
        else:
            assert stratum.mean is not None
    # The totals of the strata of one dimension add up to the cohort: the paired cases and the excluded ones.
    for dimension in ("intent", "complexity"):
        total = sum(stratum.count for stratum in comparison.strata if stratum.dimension == dimension)
        assert total == comparison.paired_cases + len(comparison.excluded)


def test_the_fixture_holds_the_three_shapes_of_run() -> None:
    """The fixture is written by hand and holds a case both variants ran, a case only one ran and a run that
    failed."""
    runs = _runs()
    by_case: dict[str, list] = {}
    for run in runs:
        by_case.setdefault(run.case_id, []).append(run)

    assert any(all(run.ran and run.score is not None for run in case_runs) for case_runs in by_case.values())
    assert any(sum(1 for run in case_runs if run.ran) == 1 for case_runs in by_case.values())
    assert any(run.ran and run.score is None and run.failure for run in runs)


def test_the_check_of_the_goal_names_the_variant_it_checked() -> None:
    """A check of the goal that does not say which variant it checked is a check a reader cannot read."""
    comparison = compare(_runs(), goal=0.80, method=METHOD)

    assert comparison.goal_variant in comparison.variants
    assert comparison.goal_met == (comparison.means[comparison.goal_variant] >= comparison.goal)

    named = compare(_runs(), goal=0.80, method=METHOD, goal_variant="studio")
    assert named.goal_variant == "studio"
    assert named.goal_met == (named.means["studio"] >= 0.80)


def test_the_goal_checked_against_a_variant_that_is_not_there_is_refused() -> None:
    """A goal checked against a variant the runs do not name is a goal that checks nothing."""
    with pytest.raises(ComparisonError):
        compare(_runs(), goal=0.80, method=METHOD, goal_variant="no_such_variant")
