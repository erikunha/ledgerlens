"""The investigation trace: the spans `investigate(on_event=...)` emits while the agent works.

What they guarantee, and why: (a) a scripted investigation emits a tree like LangSmith's, with the root `investigate`
and, under it, triage (prompt, model, parser), the agent (each model turn and each tool, with the arguments, the
envelope and the generated SQL; the model that writes the SQL sits under the tool), verification with one child per
claim, and escalation; (b) every span starts before it ends, with the same `run_id`, and every parent is a known
span; (c) the root ends last, with the one-line summary; (d) a tool that fails becomes an error span with its code;
(e) the plan's single follow-up is a span with the agent's second turn inside; (f) a question sent back by triage has
its own summary; (g) an `on_event` that breaks does not bring the investigation down; (h) the legacy integrator
emits the same tree; (i) `compact` cuts lists and texts with a marker and erases keys. The model is a
`ScriptedChatModel`, so everything runs offline and without LangSmith.
"""

from __future__ import annotations

from pathlib import Path

from ledgerlens.agents.executor_integrator import build_executor_integrator, investigate_with_executor
from ledgerlens.agents.integrator import build_integrator, investigate
from ledgerlens.memory.long_term import CaseMemory
from ledgerlens.observability.trace import Span, compact, summary_line
from ledgerlens.offline import ScriptedChatModel, text_message
from ledgerlens.schemas import Claim, Coherence, InvestigationResult, ToolCallRecord, Verdict
from ledgerlens.tools.fx import FxClient
from tests.agents.test_integrator import (  # noqa: F401  (reused fixtures)
    FX_SQL,
    S01,
    cases,
    embeddings,
    index_root,
    integrator_for,
    ledger_db,
    s01_script,
    supporting_verifier,
    triage_script,
)

PLAN = (
    ("query the ledger", "query_ledger"),
    ("search the policy", "search_policies"),
    ("read the reference FX rate", "get_reference_fx"),
    ("compute the difference", "calculate"),
)


def verifier(result: InvestigationResult, *, nli=None) -> InvestigationResult:
    return supporting_verifier([])(result) if result.evidence else result


def planned(ledger_db: Path, index_root: Path, cases: CaseMemory, script: list, *, fault: bool = False):  # noqa: F811
    """The S01 integrator with scripted triage and the verifier that supports one claim."""
    return build_integrator(
        ScriptedChatModel(script=script),
        triage_model=triage_script(*PLAN),
        db_path=ledger_db,
        verifier=verifier,
        query_model=ScriptedChatModel(script=[FX_SQL]),
        fx_client=FxClient(mode="fixtures", fault=fault, sleep=lambda _: None),
        index_root=index_root,
        case_memory=cases,
    )


def tree(events: list[Span]) -> tuple[dict[str, Span], list[str]]:
    """The last version of each span and the order they started in."""
    final: dict[str, Span] = {}
    order: list[str] = []
    for span in events:
        if span.run_id not in final:
            order.append(span.run_id)
        final[span.run_id] = span
    return final, order


def children(final: dict[str, Span], order: list[str], parent: str) -> list[Span]:
    return [final[r] for r in order if final[r].parent_run_id == parent]


def named(final: dict[str, Span], order: list[str], name: str) -> list[Span]:
    return [final[r] for r in order if final[r].name == name]


