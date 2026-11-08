"""The six-turn conversation, end to end and offline: context, pronoun, window, past case and plan.

What it guarantees, and why: each memory piece already has its own test (`tests/memory`,
`tests/chains/test_dialogue.py`), but what the analyst feels is the whole conversation. Here the pieces work
together, in six scripted turns:

1. session A keeps the context: TX-2048, named in turn 1, still holds in turns 2 to 4;
2. "and its chargeback?" (turn 2) becomes a dispute lookup for TX-2048, without the analyst repeating the id;
3. the conversation goes past the token budget: old exchanges become a summary, recent ones stay verbatim and
   the entities (TX-2048 and the dates) survive the summary;
4. a complex request (turn 4) is broken into plan steps, each with its tool and dependencies;
5. session B is new, with no history, and still recalls the past case of M-17 (turn 5) with the case id as
   the source, and the pronoun of turn 6 still points at the subject of the previous turn.

The model is the `ScriptedChatModel`. The embeddings are fake (word counts), so nothing downloads or uses
the network.
"""

from __future__ import annotations

import json
import re
import zlib
from pathlib import Path

import numpy as np
import pytest
from langchain_core.messages import AIMessage, HumanMessage

from ledgerlens import embeddings as emb
from ledgerlens.chains.dialogue import DialogueState, TurnTag, next_step, tag_turn
from ledgerlens.chains.triage import build_triage_declarative, load_triage_cases
from ledgerlens.embeddings import FastEmbedEmbeddings
from ledgerlens.memory.history import SQLiteChatHistory
from ledgerlens.memory.long_term import CaseMemory
from ledgerlens.offline import ScriptedChatModel
from ledgerlens.schemas import Triage
from ledgerlens.tools.cases import build_recall_cases_tool

DIM = 64
TX = {"transaction_ids": ["TX-2048"]}
M17 = {"merchant_ids": ["M-17"]}

TURN_1 = "What is the status of TX-2048?"
TURN_2 = "and its chargeback?"
TURN_3 = "And its refund? It was paid on 2026-10-15 and refunded on 2026-10-20."
TURN_4 = "Explain why it came in lower, check the FX policy and calculate the difference."
TURN_5 = "Has merchant M-17 had any similar case of a refund with FX before?"
TURN_6 = "and what does the policy say about that?"

ANSWERS = [
    "TX-2048 was captured on 2026-10-15 and is refunded.",
    "TX-2048 has no open dispute.",
    "The refund for TX-2048 went out on 2026-10-20, 17.48 BRL lower.",
]


class WordCountModel:
    """Stands in for fastembed's `TextEmbedding`: each word adds 1 at a fixed position out of 64."""

    def __init__(self, model_name: str, **kwargs: object) -> None:
        self.model_name = model_name

    @staticmethod
    def _vector(text: str) -> np.ndarray:
        vector = np.zeros(DIM, dtype=np.float32)
        for word in re.findall(r"\w+", text.lower()):
            vector[zlib.crc32(word.encode()) % DIM] += 1.0
        return vector

    def passage_embed(self, texts, **kwargs):
        return (self._vector(text) for text in texts)

    def query_embed(self, query, **kwargs):
        return (self._vector(text) for text in ([query] if isinstance(query, str) else query))


@pytest.fixture
def fake_embeddings(monkeypatch: pytest.MonkeyPatch) -> FastEmbedEmbeddings:
    """Fake local embeddings, so the test does not download the real model."""
    monkeypatch.setattr(emb, "_text_embedding_class", lambda: WordCountModel)
    return FastEmbedEmbeddings()


def reply(intent: str, entities: dict | None = None, tags: list[str] | None = None) -> str:
    """The answer the scripted model returns for a turn."""
    return json.dumps(
        {"intent": intent, "entities": entities or {}, "tags": tags or [], "needs_clarification": False},
        ensure_ascii=False,
    )


def run_turns(model: ScriptedChatModel, state: DialogueState, texts: list[str]) -> list[TurnTag]:
    """Tags the turns in order, keeping each one in the session state."""
    tags = []
    for text in texts:
        tag = tag_turn(model, text, state)
        state.remember(tag)
        tags.append(tag)
    return tags


@pytest.fixture
def session_a() -> tuple[DialogueState, list[TurnTag]]:
    """Turns 1 to 4 of session A, tagged with the scripted model."""
    model = ScriptedChatModel(
        script=[
            reply("status_lookup", TX, ["status"]),
            reply("chargeback_status", {}, ["chargeback", "anaphoric"]),
            reply("refund_discrepancy", {"dates": ["2026-10-15", "2026-10-20"]}, ["refund", "anaphoric"]),
            reply("refund_discrepancy", {}, ["refund", "fx", "anaphoric"]),
        ]
    )
    state = DialogueState()
    return state, run_turns(model, state, [TURN_1, TURN_2, TURN_3, TURN_4])


