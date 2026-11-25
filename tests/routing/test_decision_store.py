"""The store of the routing decisions: a decision is written once and never changed.

What they guarantee, and why: (a) a second write of the same decision is refused, because a decision is written
once and never changed, and a run whose decision changed in the middle is a run that can be read as two runs;
(b) the decision of a run is readable after the run ended, because the decision is the metadata of the trace.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import pytest

from ledgerlens.agents.decision_store import DecisionStore, DecisionStoreError
from ledgerlens.agents.routing import RoutingDecision


def _decision(case_id: str = "EC-01") -> RoutingDecision:
    return RoutingDecision(
        case_id=case_id,
        case_type="refund_discrepancy",
        risk_tier="standard",
        allowed_provider_models=("openai:gpt-4.1-mini",),
        chosen_model="openai:gpt-4.1-mini",
        reason="the task of the slot is light",
        budget="the ceiling of the run",
        price_snapshot="0.40/1.60 usd per million tokens",
        confidence_kind="verified",
    )


def test_the_store_refuses_a_second_write_of_the_same_decision() -> None:
    """A decision is written once and never changed."""
    store = DecisionStore()
    store.write("agent", _decision())

    with pytest.raises(DecisionStoreError):
        store.write("agent", _decision())


def test_the_decision_of_a_run_is_readable_after_the_run_ended() -> None:
    """The decision is the metadata of the trace, and it is readable after the run ended."""
    store = DecisionStore()
    decision = _decision()
    store.write("agent", decision)

    assert store.read("EC-01", "agent") == decision
    assert store.read("EC-01", "triage") is None
    assert store.read("EC-99", "agent") is None
