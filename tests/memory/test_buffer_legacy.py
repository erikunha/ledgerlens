"""Chatbot with `ConversationBufferMemory`: the short-term memory that keeps the whole conversation.

What they guarantee, and why: the history of the exchanges comes back in the next turn's prompt, so an entity
named earlier (TX-2048) stays available without the customer repeating the identifier; the memory used is
the legacy `ConversationBufferMemory` class from `langchain-classic`; and one turn's answer does not leak into
the next turn's history.
"""

from __future__ import annotations

import warnings

from ledgerlens.memory.buffer_legacy import BufferChatbot, build_buffer_chatbot
from ledgerlens.offline import ScriptedChatModel


def _chatbot(script: list[str]) -> BufferChatbot:
    return build_buffer_chatbot(ScriptedChatModel(script=script))


def test_the_memory_is_the_legacy_conversation_buffer_memory() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from langchain_classic.memory import ConversationBufferMemory

    chatbot = _chatbot([])
    assert isinstance(chatbot.memory, ConversationBufferMemory)


def test_the_history_of_the_previous_turn_goes_back_to_the_model() -> None:
    model = ScriptedChatModel(script=["First answer.", "Second answer."])
    chatbot = build_buffer_chatbot(model)

    chatbot.chat("What happened with TX-2048?")
    chatbot.chat("And the amount?")

    second_prompt = "\n".join(str(message.content) for message in model.calls[1])
    assert "What happened with TX-2048?" in second_prompt
    assert "First answer." in second_prompt


def test_entities_survive_across_turns() -> None:
    """The entity named in the first turn stays visible in the second, without being repeated."""
    model = ScriptedChatModel(script=["Understood, TX-2048.", "TX-2048 had a lower refund."])
    chatbot = build_buffer_chatbot(model)

    chatbot.chat("Please investigate TX-2048.")
    answer = chatbot.chat("And its refund?")

    second_prompt = "\n".join(str(message.content) for message in model.calls[1])
    assert "TX-2048" in second_prompt
    assert "Please investigate TX-2048." in second_prompt
    assert answer == "TX-2048 had a lower refund."


def test_both_turns_stay_in_the_memory() -> None:
    chatbot = _chatbot(["First answer.", "Second answer."])

    chatbot.chat("First question.")
    chatbot.chat("Second question.")

    stored = [str(message.content) for message in chatbot.memory.chat_memory.messages]
    assert stored == ["First question.", "First answer.", "Second question.", "Second answer."]


def test_the_history_grows_without_a_limit() -> None:
    """The full buffer cuts nothing: it is the comparison with the token window."""
    chatbot = _chatbot([f"Answer {n}" for n in range(4)])

    for n in range(4):
        chatbot.chat(f"Question {n}")

    assert len(chatbot.memory.chat_memory.messages) == 8
