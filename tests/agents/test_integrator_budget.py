"""The ceiling of the agent loop: the caps of a turn, the follow-up that spends them and the usage of the turn.

What they guarantee, and why: (a) a model that keeps calling a tool stops at the cap of the calls of the models
and the turn comes back as a result for a human, not as an exception; (b) the follow-up spends what the turn has
left and never gets a ceiling of its own; (c) a turn inside the cap is the turn it was before the ceiling
existed; (d) the usage of the turn is recorded and never passes the budget. The model is a `ScriptedChatModel`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ledgerlens import embeddings as emb
from ledgerlens.agents.integrator import build_integrator, investigate
from ledgerlens.embeddings import FastEmbedEmbeddings
from ledgerlens.memory.long_term import CaseMemory
from ledgerlens.offline import ScriptedChatModel, text_message, tool_call_message
from ledgerlens.retrieval import build_policy_index, index_dir_for, load_policy_documents
from ledgerlens.run_context import SHIPPED_RUN_BUDGET
from ledgerlens.schemas import Entities, InvestigationResult, PlanStep, Triage
from ledgerlens.sim.config import SimConfig
from ledgerlens.sim.pipeline import build_ledger
from ledgerlens.tools.fx import FxClient
from tests.tools import test_policies as base

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = json.loads((ROOT / "data" / "scenarios.json").read_text(encoding="utf-8"))["scenarios"]
S01 = next(s for s in SCENARIOS if s["id"] == "S01")

FX_SQL = "SELECT kind, applied_rate, applied_at FROM fx_applied WHERE transaction_id = 'TX-2048' ORDER BY applied_at"
RECORD = {"kind": "transaction", "id": "TX-2048"}

# The caps of the shipped paths, read from the one place they live (ADR-054).
MAX_MODEL_CALLS = SHIPPED_RUN_BUDGET.max_model_calls or 0
MAX_TOOL_CALLS = SHIPPED_RUN_BUDGET.max_tool_calls or 0


@pytest.fixture(scope="module")
def ledger_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("ledger") / "ledger.db"
    build_ledger(SimConfig(source="sample"), path).conn.close()
    return path


@pytest.fixture
def embeddings(monkeypatch: pytest.MonkeyPatch) -> FastEmbedEmbeddings:
    monkeypatch.setattr(emb, "_text_embedding_class", lambda: base.WordCountModel)
    return FastEmbedEmbeddings()


@pytest.fixture
def index_root(tmp_path: Path, embeddings: FastEmbedEmbeddings) -> Path:
    root = tmp_path / "index"
    build_policy_index(load_policy_documents(base.POLICIES), embeddings, index_dir_for(root, embeddings))
    return root


@pytest.fixture
def cases(tmp_path: Path, embeddings: FastEmbedEmbeddings) -> CaseMemory:
    return CaseMemory(tmp_path / "cases", embeddings=embeddings)


def triage_json(*steps: tuple[str, str | None]) -> str:
    """A `Triage` as JSON with the given `(goal, tool)` steps, as the triage model would return it."""
    plan = [PlanStep(id=f"S{n}", goal=goal, tool=tool, depends_on=[]) for n, (goal, tool) in enumerate(steps, start=1)]
    triage = Triage(
        intent="refund_discrepancy",
        entities=Entities(transaction_ids=["TX-2048"]),
        urgency="normal",
        plan=plan,
        needs_clarification=False,
        clarification_question=None,
    )
    return triage.model_dump_json()


def triage_model(*steps: tuple[str, str | None]) -> ScriptedChatModel:
    """The triage model of a plan with the given steps."""
    return ScriptedChatModel(script=[triage_json(*steps)])


def integrator_for(
    db: Path,
    index_root: Path,
    cases: CaseMemory,
    model: ScriptedChatModel,
    *,
    triage: ScriptedChatModel | None = None,
    **kw: Any,
):
    """The integrator of the test: the scripted model of the agent and a triage that has one call and no plan."""
    return build_integrator(
        model,
        db_path=db,
        verifier=lambda result, *, nli=None: result,
        query_model=ScriptedChatModel(script=[FX_SQL]),
        fx_client=FxClient(mode="fixtures", sleep=lambda _: None),
        index_root=index_root,
        case_memory=cases,
        triage_model=triage if triage is not None else ScriptedChatModel(script=[]),
        **kw,
    )


def usage_of(spans: list[Any]) -> dict[str, Any]:
    """The usage the turn recorded, read from the trace of the investigation."""
    for span in reversed(spans):
        if span.name == "investigate" and isinstance(span.outputs, dict):
            usage = span.outputs.get("usage")
            if usage:
                return dict(usage)
    return {}


def test_a_model_that_keeps_calling_a_tool_stops_at_the_cap_and_comes_back_as_a_result(
    ledger_db: Path, index_root: Path, cases: CaseMemory
) -> None:
    """The defect of ADR-054: the loop of the demo and of the evaluation had no ceiling at all."""
    script = [tool_call_message("get_ledger_record", RECORD) for _ in range(MAX_MODEL_CALLS + 5)]
    model = ScriptedChatModel(script=script)
    agent = integrator_for(ledger_db, index_root, cases, model)

    result = investigate(agent, "Where is my refund?", thread_id="t-cap")

    assert isinstance(result, InvestigationResult)  # a result, not an exception
    assert len(model.calls) == MAX_MODEL_CALLS - 1  # the triage is a call of a model too, and it takes one
    assert result.requires_human_review is True
    assert result.recommended_action == "escalate_to_human"
    assert any("max_model_calls" in item for item in result.missing_information)  # the cap that stopped the turn
    assert any(str(MAX_MODEL_CALLS) in item for item in result.missing_information)  # and its value


def test_the_follow_up_spends_the_ceiling_of_the_turn_and_not_a_ceiling_of_its_own(
    ledger_db: Path, index_root: Path, cases: CaseMemory
) -> None:
    """The turn used its whole allowance; the follow-up finds nothing left and does not run."""
    script = [tool_call_message("get_ledger_record", RECORD) for _ in range(MAX_MODEL_CALLS - 2)]
    script.append(text_message("First answer."))
    script.append(text_message("The answer of the follow-up."))
    model = ScriptedChatModel(script=script)
    triage = triage_model(("read the record", "get_ledger_record"), ("read the rate", "get_reference_fx"))
    agent = integrator_for(ledger_db, index_root, cases, model, triage=triage)

    result = investigate(agent, "Where is my refund?", thread_id="t-follow-up")

    assert len(model.calls) == MAX_MODEL_CALLS - 1  # the follow-up did not get a fresh allowance
    assert result.answer == "First answer."  # the answer that already existed stands
    assert any("max_model_calls" in item for item in result.missing_information)
    assert result.requires_human_review is True


def test_a_turn_inside_the_cap_is_the_turn_it_was_before_the_ceiling(
    ledger_db: Path, index_root: Path, cases: CaseMemory
) -> None:
    """The ceiling does not touch a turn that works: the same answer, the same evidence, no human."""
    script = [
        tool_call_message("query_ledger", {"question": "fx rates applied to TX-2048"}),
        text_message("The refund was applied at a lower rate [sql:1]."),
    ]
    model = ScriptedChatModel(script=script)
    agent = integrator_for(ledger_db, index_root, cases, model)

    result = investigate(agent, S01["questions"][0], thread_id="t-inside")

    assert result.answer == "The refund was applied at a lower rate [sql:1]."
    assert [record.tool for record in result.tool_trace] == ["query_ledger"]
    assert result.tool_trace[0].ok is True
    assert [evidence.id for evidence in result.evidence] == ["sql:1"]
    assert result.missing_information == []
    assert result.requires_human_review is False
    assert result.recommended_action == "none"


def test_the_usage_of_the_turn_is_recorded_and_never_passes_the_budget(
    ledger_db: Path, index_root: Path, cases: CaseMemory
) -> None:
    """A reader has to see what the turn spent against what it was allowed."""
    script = [
        tool_call_message("query_ledger", {"question": "fx rates applied to TX-2048"}),
        text_message("The refund was applied at a lower rate [sql:1]."),
    ]
    model = ScriptedChatModel(script=script)
    agent = integrator_for(ledger_db, index_root, cases, model)
    spans: list[Any] = []

    investigate(agent, S01["questions"][0], thread_id="t-usage", on_event=spans.append)

    usage = usage_of(spans)
    assert usage, "the turn recorded no usage"
    assert usage["model_calls"] == len(model.calls) + 1  # the triage is a call of a model too
    assert usage["model_calls"] <= MAX_MODEL_CALLS
    assert usage["tool_calls"] == 1
    assert usage["tool_calls"] <= MAX_TOOL_CALLS
    assert usage["price_known"] is False  # the price of the model of the demo is unknown, so no money at all
    assert usage["observed_cost_usd"] is None
    assert usage["estimated_cost_usd"] is None
    assert usage["cut_by"] is None


def test_a_graph_that_runs_out_of_steps_comes_back_as_a_result_and_not_as_an_exception(
    ledger_db: Path, index_root: Path, cases: CaseMemory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The backstop of the ceiling: the graph stops, and the cap it names is the cap of the calls of the models."""
    monkeypatch.setattr("ledgerlens.agents.integrator.recursion_limit_for", lambda caps: 2)
    script = [tool_call_message("get_ledger_record", RECORD) for _ in range(5)]
    model = ScriptedChatModel(script=script)
    agent = integrator_for(ledger_db, index_root, cases, model)

    result = investigate(agent, "Where is my refund?", thread_id="t-steps")

    assert isinstance(result, InvestigationResult)
    assert result.requires_human_review is True
    assert result.recommended_action == "escalate_to_human"
    assert any("max_model_calls" in item for item in result.missing_information)


def test_the_result_carries_the_calls_the_tokens_and_the_two_costs(
    ledger_db: Path, index_root: Path, cases: CaseMemory
) -> None:
    """The usage of the turn travels on the result, and not only on the trace.

    Why it matters: a reader of the result has to see what the turn spent without opening the trace, and the
    money of a turn whose price is unknown is unknown and never zero.
    """
    script = [
        tool_call_message("query_ledger", {"question": "fx rates applied to TX-2048"}),
        text_message("The refund was applied at a lower rate [sql:1]."),
    ]
    model = ScriptedChatModel(script=script)
    agent = integrator_for(ledger_db, index_root, cases, model)

    result = investigate(agent, S01["questions"][0], thread_id="t-result-usage")

    assert result.usage is not None
    assert result.usage["model_calls"] == len(model.calls) + 1  # the triage is a call of a model too
    assert result.usage["tool_calls"] == 1
    assert result.usage["input_tokens"] >= 0
    assert result.usage["output_tokens"] >= 0
    assert result.usage["observed_cost_usd"] is None
    assert result.usage["estimated_cost_usd"] is None
    assert result.usage["price_known"] is False