def test_a_scripted_investigation_emits_a_run_tree_like_langsmith(
    ledger_db: Path,  # noqa: F811
    index_root: Path,  # noqa: F811
    cases: CaseMemory,  # noqa: F811
) -> None:
    events: list[Span] = []
    result = investigate(
        planned(ledger_db, index_root, cases, s01_script()), S01["questions"][0], thread_id="t", on_event=events.append
    )
    final, order = tree(events)

    root = final[order[0]]
    assert root.name == "investigate" and root.parent_run_id is None and events[-1].run_id == root.run_id
    for run_id in order:  # each span starts as `running` and ends once, under a known parent
        span = final[run_id]
        first = next(e for e in events if e.run_id == run_id)
        assert span.status == "ok", (span.name, span.error)
        assert first.status == "running" or span.latency_ms is None  # only point spans are born finished
        assert span.parent_run_id is None or span.parent_run_id in final
    top = [s.name for s in children(final, order, root.run_id)]
    assert top == ["triage", "agent", "verify", "escalation", "CaseMemory.write_case"]

    triage = named(final, order, "triage")[0]
    assert [s.run_type for s in children(final, order, triage.run_id)] == ["prompt", "llm", "parser"]
    assert triage.outputs["intent"] == "refund_discrepancy" and triage.outputs["plan"][0]["tool"] == "query_ledger"

    tools = [final[r] for r in order if final[r].run_type == "tool"]
    assert [t.name for t in tools] == S01["expected_tools"]
    query = tools[0]
    assert query.inputs == {"question": "fx rates applied to TX-2048"}
    assert query.outputs["ok"] is True and query.outputs["evidence_ids"] == ["sql:1"]
    assert query.outputs["data"]["sql"].startswith("SELECT") and query.latency_ms is not None
    sql_model = children(final, order, query.run_id)
    assert [s.run_type for s in sql_model] == ["llm"]  # the model that wrote the SQL sits under the tool
    assert tools[2].inputs["date"] == "2026-10-20" and tools[2].outputs["data"]["rate"]
    agent_llms = [s for s in final.values() if s.run_type == "llm" and final[s.parent_run_id].name == "model"]
    assert len(agent_llms) == 5 and agent_llms[0].outputs["generations"][0]["tool_calls"][0]["name"] == "query_ledger"
    assert all(s.metadata["model"] == "ScriptedChatModel" for s in agent_llms)

    verify = named(final, order, "verify")[0]
    claims = children(final, order, verify.run_id)
    assert [c.name for c in claims] == ["CL1"]
    assert claims[0].outputs["label"] == "supported" and claims[0].metadata == {"check": "rule", "label": "supported"}
    assert verify.outputs["verdicts"] == {"supported": 1, "contradicted": 0, "not_enough_evidence": 0}
    escalation = named(final, order, "escalation")[0]
    assert escalation.outputs["requires_human_review"] is False and escalation.outputs["reasons"] == []

    assert result.answer == root.outputs["answer"]
    summary = root.outputs["summary"]
    assert summary.startswith("Checked 4 sources in ") and "1 claim supported" in summary
    assert root.outputs["tool_calls"] == 4 and root.outputs["tokens"] == 0  # the scripted model counts no tokens


def test_a_failed_tool_is_an_error_span_with_its_code(
    ledger_db: Path,  # noqa: F811
    index_root: Path,  # noqa: F811
    cases: CaseMemory,  # noqa: F811
) -> None:
    events: list[Span] = []
    agent = planned(ledger_db, index_root, cases, s01_script(), fault=True)
    investigate(agent, S01["questions"][0], thread_id="t-fault", on_event=events.append)
    final, order = tree(events)
    fx = named(final, order, "get_reference_fx")[0]
    assert fx.status == "error" and fx.error == fx.outputs["error"]["code"] and fx.outputs["ok"] is False
    escalation = named(final, order, "escalation")[0]
    assert escalation.outputs["requires_human_review"] is True and escalation.outputs["reasons"]


def test_the_plan_follow_up_is_a_span_with_the_second_agent_turn_inside(
    ledger_db: Path,  # noqa: F811
    index_root: Path,  # noqa: F811
    cases: CaseMemory,  # noqa: F811
) -> None:
    events: list[Span] = []
    script = [text_message("Without looking anything up."), text_message("I do not need the tools.")]
    investigate(
        planned(ledger_db, index_root, cases, script), S01["questions"][0], thread_id="t-f", on_event=events.append
    )
    final, order = tree(events)
    followup = named(final, order, "plan_followup")[0]
    assert [step["tool"] for step in followup.inputs["asked"]] == [tool for _, tool in PLAN]
    assert [s.name for s in children(final, order, followup.run_id)] == ["agent"]
    assert any("was not called" in d for d in followup.outputs["plan_deviations"])


def test_a_question_sent_back_by_triage_has_its_own_summary(
    ledger_db: Path,  # noqa: F811
    index_root: Path,  # noqa: F811
    cases: CaseMemory,  # noqa: F811
) -> None:
    events: list[Span] = []
    agent = build_integrator(
        ScriptedChatModel(script=[]),
        triage_model=triage_script(clarification="Which transaction?"),
        db_path=ledger_db,
        verifier=verifier,
        index_root=index_root,
        case_memory=cases,
    )
    investigate(agent, "My money is gone", thread_id="t-vague", on_event=events.append)
    final, order = tree(events)
    root = final[order[0]]
    assert [s.name for s in children(final, order, root.run_id)] == ["triage"]
    assert root.outputs["answer"] == "Which transaction?"
    assert root.outputs["summary"].startswith("Asked for a clarification in ")


