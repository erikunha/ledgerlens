"""The cascade is declared, and the router chooses the two profiles of the cascade for the two tasks.

What they guarantee, and why: (a) the two profiles of the cascade are chosen for the two tasks, because the
router chooses the cheapest model of the cascade that is at or above the level of the task and that really has
the capability the task needs; (b) a profile whose tool calling was never tested is refused with the reason,
because a model that never called a tool does not plan the answer with the tools.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import pytest

from ledgerlens.agents.routing import ModelCandidate, RoutingError, candidates_of, route
from ledgerlens.byok.registry import ALLOWLIST, profiles_by_name

CASCADE = ("openai:gpt-4.1-mini", "openai:gpt-4.1")


def test_the_two_profiles_of_the_cascade_are_chosen_for_the_two_tasks() -> None:
    """The light task takes the light model, and the robust task takes the capable one."""
    decisions = route(candidates_of(CASCADE, profiles_by_name(ALLOWLIST)), case_id="EC-01")

    assert decisions["triage"].chosen_model == "openai:gpt-4.1-mini"
    assert decisions["policy"].chosen_model == "openai:gpt-4.1-mini"
    assert decisions["agent"].chosen_model == "openai:gpt-4.1"
    assert decisions["sql"].chosen_model == "openai:gpt-4.1"


def test_a_profile_whose_tool_calling_was_never_tested_is_refused_with_the_reason() -> None:
    """A model that never called a tool does not plan the answer with the tools."""
    candidates = [
        ModelCandidate(name="openai:gpt-4.1-mini", capabilities=frozenset({"chat"}), price_snapshot=None),
    ]

    with pytest.raises(RoutingError) as refusal:
        route(candidates, case_id="EC-01")

    assert "capability" in str(refusal.value)
