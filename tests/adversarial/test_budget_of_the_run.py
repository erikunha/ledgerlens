"""The budget of the run: the coordinator stops the run with the name of the cap.

What they guarantee, and why: the exercise of the call that passes the cap runs against the coordinator of
`ledgerlens/byok/budget.py`, and the run stops with the name of the cap, because a run that stops without
saying why is a run that the reader cannot compare with the run that did not stop (SC-003 of the spec of the
studio, the same rule of the budget of every run).

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from ledgerlens.adversarial.exercises import exercise_of
from ledgerlens.adversarial.runner import run_exercise


def test_the_call_past_the_cap_is_stopped_with_the_name_of_the_cap(tmp_path) -> None:
    """The coordinator of the budget stops the run, and the reason names the cap."""
    result = run_exercise(exercise_of("call-past-the-cap"), work_dir=tmp_path)

    assert result.held
    assert "the coordinator of the budget stops the run" in result.blocked_actions[0].reason
    assert "max_model_calls" in result.blocked_actions[0].reason
