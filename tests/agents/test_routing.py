"""The router: the model of each slot of a run, chosen by the task the slot does.

What they guarantee, and why: (a) the table of the slots names the four slots of a run with the task of each one
and the capability the task needs; (b) a cascade of two models sends the light work to the light model and the
hard work to the capable one; (c) a cascade of one model sends every slot to that model, which is how the run
behaved before the router existed; (d) a task that no model of the cascade may run is refused before the run
starts, with the missing capability named; (e) a price that was never verified is unknown and never zero; (f)
the decision is a value, so the same inputs always give the same decision, and a run whose decision changed in
the middle would be two runs.
"""

from __future__ import annotations

import pytest

from ledgerlens.agents.routing import (
    CONFIDENCE_UNDECLARED,
    CONFIDENCE_VERIFIED,
    SLOT_AGENT,
    SLOT_POLICY,
    SLOT_SQL,
    SLOT_TASKS,
    SLOT_TRIAGE,
    TIER_LIGHT,
    TIER_ROBUST,
    TIER_STANDARD,
    ModelCandidate,
    RoutingError,
    budget_of,
    candidates_of,
    models_of,
    route,
    slot_task,
)
from ledgerlens.byok.registry import ALLOWLIST, ModelProfile, Pricing
from ledgerlens.run_context import RunBudget


def _profile(model_id: str, capabilities: tuple[str, ...], *, price: Pricing | None = None) -> ModelProfile:
    """A profile of the allowlist for the tests, with the capabilities the test needs."""
    return ModelProfile(
        profile_id=f"openai-{model_id}",
        provider="openai",
        model_id=model_id,
        display_name=model_id,
        capabilities=capabilities,
        status="tested",
        enabled_in_public_demo=True,
        pricing=price or Pricing(source="unknown", last_verified=None, input_per_1m_usd=None, output_per_1m_usd=None),
    )


def _candidates() -> list[ModelCandidate]:
    """Two models: a light one that chats, and a capable one that chats and calls tools."""
    return [
        ModelCandidate(
            name="openai:gpt-4.1-mini",
            capabilities=frozenset({"chat", "tool_calling"}),
            price_snapshot="0.40/1.60 usd per million tokens",
            confidence_kind=CONFIDENCE_VERIFIED,
        ),
        ModelCandidate(
            name="openai:gpt-4.1",
            capabilities=frozenset({"chat", "tool_calling"}),
            price_snapshot=None,
            confidence_kind=CONFIDENCE_VERIFIED,
        ),
    ]


def test_the_table_names_the_four_slots_with_their_task() -> None:
    """Every slot of the run has a task, a level and the capability the task needs."""
    assert set(SLOT_TASKS) == {SLOT_AGENT, SLOT_TRIAGE, SLOT_SQL, SLOT_POLICY}
    for slot, task in SLOT_TASKS.items():
        assert task.slot == slot
        assert task.task
        assert task.tier in {TIER_LIGHT, TIER_STANDARD, TIER_ROBUST}
        assert task.capabilities


def test_the_agent_needs_a_model_that_calls_tools_and_the_rest_do_not() -> None:
    """The task that plans the answer with the tools is the one that needs the tool calling."""
    assert "tool_calling" in slot_task(SLOT_AGENT).capabilities
    assert "tool_calling" not in slot_task(SLOT_TRIAGE).capabilities
    assert "tool_calling" not in slot_task(SLOT_POLICY).capabilities
    assert "tool_calling" not in slot_task(SLOT_SQL).capabilities


def test_the_light_work_goes_to_the_light_model() -> None:
    """The triage and the rewrite of the policy search take the lightest model of the cascade."""
    decisions = route(_candidates(), case_id="case-1")
    assert decisions[SLOT_TRIAGE].chosen_model == "openai:gpt-4.1-mini"
    assert decisions[SLOT_POLICY].chosen_model == "openai:gpt-4.1-mini"


def test_the_hard_work_goes_to_the_capable_model() -> None:
    """The statement and the answer with the tools take the model that reaches their level."""
    decisions = route(_candidates(), case_id="case-1")
    assert decisions[SLOT_SQL].chosen_model == "openai:gpt-4.1"
    assert decisions[SLOT_AGENT].chosen_model == "openai:gpt-4.1"


