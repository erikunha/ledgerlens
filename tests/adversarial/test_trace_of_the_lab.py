"""The trace of the laboratory: one event per attempt, with the reason of the refusal.

What they guarantee, and why: the events of `ledgerlens/observability/trace_event.py` produced by an exercise
carry one event per attempt with the reason of the refusal, because a reader of the trace has to see what was
attempted, whether a layer stopped it and why, and a trace that does not say it is a trace that proves nothing.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from ledgerlens.adversarial.exercises import EXERCISES
from ledgerlens.adversarial.runner import run_exercise


def test_every_exercise_produces_one_event_per_attempt_with_the_reason(tmp_path) -> None:
    """The trace of the attempt says what was attempted, whether it was blocked and why."""
    for exercise in EXERCISES:
        result = run_exercise(exercise, work_dir=tmp_path / exercise.exercise_id)
        assert result.events, f"the exercise {exercise.exercise_id} produced no event"
        for event in result.events:
            assert event.payload["exercise"] == exercise.exercise_id
            assert event.payload["action"]
            assert event.payload["blocked"] in (True, False)
            assert event.payload["reason"]
