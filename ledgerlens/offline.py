"""Scripted chat model for offline runs and tests.

`ScriptedChatModel` replays a list of messages in order: plain text, or text plus tool calls. It
implements `_generate` only, so the agent executor takes the non-streaming path and tool calls
survive (a model that rebuilds chunks from text alone drops them). `bind_tools` returns the model
itself, so code written for tool-calling models accepts it.
"""

from __future__ import annotations

import uuid
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import PrivateAttr

ScriptItem = str | AIMessage


class ScriptExhausted(RuntimeError):
    """The model was called more often than its script has messages."""


def text_message(content: str) -> AIMessage:
    """A scripted reply with text only."""
    return AIMessage(content=content)


def tool_call_message(name: str, args: dict[str, Any], *, call_id: str | None = None, content: str = "") -> AIMessage:
    """A scripted reply that asks for one tool call, with optional text beside it."""
    call = {"name": name, "args": args, "id": call_id or f"call-{uuid.uuid4().hex[:8]}", "type": "tool_call"}
    return AIMessage(content=content, tool_calls=[call])


class ScriptedChatModel(BaseChatModel):
    """Replays `script` one message per call and records every prompt it receives."""

    script: list[ScriptItem]

    _cursor: int = PrivateAttr(default=0)
    _calls: list[list[BaseMessage]] = PrivateAttr(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "ledgerlens-scripted"

    @property
    def calls(self) -> list[list[BaseMessage]]:
        """The messages of each call so far, oldest first."""
        return self._calls

    @property
    def remaining(self) -> int:
        """How many scripted messages have not been used."""
        return len(self.script) - self._cursor

    def reset(self) -> None:
        """Rewind the script and forget the recorded calls."""
        self._cursor = 0
        self._calls = []

    def bind_tools(self, tools: Any, **kwargs: Any) -> ScriptedChatModel:  # type: ignore[override]
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        self._calls.append(list(messages))
        if self._cursor >= len(self.script):
            raise ScriptExhausted(
                f"the script has {len(self.script)} scripted message(s) and call {self._cursor + 1} needs another"
            )
        item = self.script[self._cursor]
        self._cursor += 1
        message = AIMessage(content=item) if isinstance(item, str) else item.model_copy(deep=True)
        return ChatResult(generations=[ChatGeneration(message=message)])
