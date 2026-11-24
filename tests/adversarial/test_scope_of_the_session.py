"""The scope of the session: the store of the branch refuses the read of a branch of another visitor.

What they guarantee, and why: the exercise of the row of another visitor runs against the store of the branch
and the session folder of `ledgerlens/sandbox/memory.py`, and the read of a branch of another session is
refused, because the memory and the branch of one visitor never show up in the answer of another one (FR-027).

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from ledgerlens.adversarial.exercises import exercise_of
from ledgerlens.adversarial.runner import run_exercise
from ledgerlens.sandbox.memory import session_memory_dir


def test_the_store_of_the_branch_refuses_the_read_of_a_branch_of_another_session(tmp_path) -> None:
    """The branch of another visitor is not there for this session."""
    result = run_exercise(exercise_of("row-of-another-visitor"), work_dir=tmp_path)

    assert result.held
    assert "the store of the branch refuses it" in result.blocked_actions[0].reason


def test_the_session_folder_of_the_memory_is_the_folder_of_the_session(tmp_path) -> None:
    """The folder of the memory of a session names the session, and no other session reads it."""
    folder = session_memory_dir("session-of-one-visitor", tmp_path)

    assert folder.name == "session-of-one-visitor"
    assert folder.parent.name == "sessions"
