"""The layers of the repository answer the attacks of the laboratory, and the reason of each refusal is in the trace.

What they guarantee, and why: the exercises of the write, of the table outside the allowlist and of the tool
that does not exist are stopped by the layer of the repository that owns the boundary (the guard of the SQL,
the read-only connection of `ledgerlens/tools/sql.py` and the allowlist of the tools of
`ledgerlens/api/live_case.py`), and the reason of each refusal is in the trace of the attempt, because a
blocked action that names neither the layer nor the reason is a claim and not a measurement.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from ledgerlens.adversarial.exercises import exercise_of
from ledgerlens.adversarial.runner import run_exercise


def test_the_write_in_a_generated_query_is_refused_by_the_guard_and_by_the_connection(tmp_path) -> None:
    """The guard of the SQL refuses the write, and the read-only connection is the second wall."""
    result = run_exercise(exercise_of("write-in-generated-query"), work_dir=tmp_path)

    assert result.held
    layers = {blocked.layer for blocked in result.blocked_actions}
    assert any("guard of the SQL" in layer for layer in layers)
    assert any("read-only connection" in layer for layer in layers)
    assert all(blocked.reason for blocked in result.blocked_actions)


def test_the_table_outside_the_allowlist_is_refused_by_the_guard(tmp_path) -> None:
    """The guard of the SQL refuses the table that is not in the allowlist."""
    result = run_exercise(exercise_of("table-outside-the-allowlist"), work_dir=tmp_path)

    assert result.held
    assert "the guard of the SQL refuses it" in result.blocked_actions[0].reason


def test_the_tool_that_does_not_exist_is_refused_by_the_allowlist(tmp_path) -> None:
    """The allowlist of the tools of the live path refuses the tool that does not exist."""
    result = run_exercise(exercise_of("tool-that-does-not-exist"), work_dir=tmp_path)

    assert result.held
    assert "the allowlist of the tools refuses it" in result.blocked_actions[0].reason


def test_the_reason_of_each_refusal_is_in_the_trace(tmp_path) -> None:
    """A reader of the trace sees which layer answered and why."""
    result = run_exercise(exercise_of("write-in-generated-query"), work_dir=tmp_path)

    assert result.events
    for event in result.events:
        assert event.payload["reason"]
        assert event.payload["blocked"] is True
