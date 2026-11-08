"""Legacy ReAct agent: `initialize_agent` with `ZERO_SHOT_REACT_DESCRIPTION`.

What they guarantee: (a) each project tool becomes a single-text tool, the only shape this kind of agent
accepts; (b) the prompt has `{chat_history}`, so memory shows up for the model; (c) scenario S01 calls the
tools in the expected order and the arithmetic comes back from `calculate`, not from the model; (d) in S11
the FX source is down and the agent gets the error as data, with no rate at all.

The agent model is a `ScriptedChatModel` that writes the ReAct text (Thought, Action, Action Input). The SQL
of `query_ledger` comes from another scripted model, because the tool has its own. No test uses the network.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from langchain_core.tools import Tool

from ledgerlens.agents.legacy_react import (
    build_legacy_agent,
    build_legacy_memory,
    build_legacy_tools,
    single_string_tool,
)
from ledgerlens.offline import ScriptedChatModel
from ledgerlens.sim.config import SimConfig
from ledgerlens.sim.pipeline import build_ledger
from ledgerlens.tools.calculator import build_calculate_tool
from ledgerlens.tools.fx import FxClient, build_get_reference_fx_tool
from ledgerlens.tools.sql import build_query_ledger_tool

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = json.loads((ROOT / "data" / "scenarios.json").read_text(encoding="utf-8"))["scenarios"]
S01 = next(s for s in SCENARIOS if s["id"] == "S01")
S11 = next(s for s in SCENARIOS if s["id"] == "S11")

FX_SQL = "SELECT kind, applied_rate, applied_at FROM fx_applied WHERE transaction_id = 'TX-2048' ORDER BY applied_at"
LEDGER_SQL = (
    "SELECT r.id, r.requested_amount_minor, r.payout_amount_minor, r.payout_currency "
    "FROM refunds r WHERE r.transaction_id = 'TX-2048'"
)


@pytest.fixture(scope="module")
def ledger_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("ledger") / "ledger.db"
    build_ledger(SimConfig(source="sample"), path).conn.close()
    return path


def step(tool: str, tool_input: str, thought: str = "I need a piece of data.") -> str:
    return f"Thought: {thought}\nAction: {tool}\nAction Input: {tool_input}"


def final(answer: str) -> str:
    return f"Thought: I now know the final answer\nFinal Answer: {answer}"


def agent_for(script: list[str], db: Path, *, fault: bool = False, sql: list[str] | None = None, **kwargs):
    llm = ScriptedChatModel(script=script)
    sql_model = ScriptedChatModel(script=sql or [LEDGER_SQL, FX_SQL])
    fx = FxClient(mode="fixtures", fault=fault, sleep=lambda _: None)
    tools = build_legacy_tools(query_model=sql_model, db_path=db, fx_client=fx)
    return build_legacy_agent(llm, tools, **kwargs), llm


def order_of_tools(result: dict) -> list[str]:
    return [action.tool for action, _ in result["intermediate_steps"]]


# --- single-text adapters ---------------------------------------------------------------------


def test_every_legacy_tool_takes_one_string(ledger_db: Path) -> None:
    tools = build_legacy_tools(query_model=ScriptedChatModel(script=[]), db_path=ledger_db)
    assert [t.name for t in tools] == ["query_ledger", "search_policies", "get_reference_fx", "calculate"]
    for tool in tools:
        assert isinstance(tool, Tool)
        assert set(tool.args) == {"tool_input"} and tool.args["tool_input"]["type"] == "string"
        assert "Input: a JSON object with keys" in tool.description


def test_the_adapter_takes_json_or_the_single_required_argument(ledger_db: Path) -> None:
    sql_model = ScriptedChatModel(script=[FX_SQL, FX_SQL, FX_SQL])
    tool = single_string_tool(build_query_ledger_tool(sql_model, db_path=ledger_db))
    as_json = json.loads(tool.invoke('{"question": "fx for TX-2048", "max_rows": 5}'))
    as_text = json.loads(tool.invoke("fx for TX-2048"))
    quoted = json.loads(tool.invoke('"fx for TX-2048"'))
    assert as_json["ok"] and as_text["ok"] and quoted["ok"]
    assert as_text["data"]["row_count"] == 2


def test_a_bad_input_comes_back_as_an_error_envelope_not_an_exception() -> None:
    fx = single_string_tool(build_get_reference_fx_tool(FxClient(mode="fixtures")))
    not_json = json.loads(fx.invoke("EUR BRL 2026-10-20"))  # three required arguments: loose text does not work
    assert not_json["ok"] is False and not_json["error"]["code"] == "INVALID_INPUT"
    missing = json.loads(fx.invoke('{"from_currency": "EUR"}'))
    assert missing["ok"] is False
    calc = single_string_tool(build_calculate_tool())
    difference = calc.invoke('{"operation": "difference", "values": {"a": "5", "b": "2"}}')
    assert json.loads(difference)["data"]["result"] == "3.00"


# --- prompt and memory ------------------------------------------------------------------------


def test_the_prompt_shows_the_memory_variable(ledger_db: Path) -> None:
    agent, _ = agent_for([final("ok")], ledger_db, memory=build_legacy_memory())
    template = agent.agent.llm_chain.prompt.template
    assert "{chat_history}" in template and "{agent_scratchpad}" in template
    assert "query_ledger" in template and "Action Input" in template


def test_the_second_question_sees_the_first_in_the_prompt(ledger_db: Path) -> None:
    agent, llm = agent_for(
        [final("TX-2048 is refunded."), final("It was TX-2048.")], ledger_db, memory=build_legacy_memory()
    )
    agent.invoke({"input": "What is the status of TX-2048?"})
    agent.invoke({"input": "And which transaction was it again?"})
    first, second = (str(call[-1].content) for call in llm.calls)
    assert "What is the status of TX-2048?" not in first.split("Question:")[0]
    assert "Human: What is the status of TX-2048?" in second and "AI: TX-2048 is refunded." in second


def test_a_system_prefix_with_braces_does_not_break_the_template(ledger_db: Path) -> None:
    agent, llm = agent_for([final("ok")], ledger_db, prefix='Answer in JSON like {"a": 1}. Tools:')
    agent.invoke({"input": "hi"})
    assert 'Answer in JSON like {"a": 1}.' in str(llm.calls[0][-1].content)


# --- S01: the tool order and the arithmetic ---------------------------------------------------


def test_s01_calls_the_tools_in_the_expected_order(ledger_db: Path) -> None:
    truth = S01["truth"]
    script = [
        step("query_ledger", '{"question": "fx rates applied to TX-2048"}'),
        step("search_policies", '{"query": "refund in another currency and exchange rate", "transform": "none"}'),
        step("get_reference_fx", '{"from_currency": "EUR", "to_currency": "BRL", "date": "2026-10-20"}'),
        step(
            "calculate",
            json.dumps(
                {
                    "operation": "fx_gap_breakdown",
                    "values": {
                        "units": "100.00",
                        "charge_rate": truth["charge_rate"],
                        "refund_reference_rate": truth["reference_rate_refund_date"],
                        "refund_applied_rate": truth["applied_rate"],
                    },
                }
            ),
        ),
        final(f"The refund was BRL {truth['refund_brl']} against BRL {truth['charge_brl']} paid."),
    ]
    agent, llm = agent_for(script, ledger_db, sql=[FX_SQL])
    result = agent.invoke({"input": S01["questions"][0]})

    assert order_of_tools(result) == S01["expected_tools"]
    observations = {action.tool: obs for action, obs in result["intermediate_steps"]}
    assert json.loads(observations["query_ledger"])["data"]["rows"][1][:2] == ["refund", truth["applied_rate"]]
    assert json.loads(observations["get_reference_fx"])["data"]["rate"] == truth["reference_rate_refund_date"]
    breakdown = json.loads(observations["calculate"])["data"]["result"]
    assert (breakdown["gap"], breakdown["markup"], breakdown["rate_move"]) == (
        truth["gap_brl"],
        truth["markup_brl"],
        truth["rate_move_brl"],
    )
    # the arithmetic reached the model as an observation, and that is what it read before answering
    assert truth["gap_brl"] in str(llm.calls[-1][-1].content)
    assert llm.remaining == 0
    assert str(truth["refund_brl"]) in result["output"]


# --- S11: the FX source is down ---------------------------------------------------------------


def test_s11_the_fx_error_reaches_the_agent_and_no_rate_is_invented(ledger_db: Path) -> None:
    truth = S11["truth"]
    assert S11["expected_tools"] == ["query_ledger", "get_reference_fx"]
    answer = (
        f"I could not get the reference rate {truth['missing_rate']}: the FX source was unavailable. "
        "The ledger shows the amount paid and the amount refunded, but I cannot explain the difference or compute "
        "the markup without that rate. I sent it to human review."
    )
    script = [
        step("query_ledger", '{"question": "refunds of TX-2048"}'),
        step("get_reference_fx", '{"from_currency": "EUR", "to_currency": "BRL", "date": "2026-10-20"}'),
        final(answer),
    ]
    agent, llm = agent_for(script, ledger_db, fault=True)
    result = agent.invoke({"input": S11["questions"][0]})

    assert order_of_tools(result) == S11["expected_tools"]
    fx_observation = json.loads(result["intermediate_steps"][1][1])
    assert fx_observation["ok"] is False and fx_observation["error"]["code"] == truth["fault_error"]
    assert "rate" not in fx_observation.get("data", {})
    assert truth["fault_error"] in str(llm.calls[-1][-1].content)
    assert truth["missing_rate"] in result["output"]
    # no reference rate shows up in the answer: neither the request date's nor the purchase date's
    for invented in ("5.6339", "5.6679", "2.50", "14.08"):
        assert invented not in result["output"]
    assert "calculate" not in order_of_tools(result)


# --- tolerance of format errors ---------------------------------------------------------------


def test_a_reply_out_of_format_is_handled_and_the_agent_continues(ledger_db: Path) -> None:
    script = ["I will just answer without following the format.", final("Following the format now.")]
    agent, llm = agent_for(script, ledger_db)
    result = agent.invoke({"input": "hi"})
    assert result["output"] == "Following the format now."
    assert "Invalid Format" in str(llm.calls[-1][-1].content)


def test_the_agent_stops_after_the_iteration_limit(ledger_db: Path) -> None:
    loop = [step("calculate", '{"operation": "difference", "values": {"a": "1", "b": "1"}}')] * 3
    agent, _ = agent_for(loop + [final("should not get here")], ledger_db, max_iterations=3)
    result = agent.invoke({"input": "loop"})
    assert "Agent stopped" in result["output"] or "limit" in result["output"].lower()


# --- callbacks --------------------------------------------------------------------------------


def test_a_handler_passed_in_the_call_sees_the_model_and_the_tools(ledger_db: Path) -> None:
    """A handler in the executor constructor only sees the chain; to see model and tools it goes in `config`."""
    import io

    from ledgerlens.observability.callbacks import JsonlCallbackHandler

    sink = io.StringIO()
    agent, _ = agent_for(
        [step("calculate", '{"operation": "difference", "values": {"a": "5", "b": "2"}}'), final("3.00")], ledger_db
    )
    agent.invoke({"input": "5 minus 2"}, config={"callbacks": [JsonlCallbackHandler(sink)]})
    events = {json.loads(line)["event"] for line in sink.getvalue().splitlines()}
    assert {"llm_start", "llm_end", "tool_start", "tool_end", "chain_start"} <= events
