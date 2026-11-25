"""A model a human chose is never silently replaced.

What they guarantee, and why: the router chooses among the models the deployment allowed, and the choice of a
person is the choice. A decision that named a model and then ran another would be a substitution, and a
substitution that nobody decided is a lie about what ran.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from ledgerlens.agents.routing import candidates_of, route
from ledgerlens.byok.registry import ALLOWLIST, profiles_by_name

CASCADE = ("openai:gpt-4.1-mini", "openai:gpt-4.1")


def test_the_decision_names_a_model_of_the_allowed_models_and_never_a_substitution() -> None:
    """Every decision names a model of the allowed models, and the chosen model is the model that runs."""
    candidates = candidates_of(CASCADE, profiles_by_name(ALLOWLIST))
    decisions = route(candidates, case_id="EC-01")

    for slot, decision in decisions.items():
        assert decision.chosen_model in decision.allowed_provider_models, (
            f"the decision of the slot {slot} names a model that was not allowed"
        )


def test_the_model_of_the_visitor_is_the_model_of_the_decision_when_the_deployment_allows_it() -> None:
    """When the deployment allows one model, the decision of every slot names that model."""
    candidates = candidates_of(("openai:gpt-4.1-mini",), profiles_by_name(ALLOWLIST))
    decisions = route(candidates, case_id="EC-01")

    for decision in decisions.values():
        assert decision.chosen_model == "openai:gpt-4.1-mini"