def test_the_context_is_kept_across_the_turns(session_a: tuple[DialogueState, list[TurnTag]]) -> None:
    state, tags = session_a

    assert [tag.entities.transaction_ids for tag in tags] == [["TX-2048"]] * 4
    assert [tag.mentioned_entities.transaction_ids for tag in tags] == [["TX-2048"], [], [], []]
    assert [tag.resolved_from_previous_turn for tag in tags] == [False, True, True, True]
    assert len(state.turns) == 4
    assert state.entities.transaction_ids == ["TX-2048"]
    assert [d.isoformat() for d in state.entities.dates] == ["2026-10-15", "2026-10-20"]


def test_the_chargeback_of_turn_2_resolves_to_the_transaction_of_turn_1(
    session_a: tuple[DialogueState, list[TurnTag]],
) -> None:
    _, tags = session_a

    step = next_step(tags[1])

    assert step.tool == "query_ledger"
    assert step.arguments == {"question": "chargebacks for TX-2048"}
    assert step.needs_clarification is False


def test_a_long_conversation_is_trimmed_and_summarized_keeping_the_entity_ids(tmp_path: Path) -> None:
    summarizer = ScriptedChatModel(script=["The analyst investigated a refund."])
    history = SQLiteChatHistory("session-a", tmp_path / "history.db", max_tokens=40, model=summarizer, keep_recent=2)
    turns = [TURN_1, TURN_2, TURN_3]
    for question, answer in zip(turns, ANSWERS, strict=True):
        history.add_messages([HumanMessage(question), AIMessage(answer)])

    messages = history.messages
    contents = [str(message.content) for message in messages]

    assert messages[0].type == "system"  # the summary comes first
    assert "TX-2048" in contents[0]
    assert "2026-10-15" in contents[0]  # the date of turn 1 only exists in the summary
    assert contents[-2:] == [turns[-1], ANSWERS[-1]]  # recent exchanges stay verbatim
    assert turns[0] not in contents  # the oldest left the window, but stays in the database
    assert summarizer.remaining == 0


def test_the_complex_request_is_decomposed_into_plan_steps(
    session_a: tuple[DialogueState, list[TurnTag]],
) -> None:
    _, tags = session_a
    case = load_triage_cases()[0]  # the lower refund complaint, with a five-step plan
    triage_model = ScriptedChatModel(script=[json.dumps(case.expected.model_dump(mode="json"), ensure_ascii=False)])

    triage = build_triage_declarative(triage_model).invoke({"complaint": tags[3].text})

    assert isinstance(triage, Triage)
    assert len(triage.plan) >= 4
    assert [step.id for step in triage.plan] == [f"S{n}" for n in range(1, len(triage.plan) + 1)]
    assert {step.tool for step in triage.plan} >= {"query_ledger", "search_policies", "get_reference_fx", "calculate"}
    seen: set[str] = set()
    for step in triage.plan:
        assert set(step.depends_on) <= seen, f"{step.id} depends on a step that has not run yet"
        seen.add(step.id)
    assert len(triage.plan[-1].depends_on) >= 2  # the last step joins the results of the earlier ones


def test_a_past_case_is_recalled_in_a_new_session(tmp_path: Path, fake_embeddings: FastEmbedEmbeddings) -> None:
    history = SQLiteChatHistory("session-b", tmp_path / "history.db")
    assert history.messages == []  # session B starts empty: nothing came from session A
    model = ScriptedChatModel(
        script=[
            reply("other", M17, ["recall"]),
            reply("policy_question", {}, ["policy", "anaphoric"]),
        ]
    )
    state = DialogueState()
    recall_tag, policy_tag = run_turns(model, state, [TURN_5, TURN_6])
    recall_step = next_step(recall_tag)

    assert recall_step.tool == "recall_cases"
    assert recall_step.arguments["merchant_id"] == "M-17"

    tool = build_recall_cases_tool(memory=CaseMemory(tmp_path, embeddings=fake_embeddings))
    result = tool.invoke(recall_step.arguments)

    assert result["ok"] is True
    assert result["evidence_ids"] == ["case:CASE-0001"]  # the source the answer cites
    finding = result["data"]["results"][0]
    assert finding["case_id"] == "CASE-0001"
    assert "M-17" in finding["finding"]
    assert "2.5%" in finding["finding"]

    assert policy_tag.entities.merchant_ids == ["M-17"]  # the pronoun of turn 6 still points at the subject
    assert policy_tag.resolved_from_previous_turn is True
    assert next_step(policy_tag).tool == "search_policies"


def test_the_two_sessions_do_not_share_the_dialogue_state(
    session_a: tuple[DialogueState, list[TurnTag]],
) -> None:
    state_a, _ = session_a
    model = ScriptedChatModel(script=[reply("chargeback_status", {}, ["chargeback", "anaphoric"])])

    tag = tag_turn(model, TURN_2, DialogueState())

    assert state_a.entities.transaction_ids == ["TX-2048"]
    assert tag.entities.transaction_ids == []  # without turn 1 in the session, the pronoun has nothing to point at
    assert tag.needs_clarification is True
