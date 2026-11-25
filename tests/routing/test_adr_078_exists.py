"""ADR-078 exists and says what the routing of the inference is.

What they guarantee, and why: the decision of the routing between models by task is written down, with the fixed
cascade, the rules of the honesty of the routing, the metadata of the trace and the rule of the one model of a
live run. A routing that nobody decided is a routing that drifts, and a decision that is not written down is a
decision nobody can check.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADR = ROOT / "docs" / "decisions" / "ADR-078-the-model-of-each-slot-is-chosen-by-the-work-it-does.md"


def test_adr_078_exists() -> None:
    """The decision of the routing is written down."""
    assert ADR.is_file(), "ADR-078 is not in docs/decisions/"


def test_adr_078_says_the_routing_is_by_task_over_a_fixed_cascade() -> None:
    """The routing chooses the model of each slot by the task the slot does, over a cascade the deployment
    declares."""
    text = ADR.read_text(encoding="utf-8")

    assert "slot" in text
    assert "task" in text
    assert "cascade" in text


def test_adr_078_says_the_rules_of_the_honesty_and_the_one_model_of_a_live_run() -> None:
    """The honesty rules and the one model of a live run are in the decision."""
    text = ADR.read_text(encoding="utf-8").lower()

    assert "verifier" in text
    assert "never silently replaced" in text or "never replaced" in text
    assert "one model" in text
    assert "unknown" in text and "never zero" in text
