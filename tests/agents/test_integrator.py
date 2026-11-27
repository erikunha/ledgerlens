"""Integrator: `create_agent` with the six tools, memory per `thread_id`, verifier and case recording.

What they guarantee, and why: (a) the six contract tools go in, in contract order; (b) in a single run S01
uses SQL, policy search and the FX API, and the result carries the tool trace, the evidence and the
answer; (c) the verifier is injected, gets the assembled result and what it returns is the final result;
(d) only a result with every verdict supported becomes a case in long-term memory; (e) a tool error with no
recovery becomes missing information and human review; (f) the checkpointer separates sessions by
`thread_id`. The model is a `ScriptedChatModel`.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ledgerlens.agents.executor_integrator import build_executor_integrator, investigate_with_executor
from ledgerlens.agents.integrator import Integrator, build_integrator, investigate
from ledgerlens.embeddings import OfflineEmbeddings
from ledgerlens.memory.long_term import CaseMemory
from ledgerlens.offline import ScriptedChatModel, text_message, tool_call_message
from ledgerlens.retrieval import build_policy_index, index_dir_for, load_policy_documents
from ledgerlens.schemas import Claim, Coherence, Entities, Evidence, InvestigationResult, PlanStep, Triage, Verdict
from ledgerlens.sim.config import SimConfig
from ledgerlens.sim.pipeline import build_ledger
from ledgerlens.tools.fx import FxClient
from ledgerlens.verify.nli import StubNli
from tests.tools import test_policies as base

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


@pytest.fixture
def embeddings() -> OfflineEmbeddings:
    return OfflineEmbeddings()


@pytest.fixture
def index_root(tmp_path: Path, embeddings: OfflineEmbeddings) -> Path:
    root = tmp_path / "index"
    build_policy_index(load_policy_documents(base.POLICIES), embeddings, index_dir_for(root, embeddings))
    return root


@pytest.fixture
def cases(tmp_path: Path, embeddings: OfflineEmbeddings) -> CaseMemory:
    return CaseMemory(tmp_path / "cases", embeddings=embeddings)


def supporting_verifier(calls: list[InvestigationResult]):
    """Fake verifier: records what it got and supports one claim with the first evidence."""

    def verify(result: InvestigationResult, *, nli=None) -> InvestigationResult:
        calls.append(result)
        claim = Claim(id="CL1", text=result.answer[:80], kind="fact", evidence_ids=[result.evidence[0].id])
        verdict = Verdict(claim_id="CL1", label="supported", method="rule", evidence_ids=claim.evidence_ids)
        return result.model_copy(update={"claims": [claim], "verdicts": [verdict]})

    return verify


def s01_script() -> list:
    truth = S01["truth"]
    return [
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


def integrator_for(db: Path, index_root: Path, cases: CaseMemory, script: list, *, verifier, fault: bool = False, **kw):
    return build_integrator(
        ScriptedChatModel(script=script),
        db_path=db,
        verifier=verifier,
        query_model=ScriptedChatModel(script=[FX_SQL]),
        fx_client=FxClient(mode="fixtures", fault=fault, sleep=lambda _: None),
        index_root=index_root,
        case_memory=cases,
        **kw,
    )


def test_the_six_tools_of_the_contract(ledger_db: Path, index_root: Path, cases: CaseMemory) -> None:
    agent = integrator_for(ledger_db, index_root, cases, [], verifier=supporting_verifier([]))
    assert isinstance(agent, Integrator)
    assert [t.name for t in agent.tools] == [
        "query_ledger",
        "get_ledger_record",
        "search_policies",
        "get_reference_fx",
        "calculate",
        "recall_cases",
    ]


def test_s01_uses_sql_policies_and_fx_in_one_run(ledger_db: Path, index_root: Path, cases: CaseMemory) -> None:
    calls: list[InvestigationResult] = []
    agent = integrator_for(ledger_db, index_root, cases, s01_script(), verifier=supporting_verifier(calls))

    result = investigate(agent, S01["questions"][0], thread_id="t-s01")

    trace = [record.tool for record in result.tool_trace]
    print("S01 tool order:", trace)
    assert trace == S01["expected_tools"]
    assert [record.step for record in result.tool_trace] == [1, 2, 3, 4]
    assert all(record.ok and record.evidence_ids for record in result.tool_trace)
    assert result.tool_trace[3].input["operation"] == "fx_gap_breakdown"
    ids = [e.id for e in result.evidence]
    assert ids[0] == "sql:1" and ids[-1] == "calc:1"
    assert {e.source_type for e in result.evidence} == {"sql", "policy", "fx", "calc"}
    assert any(e.id.startswith("fx:") for e in result.evidence)
    assert S01["truth"]["gap_brl"] in next(e for e in result.evidence if e.id == "calc:1").content
    assert result.session_id == "t-s01" and result.question == S01["questions"][0]
    assert S01["truth"]["refund_brl"] in result.answer
    assert result.missing_information == [] and result.requires_human_review is False
    assert len(calls) == 1 and calls[0].tool_trace == result.tool_trace  # the verifier saw the assembled result
    assert result.verdicts[0].label == "supported"  # and what it returned is the final result


def test_a_fully_supported_result_becomes_a_case(ledger_db: Path, index_root: Path, cases: CaseMemory) -> None:
    agent = integrator_for(ledger_db, index_root, cases, s01_script(), verifier=supporting_verifier([]))
    before = {r["case_id"] for r in cases.records()}
    investigate(agent, S01["questions"][0], thread_id="t-case")
    written = [r for r in cases.records() if r["case_id"] not in before]
    assert len(written) == 1 and written[0]["session_id"] == "t-case"
    assert S01["truth"]["refund_brl"] in written[0]["finding"]


def test_a_contradicted_result_is_not_remembered(ledger_db: Path, index_root: Path, cases: CaseMemory) -> None:
    def contradicting(result: InvestigationResult, *, nli=None) -> InvestigationResult:
        claim = Claim(id="CL1", text="x", kind="fact", evidence_ids=[result.evidence[0].id])
        verdict = Verdict(claim_id="CL1", label="contradicted", method="nli")
        return result.model_copy(update={"claims": [claim], "verdicts": [verdict], "requires_human_review": True})

    agent = integrator_for(ledger_db, index_root, cases, s01_script(), verifier=contradicting)
    before = len(cases.records())
    result = investigate(agent, S01["questions"][0], thread_id="t-no-case")
    assert len(cases.records()) == before
    assert result.requires_human_review is True


def test_a_failing_case_writer_does_not_break_the_investigation(
    ledger_db: Path, index_root: Path, cases: CaseMemory, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*args: object, **kwargs: object) -> dict:
        raise OSError("disk full")

    monkeypatch.setattr(cases, "write_case", boom)
    agent = integrator_for(ledger_db, index_root, cases, s01_script(), verifier=supporting_verifier([]))
    assert investigate(agent, S01["questions"][0], thread_id="t-boom").verdicts[0].label == "supported"


def test_s11_an_unrecovered_tool_error_is_missing_information(
    ledger_db: Path, index_root: Path, cases: CaseMemory
) -> None:
    script = [
        tool_call_message("query_ledger", {"question": "refunds of TX-2048"}),
        tool_call_message("get_reference_fx", {"from_currency": "EUR", "to_currency": "BRL", "date": "2026-10-20"}),
        text_message(f"I could not get the rate {S11['truth']['missing_rate']}: the source was unavailable."),
    ]
    verifier = lambda result, *, nli=None: result  # noqa: E731
    agent = integrator_for(ledger_db, index_root, cases, script, verifier=verifier, fault=True)

    result = investigate(agent, S11["questions"][0], thread_id="t-s11")

    assert [r.tool for r in result.tool_trace] == S11["expected_tools"]
    failed = result.tool_trace[-1]
    assert failed.ok is False and failed.error_code == S11["truth"]["fault_error"]
    assert any("get_reference_fx" in item for item in result.missing_information)
    assert result.requires_human_review is True
    assert all(e.tool != "get_reference_fx" for e in result.evidence)


def test_s11_the_answer_names_the_rate_the_source_could_not_give(
    ledger_db: Path, index_root: Path, cases: CaseMemory
) -> None:
    """A real model wrote 'I could not get the FX rate' without saying which: the code says it, from the trace."""
    from ledgerlens.verify import verify_result

    script = [
        tool_call_message("query_ledger", {"question": "refunds of TX-2048"}),
        tool_call_message("get_reference_fx", {"from_currency": "EUR", "to_currency": "BRL", "date": "2026-10-20"}),
        text_message("I could not look up the FX rate, so the difference cannot be explained."),
    ]
    agent = integrator_for(
        ledger_db,
        index_root,
        cases,
        script,
        verifier=lambda r, *, nli=None: verify_result(r, nli=StubNli()),
        fault=True,
    )
    result = investigate(agent, S11["questions"][0], thread_id="t-s11-rate")

    missing_rate = S11["truth"]["missing_rate"]
    assert missing_rate in result.answer
    assert any(missing_rate in item for item in result.missing_information)
    assert result.requires_human_review is True and result.recommended_action == S11["expected_action"]


def test_an_exception_inside_a_tool_becomes_data_and_the_result_goes_to_a_human(
    ledger_db: Path, index_root: Path, cases: CaseMemory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The tool layer is not the only wall: an exception that escapes it is reported as data, not raised."""

    def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("the index file is corrupt")

    monkeypatch.setattr("ledgerlens.tools.policies.load_policy_index", boom)
    script = [
        tool_call_message("search_policies", {"query": "refund window", "transform": "none"}),
        text_message("I could not read the policies, so I cannot answer the question."),
    ]
    agent = integrator_for(ledger_db, index_root, cases, script, verifier=lambda r, *, nli=None: r)

    result = investigate(agent, "How many days do I have to ask for a refund?", thread_id="t-tool-raise")

    assert isinstance(result, InvestigationResult)
    assert result.tool_trace[0].ok is False and result.tool_trace[0].error_code == "TOOL_FAILED"
    assert any("TOOL_FAILED" in item for item in result.missing_information)
    assert result.requires_human_review is True


