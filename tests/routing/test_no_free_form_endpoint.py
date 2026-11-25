"""The router never accepts an address of a server that a visitor wrote.

What they guarantee, and why: the router chooses among the models of the registry, and a candidate whose name is
an address of a server is refused with the name of the rule. An address is not a model, and a model of an
address of a visitor is a model the deployment never allowed, beside the check of the endpoint of
`ledgerlens/byok/adapter.py`.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import pytest

from ledgerlens.agents.routing import ModelCandidate, RoutingError, route


def test_a_candidate_that_is_an_address_of_a_server_is_refused() -> None:
    """A candidate whose name is an address of a server is refused with the name of the rule."""
    candidates = [
        ModelCandidate(
            name="https://visitor-server.example.com/v1/model",
            capabilities=frozenset({"chat", "tool_calling"}),
            price_snapshot=None,
        ),
    ]

    with pytest.raises(RoutingError) as refusal:
        route(candidates, case_id="EC-01")

    assert "address" in str(refusal.value)


def test_a_candidate_that_is_a_model_of_the_registry_is_not_refused_for_its_name() -> None:
    """A model of the registry is not an address, and the router does not refuse it for its name."""
    candidates = [
        ModelCandidate(
            name="openai:gpt-4.1-mini",
            capabilities=frozenset({"chat", "tool_calling"}),
            price_snapshot=None,
        ),
    ]

    decisions = route(candidates, case_id="EC-01")
    assert decisions["agent"].chosen_model == "openai:gpt-4.1-mini"