def test_a_cascade_of_one_model_sends_every_slot_to_it() -> None:
    """A deployment with one model keeps the behaviour it had before the router existed."""
    decisions = route(_candidates()[:1], case_id="case-1")
    assert models_of(decisions) == {
        SLOT_AGENT: "openai:gpt-4.1-mini",
        SLOT_TRIAGE: "openai:gpt-4.1-mini",
        SLOT_SQL: "openai:gpt-4.1-mini",
        SLOT_POLICY: "openai:gpt-4.1-mini",
    }


def test_a_task_that_no_model_may_run_is_refused_before_the_run() -> None:
    """A task with no model fails in the middle of a run, so the router refuses it first."""
    candidates = [ModelCandidate(name="openai:gpt-4.1-mini", capabilities=frozenset({"chat"}))]
    with pytest.raises(RoutingError) as refusal:
        route(candidates, case_id="case-1")
    assert SLOT_AGENT in str(refusal.value)
    assert "tool_calling" in str(refusal.value)


def test_the_decision_says_what_was_allowed_and_why() -> None:
    """The decision carries the models it was made among, the reason, the budget and the confidence."""
    decisions = route(_candidates(), case_id="case-7", case_type="refund_discrepancy", risk_tier=TIER_STANDARD)
    decision = decisions[SLOT_AGENT]
    assert decision.case_id == "case-7"
    assert decision.case_type == "refund_discrepancy"
    assert decision.risk_tier == TIER_STANDARD
    assert decision.allowed_provider_models == ("openai:gpt-4.1-mini", "openai:gpt-4.1")
    assert decision.chosen_model == "openai:gpt-4.1"
    assert decision.reason
    assert decision.confidence_kind == CONFIDENCE_VERIFIED


def test_a_price_that_was_never_verified_is_unknown_and_not_zero() -> None:
    """The price of the model nobody checked is absent, because a zero would say the call was free."""
    decisions = route(_candidates(), case_id="case-1")
    assert decisions[SLOT_AGENT].price_snapshot is None
    assert decisions[SLOT_TRIAGE].price_snapshot == "0.40/1.60 usd per million tokens"


def test_a_model_outside_the_allowlist_is_marked_as_undeclared() -> None:
    """The capabilities of a model the repository never exercised are a claim and not a verification."""
    candidates = candidates_of(
        ["openai:not-tested"],
        {},
    )
    assert candidates[0].confidence_kind == CONFIDENCE_UNDECLARED
    assert candidates[0].capabilities == frozenset()


def test_the_candidates_take_the_capabilities_the_allowlist_verified() -> None:
    """The capabilities of a candidate come from the allowlist, the only place the repository verified them."""
    profiles = {profile.model_id: profile for profile in ALLOWLIST}
    candidates = candidates_of(["gpt-4.1-mini"], profiles)
    assert candidates[0].name == "gpt-4.1-mini"
    assert candidates[0].confidence_kind == CONFIDENCE_VERIFIED
    assert "tool_calling" in candidates[0].capabilities
    assert candidates[0].price_snapshot is not None


def test_the_budget_says_that_the_money_is_unknown_when_it_is_unknown() -> None:
    """The budget of the decision is the ceiling of the run, and an unknown price is never a price of zero."""
    assert "money unknown" in budget_of(RunBudget(max_model_calls=12, max_tool_calls=16))
    assert budget_of(None) == "no budget declared"


def test_the_decision_is_a_value_and_the_same_inputs_give_the_same_decision() -> None:
    """A decision that changed in the middle of a run would make the run two runs."""
    first = route(_candidates(), case_id="case-1")
    second = route(_candidates(), case_id="case-1")
    assert {slot: decision.to_dict() for slot, decision in first.items()} == {
        slot: decision.to_dict() for slot, decision in second.items()
    }


def test_a_slot_that_is_not_one_of_the_four_is_refused() -> None:
    """A slot nobody declared has no task and no model."""
    with pytest.raises(RoutingError):
        slot_task("judge")
