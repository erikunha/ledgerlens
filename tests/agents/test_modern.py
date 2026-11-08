"""Modern agent: LangChain 1.x `create_agent` with the same tools as the legacy agent (ADR-010).

What they guarantee: (a) structured tools go in directly, with no single-text adapter; (b) S01 calls the
tools in the same order as the legacy agent; (c) the per-session history lives in the `checkpointer`, so a
second question with the same `thread_id` sees the first; (d) in S11 the FX error reaches the model as
data. The model is a `ScriptedChatModel` that returns ready tool calls.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from ledgerlens.agents.modern import (
    DEFAULT_SYSTEM_PROMPT,
    build_investigation_tools,
    build_modern_agent,
    build_modern_tools,
    build_tools_agent_executor,
)
from ledgerlens.offline import ScriptedChatModel, text_message, tool_call_message
from ledgerlens.sim.config import SimConfig
from ledgerlens.sim.pipeline import build_ledger
from ledgerlens.tools.fx import FxClient

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = json.loads((ROOT / "data" / "scenarios.json").read_text(encoding="utf-8"))["scenarios"]
S01 = next(s for s in SCENARIOS if s["id"] == "S01")
S11 = next(s for s in SCENARIOS if s["id"] == "S11")

FX_SQL = "SELECT kind, applied_rate, applied_at FROM fx_applied WHERE transaction_id = 'TX-2048' ORDER BY applied_at"


@pytest.fixture(scope="module")
def ledger_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("ledger") / "ledger.db"
    build_ledger(SimConfig(source="sample"), path).conn.close()
    return path


def tools_for(db: Path, *, fault: bool = False):
    return build_modern_tools(
        query_model=ScriptedChatModel(script=[FX_SQL]),
        db_path=db,
        fx_client=FxClient(mode="fixtures", fault=fault, sleep=lambda _: None),
    )


def tool_messages(result: dict) -> list[ToolMessage]:
    return [m for m in result["messages"] if isinstance(m, ToolMessage)]


def test_the_tools_are_the_structured_ones(ledger_db: Path) -> None:
    tools = tools_for(ledger_db)
    assert [t.name for t in tools] == ["query_ledger", "search_policies", "get_reference_fx", "calculate"]
    assert set(tools[2].args) == {"from_currency", "to_currency", "date", "source"}  # separate arguments


def test_s01_runs_the_same_tool_order_as_the_legacy_agent(ledger_db: Path) -> None:
    truth = S01["truth"]
    script = [
        tool_call_message("query_ledger", {"question": "fx rates applied to TX-2048"}),
        tool_call_message("search_policies", {"query": "refund in another currency", "transform": "none"}),
        tool_call_message("get_reference_fx", {"from_currency": "EUR", "to_currency": "BRL", "date": "2026-10-20"}),
        tool_call_message(
            "calculate",
            {
                "operation": "fx_gap_breakdown",
                "values": {
                    "units": "100.00",
                    "charge_rate": truth["charge_rate"],
                    "refund_reference_rate": truth["reference_rate_refund_date"],
                    "refund_applied_rate": truth["applied_rate"],
                },
            },
        ),
        text_message(f"The refund was BRL {truth['refund_brl']} against BRL {truth['charge_brl']} paid."),
    ]
    llm = ScriptedChatModel(script=script)
    agent = build_modern_agent(llm, tools_for(ledger_db))
    result = agent.invoke({"messages": [HumanMessage(S01["questions"][0])]})

    assert [m.name for m in tool_messages(result)] == S01["expected_tools"]
    breakdown = json.loads(tool_messages(result)[-1].content)["data"]["result"]
    assert breakdown["gap"] == truth["gap_brl"]
    assert truth["refund_brl"] in result["messages"][-1].content
    assert llm.remaining == 0


def test_the_system_prompt_reaches_the_model(ledger_db: Path) -> None:
    llm = ScriptedChatModel(script=[text_message("ok")])
    build_modern_agent(llm, tools_for(ledger_db), system_prompt="TEST PROMPT").invoke(
        {"messages": [HumanMessage("hi")]}
    )
    assert llm.calls[0][0].type == "system" and llm.calls[0][0].content == "TEST PROMPT"
    assert "fx" in DEFAULT_SYSTEM_PROMPT.lower() and "{" not in DEFAULT_SYSTEM_PROMPT


def test_the_checkpointer_keeps_the_session_history(ledger_db: Path) -> None:
    llm = ScriptedChatModel(script=[text_message("TX-2048 is refunded."), text_message("It was TX-2048.")])
    agent = build_modern_agent(llm, tools_for(ledger_db), checkpointer=InMemorySaver())
    session = {"configurable": {"thread_id": "session-1"}}
    agent.invoke({"messages": [HumanMessage("What is the status of TX-2048?")]}, session)
    agent.invoke({"messages": [HumanMessage("And which transaction was it again?")]}, session)
    second_call = " ".join(str(m.content) for m in llm.calls[1])
    assert "What is the status of TX-2048?" in second_call and "TX-2048 is refunded." in second_call
    other = {"configurable": {"thread_id": "session-2"}}
    llm.reset()
    agent.invoke({"messages": [HumanMessage("new")]}, other)
    assert "TX-2048" not in " ".join(str(m.content) for m in llm.calls[0] if m.type != "system")


def test_s11_the_fx_error_is_data_for_the_model(ledger_db: Path) -> None:
    truth = S11["truth"]
    script = [
        tool_call_message("query_ledger", {"question": "refunds of TX-2048"}),
        tool_call_message("get_reference_fx", {"from_currency": "EUR", "to_currency": "BRL", "date": "2026-10-20"}),
        text_message(f"I could not get the rate {truth['missing_rate']}: the source was unavailable."),
    ]
    llm = ScriptedChatModel(script=script)
    agent = build_modern_agent(llm, tools_for(ledger_db, fault=True))
    result = agent.invoke({"messages": [HumanMessage(S11["questions"][0])]})
    assert [m.name for m in tool_messages(result)] == S11["expected_tools"]
    fx = json.loads(tool_messages(result)[-1].content)
    assert fx["ok"] is False and fx["error"]["code"] == truth["fault_error"]
    assert truth["missing_rate"] in result["messages"][-1].content


def test_the_investigation_tools_add_the_record_and_case_tools(ledger_db: Path, tmp_path: Path) -> None:
    from ledgerlens.memory.long_term import CaseMemory

    tools = build_investigation_tools(
        query_model=ScriptedChatModel(script=[FX_SQL]),
        db_path=ledger_db,
        fx_client=FxClient(mode="fixtures", sleep=lambda _: None),
        case_memory=CaseMemory(tmp_path / "cases"),
    )
    assert [t.name for t in tools] == [
        "query_ledger",
        "get_ledger_record",
        "search_policies",
        "get_reference_fx",
        "calculate",
        "recall_cases",
    ]
    assert [t.name for t in build_modern_tools(db_path=ledger_db)] == [  # the four earlier ones stay the same
        "query_ledger",
        "search_policies",
        "get_reference_fx",
        "calculate",
    ]


def test_the_legacy_tools_agent_executor_runs_the_same_tools(ledger_db: Path) -> None:
    llm = ScriptedChatModel(
        script=[
            tool_call_message("query_ledger", {"question": "fx rates applied to TX-2048"}),
            text_message("The rates were read from the ledger."),
        ]
    )
    executor = build_tools_agent_executor(llm, tools_for(ledger_db))
    result = executor.invoke({"input": S01["questions"][0]})

    assert result["output"] == "The rates were read from the ledger."
    assert [action.tool for action, _ in result["intermediate_steps"]] == ["query_ledger"]
    assert llm.calls[0][0].content == DEFAULT_SYSTEM_PROMPT
