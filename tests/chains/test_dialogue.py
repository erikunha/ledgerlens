"""Tests of the dialogue chain: each turn becomes an intent and entities, and the tags pick the step.

What they guarantee:
- every tagged turn has an intent and entities, even when the model answers badly;
- a pronoun ("and its chargeback?") points at the transaction of the previous turn;
- the turn's tags pick the tool and the arguments of the next step;
- the session keeps the turns already tagged and the entities seen;
- an unusable answer becomes a request for clarification, instead of breaking the conversation.

The model is the `ScriptedChatModel`: one JSON answer per call, in the order they are asked for.
"""

from __future__ import annotations

import json

from ledgerlens.chains.dialogue import (
    DialogueState,
    NextStep,
    TurnTag,
    next_step,
    tag_turn,
)
from ledgerlens.offline import ScriptedChatModel

TX_2048 = {"transaction_ids": ["TX-2048"]}


def reply(
    intent: str,
    entities: dict | None = None,
    tags: list[str] | None = None,
    clarify: bool = False,
) -> str:
    """The answer the scripted model returns for a turn."""
    return json.dumps(
        {
            "intent": intent,
            "entities": entities or {},
            "tags": tags or [],
            "needs_clarification": clarify,
        },
        ensure_ascii=False,
    )


def test_each_turn_gets_an_intent_and_entities() -> None:
    model = ScriptedChatModel(script=[reply("status_lookup", TX_2048, ["status"])])
    tag = tag_turn(model, "What is the status of TX-2048?", DialogueState())
    assert isinstance(tag, TurnTag)
    assert tag.intent == "status_lookup"
    assert tag.entities.transaction_ids == ["TX-2048"]
    assert tag.mentioned_entities.transaction_ids == ["TX-2048"]
    assert tag.needs_clarification is False
    assert tag.tags == ["status"]


def test_a_pronoun_resolves_to_the_transaction_of_the_previous_turn() -> None:
    model = ScriptedChatModel(
        script=[
            reply("status_lookup", TX_2048, ["status"]),
            reply("chargeback_status", {}, ["chargeback", "anaphoric"]),
        ]
    )
    state = DialogueState()
    state.remember(tag_turn(model, "What is the status of TX-2048?", state))
    tag = tag_turn(model, "and its chargeback?", state)
    assert tag.entities.transaction_ids == ["TX-2048"]
    assert tag.mentioned_entities.transaction_ids == []
    assert tag.resolved_from_previous_turn is True


def test_a_possessive_pronoun_also_resolves_to_the_previous_transaction() -> None:
    model = ScriptedChatModel(
        script=[
            reply("status_lookup", TX_2048, ["status"]),
            reply("chargeback_status", {}, ["chargeback", "anaphoric"]),
        ]
    )
    state = DialogueState()
    state.remember(tag_turn(model, "What is the status of TX-2048?", state))
    tag = tag_turn(model, "and what about their chargeback?", state)
    assert tag.entities.transaction_ids == ["TX-2048"]
    assert tag.resolved_from_previous_turn is True


def test_the_tags_choose_the_next_step() -> None:
    model = ScriptedChatModel(
        script=[
            reply("status_lookup", TX_2048, ["status"]),
            reply("chargeback_status", {}, ["chargeback", "anaphoric"]),
        ]
    )
    state = DialogueState()
    state.remember(tag_turn(model, "What is the status of TX-2048?", state))
    tag = tag_turn(model, "and its chargeback?", state)
    step = next_step(tag)
    assert isinstance(step, NextStep)
    assert step.tool == "query_ledger"
    assert step.arguments["question"] == "chargebacks for TX-2048"
    assert step.needs_clarification is False


def test_a_turn_without_identifiers_asks_for_clarification() -> None:
    model = ScriptedChatModel(script=[reply("status_lookup", {}, [])])
    tag = tag_turn(model, "what is the status?", DialogueState())
    assert tag.needs_clarification is True
    step = next_step(tag)
    assert step.tool is None
    assert step.needs_clarification is True
    assert step.clarification_question


