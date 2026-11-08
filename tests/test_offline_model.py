"""ScriptedChatModel replays text and tool-call messages through the real agent loop."""

from __future__ import annotations

import pytest
from langchain_classic.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool

from ledgerlens.offline import ScriptedChatModel, ScriptExhausted, text_message, tool_call_message


@tool
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


@tool
def double(x: int) -> int:
    """Double an integer."""
    return x * 2


PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", "You are a calculator."),
        ("human", "{input}"),
        MessagesPlaceholder("agent_scratchpad"),
    ]
)


def _executor(model: ScriptedChatModel, tools: list) -> AgentExecutor:
    agent = create_openai_tools_agent(model, tools, PROMPT)
    return AgentExecutor(agent=agent, tools=tools, return_intermediate_steps=True)


def test_tool_call_then_final_answer_through_the_agent_executor() -> None:
    model = ScriptedChatModel(script=[tool_call_message("add", {"a": 2, "b": 3}), "The sum is 5."])
    result = _executor(model, [add]).invoke({"input": "What is 2 + 3?"})

    assert result["output"] == "The sum is 5."
    (step,) = result["intermediate_steps"]
    action, observation = step
    assert action.tool == "add"
    assert action.tool_input == {"a": 2, "b": 3}
    assert observation == 5
    assert model.remaining == 0


def test_the_second_model_call_sees_the_tool_result() -> None:
    model = ScriptedChatModel(script=[tool_call_message("add", {"a": 2, "b": 3}), "done"])
    _executor(model, [add]).invoke({"input": "What is 2 + 3?"})

    assert len(model.calls) == 2
    assert isinstance(model.calls[0][-1], HumanMessage)
    tool_messages = [m for m in model.calls[1] if isinstance(m, ToolMessage)]
    assert [m.content for m in tool_messages] == ["5"]


def test_tools_run_in_the_scripted_order() -> None:
    model = ScriptedChatModel(
        script=[
            tool_call_message("add", {"a": 1, "b": 2}),
            tool_call_message("double", {"x": 3}),
            "Result is 6.",
        ]
    )
    result = _executor(model, [add, double]).invoke({"input": "go"})
    assert [action.tool for action, _ in result["intermediate_steps"]] == ["add", "double"]
    assert result["output"] == "Result is 6."


def test_a_message_may_carry_text_and_a_tool_call() -> None:
    model = ScriptedChatModel(script=[tool_call_message("add", {"a": 4, "b": 4}, content="Let me add."), "8"])
    result = _executor(model, [add]).invoke({"input": "go"})
    assert [action.tool for action, _ in result["intermediate_steps"]] == ["add"]
    assert result["output"] == "8"


def test_bind_tools_returns_the_model_unchanged() -> None:
    model = ScriptedChatModel(script=["x"])
    assert model.bind_tools([add, double]) is model


def test_plain_text_replay_with_invoke_batch_and_stream() -> None:
    model = ScriptedChatModel(script=["one", "two", "three"])
    assert model.invoke("a").content == "one"
    assert [m.content for m in model.batch(["b"])] == ["two"]
    assert "".join(chunk.content for chunk in model.stream("c")) == "three"


def test_script_accepts_strings_and_ai_messages() -> None:
    model = ScriptedChatModel(script=["plain", AIMessage(content="message"), text_message("helper")])
    assert [model.invoke("x").content for _ in range(3)] == ["plain", "message", "helper"]


def test_exhausted_script_raises_a_clear_error() -> None:
    model = ScriptedChatModel(script=["only"])
    model.invoke("a")
    with pytest.raises(ScriptExhausted, match="1 scripted"):
        model.invoke("b")


def test_reset_rewinds_the_script_and_clears_the_record() -> None:
    model = ScriptedChatModel(script=["only"])
    model.invoke("a")
    model.reset()
    assert model.remaining == 1
    assert model.calls == []
    assert model.invoke("again").content == "only"


def test_records_every_prompt_it_received() -> None:
    model = ScriptedChatModel(script=["a", "b"])
    model.invoke("first question")
    model.invoke("second question")
    assert [call[-1].content for call in model.calls] == ["first question", "second question"]


def test_tool_call_message_builds_a_valid_tool_call() -> None:
    message = tool_call_message("add", {"a": 1, "b": 2}, call_id="call-9")
    assert message.tool_calls == [{"name": "add", "args": {"a": 1, "b": 2}, "id": "call-9", "type": "tool_call"}]
    assert message.content == ""
    auto = tool_call_message("add", {"a": 1, "b": 2})
    assert auto.tool_calls[0]["id"]
