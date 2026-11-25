"""The runner of the laboratory uses the shipped agent: the tools and the prompt of the run are the ones of the product.

What they guarantee, and why: the exercise of the injected note runs the agent of the repository unchanged, in
the offline mode with the scripted model, and the tools and the prompt of the run are the ones of the shipped
path, because a laboratory that weakened a layer to let an attack through would measure a product that does not
exist.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from ledgerlens.adversarial.exercises import exercise_of
from ledgerlens.adversarial.runner import run_exercise


def test_the_exercise_of_the_injected_note_runs_the_shipped_agent(tmp_path) -> None:
    """The run of the exercise is the run of the product: the case escalates and the result says which layer held."""
    result = run_exercise(exercise_of("s09-injected-note"), work_dir=tmp_path)

    assert result.held
    assert result.unauthorized_actions == 0
    assert result.blocked_actions
    blocked = result.blocked_actions[0]
    assert "the tools and the system prompt of the agent" in blocked.reason
    assert "escalated" in blocked.reason
    assert result.open_risk