def test_the_state_remembers_the_turns_and_the_entities() -> None:
    model = ScriptedChatModel(script=[reply("status_lookup", TX_2048, ["status"])])
    state = DialogueState()
    tag = tag_turn(model, "What is the status of TX-2048?", state)
    returned = state.remember(tag)
    assert returned is state
    assert state.turns == [tag]
    assert state.last_turn is tag
    assert state.entities.transaction_ids == ["TX-2048"]


def test_the_prompt_carries_the_entities_already_known() -> None:
    model = ScriptedChatModel(
        script=[
            reply("status_lookup", TX_2048, ["status"]),
            reply("chargeback_status", {}, ["chargeback", "anaphoric"]),
        ]
    )
    state = DialogueState()
    state.remember(tag_turn(model, "What is the status of TX-2048?", state))
    tag_turn(model, "and its chargeback?", state)
    second_prompt = "\n".join(str(message.content) for message in model.calls[1])
    assert "TX-2048" in second_prompt


def test_a_turn_that_names_another_transaction_does_not_inherit_the_old_one() -> None:
    model = ScriptedChatModel(
        script=[
            reply("status_lookup", TX_2048, ["status"]),
            reply("status_lookup", {"transaction_ids": ["TX-2051"]}, ["status"]),
        ]
    )
    state = DialogueState()
    state.remember(tag_turn(model, "What is the status of TX-2048?", state))
    tag = tag_turn(model, "and TX-2051?", state)
    assert tag.entities.transaction_ids == ["TX-2051"]
    assert tag.resolved_from_previous_turn is False


def test_a_policy_question_goes_to_the_policy_search() -> None:
    question = "Can I still get my money back after a month?"
    model = ScriptedChatModel(script=[reply("policy_question", {}, ["policy"])])
    tag = tag_turn(model, question, DialogueState())
    step = next_step(tag)
    assert step.tool == "search_policies"
    assert step.arguments["query"] == question


def test_a_question_about_a_past_case_goes_to_the_case_memory() -> None:
    model = ScriptedChatModel(script=[reply("other", {"merchant_ids": ["M-17"]}, ["recall"])])
    tag = tag_turn(model, "Has merchant M-17 had any similar case before?", DialogueState())
    step = next_step(tag)
    assert step.tool == "recall_cases"
    assert step.arguments["merchant_id"] == "M-17"


def test_a_rate_question_with_two_currencies_and_a_date_calls_the_rate_tool() -> None:
    model = ScriptedChatModel(
        script=[
            reply(
                "fx_question",
                {"currencies": ["EUR", "BRL"], "dates": ["2026-10-20"]},
                ["fx"],
            )
        ]
    )
    tag = tag_turn(model, "What was the EUR to BRL rate on 2026-10-20?", DialogueState())
    step = next_step(tag)
    assert step.tool == "get_reference_fx"
    assert step.arguments == {"from_currency": "EUR", "to_currency": "BRL", "date": "2026-10-20"}


def test_a_rate_question_without_a_date_starts_from_the_ledger() -> None:
    model = ScriptedChatModel(script=[reply("fx_question", {"currencies": ["EUR", "BRL"]}, ["fx"])])
    tag = tag_turn(model, "What was the EUR to BRL rate?", DialogueState())
    step = next_step(tag)
    assert step.tool == "query_ledger"


def test_an_invalid_answer_is_repaired_once() -> None:
    good = reply("status_lookup", TX_2048, ["status"])
    model = ScriptedChatModel(script=['{"intent": "nonexistent", "entities": {}}', good])
    tag = tag_turn(model, "What is the status of TX-2048?", DialogueState())
    assert tag.intent == "status_lookup"
    assert tag.entities.transaction_ids == ["TX-2048"]


def test_a_broken_answer_becomes_a_clarification_instead_of_a_crash() -> None:
    model = ScriptedChatModel(script=["{broken", "{still broken"])
    tag = tag_turn(model, "What is the status of TX-2048?", DialogueState())
    assert tag.intent == "other"
    assert tag.entities.transaction_ids == []
    assert tag.needs_clarification is True
    assert next_step(tag).tool is None
