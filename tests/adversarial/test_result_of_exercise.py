"""The result of an exercise: the six fields, and the blocked actions carry the reason of the layer.

What they guarantee, and why: the result of an exercise carries the surface that was attacked, the boundary
that was expected, the reference of the trace, the actions that were blocked with the reason of the layer that
stopped them and the risk that is still open, because a result that misses one of them is a result a reader
cannot check (the definition of done of the milestone).

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from ledgerlens.adversarial.exercises import EXERCISES, exercise_of
from ledgerlens.adversarial.runner import run_exercise


def test_the_result_of_an_exercise_carries_the_six_fields(tmp_path) -> None:
    """The surface, the boundary, the trace, the blocked actions and the open risk, all of them."""
    result = run_exercise(exercise_of("forged-evidence-identifier"), work_dir=tmp_path)

    assert result.surface == "the join of the evidence"
    assert result.expected_boundary
    assert result.trace_ref
    assert result.blocked_actions
    assert result.open_risk
    assert result.unauthorized_actions == 0


def test_the_blocked_actions_carry_the_reason_of_the_layer_that_stopped_them(tmp_path) -> None:
    """A blocked action that names neither the layer nor the reason is a claim and not a measurement."""
    for exercise in EXERCISES:
        result = run_exercise(exercise, work_dir=tmp_path / exercise.exercise_id)
        for blocked in result.blocked_actions:
            assert blocked.layer, f"the exercise {exercise.exercise_id} has a blocked action with no layer"
            assert blocked.reason, f"the exercise {exercise.exercise_id} has a blocked action with no reason"