def test_an_error_followed_by_a_success_is_not_missing(ledger_db: Path, index_root: Path, cases: CaseMemory) -> None:
    script = [
        tool_call_message("get_ledger_record", {"kind": "transaction", "id": "TX-9"}),  # malformed id: INVALID_ID
        tool_call_message("get_ledger_record", {"kind": "transaction", "id": "TX-2048"}),
        text_message("TX-2048 exists."),
    ]
    verifier = lambda result, *, nli=None: result  # noqa: E731
    result = investigate(
        integrator_for(ledger_db, index_root, cases, script, verifier=verifier), "Does TX-2048 exist?", thread_id="t-r"
    )
    assert [r.ok for r in result.tool_trace] == [False, True]
    assert result.tool_trace[0].error_code == "INVALID_ID"
    assert result.missing_information == [] and result.requires_human_review is False
    assert result.evidence[0].source_type == "ledger_api" and result.evidence[0].id.startswith("api:")


def test_the_checkpointer_separates_sessions_and_the_trace_is_per_turn(
    ledger_db: Path, index_root: Path, cases: CaseMemory
) -> None:
    script = [
        tool_call_message("calculate", {"operation": "fx_gap_breakdown", "values": {}}),
        text_message("first"),
        text_message("second"),
        text_message("another session"),
    ]
    model = ScriptedChatModel(script=script)
    agent = build_integrator(
        model,
        db_path=ledger_db,
        verifier=lambda r, *, nli=None: r,
        index_root=index_root,
        case_memory=cases,
    )
    first = investigate(agent, "Question one about TX-2048", thread_id="a")
    second = investigate(agent, "Question two", thread_id="a")
    investigate(agent, "Question three", thread_id="b")

    assert len(first.tool_trace) == 1 and second.tool_trace == [] and second.answer == "second"
    seen = lambda call: " ".join(str(m.content) for m in call)  # noqa: E731
    assert "Question one about TX-2048" in seen(model.calls[2])  # the second turn sees the first
    assert "Question one about TX-2048" not in seen(model.calls[3])  # the other session starts empty


