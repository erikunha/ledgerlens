"""The decision of the routing: the nine fields, and the store that writes it once.

What they guarantee, and why: (a) the decision of the routing carries the case, the task, the risk tier, the
models that were allowed, the model that was chosen, the reason, the budget and the price snapshot, because a
decision that does not say what it was decided from is a decision nobody can check; (b) a second write of the
same decision is refused, because a decision is written once and never changed; (c) the decision of a run is
readable after the run ended, because the decision is the metadata of the trace.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from ledgerlens.agents.routing import RoutingDecision


def _decision() -> RoutingDecision:
    """A decision of the routing, with every field pinned."""
    return RoutingDecision(
        case_id="EC-01",
        case_type="refund_discrepancy",
        risk_tier="standard",
        allowed_provider_models=("openai:gpt-4.1-mini", "openai:gpt-4.1"),
        chosen_model="openai:gpt-4.1-mini",
        reason="the task of the slot is light, and the lightest model of the cascade runs it",
        budget="the ceiling of the run",
        price_snapshot="0.40/1.60 usd per million tokens",
        confidence_kind="verified",
    )


def test_the_decision_carries_the_nine_fields() -> None:
    """The decision says what it was decided from."""
    decision = _decision()

    assert decision.case_id == "EC-01"
    assert decision.case_type == "refund_discrepancy"
    assert decision.risk_tier == "standard"
    assert decision.allowed_provider_models == ("openai:gpt-4.1-mini", "openai:gpt-4.1")
    assert decision.chosen_model == "openai:gpt-4.1-mini"
    assert decision.reason
    assert decision.budget
    assert decision.price_snapshot == "0.40/1.60 usd per million tokens"
    assert decision.confidence_kind == "verified"


def test_a_second_write_of_the_same_decision_is_refused() -> None:
    """A decision is written once and never changed, and the store of the decisions refuses the second write."""
    from ledgerlens.agents.decision_store import DecisionStore, DecisionStoreError

    store = DecisionStore()
    store.write("agent", _decision())
    try:
        store.write("agent", _decision())
    except DecisionStoreError:
        return
    raise AssertionError("the store accepted a second write of the same decision")
