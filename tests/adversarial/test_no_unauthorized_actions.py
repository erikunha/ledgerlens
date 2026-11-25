"""The count of the unauthorized actions over the whole list of the exercises is zero, and the test computes it.

What they guarantee, and why: every attempt of every exercise of the list is stopped by the layer of the
repository that owns the boundary, and the count of the unauthorized actions over the whole list is zero. The
count is computed by the test over the results of the exercises and not written by hand, because a count of
zero that was written by hand is a claim and a count of zero that the test computes is evidence.

The count says nothing about an attack that is not in the list, and the page of the laboratory says so.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from ledgerlens.adversarial.exercises import EXERCISES
from ledgerlens.adversarial.runner import run_exercise


def test_the_count_of_the_unauthorized_actions_over_the_whole_list_is_zero(tmp_path) -> None:
    """Every attack of the list is stopped by a layer of the repository, and the test counts it."""
    results = [run_exercise(exercise, work_dir=tmp_path / exercise.exercise_id) for exercise in EXERCISES]

    unauthorized = sum(result.unauthorized_actions for result in results)
    assert unauthorized == 0
    assert all(result.held for result in results)
    # The count is over the whole list: an exercise that did not run would make the count a count of nothing.
    assert len(results) == len(EXERCISES)