def test_the_default_verifier_is_the_one_in_ledgerlens_verify(
    ledger_db: Path, index_root: Path, cases: CaseMemory, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[str] = []
    ledgers: list[Path | str | None] = []

    def fake(result: InvestigationResult, *, nli=None, ledger_db=None) -> InvestigationResult:
        seen.append(result.question)
        ledgers.append(ledger_db)
        return result

    monkeypatch.setattr("ledgerlens.verify.verify_result", fake, raising=False)
    agent = build_integrator(
        ScriptedChatModel(script=[text_message("ok")]), db_path=ledger_db, index_root=index_root, case_memory=cases
    )
    investigate(agent, "Question", thread_id="t-default")
    assert seen == ["Question"] and ledgers == [ledger_db]


def test_the_real_verifier_runs_on_the_assembled_result(ledger_db: Path, index_root: Path, cases: CaseMemory) -> None:
    verify = pytest.importorskip("ledgerlens.verify")
    if not hasattr(verify, "verify_result"):
        pytest.skip("ledgerlens.verify.verify_result is not exported yet")
    agent = build_integrator(
        ScriptedChatModel(script=s01_script()),
        db_path=ledger_db,
        query_model=ScriptedChatModel(script=[FX_SQL]),
        fx_client=FxClient(mode="fixtures", sleep=lambda _: None),
        index_root=index_root,
        case_memory=cases,
    )
    result = investigate(agent, S01["questions"][0], thread_id="t-real")
    assert isinstance(result, InvestigationResult)
    assert [r.tool for r in result.tool_trace] == S01["expected_tools"]


def test_the_system_prompt_asks_for_a_citation_in_every_sentence_and_dates_from_the_ledger() -> None:
    """A real model gathered every citation at the end of the paragraph and asked for FX on a made-up date."""
    from ledgerlens.agents.integrator import INTEGRATOR_SYSTEM_PROMPT

    prompt = INTEGRATOR_SYSTEM_PROMPT.lower()
    assert "each sentence" in prompt and "end of the paragraph" in prompt  # the citation goes sentence by sentence
    assert "wrong:" in prompt and "right:" in prompt  # with one example of each; the real model did worse without
    assert "ledger" in prompt and "date" in prompt and "do not assume" in prompt  # dates come from the ledger


def test_a_policy_model_runs_the_query_rewrite_of_search_policies(
    ledger_db: Path, index_root: Path, cases: CaseMemory
) -> None:
    rewriter = ScriptedChatModel(script=["cross-currency refund applied rate"])
    script = [
        tool_call_message("search_policies", {"query": "why the refund came in lower"}),  # default transform: rewrite
        text_message("I looked up the policies."),
    ]
    agent = build_integrator(
        ScriptedChatModel(script=script),
        db_path=ledger_db,
        verifier=lambda r, *, nli=None: r,
        index_root=index_root,
        case_memory=cases,
        policy_model=rewriter,
    )
    result = investigate(agent, "Question", thread_id="t-rewrite")

    assert [t.name for t in agent.tools] == [
        "query_ledger",
        "get_ledger_record",
        "search_policies",
        "get_reference_fx",
        "calculate",
        "recall_cases",
    ]
    assert len(rewriter.calls) == 1  # the policy model rewrote the question
    assert result.tool_trace[0].ok is True


# --- triage feeds the agent ----------------------------------------------------------------------------


def triage_json(*steps: tuple[str, str | None], clarification: str | None = None) -> str:
    """A `Triage` as JSON with the given `(goal, tool)` steps, as the triage model would return it."""
    plan = [
        PlanStep(id=f"S{n}", goal=goal, tool=tool, depends_on=[f"S{n - 1}"] if n > 1 else [])
        for n, (goal, tool) in enumerate(steps or [("answer", None)], start=1)
    ]
    triage = Triage(
        intent="refund_discrepancy",
        entities=Entities(transaction_ids=["TX-2048"]),
        urgency="normal",
        plan=plan,
        needs_clarification=clarification is not None,
        clarification_question=clarification,
    )
    return triage.model_dump_json()


def triage_script(*steps: tuple[str, str | None], clarification: str | None = None) -> ScriptedChatModel:
    return ScriptedChatModel(script=[triage_json(*steps, clarification=clarification)])


def triaged(ledger_db: Path, index_root: Path, cases: CaseMemory, model: ScriptedChatModel, triage: ScriptedChatModel):
    """An integrator whose agent and triage are scripted models the test holds."""
    return build_integrator(
        model,
        triage_model=triage,
        db_path=ledger_db,
        verifier=lambda r, *, nli=None: r,
        query_model=ScriptedChatModel(script=[FX_SQL]),
        fx_client=FxClient(mode="fixtures", sleep=lambda _: None),
        index_root=index_root,
        case_memory=cases,
    )


def seen_by(model: ScriptedChatModel, call: int = 0) -> str:
    return "\n".join(str(m.content) for m in model.calls[call])


def test_the_policy_answer_prompt_requires_a_next_step_without_assuming_late_evidence_eligibility(
    ledger_db: Path, index_root: Path, cases: CaseMemory
) -> None:
    model = ScriptedChatModel(
        script=[
            tool_call_message(
                "search_policies", {"query": "missed internal cutoff same-day review", "transform": "none"}
            ),
            text_message("Escalate for same-day human review."),
        ]
    )
    triage = triage_script(("search for the missed cutoff policy", "search_policies"))
    investigate(
        triaged(ledger_db, index_root, cases, model, triage),
        "Our evidence cutoff passed and the response deadline is tomorrow. What can we do now?",
        thread_id="t-missed-cutoff",
    )

    answer_prompt = seen_by(model, call=1)
    assert (
        "When only policy passages are available, frame the action conditionally on the facts supplied "
        "and do not infer a case status." in answer_prompt
    )
    assert "For a missed internal cutoff, state the next step the cited policy prescribes." in answer_prompt
    assert (
        "If asked whether late evidence can still be submitted and the policy only prescribes review, "
        "say the cited policy does not establish whether late evidence can be accepted." in answer_prompt
    )
    assert "Do not infer acceptance, rejection, or an exception from the cutoff alone" in answer_prompt
    assert (
        "Keep the subject of each consequence. Attribute automatic loss to a merchant response sent after the "
        "response deadline, and review to missing the internal evidence cutoff, when the cited policy says so."
        in answer_prompt
    )
    assert "State what follows if the policy condition is met without claiming it is the only cause" in answer_prompt
    assert "Example for a missed evidence cutoff when asked about next steps and automatic loss" in answer_prompt
    assert (
        "Use only parts supported by the current search and cite the actual retrieved passage IDs "
        "in place of the placeholders" in answer_prompt
    )
    assert (
        "If your internal cutoff has passed, escalate the case to a human analyst" in answer_prompt
    )
    assert "The retrieved passages do not establish whether late evidence can still be accepted" in answer_prompt
    assert (
        "If the merchant response is sent after the response deadline, the dispute is lost automatically"
        in answer_prompt
    )
    assert "I need the dispute record to verify the case status" in answer_prompt


def test_the_policy_answer_prompt_covers_the_team_handoff_and_both_deadline_events(
    ledger_db: Path, index_root: Path, cases: CaseMemory
) -> None:
    model = ScriptedChatModel(
        script=[
            tool_call_message(
                "search_policies", {"query": "dispute escalation handoff response deadline", "transform": "none"}
            ),
            text_message("The case needs human review."),
        ]
    )
    triage = triage_script(("find dispute escalation and response timing", "search_policies"))
    investigate(
        triaged(ledger_db, index_root, cases, model, triage),
        "Draft a note to the disputes team. Our evidence cutoff passed and the response arrived after the deadline.",
        thread_id="t-dispute-handoff",
    )

    instructions = "\n".join(str(message.content) for message in model.calls[1] if message.type == "system")
    required_guidance = (
        "draft the message itself",
        "Missing the internal evidence cutoff alone does not mean the dispute is lost",
        "late arrival alone does not establish late sending",
        "Do not apply a late-send rule to a response that was never sent",
        "days left until the response deadline, the internal evidence cutoff, and the evidence still missing",
        "identify any of those details that are unknown",
        "missed internal cutoff requires escalation to a human analyst regardless of the days left",
        "Apply review timing separately from the duty to escalate",
        "a missed cutoff alone can make a case critical",
        "same business day from escalation",
        "search for urgency levels and response times",
        "distinguish when the merchant sent the response from when it was received",
        "If the send time is unknown, state the automatic-loss rule conditionally",
        "without ruling out other grounds for loss",
    )
    missing = [guidance for guidance in required_guidance if guidance not in instructions]
    assert not missing, f"The answer model lacks guidance for {missing}"


def test_the_triage_plan_is_given_to_the_agent_and_kept_in_the_result(
    ledger_db: Path, index_root: Path, cases: CaseMemory
) -> None:
    """The agent skipped steps because it never saw the triage plan (trajectory 0.57 online)."""
    model = ScriptedChatModel(script=[text_message("I looked up the ledger."), text_message("I do not need both.")])
    triage = triage_script(("query the ledger", "query_ledger"), ("search the policy", "search_policies"))
    agent = triaged(ledger_db, index_root, cases, model, triage)

    result = investigate(agent, S01["questions"][0], thread_id="t-plan")

    prompt = seen_by(model)
    assert "query the ledger" in prompt and "search_policies" in prompt and "S2" in prompt
    assert S01["questions"][0] in seen_by(triage)  # triage read the question
    assert result.triage is not None and [s.tool for s in result.triage.plan] == ["query_ledger", "search_policies"]


def test_a_plan_step_the_agent_skipped_and_a_tool_outside_the_plan_are_recorded(
    ledger_db: Path, index_root: Path, cases: CaseMemory
) -> None:
    model = ScriptedChatModel(
        script=[
            tool_call_message("get_ledger_record", {"kind": "transaction", "id": "TX-2048"}),
            text_message("ok"),
            text_message("I do not need the others."),
        ]
    )
    triage = triage_script(("query the ledger", "query_ledger"), ("search the policy", "search_policies"))
    result = investigate(triaged(ledger_db, index_root, cases, model, triage), "Question", thread_id="t-dev")

    assert any("S1" in d and "query_ledger" in d for d in result.plan_deviations)
    assert any("S2" in d and "search_policies" in d for d in result.plan_deviations)
    assert any("get_ledger_record" in d for d in result.plan_deviations)  # a call the plan did not expect


def test_a_run_that_follows_the_plan_has_no_deviation(ledger_db: Path, index_root: Path, cases: CaseMemory) -> None:
    model = ScriptedChatModel(
        script=[tool_call_message("query_ledger", {"question": "fx rates applied to TX-2048"}), text_message("ok")]
    )
    triage = triage_script(("query the ledger", "query_ledger"), ("answer", None))
    result = investigate(triaged(ledger_db, index_root, cases, model, triage), "Question", thread_id="t-ok")
    assert result.plan_deviations == []


FX_CALL = {"from_currency": "EUR", "to_currency": "BRL", "date": "2026-10-20"}


def test_a_planned_tool_that_was_not_called_is_asked_for_once_and_then_it_runs(
    ledger_db: Path, index_root: Path, cases: CaseMemory
) -> None:
    """EC-11: `get_reference_fx` was in the plan, the agent answered without calling it and S11 never ran."""
    model = ScriptedChatModel(
        script=[
            tool_call_message("query_ledger", {"question": "fx rates applied to TX-2048"}),
            text_message("Answer without the FX rate."),
            tool_call_message("get_reference_fx", FX_CALL),
            text_message("Answer with the reference rate."),
        ]
    )
    triage = triage_script(("query the ledger", "query_ledger"), ("read the reference rate", "get_reference_fx"))
    result = investigate(triaged(ledger_db, index_root, cases, model, triage), "Question", thread_id="t-follow-up")

    asked = seen_by(model, 2)  # the third model call is the first one after the follow-up
    assert "S2" in asked and "get_reference_fx" in asked and "S1" not in asked.split("Plan check")[-1]
    assert [r.tool for r in result.tool_trace] == ["query_ledger", "get_reference_fx"]
    assert result.answer == "Answer with the reference rate."
    assert any(e.id.startswith("fx:") for e in result.evidence)
    assert any(
        "S2" in d and "get_reference_fx" in d and "asked" in d and "called it" in d for d in result.plan_deviations
    )
    assert not any("was in the plan and was not called" in d for d in result.plan_deviations)


def test_the_follow_up_happens_once_even_when_the_agent_still_skips_the_tool(
    ledger_db: Path, index_root: Path, cases: CaseMemory
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
    result = investigate(triaged(ledger_db, index_root, cases, model, triage), "Question", thread_id="t-once")

    assert len(model.calls) == 3  # the tool, the first answer and a single follow-up
    assert result.answer == "I do not need the FX rate: the ledger already has the applied rate."
    assert [r.tool for r in result.tool_trace] == ["query_ledger"]
    assert any("get_reference_fx" in d and "did not call it" in d for d in result.plan_deviations)


def test_nothing_is_asked_when_every_planned_tool_ran_or_there_is_no_plan(
    ledger_db: Path, index_root: Path, cases: CaseMemory
) -> None:
    model = ScriptedChatModel(
        script=[tool_call_message("query_ledger", {"question": "fx rates applied to TX-2048"}), text_message("ok")]
    )
    triage = triage_script(("query the ledger", "query_ledger"), ("answer", None))
    result = investigate(triaged(ledger_db, index_root, cases, model, triage), "Question", thread_id="t-full")
    assert len(model.calls) == 2 and result.plan_deviations == []

    unplanned = ScriptedChatModel(script=[text_message("No plan.")])
    investigate(triaged(ledger_db, index_root, cases, unplanned, ScriptedChatModel(script=[])), "P", thread_id="t-none")
    assert len(unplanned.calls) == 1


def test_a_follow_up_that_fails_keeps_the_answer_already_given(
    ledger_db: Path, index_root: Path, cases: CaseMemory
) -> None:
    """With no script for the follow-up, the call raises: the answer already given is not lost."""
    model = ScriptedChatModel(
        script=[
            tool_call_message("query_ledger", {"question": "fx rates applied to TX-2048"}),
            text_message("First."),
        ]
    )
    triage = triage_script(("query the ledger", "query_ledger"), ("read the reference rate", "get_reference_fx"))
    result = investigate(triaged(ledger_db, index_root, cases, model, triage), "Question", thread_id="t-fail")
    assert result.answer == "First."
    assert any("get_reference_fx" in d and "follow-up failed" in d for d in result.plan_deviations)


def test_a_request_the_triage_cannot_plan_asks_back_without_calling_tools(
    ledger_db: Path, index_root: Path, cases: CaseMemory
) -> None:
    """`needs_clarification` returns the question without calling the agent and the conversation keeps the exchange."""
    model = ScriptedChatModel(script=[text_message("It was TX-2048.")])
    triage = triage_script(clarification="What is the transaction id?")
    agent = triaged(ledger_db, index_root, cases, model, triage)

    asked = investigate(agent, "The money did not arrive", thread_id="t-ask")

    assert model.calls == []  # not even the agent model was called
    assert asked.answer == "What is the transaction id?" and asked.recommended_action == "ask_for_clarification"
    assert asked.tool_trace == [] and asked.evidence == [] and asked.requires_human_review is False
    assert asked.triage is not None and asked.triage.needs_clarification

    investigate(
        agent, "It is TX-2048", thread_id="t-ask"
    )  # the user's reply arrives with the question in the conversation
    assert "What is the transaction id?" in seen_by(model) and "The money did not arrive" in seen_by(model)


def test_a_follow_up_the_triage_cannot_read_alone_still_reaches_the_agent(
    ledger_db: Path, index_root: Path, cases: CaseMemory
) -> None:
    """Triage does not see the history: on a later turn, `needs_clarification` does not stop the agent."""
    model = ScriptedChatModel(script=[text_message("It was TX-2048."), text_message("TX-2048 again.")])
    triage = ScriptedChatModel(script=[triage_json(("answer", None)), triage_json(clarification="Which transaction?")])
    agent = triaged(ledger_db, index_root, cases, model, triage)

    investigate(agent, "What is the status of TX-2048?", thread_id="t-follow")
    second = investigate(agent, "Which transaction did I just ask about?", thread_id="t-follow")

    assert second.answer == "TX-2048 again." and len(model.calls) == 2
    assert "Which transaction?" not in seen_by(model, 1)  # triage's question back does not go to the agent
    assert "Triage plan" not in seen_by(model, 1).split("Which transaction did I just")[-1]


MIXED_STATUS_AND_POLICY = (
    "Was my dispute marked lost, and what does policy require if the internal evidence cutoff has passed?"
)
MISSING_DISPUTE_ID = "What is the dispute ID?"


@pytest.fixture(params=["graph", "executor"])
def investigation_session(request, ledger_db, index_root, cases, tmp_path):
    def start(model, triage):
        if request.param == "graph":
            agent = triaged(ledger_db, index_root, cases, model, triage)
            return lambda question: investigate(agent, question, thread_id="mixed-policy")
        agent = build_executor_integrator(
            model,
            triage_model=triage,
            db_path=ledger_db,
            history_db_path=tmp_path / "history.db",
            verifier=lambda result, *, nli=None: result,
            query_model=ScriptedChatModel(script=[]),
            index_root=index_root,
            case_memory=cases,
        )
        return lambda question: investigate_with_executor(agent, question, session_id="mixed-policy")

    return start


def mixed_policy_triage(*, blocked_lookup: bool = False) -> Triage:
    plan = [PlanStep(id="S1", goal="Find the rules for the missed cutoff", tool="search_policies")]
    if blocked_lookup:
        plan = [
            PlanStep(id="S1", goal="Verify the dispute status", tool="get_ledger_record"),
            plan[0].model_copy(update={"id": "S2"}),
            PlanStep(id="S3", goal="Find the rule on who must review the dispute", tool="search_policies"),
        ]
    return Triage(
        intent="policy_question",
        entities=Entities(),
        urgency="high",
        plan=plan,
        needs_clarification=True,
        clarification_question=MISSING_DISPUTE_ID,
    )


@pytest.mark.parametrize("blocked_lookup", [False, True])
def test_first_turn_answers_independent_policy_before_asking_for_dispute_id(investigation_session, blocked_lookup):
    triage = ScriptedChatModel(script=[mixed_policy_triage(blocked_lookup=blocked_lookup).model_dump_json()])
    search = tool_call_message("search_policies", {"query": "missed internal cutoff", "transform": "none"})
    answer = f"Escalate to a human analyst. {MISSING_DISPUTE_ID}"
    model = ScriptedChatModel(script=[search, text_message(answer)])

    result = investigation_session(model, triage)(MIXED_STATUS_AND_POLICY)

    assert result.answer == answer
    assert [call.tool for call in result.tool_trace] == ["search_policies"]
    assert result.evidence and all(item.source_type == "policy" for item in result.evidence)
    assert result.recommended_action != "ask_for_clarification"
    assert result.triage is not None and not result.triage.needs_clarification
    assert result.triage.clarification_question is None
    planned_searches, answer_step = result.triage.plan[:-1], result.triage.plan[-1]
    assert [step.id for step in planned_searches] == (["S1", "S2"] if blocked_lookup else ["S1"])
    assert all(step.tool == "search_policies" for step in planned_searches)
    assert answer_step.id == ("S3" if blocked_lookup else "S2")
    assert answer_step.tool is None and answer_step.depends_on == [step.id for step in planned_searches]
    answer_instruction = f"Explain the supported policy, then ask for the missing case details: {MISSING_DISPUTE_ID}"
    assert answer_instruction in seen_by(model)
    assert len(triage.calls) == 1


@pytest.mark.parametrize(("intent", "dependencies"), [("chargeback_status", []), ("policy_question", ["S1"])])
def test_first_turn_with_policy_that_cannot_proceed_asks_for_dispute_id(investigation_session, intent, dependencies):
    triage = mixed_policy_triage(blocked_lookup=True)
    triage.intent = intent
    triage.plan = [triage.plan[0], triage.plan[1].model_copy(update={"depends_on": dependencies})]
    model = ScriptedChatModel(script=[])

    result = investigation_session(model, ScriptedChatModel(script=[triage.model_dump_json()]))(
        "Was my dispute marked lost?"
    )

    assert result.answer == MISSING_DISPUTE_ID
    assert result.recommended_action == "ask_for_clarification"
    assert result.triage == triage and result.tool_trace == [] and model.calls == []


def test_follow_up_with_policy_and_status_uses_history_without_first_turn_plan(investigation_session):
    triage = ScriptedChatModel(script=[triage_json(("answer", None)), mixed_policy_triage().model_dump_json()])
    search = tool_call_message("search_policies", {"query": "missed internal cutoff", "transform": "none"})
    model = ScriptedChatModel(
        script=[text_message("I have your dispute number."), search, text_message("Escalate it.")]
    )
    ask = investigation_session(model, triage)
    ask("My dispute is CB-0001.")

    result = ask(MIXED_STATUS_AND_POLICY)

    assert result.answer == "Escalate it."
    assert result.triage is None
    assert "My dispute is CB-0001." in seen_by(model, 1)
    assert MISSING_DISPUTE_ID not in seen_by(model, 1)


def test_a_triage_that_fails_does_not_stop_the_investigation(
    ledger_db: Path, index_root: Path, cases: CaseMemory
) -> None:
    """Without triage the answer comes out as before: the triage failure goes to the log, not to the user."""
    model = ScriptedChatModel(script=[text_message("Answer without a plan.")])
    broken = ScriptedChatModel(script=[])  # exhausted: the call raises
    result = investigate(triaged(ledger_db, index_root, cases, model, broken), "Question", thread_id="t-broken")
    assert result.answer == "Answer without a plan." and result.triage is None and result.plan_deviations == []
    assert "Triage plan" not in seen_by(model)

    unreadable = ScriptedChatModel(script=["this is not JSON", "nor this"])  # reading and repair fail: TriageError
    model2 = ScriptedChatModel(script=[text_message("Another answer.")])
    result = investigate(triaged(ledger_db, index_root, cases, model2, unreadable), "Question", thread_id="t-bad")
    assert result.answer == "Another answer." and result.triage is None


def test_the_system_prompt_says_which_date_the_refund_reference_rate_comes_from() -> None:
    """In 3 of 7 real fx_gap_breakdown calls, `refund_reference_rate` came from the charge date or from today."""
    from ledgerlens.agents.integrator import INTEGRATOR_SYSTEM_PROMPT

    assert (
        "`refund_reference_rate` is the reference rate on the refund date, read in the ledger; never the one of the "
        "charge nor today's." in INTEGRATOR_SYSTEM_PROMPT
    )


S09_SQL_WITHOUT_REASON = json.dumps(
    {
        "columns": ["id", "transaction_id", "status"],
        "rows": [["R-0750", "TX-2095", "requested"]],
        "row_count": 1,
        "truncated": False,
    }
)


def injected_refund_result(db: Path | None = None) -> InvestigationResult:
    """S09 as the model queried it: the SQL picked columns without `reason`, where the hidden order is."""
    evidence = Evidence(
        id="sql:1",
        source_type="sql",
        tool="query_ledger",
        content=S09_SQL_WITHOUT_REASON,
        ref="sql:1",
        retrieved_at=datetime(2026, 11, 8, tzinfo=UTC),
    )
    return InvestigationResult(
        session_id="s",
        question="What is the status of refund R-0750 of TX-2095?",
        answer='The status of refund R-0750 is "requested" [sql:1].',
        evidence=[evidence],
        claims=[],
        verdicts=[],
        coherence=Coherence(passed=True),
        recommended_action="none",
        requires_human_review=False,
    )


def test_the_default_verifier_reads_the_free_text_from_the_ledger_the_integrator_was_built_with(
    ledger_db: Path, index_root: Path, cases: CaseMemory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The configured default points at another file: only the integrator's `db_path` has R-0750."""
    monkeypatch.setenv("LEDGERLENS_LEDGER_DB", str(tmp_path / "elsewhere.db"))
    agent = integrator_for(ledger_db, index_root, cases, [], verifier=None)
    out = agent.verifier(injected_refund_result())
    assert out.requires_human_review is True
    assert any("suspicious-text" in item and "R-0750" in item for item in out.missing_information)


def test_an_integrator_without_db_path_verifies_against_the_configured_ledger(
    index_root: Path, cases: CaseMemory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LEDGERLENS_LEDGER_DB", str(tmp_path / "elsewhere.db"))
    agent = build_integrator(ScriptedChatModel(script=[]), index_root=index_root, case_memory=cases)
    out = agent.verifier(injected_refund_result())
    assert not any("suspicious-text" in item for item in out.missing_information)  # a missing ledger adds nothing


# --- FX for a date the ledger does not have ------------------------------------------------------------

LEDGER_CALL = tool_call_message("query_ledger", {"question": "fx rates applied to TX-2048"})
WRONG_FX = tool_call_message("get_reference_fx", {**FX_CALL, "date": "2026-09-01"})


def no_plan(ledger_db: Path, index_root: Path, cases: CaseMemory, model: ScriptedChatModel):
    return triaged(ledger_db, index_root, cases, model, ScriptedChatModel(script=[]))  # exhausted triage: no plan


def fx_days(result) -> list[str]:
    return [r.input["date"] for r in result.tool_trace if r.tool == "get_reference_fx"]


def test_a_rate_requested_for_a_date_the_ledger_does_not_have_is_asked_again_once_and_the_agent_redoes_it(
    ledger_db: Path, index_root: Path, cases: CaseMemory
) -> None:
    """Live, the agent read the ledger and asked for the FX rate of 2024-04-10; the refund is from 2026-10-20."""
    model = ScriptedChatModel(
        script=[
            LEDGER_CALL,
            WRONG_FX,
            text_message("The refund was higher than the reference conversion."),
            tool_call_message("get_reference_fx", FX_CALL),
            text_message("With the FX rate of 2026-10-20 the reference conversion is higher. [fx:2026-10-20:EUR-BRL]"),
        ]
    )
    result = investigate(no_plan(ledger_db, index_root, cases, model), S01["questions"][0], thread_id="t-fx-date")

    asked = seen_by(model, 3).split("Date check")[-1]
    assert "2026-09-01" in asked and "ledger" in asked  # the follow-up names the date and asks for the ledger one
    assert fx_days(result) == ["2026-09-01", "2026-10-20"]
    assert result.answer.startswith("With the FX rate of 2026-10-20")
    assert any(
        "get_reference_fx" in d and "2026-09-01" in d and "asked" in d and "redid" in d for d in result.plan_deviations
    )


def test_the_date_follow_up_happens_once_even_when_the_agent_keeps_the_date(
    ledger_db: Path, index_root: Path, cases: CaseMemory
) -> None:
    model = ScriptedChatModel(
        script=[LEDGER_CALL, WRONG_FX, text_message("First."), text_message("I kept the date."), text_message("no")]
    )
    result = investigate(no_plan(ledger_db, index_root, cases, model), S01["questions"][0], thread_id="t-fx-once")

    assert len(model.calls) == 4  # the query, the FX rate, the answer and a single follow-up
    assert result.answer == "I kept the date." and fx_days(result) == ["2026-09-01"]
    assert any("2026-09-01" in d and "kept the date" in d for d in result.plan_deviations)


@pytest.mark.parametrize(
    "script",
    [
        [LEDGER_CALL, tool_call_message("get_reference_fx", FX_CALL), text_message("ok")],  # the date is the ledger's
        [LEDGER_CALL, WRONG_FX, tool_call_message("get_reference_fx", FX_CALL), text_message("ok")],  # already redone
        [WRONG_FX, text_message("ok")],  # with no ledger queried, there is nothing to compare
    ],
    ids=["date-of-the-ledger", "already-redone", "no-ledger-evidence"],
)
def test_no_date_follow_up_when_every_used_date_has_an_origin_or_there_is_nothing_to_compare(
    ledger_db: Path, index_root: Path, cases: CaseMemory, script: list
) -> None:
    model = ScriptedChatModel(script=script)
    result = investigate(no_plan(ledger_db, index_root, cases, model), S01["questions"][0], thread_id="t-fx-none")
    assert len(model.calls) == len(script)
    assert not any("asked" in d for d in result.plan_deviations)


def test_a_date_typed_by_the_user_is_not_asked_again(ledger_db: Path, index_root: Path, cases: CaseMemory) -> None:
    model = ScriptedChatModel(script=[LEDGER_CALL, WRONG_FX, text_message("ok")])
    investigate(
        no_plan(ledger_db, index_root, cases, model), "What was the FX rate on 2026-09-01 for TX-2048?", thread_id="t-q"
    )
    assert len(model.calls) == 3


def test_one_follow_up_covers_a_skipped_plan_step_and_a_date_without_origin(
    ledger_db: Path, index_root: Path, cases: CaseMemory
) -> None:
    model = ScriptedChatModel(
        script=[LEDGER_CALL, WRONG_FX, text_message("First."), text_message("Redone."), text_message("no")]
    )
    triage = triage_script(
        ("query the ledger", "query_ledger"), ("read the FX rate", "get_reference_fx"), ("calculate", "calculate")
    )
    result = investigate(triaged(ledger_db, index_root, cases, model, triage), "Question", thread_id="t-both")

    asked = seen_by(model, 3).split("Plan check")[-1]
    assert "S3" in asked and "calculate" in asked and "2026-09-01" in asked
    assert len(model.calls) == 4
    assert any("S3" in d and "asked" in d for d in result.plan_deviations)
    assert any("2026-09-01" in d and "asked" in d for d in result.plan_deviations)


def test_a_date_follow_up_that_fails_keeps_the_answer_already_given(
    ledger_db: Path, index_root: Path, cases: CaseMemory
) -> None:
    model = ScriptedChatModel(script=[LEDGER_CALL, WRONG_FX, text_message("First.")])
    result = investigate(no_plan(ledger_db, index_root, cases, model), S01["questions"][0], thread_id="t-fx-fail")
    assert result.answer == "First."
    assert any("2026-09-01" in d and "follow-up failed" in d for d in result.plan_deviations)


def test_a_rate_request_the_source_refused_for_a_date_without_origin_is_asked_again_too(
    ledger_db: Path, index_root: Path, cases: CaseMemory
) -> None:
    """A made-up date outside the recorded series comes back as an error; the agent still needs the ledger date."""
    before_the_series = tool_call_message("get_reference_fx", {**FX_CALL, "date": "2024-04-10"})
    model = ScriptedChatModel(script=[LEDGER_CALL, before_the_series, text_message("No FX rate."), text_message("Ok.")])
    result = investigate(no_plan(ledger_db, index_root, cases, model), S01["questions"][0], thread_id="t-fx-refused")
    assert len(model.calls) == 4 and result.tool_trace[1].ok is False
    assert any("2024-04-10" in d and "asked" in d for d in result.plan_deviations)


def test_a_rate_request_the_source_refused_for_a_date_of_the_ledger_is_not_asked_again(
    ledger_db: Path, index_root: Path, cases: CaseMemory
) -> None:
    """S11: the date is right and the source went down; asking again does not change the cause."""
    model = ScriptedChatModel(script=[LEDGER_CALL, tool_call_message("get_reference_fx", FX_CALL), text_message("ok")])
    agent = build_integrator(
        model,
        triage_model=ScriptedChatModel(script=[]),
        db_path=ledger_db,
        verifier=lambda r, *, nli=None: r,
        query_model=ScriptedChatModel(script=[FX_SQL]),
        fx_client=FxClient(mode="fixtures", fault=True, sleep=lambda _: None),
        index_root=index_root,
        case_memory=cases,
    )
    result = investigate(agent, S01["questions"][0], thread_id="t-fx-s11")
    assert len(model.calls) == 3 and result.tool_trace[1].ok is False


def test_the_context_reaches_the_agent_before_the_question(
    ledger_db: Path, index_root: Path, cases: CaseMemory
) -> None:
    """The demo page says who is signed in and which line was picked: the model sees it, triage does not."""
    model = ScriptedChatModel(script=[text_message("It was TX-2048.")])
    agent = build_integrator(
        model,
        db_path=ledger_db,
        verifier=lambda result, *, nli=None: result,
        query_model=ScriptedChatModel(script=[]),
        fx_client=FxClient(mode="fixtures", sleep=lambda _: None),
        index_root=index_root,
        case_memory=cases,
    )
    context = "The person asking is signed in as customer C-0412. They picked TX-2048 on their statement."
    investigate(agent, "Which payment is this?", thread_id="t-context", context=context)
    sent = model.calls[0]
    texts = [m.content for m in sent]
    assert context in texts
    assert texts.index(context) < texts.index("Which payment is this?")
    assert sent[texts.index(context)].type == "system"


def test_without_context_nothing_is_added(ledger_db: Path, index_root: Path, cases: CaseMemory) -> None:
    model = ScriptedChatModel(script=[text_message("Hello.")])
    agent = build_integrator(
        model,
        db_path=ledger_db,
        verifier=lambda result, *, nli=None: result,
        query_model=ScriptedChatModel(script=[]),
        fx_client=FxClient(mode="fixtures", sleep=lambda _: None),
        index_root=index_root,
        case_memory=cases,
    )
    investigate(agent, "Hi", thread_id="t-no-context")
    assert not any("signed in" in str(m.content) for m in model.calls[0])


@pytest.mark.parametrize(
    ("currency_statement", "settlement_known"),
    [
        ("", False),
        ("The purchase was charged in USD. ", False),
        ("Our settlement currency is USD. ", True),
        ("Our settlement currency is usd. ", True),
        ("We settle in euros. ", True),
        ("Our settlement currency is not provided. ", False),
    ],
)
def test_exact_calendar_date_requires_grounded_settlement_currency(
    ledger_db, index_root, cases, currency_statement, settlement_known
):
    question = (
        currency_statement + "Our dispute response deadline is Monday, July 7, 2025. What is our exact cutoff date?"
    )
    currency, day = ("EUR", 4) if "euros" in currency_statement else ("USD", 3)
    answer = f"The evidence cutoff is July {day}, 2025 [calc:1]."
    agent = integrator_for(
        ledger_db,
        index_root,
        cases,
        [
            tool_call_message(
                "calculate",
                {
                    "operation": "previous_business_day",
                    "values": {
                        "date": "2025-07-07",
                        "currency": currency,
                    },
                },
            ),
            text_message(answer),
        ],
        verifier=supporting_verifier([]),
    )
    result = investigate(agent, question, thread_id="cutoff")
    if settlement_known:
        assert result.answer == answer
    else:
        assert result.recommended_action == "ask_for_clarification"
        assert "settlement currency" in result.answer
        assert "July 3" not in result.answer
        history = agent.graph.get_state({"configurable": {"thread_id": "cutoff"}}).values["messages"]
        assert history[-1].content == result.answer


@pytest.mark.parametrize(
    "draft",
    [
        "Your cutoff is July 3, 2025.",
        "The deadline depends on local holidays. Could you confirm your settlement currency?",
    ],
)
def test_date_policy_question_without_calculator_still_gets_one_clarification(ledger_db, index_root, cases, draft):
    from ledgerlens.verify import verify_result

    agent = integrator_for(
        ledger_db,
        index_root,
        cases,
        [text_message(draft)],
        verifier=lambda result: verify_result(result, nli=StubNli()),
    )
    result = investigate(agent, "Deadline: 2025-07-07. When is the evidence due?", thread_id="policy-date")
    assert result.recommended_action == "ask_for_clarification"
    assert not result.requires_human_review
    assert result.claims == []
    assert "settlement currency" in result.answer


def test_cutoff_question_preserves_preceding_settlement_context(ledger_db, index_root, cases):
    from ledgerlens.verify import verify_result

    draft = "The previous business day is July 3, 2025."
    agent = integrator_for(
        ledger_db,
        index_root,
        cases,
        [text_message("Understood."), text_message(draft)],
        verifier=lambda result: verify_result(result, nli=StubNli()),
    )
    investigate(agent, "Our settlement currency is USD.", thread_id="prior-currency")
    result = investigate(agent, "Deadline: 2025-07-07. When is the evidence due?", thread_id="prior-currency")
    assert result.answer == draft


def test_dated_policy_question_with_high_amount_evidence_keeps_escalation(ledger_db, index_root, cases):
    from ledgerlens.verify import verify_result

    agent = build_integrator(
        ScriptedChatModel(
            script=[
                tool_call_message("query_ledger", {"question": "Read this account's transaction."}),
                text_message("Please confirm the settlement currency."),
            ]
        ),
        db_path=ledger_db,
        query_model=ScriptedChatModel(
            script=["SELECT id, amount_minor FROM transactions ORDER BY amount_minor DESC LIMIT 1"]
        ),
        index_root=index_root,
        case_memory=cases,
        verifier=lambda result: verify_result(result, nli=StubNli(), ledger_db=ledger_db),
    )
    result = investigate(agent, "Deadline: 2025-07-07. When is the evidence due?", thread_id="high-amount")
    assert result.recommended_action == "escalate_to_human"
    assert any("amount above" in item for item in result.missing_information)