def test_a_broken_listener_does_not_break_the_investigation(
    ledger_db: Path,  # noqa: F811
    index_root: Path,  # noqa: F811
    cases: CaseMemory,  # noqa: F811
) -> None:
    def broken(span: Span) -> None:
        raise RuntimeError("the screen went down")

    agent = integrator_for(ledger_db, index_root, cases, s01_script(), verifier=supporting_verifier([]))
    result = investigate(agent, S01["questions"][0], thread_id="t-broken", on_event=broken)
    assert [r.tool for r in result.tool_trace] == S01["expected_tools"]


def test_without_a_listener_nothing_is_added_to_the_calls(
    ledger_db: Path,  # noqa: F811
    index_root: Path,  # noqa: F811
    cases: CaseMemory,  # noqa: F811
) -> None:
    """With no `on_event` the investigation runs as before: no trace callback goes into the LangChain config."""
    from ledgerlens.agents.integrator import traced
    from ledgerlens.observability.trace import Tracer

    assert traced("agent", Tracer())["callbacks"] == []
    agent = integrator_for(ledger_db, index_root, cases, s01_script(), verifier=supporting_verifier([]))
    result = investigate(agent, S01["questions"][0], thread_id="t-quiet")
    assert [r.tool for r in result.tool_trace] == S01["expected_tools"]


def test_the_executor_integrator_emits_the_same_tree(
    tmp_path: Path,
    ledger_db: Path,  # noqa: F811
    index_root: Path,  # noqa: F811
    cases: CaseMemory,  # noqa: F811
) -> None:
    events: list[Span] = []
    agent = build_executor_integrator(
        ScriptedChatModel(script=s01_script()),
        triage_model=triage_script(*PLAN),
        db_path=ledger_db,
        history_db_path=tmp_path / "history.db",
        verifier=verifier,
        query_model=ScriptedChatModel(script=[FX_SQL]),
        fx_client=FxClient(mode="fixtures", sleep=lambda _: None),
        index_root=index_root,
        case_memory=cases,
    )
    investigate_with_executor(agent, S01["questions"][0], session_id="s-trace", on_event=events.append)
    final, order = tree(events)
    root = final[order[0]]
    assert [s.name for s in children(final, order, root.run_id)][:3] == ["triage", "agent", "verify"]
    assert [s.name for s in final.values() if s.run_type == "tool"] == S01["expected_tools"]
    assert root.outputs["summary"].startswith("Checked 4 sources")


# ---- the summary and the cuts ---------------------------------------------------------------------------


def _result(trace: int, labels: list[str], review: bool = False) -> InvestigationResult:
    claims = [Claim(id=f"CL{n}", text="x", kind="fact") for n in range(1, len(labels) + 1)]
    verdicts = [Verdict(claim_id=c.id, label=label, method="nli") for c, label in zip(claims, labels, strict=True)]
    tools = [ToolCallRecord(step=n, tool="query_ledger", input={}, ok=True, duration_ms=1) for n in range(1, trace + 1)]
    return InvestigationResult(
        session_id="s",
        question="q",
        answer="a",
        claims=claims,
        evidence=[],
        verdicts=verdicts,
        coherence=Coherence(passed=True),
        recommended_action="none",
        requires_human_review=review,
        tool_trace=tools,
    )


def test_the_summary_line_counts_sources_tokens_and_verdicts() -> None:
    labels = ["supported"] * 3 + ["not_enough_evidence"]
    assert summary_line(_result(4, labels), 6200) == (
        "Checked 4 sources in 6.2 s: 3 claims supported, 1 without evidence"
    )
    assert summary_line(_result(1, ["supported"]), 950, 1234) == (
        "Checked 1 source in 1.0 s, 1234 tokens: 1 claim supported"
    )
    assert summary_line(_result(2, ["contradicted"], review=True), 3000) == (
        "Checked 2 sources in 3.0 s: 1 claim contradicted; goes to human review"
    )
    assert summary_line(_result(0, []), 400) == "Answered without checking any source in 0.4 s"
    assert summary_line(_result(2, []), 1000) == "Checked 2 sources in 1.0 s: no claim to verify"


def test_compact_cuts_long_lists_and_texts_and_redacts_keys() -> None:
    data = {"rows": [[n] for n in range(20)], "note": "x" * 700, "auth": "Bearer abc.def-123", "key": "sk-" + "a" * 20}
    out = compact(data)
    assert out["rows"][-1] == "…+12 rows" and len(out["rows"]) == 9
    assert out["note"].endswith("…+100 chars")
    assert out["auth"] == "[REDACTED]" and out["key"] == "[REDACTED]"
