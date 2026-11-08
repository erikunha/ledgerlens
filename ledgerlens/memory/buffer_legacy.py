"""Demo chatbot with `ConversationBufferMemory`: short-term working memory (CoALA).

Why it exists: it shows a chatbot with `ConversationBufferMemory`, the `langchain-classic` class,
as a demonstration, because it was deprecated. In the CoALA taxonomy this module is working memory:
it lasts only while the conversation lasts, keeps the whole exchanges and is gone when the session closes. It is
the simplest and most exact strategy (it loses no detail), and so it grows without bound, which is the flaw
that the token window fixes in `ledgerlens/memory/history.py`.

How it works: on each turn the memory returns the earlier exchanges in `{history}`, the prompt puts that
history next to the question, the model answers and the exchange is saved in memory. Since the history goes into
the prompt, an entity said earlier (TX-2048) is still available on the next turn without the customer repeating
the identifier.

Deprecation notice: `ConversationBufferMemory` comes from `langchain-classic` and is deprecated in LangChain
1.x (ADR-010). Here it is a short demonstration next to the SQLite history, which is the path actually used
in the integrator.
"""

from __future__ import annotations

import warnings
from typing import Any

from langchain_classic.memory import ConversationBufferMemory
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate

MEMORY_KEY = "history"
INPUT_KEY = "input"
OUTPUT_KEY = "output"

CHAT_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are the LedgerLens assistant, who helps with questions about payments. "
            "Use the conversation history to keep the context: identifiers (TX-0000, R-0000, CB-0000, "
            "ST-0000, M-00, C-0000), amounts with currency and dates said earlier still hold. "
            "If the history does not carry what the question asks for, ask for what is missing.",
        ),
        ("human", "Conversation history:\n{history}\n\nQuestion: {input}"),
    ]
)


def build_legacy_memory() -> ConversationBufferMemory:
    """The legacy memory: keeps the whole exchanges and delivers them in `{history}`."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # the deprecation is the point of the demonstration, see the docstring
        return ConversationBufferMemory(
            memory_key=MEMORY_KEY,
            input_key=INPUT_KEY,
            output_key=OUTPUT_KEY,
            return_messages=False,
        )


class BufferChatbot:
    """A chatbot that remembers earlier exchanges because the legacy memory returns them in the prompt."""

    def __init__(self, model: BaseChatModel, *, memory: ConversationBufferMemory | None = None) -> None:
        self.model = model
        self.memory = memory if memory is not None else build_legacy_memory()

    def chat(self, message: str) -> str:
        """Answers one turn, with the history in the prompt, and saves the exchange in memory."""
        inputs = {INPUT_KEY: message}
        variables = self.memory.load_memory_variables(inputs)
        prompt = CHAT_PROMPT.invoke({**variables, INPUT_KEY: message})
        answer = str(self.model.invoke(prompt).content)
        self.memory.save_context(inputs, {OUTPUT_KEY: answer})
        return answer

    def invoke(self, payload: str | dict[str, Any], config: Any = None, **kwargs: Any) -> str:
        """The same as `chat`, with the input in chain format (`{"input": ...}`) or as text."""
        return self.chat(_question(payload))

    def history(self) -> str:
        """The history as text, the way the memory hands it to the prompt."""
        return str(self.memory.load_memory_variables({})[MEMORY_KEY])


def _question(payload: str | dict[str, Any]) -> str:
    """Accepts text, `{"input": ...}` or `{"question": ...}` and returns the question."""
    if isinstance(payload, str):
        return payload
    for key in (INPUT_KEY, "question"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    raise ValueError("the chatbot needs the question under 'input' or 'question'")


def build_buffer_chatbot(model: BaseChatModel) -> BufferChatbot:
    """Builds the buffer chatbot. Call it with `chatbot.chat("question")`."""
    return BufferChatbot(model)
