"""Legacy ReAct agent: `initialize_agent` with `AgentType.ZERO_SHOT_REACT_DESCRIPTION`.

Why it exists: the project shows this agent as a demonstration, next to the modern `create_agent`
(`modern.py`, ADR-010), because the API was deprecated. The code comes from the `langchain-classic` package.

How it works: the model writes text in the ReAct format, one round at a time::

    Thought: I need the FX rate on the day of the refund
    Action: get_reference_fx
    Action Input: {"from_currency": "EUR", "to_currency": "BRL", "date": "2026-10-20"}

The executor reads that text, calls the tool and returns `Observation: ...` to the model, until
`Final Answer:` shows up. Three consequences shape this module:

- This kind of agent only accepts tools with ONE text input. The project's tools have
  several typed arguments, so `single_string_tool` wraps each one: it reads the text as a JSON object
  (or, if the tool has a single required argument, as the value itself), calls the tool
  and returns the result envelope as JSON. Bad input comes back as an error envelope, never as an
  exception, so the agent can react.
- Memory only reaches the model if the prompt has `{chat_history}`. The suffix here has it, and the memory
  is a `ConversationBufferMemory` with the same key.
- The model can leave the format. `handle_parsing_errors=True` returns the error as an observation and the agent
  tries again, instead of stopping.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from langchain_classic.agents import AgentExecutor, AgentType, initialize_agent
from langchain_classic.memory import ConversationBufferMemory
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool, StructuredTool, Tool

from ledgerlens.agents.modern import DEFAULT_SYSTEM_PROMPT, build_modern_tools
from ledgerlens.tools.envelope import error

MEMORY_KEY = "chat_history"

# `{chat_history}` is what makes memory reach the model; `{input}` and `{agent_scratchpad}` are
# the ReAct format variables (the question and the scratchpad of earlier rounds).
LEGACY_SUFFIX = "Begin!\n\nConversation so far:\n{chat_history}\n\nQuestion: {input}\nThought:{agent_scratchpad}"

# The langchain-classic default prefix is generic; this one states the job and ends before the
# list of tools, which LangChain inserts right after it.
LEGACY_PREFIX = f"{DEFAULT_SYSTEM_PROMPT}\n\nYou have access to the following tools:"


def _field_names(tool: StructuredTool) -> tuple[list[str], list[str]]:
    schema = tool.args_schema
    fields = getattr(schema, "model_fields", {})
    required = [name for name, field in fields.items() if field.is_required()]
    optional = [name for name in fields if name not in required]
    return required, optional


def _parse_input(text: str, required: list[str]) -> dict[str, Any] | None:
    """The model's text becomes arguments. `None` when it is not possible to tell which value goes to which argument."""
    cleaned = text.strip()
    if cleaned.startswith("```"):  # the model sometimes fences the JSON with backticks
        cleaned = cleaned.strip("`").removeprefix("json").strip()
    try:
        parsed: Any = json.loads(cleaned)
    except json.JSONDecodeError:
        parsed = cleaned
    if isinstance(parsed, dict):
        return parsed
    if len(required) == 1:  # a single required argument: the bare text is its value
        return {required[0]: parsed if isinstance(parsed, str) else cleaned}
    return None


def single_string_tool(tool: StructuredTool) -> Tool:
    """Wraps a tool with several arguments into a single-text tool."""
    required, optional = _field_names(tool)
    keys = ", ".join([*(f"{name} (required)" for name in required), *(f"{name} (optional)" for name in optional)])
    description = f"{tool.description} Input: a JSON object with keys {keys}."

    def run(text: str) -> str:
        arguments = _parse_input(text, required)
        if arguments is None:
            hint = f"expected a JSON object with keys {', '.join(required)}"
            return json.dumps(error("INVALID_INPUT", f"input is not a JSON object; {hint}", True), ensure_ascii=False)
        result = tool.invoke(arguments)
        # With `handle_validation_error`, the tool already returns text when the schema rejects the input.
        return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)

    return Tool(name=tool.name, func=run, description=description)


def build_legacy_tools(**kwargs: Any) -> list[Tool]:
    """The same four tools as the modern agent, each one wrapped as single text.

    The arguments are those of `build_modern_tools` (`query_model`, `db_path`, `fx_client`, ...).
    """
    return [single_string_tool(tool) for tool in build_modern_tools(**kwargs)]  # type: ignore[arg-type]


def build_legacy_memory() -> ConversationBufferMemory:
    """Conversation memory: keeps the whole exchanges and delivers them in `{chat_history}`."""
    return ConversationBufferMemory(memory_key=MEMORY_KEY, input_key="input", output_key="output")


def build_legacy_agent(
    llm: BaseChatModel,
    tools: Sequence[BaseTool],
    *,
    prefix: str = LEGACY_PREFIX,
    memory: ConversationBufferMemory | None = None,
    max_iterations: int = 8,
    **kwargs: Any,
) -> AgentExecutor:
    """Builds the agent with `initialize_agent`. Call it with `agent.invoke({"input": "..."})`.

    `prefix` can be the project's system prompt: `{}` braces in the text are escaped, because the
    prefix goes into a text template. Without `memory`, the agent creates its own; pass yours to
    share the conversation between agents. Other arguments go straight to the executor. A callback
    handler passed here sees only the chain; to also see the model and the tools, pass it in
    `agent.invoke(..., config={"callbacks": [...]})`.
    """
    escaped = prefix.replace("{", "{{").replace("}", "}}")
    memory = memory or build_legacy_memory()  # the prompt requires `chat_history`, so there is always a memory
    return initialize_agent(
        list(tools),
        llm,
        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        memory=memory,
        handle_parsing_errors=True,
        max_iterations=max_iterations,
        return_intermediate_steps=True,
        agent_kwargs={
            "prefix": escaped,
            "suffix": LEGACY_SUFFIX,
            "input_variables": ["input", MEMORY_KEY, "agent_scratchpad"],
        },
        **kwargs,
    )
