"""Tests of the legacy `LLMRouterChain` router with `MultiPromptChain` and of the modern equivalent.

What they guarantee, and why: a policy question goes to the policy chain and an investigation goes to the
investigation chain (the scripted model answers the router first, then the destination); an unknown path or
"DEFAULT" falls into the default route; the modern equivalent (`build_modern_router`) picks the same
destinations with `RunnableBranch`; the legacy names import from `langchain_classic`.
"""

from __future__ import annotations

import warnings

import pytest

from ledgerlens.chains.router_legacy import (
    DESTINATIONS,
    build_legacy_router,
    build_modern_router,
)
from ledgerlens.offline import ScriptedChatModel

POLICY_Q = "What is the refund deadline for a purchase in another currency?"
INVESTIGATION_Q = "The refund for TX-2048 came in lower than what the customer paid. Why?"


def _route(destination: str, text: str) -> str:
    return f'```json\n{{"destination": "{destination}", "next_inputs": "{text}"}}\n```'


def _legacy(model: ScriptedChatModel):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return build_legacy_router(model)


def test_policy_question_goes_to_the_policy_chain() -> None:
    model = ScriptedChatModel(script=[_route("policy", POLICY_Q), "Policy answer."])
    chain = _legacy(model)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = chain.invoke({"input": POLICY_Q})
    assert result["text"] == "Policy answer."
    router_prompt = "\n".join(str(m.content) for m in model.calls[0])
    assert "policy" in router_prompt and "investigation" in router_prompt
    destination_prompt = "\n".join(str(m.content) for m in model.calls[1])
    assert "polic" in destination_prompt.lower() and POLICY_Q in destination_prompt


def test_investigation_goes_to_the_investigation_chain() -> None:
    model = ScriptedChatModel(script=[_route("investigation", INVESTIGATION_Q), "Investigation answer."])
    chain = _legacy(model)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = chain.invoke({"input": INVESTIGATION_Q})
    assert result["text"] == "Investigation answer."
    destination_prompt = "\n".join(str(m.content) for m in model.calls[1])
    assert "investigat" in destination_prompt.lower()


@pytest.mark.parametrize("destination", ["DEFAULT", "default"])
def test_default_route_when_no_destination_fits(destination: str) -> None:
    model = ScriptedChatModel(script=[_route(destination, "good morning"), "Can you give more details?"])
    chain = _legacy(model)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = chain.invoke({"input": "good morning"})
    assert result["text"] == "Can you give more details?"
    default_prompt = "\n".join(str(m.content) for m in model.calls[1])
    assert "good morning" in default_prompt
    assert "identifier" in default_prompt.lower() or "detail" in default_prompt.lower()


def test_destinations_are_declared() -> None:
    assert {"policy", "investigation"} <= set(DESTINATIONS)


def test_modern_router_picks_the_same_destinations() -> None:
    # The modern router uses a single word (ROUTER_PROMPT) and RunnableBranch instead of JSON in Markdown.
    for word, expected in (("policy", "Policy answer."), ("investigation", "Investigation answer.")):
        model = ScriptedChatModel(script=[word, expected])
        assert build_modern_router(model).invoke({"question": "anything"}) == expected


def test_modern_router_falls_back_to_default_on_unknown_word() -> None:
    model = ScriptedChatModel(script=["banana", "Can you give more details?"])
    assert build_modern_router(model).invoke({"question": "good morning"}) == "Can you give more details?"
