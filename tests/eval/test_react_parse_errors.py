"""A ReAct output-parsing failure is not a tool call.

With `handle_parsing_errors`, the legacy agent records a malformed step as an `AgentAction` whose tool is
`_Exception`. Turning it into a tool call made the result builder reject the whole case, so one bad step from
the model erased the case from the online report.
"""

from __future__ import annotations

from langchain_core.agents import AgentAction
from langchain_core.messages import AIMessage

from ledgerlens.agents.integrator import _assemble
from ledgerlens.eval.run import _react_messages


def test_a_parsing_failure_step_is_left_out_of_the_tool_calls() -> None:
    steps = [
        (AgentAction(tool="_Exception", tool_input="Invalid Format: Missing 'Action:'", log="bad"), "retry"),
        (AgentAction(tool="calculate", tool_input='{"expression": "1 + 1"}', log="ok"), '{"ok": true, "data": {}}'),
    ]
    messages = _react_messages("What is 1 + 1?", steps, "2")

    names = [call["name"] for m in messages if isinstance(m, AIMessage) for call in m.tool_calls]
    assert names == ["calculate"]


def test_a_case_with_a_parsing_failure_still_assembles() -> None:
    steps = [(AgentAction(tool="_Exception", tool_input="Invalid Format", log="bad"), "retry")]
    result = _assemble(
        "Why was I charged twice?", "t", _react_messages("Why was I charged twice?", steps, "answer"), [0]
    )

    assert result.tool_trace == []
