"""Legacy integrator: `AgentExecutor` and `RunnableWithMessageHistory` with the six tools and the project verifier.

What they guarantee, and why: (a) an S01 run through the `AgentExecutor` calls the tools in the expected order and
returns an `InvestigationResult` whose numeric claims go through the real verifier; (b) the SQLite history
separates sessions: the second turn with the same `session_id` sees the first, another `session_id` does not;
(c) a new object over the same file recovers the session; (d) a result with a contradicted claim does not become
a case in long-term memory; (e) a tool error with no recovery becomes missing information, as in the
`create_agent` integrator. The model is a `ScriptedChatModel`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ledgerlens import embeddings as emb
from ledgerlens.agents.executor_integrator import (
    ExecutorIntegrator,
    build_executor_integrator,
    investigate_with_executor,
)
from ledgerlens.embeddings import FastEmbedEmbeddings
from ledgerlens.memory.long_term import CaseMemory
from ledgerlens.offline import ScriptedChatModel, text_message, tool_call_message
from ledgerlens.retrieval import build_policy_index, index_dir_for, load_policy_documents
from ledgerlens.schemas import Claim, InvestigationResult, Verdict
from ledgerlens.sim.config import SimConfig
from ledgerlens.sim.pipeline import build_ledger
from ledgerlens.tools.fx import FxClient
from tests.agents.test_integrator import (
    FX_CALL,
    LEDGER_CALL,
    S01,
    S11,
    WRONG_FX,
    fx_days,
    injected_refund_result,
    s01_script,
    seen_by,
    supporting_verifier,
    triage_json,
    triage_script,
)
from tests.tools import test_policies as base

FX_SQL = "SELECT kind, applied_rate, applied_at FROM fx_applied WHERE transaction_id = 'TX-2048' ORDER BY applied_at"


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


def executor_for(
    ledger_db: Path,
    index_root: Path,
    cases: CaseMemory,
    history_db: Path,
    script: list,
    *,
    verifier=None,
    fault: bool = False,
) -> ExecutorIntegrator:
    kwargs = {} if verifier is None else {"verifier": verifier}
    return build_executor_integrator(
        ScriptedChatModel(script=script),
        db_path=ledger_db,
        history_db_path=history_db,
        query_model=ScriptedChatModel(script=[FX_SQL]),
        fx_client=FxClient(mode="fixtures", fault=fault, sleep=lambda _: None),
        index_root=index_root,
        case_memory=cases,
        **kwargs,
    )


def test_the_executor_has_the_six_tools_of_the_contract(
    ledger_db: Path, index_root: Path, cases: CaseMemory, tmp_path: Path
) -> None:
    agent = executor_for(ledger_db, index_root, cases, tmp_path / "h.db", [], verifier=supporting_verifier([]))
    assert [t.name for t in agent.tools] == [
        "query_ledger",
        "get_ledger_record",
        "search_policies",
        "get_reference_fx",
        "calculate",
        "recall_cases",
    ]
    assert [t.name for t in agent.executor.tools] == [t.name for t in agent.tools]


def test_s01_runs_the_expected_tools_and_the_real_verifier_supports_the_numbers(
    ledger_db: Path, index_root: Path, cases: CaseMemory, tmp_path: Path
) -> None:
    pytest.importorskip("ledgerlens.verify")
    truth = S01["truth"]
    # The verifier only links a claim to evidence when the sentence cites the id; that is why the answer cites.
    script = [
        *s01_script()[:-1],
        text_message(f"The refund was BRL {truth['refund_brl']} against BRL {truth['charge_brl']} paid [calc:1]."),
    ]
    agent = executor_for(ledger_db, index_root, cases, tmp_path / "h.db", script)  # default verifier
    result = investigate_with_executor(agent, S01["questions"][0], session_id="t-s01")

    assert isinstance(result, InvestigationResult)
    assert [r.tool for r in result.tool_trace] == S01["expected_tools"]
    assert [r.step for r in result.tool_trace] == [1, 2, 3, 4]
    assert all(r.ok and r.evidence_ids for r in result.tool_trace)
    assert result.tool_trace[3].input["operation"] == "fx_gap_breakdown"  # the call arguments reach the trace
    assert result.session_id == "t-s01" and result.question == S01["questions"][0]
    assert S01["truth"]["refund_brl"] in result.answer
    assert S01["truth"]["gap_brl"] in next(e for e in result.evidence if e.id == "calc:1").content
    assert [e.id for e in result.evidence][0] == "sql:1" and [e.id for e in result.evidence][-1] == "calc:1"
    numeric = [c for c in result.claims if c.kind == "numeric"]
    assert numeric, "the answer cites values and the verifier must extract numeric claims"
    labels = {v.claim_id: v.label for v in result.verdicts}
    assert all(labels[c.id] == "supported" for c in numeric)


def test_the_verifier_gets_the_assembled_result_and_its_output_is_final(
    ledger_db: Path, index_root: Path, cases: CaseMemory, tmp_path: Path
) -> None:
    calls: list[InvestigationResult] = []
    agent = executor_for(
        ledger_db, index_root, cases, tmp_path / "h.db", s01_script(), verifier=supporting_verifier(calls)
    )
    result = investigate_with_executor(agent, S01["questions"][0], session_id="t-v")
    assert len(calls) == 1 and calls[0].tool_trace == result.tool_trace
    assert result.verdicts[0].label == "supported"


def test_a_fully_supported_result_becomes_a_case(
    ledger_db: Path, index_root: Path, cases: CaseMemory, tmp_path: Path
) -> None:
    agent = executor_for(
        ledger_db, index_root, cases, tmp_path / "h.db", s01_script(), verifier=supporting_verifier([])
    )
    before = {r["case_id"] for r in cases.records()}
    investigate_with_executor(agent, S01["questions"][0], session_id="t-case")
    written = [r for r in cases.records() if r["case_id"] not in before]
    assert len(written) == 1 and written[0]["session_id"] == "t-case"


def test_a_contradicted_result_is_not_remembered(
    ledger_db: Path, index_root: Path, cases: CaseMemory, tmp_path: Path
) -> None:
    def contradicting(result: InvestigationResult, *, nli=None) -> InvestigationResult:
        claim = Claim(id="CL1", text="x", kind="fact", evidence_ids=[result.evidence[0].id])
        verdict = Verdict(claim_id="CL1", label="contradicted", method="nli")
        return result.model_copy(update={"claims": [claim], "verdicts": [verdict], "requires_human_review": True})

    agent = executor_for(ledger_db, index_root, cases, tmp_path / "h.db", s01_script(), verifier=contradicting)
    before = len(cases.records())
    result = investigate_with_executor(agent, S01["questions"][0], session_id="t-no-case")
    assert len(cases.records()) == before
    assert result.requires_human_review is True


def test_the_same_session_sees_the_first_turn_and_a_new_session_does_not(
    ledger_db: Path, index_root: Path, cases: CaseMemory, tmp_path: Path
) -> None:
    model = ScriptedChatModel(script=[text_message("first"), text_message("second"), text_message("other")])
    agent = build_executor_integrator(
        model,
        db_path=ledger_db,
        history_db_path=tmp_path / "h.db",
        verifier=lambda r, *, nli=None: r,
        index_root=index_root,
        case_memory=cases,
    )
    first = investigate_with_executor(agent, "Question one about TX-2048", session_id="a")
    second = investigate_with_executor(agent, "Question two", session_id="a")
    investigate_with_executor(agent, "Question three", session_id="b")

    seen = lambda call: " ".join(str(m.content) for m in call)  # noqa: E731
    assert first.answer == "first" and second.answer == "second"
    assert "Question one about TX-2048" in seen(model.calls[1]) and "first" in seen(model.calls[1])
    assert "Question one about TX-2048" not in seen(model.calls[2])  # the other session starts empty


def test_the_trace_of_a_second_turn_holds_only_that_turn(
    ledger_db: Path, index_root: Path, cases: CaseMemory, tmp_path: Path
) -> None:
    script = [
        tool_call_message("calculate", {"operation": "fx_gap_breakdown", "values": {}}),
        text_message("first"),
        text_message("second"),
    ]
    agent = build_executor_integrator(
        ScriptedChatModel(script=script),
        db_path=ledger_db,
        history_db_path=tmp_path / "h.db",
        verifier=lambda r, *, nli=None: r,
        index_root=index_root,
        case_memory=cases,
    )
    first = investigate_with_executor(agent, "Question one", session_id="a")
    second = investigate_with_executor(agent, "Question two", session_id="a")
    assert len(first.tool_trace) == 1 and second.tool_trace == []


def test_a_new_object_over_the_same_sqlite_file_recovers_the_session(
    ledger_db: Path, index_root: Path, cases: CaseMemory, tmp_path: Path
) -> None:
    history_db = tmp_path / "h.db"
    verifier = lambda r, *, nli=None: r  # noqa: E731
    first = executor_for(ledger_db, index_root, cases, history_db, [text_message("Noted: TX-2048.")], verifier=verifier)
    investigate_with_executor(first, "Remember TX-2048", session_id="s1")

    model = ScriptedChatModel(script=[text_message("It was TX-2048.")])
    second = build_executor_integrator(
        model,
        db_path=ledger_db,
        history_db_path=history_db,
        verifier=verifier,
        index_root=index_root,
        case_memory=cases,
    )
    investigate_with_executor(second, "Which one was it?", session_id="s1")
    prompt = " ".join(str(m.content) for m in model.calls[0])
    assert "Remember TX-2048" in prompt and "Noted: TX-2048." in prompt

    other = ScriptedChatModel(script=[text_message("I do not know.")])
    elsewhere = build_executor_integrator(
        other,
        db_path=ledger_db,
        history_db_path=tmp_path / "other.db",
        verifier=verifier,
        index_root=index_root,
        case_memory=cases,
    )
    investigate_with_executor(elsewhere, "Which one was it?", session_id="s1")  # same session_id, another file
    assert "Remember TX-2048" not in " ".join(str(m.content) for m in other.calls[0])


def test_s11_an_unrecovered_tool_error_is_missing_information(
    ledger_db: Path, index_root: Path, cases: CaseMemory, tmp_path: Path
) -> None:
    script = [
        tool_call_message("query_ledger", {"question": "refunds of TX-2048"}),
        tool_call_message("get_reference_fx", {"from_currency": "EUR", "to_currency": "BRL", "date": "2026-10-20"}),
        text_message(f"I could not get the rate {S11['truth']['missing_rate']}: the source was unavailable."),
    ]
    agent = executor_for(
        ledger_db, index_root, cases, tmp_path / "h.db", script, verifier=lambda r, *, nli=None: r, fault=True
    )
    result = investigate_with_executor(agent, S11["questions"][0], session_id="t-s11")

    assert [r.tool for r in result.tool_trace] == S11["expected_tools"]
    failed = result.tool_trace[-1]
    assert failed.ok is False and failed.error_code == S11["truth"]["fault_error"]
    assert any("get_reference_fx" in item for item in result.missing_information)
    assert result.requires_human_review is True
    assert all(e.tool != "get_reference_fx" for e in result.evidence)


def test_the_system_prompt_is_the_integrator_prompt(
    ledger_db: Path, index_root: Path, cases: CaseMemory, tmp_path: Path
) -> None:
    from ledgerlens.agents.integrator import INTEGRATOR_SYSTEM_PROMPT

    model = ScriptedChatModel(script=[text_message("ok")])
    agent = build_executor_integrator(
        model,
        db_path=ledger_db,
        history_db_path=tmp_path / "h.db",
        verifier=lambda r, *, nli=None: r,
        index_root=index_root,
        case_memory=cases,
    )
    investigate_with_executor(agent, "Question", session_id="p")
    assert model.calls[0][0].content == INTEGRATOR_SYSTEM_PROMPT


def test_each_step_carries_the_duration_measured_by_the_callbacks(
    ledger_db: Path, index_root: Path, cases: CaseMemory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Clock:  # each reading moves 5 ms, so each tool takes 5 ms
        now = 0.0

        def perf_counter(self) -> float:
            self.now += 0.005
            return self.now

    monkeypatch.setattr("ledgerlens.agents.integrator.time", Clock())
    agent = executor_for(
        ledger_db, index_root, cases, tmp_path / "h.db", s01_script(), verifier=lambda r, *, nli=None: r
    )
    result = investigate_with_executor(agent, S01["questions"][0], session_id="t-time")
    assert [r.duration_ms for r in result.tool_trace] == [5, 5, 5, 5]


def test_recall_cases_reads_the_case_memory_given_to_the_builder(
    ledger_db: Path, index_root: Path, cases: CaseMemory, tmp_path: Path
) -> None:
    writer = executor_for(
        ledger_db, index_root, cases, tmp_path / "h.db", s01_script(), verifier=supporting_verifier([])
    )
    investigate_with_executor(writer, S01["questions"][0], session_id="t-first")  # writes a case into `cases`

    script = [tool_call_message("recall_cases", {"query": "refund in another currency TX-2048"}), text_message("ok")]
    reader = executor_for(ledger_db, index_root, cases, tmp_path / "h2.db", script, verifier=lambda r, *, nli=None: r)
    result = investigate_with_executor(reader, "Are there similar cases?", session_id="t-second")
    assert result.tool_trace[0].tool == "recall_cases" and result.tool_trace[0].ok is True
    # the configured memory has seed cases; only the builder's has the case written in this session
    assert any(S01["truth"]["refund_brl"] in e.content for e in result.evidence if e.id.startswith("case:"))


def test_an_input_the_schema_rejects_is_a_failed_step_not_an_exception(
    ledger_db: Path, index_root: Path, cases: CaseMemory, tmp_path: Path
) -> None:
    """The input error handler returns text, not the envelope dict; the step has to stay in the trace."""
    script = [tool_call_message("calculate", {"values": {}}), text_message("I could not calculate.")]  # no operation
    agent = executor_for(ledger_db, index_root, cases, tmp_path / "h.db", script, verifier=lambda r, *, nli=None: r)
    result = investigate_with_executor(agent, "Calculate", session_id="t-bad")
    assert [(r.tool, r.ok, r.error_code) for r in result.tool_trace] == [("calculate", False, "INVALID_INPUT")]
    assert any("calculate" in item for item in result.missing_information)


def test_the_iteration_limit_stops_the_loop_and_keeps_only_the_steps_that_ran(
    ledger_db: Path, index_root: Path, cases: CaseMemory, tmp_path: Path
) -> None:
    script = [
        tool_call_message("query_ledger", {"question": "fx rates applied to TX-2048"}),
        tool_call_message("query_ledger", {"question": "fx rates applied to TX-2048"}),
        text_message("never gets here"),
    ]
    agent = build_executor_integrator(
        ScriptedChatModel(script=script),
        db_path=ledger_db,
        history_db_path=tmp_path / "h.db",
        verifier=lambda r, *, nli=None: r,
        query_model=ScriptedChatModel(script=[FX_SQL, FX_SQL]),
        index_root=index_root,
        case_memory=cases,
        max_iterations=1,
    )
    result = investigate_with_executor(agent, "Question", session_id="t-limit")
    assert [r.tool for r in result.tool_trace] == ["query_ledger"]
    assert "never gets here" not in result.answer


# --- triage feeds the agent ----------------------------------------------------------------------------


def triaged_executor(
    ledger_db: Path,
    index_root: Path,
    cases: CaseMemory,
    history_db: Path,
    model: ScriptedChatModel,
    triage: ScriptedChatModel,
) -> ExecutorIntegrator:
    return build_executor_integrator(
        model,
        triage_model=triage,
        db_path=ledger_db,
        history_db_path=history_db,
        verifier=lambda r, *, nli=None: r,
        query_model=ScriptedChatModel(script=[FX_SQL]),
        index_root=index_root,
        case_memory=cases,
    )


def test_the_triage_plan_is_given_to_the_executor_and_kept_in_the_result(
    ledger_db: Path, index_root: Path, cases: CaseMemory, tmp_path: Path
) -> None:
    model = ScriptedChatModel(
        script=[
            tool_call_message("calculate", {"values": {}}),
            text_message("Looked it up."),
            text_message("I do not need both."),
        ]
    )
    triage = triage_script(("query the ledger", "query_ledger"), ("search the policy", "search_policies"))
    agent = triaged_executor(ledger_db, index_root, cases, tmp_path / "h.db", model, triage)

    result = investigate_with_executor(agent, S01["questions"][0], session_id="t-plan")

    for call in range(len(model.calls)):  # the plan holds on every loop turn, not only the first
        assert "query the ledger" in seen_by(model, call) and "search_policies" in seen_by(model, call)
    assert result.triage is not None and [s.tool for s in result.triage.plan] == ["query_ledger", "search_policies"]
    assert any("calculate" in d for d in result.plan_deviations)  # the tool outside the plan is recorded
    assert any("S1" in d for d in result.plan_deviations)


def test_a_planned_tool_that_was_not_called_is_asked_for_once_and_then_it_runs(
    ledger_db: Path, index_root: Path, cases: CaseMemory, tmp_path: Path
) -> None:
    model = ScriptedChatModel(
        script=[
            tool_call_message("query_ledger", {"question": "fx rates applied to TX-2048"}),
            text_message("Answer without the FX rate."),
            tool_call_message("get_reference_fx", FX_CALL),
            text_message("Answer with the reference rate."),
        ]
    )
    triage = triage_script(("query the ledger", "query_ledger"), ("read the reference rate", "get_reference_fx"))
    agent = triaged_executor(ledger_db, index_root, cases, tmp_path / "h.db", model, triage)

    result = investigate_with_executor(agent, "Question", session_id="t-follow-up")

    asked = seen_by(model, 2)
    assert "S2" in asked and "get_reference_fx" in asked and "Triage plan" in asked  # the plan holds on the extra turn
    assert [r.tool for r in result.tool_trace] == ["query_ledger", "get_reference_fx"]
    assert result.answer == "Answer with the reference rate."
    assert any(
        "S2" in d and "get_reference_fx" in d and "asked" in d and "called it" in d for d in result.plan_deviations
    )
    assert not any("was in the plan and was not called" in d for d in result.plan_deviations)


def test_the_follow_up_happens_once_even_when_the_executor_still_skips_the_tool(
    ledger_db: Path, index_root: Path, cases: CaseMemory, tmp_path: Path
) -> None:
    model = ScriptedChatModel(
        script=[
            tool_call_message("query_ledger", {"question": "fx rates applied to TX-2048"}),
            text_message("First answer."),
            text_message("I do not need the FX rate: the ledger already has the applied rate."),
            text_message("never gets here"),
        ]
    )
    triage = triage_script(("query the ledger", "query_ledger"), ("read the reference rate", "get_reference_fx"))
    agent = triaged_executor(ledger_db, index_root, cases, tmp_path / "h.db", model, triage)

    result = investigate_with_executor(agent, "Question", session_id="t-once")

    assert len(model.calls) == 3
    assert result.answer == "I do not need the FX rate: the ledger already has the applied rate."
    assert [r.tool for r in result.tool_trace] == ["query_ledger"]
    assert any("get_reference_fx" in d and "did not call it" in d for d in result.plan_deviations)


def test_nothing_is_asked_when_every_planned_tool_ran_or_there_is_no_plan(
    ledger_db: Path, index_root: Path, cases: CaseMemory, tmp_path: Path
) -> None:
    model = ScriptedChatModel(
        script=[tool_call_message("query_ledger", {"question": "fx rates applied to TX-2048"}), text_message("ok")]
    )
    triage = triage_script(("query the ledger", "query_ledger"), ("answer", None))
    agent = triaged_executor(ledger_db, index_root, cases, tmp_path / "h.db", model, triage)
    result = investigate_with_executor(agent, "Question", session_id="t-full")
    assert len(model.calls) == 2 and result.plan_deviations == []

    unplanned = ScriptedChatModel(script=[text_message("No plan.")])
    agent = triaged_executor(ledger_db, index_root, cases, tmp_path / "h2.db", unplanned, ScriptedChatModel(script=[]))
    investigate_with_executor(agent, "P", session_id="t-none")
    assert len(unplanned.calls) == 1


def test_a_follow_up_that_fails_keeps_the_answer_already_given(
    ledger_db: Path, index_root: Path, cases: CaseMemory, tmp_path: Path
) -> None:
    model = ScriptedChatModel(
        script=[
            tool_call_message("query_ledger", {"question": "fx rates applied to TX-2048"}),
            text_message("First."),
        ]
    )
    triage = triage_script(("query the ledger", "query_ledger"), ("read the reference rate", "get_reference_fx"))
    agent = triaged_executor(ledger_db, index_root, cases, tmp_path / "h.db", model, triage)
    result = investigate_with_executor(agent, "Question", session_id="t-fail")
    assert result.answer == "First."
    assert any("get_reference_fx" in d and "follow-up failed" in d for d in result.plan_deviations)


def test_the_plan_is_not_stored_in_the_session_history(
    ledger_db: Path, index_root: Path, cases: CaseMemory, tmp_path: Path
) -> None:
    # the second message answers the plan follow-up the first question triggers (query_ledger did not run)
    model = ScriptedChatModel(script=[text_message("first"), text_message("no query"), text_message("second")])
    triage = ScriptedChatModel(script=[triage_json(("query the ledger", "query_ledger")), triage_json()])
    agent = triaged_executor(ledger_db, index_root, cases, tmp_path / "h.db", model, triage)
    investigate_with_executor(agent, "Question one", session_id="a")
    investigate_with_executor(agent, "Question two", session_id="a")
    assert "Triage plan" in seen_by(model, 2) and seen_by(model, 2).count("query the ledger") == 0


def test_a_request_the_triage_cannot_plan_asks_back_and_the_session_keeps_the_exchange(
    ledger_db: Path, index_root: Path, cases: CaseMemory, tmp_path: Path
) -> None:
    model = ScriptedChatModel(script=[text_message("It was TX-2048.")])
    triage = triage_script(clarification="What is the transaction id?")
    agent = triaged_executor(ledger_db, index_root, cases, tmp_path / "h.db", model, triage)

    asked = investigate_with_executor(agent, "The money did not arrive", session_id="t-ask")

    assert model.calls == []
    assert asked.answer == "What is the transaction id?" and asked.recommended_action == "ask_for_clarification"
    assert asked.tool_trace == [] and asked.requires_human_review is False

    agent.triage = None  # the second turn needs no triage; only the history matters
    investigate_with_executor(agent, "It is TX-2048", session_id="t-ask")
    assert "What is the transaction id?" in seen_by(model) and "The money did not arrive" in seen_by(model)


def test_a_follow_up_the_triage_cannot_read_alone_still_reaches_the_executor(
    ledger_db: Path, index_root: Path, cases: CaseMemory, tmp_path: Path
) -> None:
    model = ScriptedChatModel(script=[text_message("It was TX-2048."), text_message("TX-2048 again.")])
    triage = ScriptedChatModel(script=[triage_json(("answer", None)), triage_json(clarification="Which transaction?")])
    agent = triaged_executor(ledger_db, index_root, cases, tmp_path / "h.db", model, triage)
    investigate_with_executor(agent, "What is the status of TX-2048?", session_id="t-follow")
    second = investigate_with_executor(agent, "Which transaction did I just ask about?", session_id="t-follow")
    assert second.answer == "TX-2048 again." and len(model.calls) == 2


def test_a_triage_that_fails_does_not_stop_the_executor(
    ledger_db: Path, index_root: Path, cases: CaseMemory, tmp_path: Path
) -> None:
    model = ScriptedChatModel(script=[text_message("Answer without a plan.")])
    result = investigate_with_executor(
        triaged_executor(ledger_db, index_root, cases, tmp_path / "h.db", model, ScriptedChatModel(script=[])),
        "Question",
        session_id="t-broken",
    )
    assert result.answer == "Answer without a plan." and result.triage is None
    assert "Triage plan" not in seen_by(model)


def test_the_executor_default_verifier_reads_the_free_text_from_its_own_ledger(
    ledger_db: Path, index_root: Path, cases: CaseMemory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LEDGERLENS_LEDGER_DB", str(tmp_path / "elsewhere.db"))
    agent = executor_for(ledger_db, index_root, cases, tmp_path / "h.db", [])
    out = agent.verifier(injected_refund_result())
    assert out.requires_human_review is True
    assert any("suspicious-text" in item and "R-0750" in item for item in out.missing_information)


# --- FX for a date the ledger does not have ------------------------------------------------------------


def unplanned_executor(ledger_db: Path, index_root: Path, cases: CaseMemory, tmp_path: Path, model: ScriptedChatModel):
    return triaged_executor(ledger_db, index_root, cases, tmp_path / "h.db", model, ScriptedChatModel(script=[]))


def test_a_rate_requested_for_a_date_the_ledger_does_not_have_is_asked_again_once_and_the_executor_redoes_it(
    ledger_db: Path, index_root: Path, cases: CaseMemory, tmp_path: Path
) -> None:
    model = ScriptedChatModel(
        script=[
            LEDGER_CALL,
            WRONG_FX,
            text_message("The refund was higher than the reference conversion."),
            tool_call_message("get_reference_fx", FX_CALL),
            text_message("With the FX rate of 2026-10-20 the reference conversion is higher. [fx:2026-10-20:EUR-BRL]"),
        ]
    )
    agent = unplanned_executor(ledger_db, index_root, cases, tmp_path, model)

    result = investigate_with_executor(agent, S01["questions"][0], session_id="t-fx-date")

    asked = seen_by(model, 3)
    assert "Date check" in asked and "2026-09-01" in asked and "Triage plan" not in asked
    assert fx_days(result) == ["2026-09-01", "2026-10-20"]
    assert result.answer.startswith("With the FX rate of 2026-10-20")
    assert any("2026-09-01" in d and "asked" in d and "redid" in d for d in result.plan_deviations)


def test_the_date_follow_up_happens_once_in_the_executor_too(
    ledger_db: Path, index_root: Path, cases: CaseMemory, tmp_path: Path
) -> None:
    model = ScriptedChatModel(
        script=[LEDGER_CALL, WRONG_FX, text_message("First."), text_message("I kept the date."), text_message("no")]
    )
    agent = unplanned_executor(ledger_db, index_root, cases, tmp_path, model)
    result = investigate_with_executor(agent, S01["questions"][0], session_id="t-fx-once")
    assert len(model.calls) == 4 and result.answer == "I kept the date."
    assert any("2026-09-01" in d and "kept the date" in d for d in result.plan_deviations)


def test_no_date_follow_up_in_the_executor_when_the_date_is_the_ledgers_or_there_is_no_ledger_evidence(
    ledger_db: Path, index_root: Path, cases: CaseMemory, tmp_path: Path
) -> None:
    for n, script in enumerate(
        [
            [LEDGER_CALL, tool_call_message("get_reference_fx", FX_CALL), text_message("ok")],
            [WRONG_FX, text_message("ok")],
        ]
    ):
        model = ScriptedChatModel(script=script)
        agent = triaged_executor(
            ledger_db, index_root, cases, tmp_path / f"h{n}.db", model, ScriptedChatModel(script=[])
        )
        result = investigate_with_executor(agent, S01["questions"][0], session_id=f"t-fx-none-{n}")
        assert len(model.calls) == len(script) and not any("asked" in d for d in result.plan_deviations)


def test_a_date_follow_up_that_fails_keeps_the_answer_already_given_in_the_executor(
    ledger_db: Path, index_root: Path, cases: CaseMemory, tmp_path: Path
) -> None:
    model = ScriptedChatModel(script=[LEDGER_CALL, WRONG_FX, text_message("First.")])
    agent = unplanned_executor(ledger_db, index_root, cases, tmp_path, model)
    result = investigate_with_executor(agent, S01["questions"][0], session_id="t-fx-fail")
    assert result.answer == "First."
    assert any("2026-09-01" in d and "follow-up failed" in d for d in result.plan_deviations)
