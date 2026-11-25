"""The router chooses the model of a slot by the task the slot does, and the verifier is never a routed model.

What they guarantee, and why: (a) the router writes a decision per slot with the task of the slot, because the
choice of the model is a choice by the task and by the capability the provider really has; (b) the verifier of
`ledgerlens/verify/` is absent from the routed models, because the verifier is the deterministic judge of the
repository and it is never a model.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from ledgerlens.agents.routing import SLOTS, candidates_of, route, slot_task
from ledgerlens.byok.registry import ALLOWLIST, profiles_by_name

CASCADE = ("openai:gpt-4.1-mini", "openai:gpt-4.1")


def test_the_router_writes_a_decision_per_slot_with_the_task_of_the_slot() -> None:
    """Every slot of the run has a decision, and the decision names the model of the task of the slot."""
    decisions = route(candidates_of(CASCADE, profiles_by_name(ALLOWLIST)), case_id="EC-01")

    assert set(decisions) == set(SLOTS)
    for slot, decision in decisions.items():
        assert decision.chosen_model
        assert slot_task(slot).capabilities is not None


def test_the_verifier_is_never_a_routed_model() -> None:
    """The verifier is the deterministic judge of the repository, and it is never a model of the routing."""
    decisions = route(candidates_of(CASCADE, profiles_by_name(ALLOWLIST)), case_id="EC-01")

    assert "verifier" not in decisions
    assert "verify" not in decisions
    assert set(decisions) == set(SLOTS)
