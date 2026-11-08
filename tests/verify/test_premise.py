"""The NLI premise: the evidence content read as text, without changing what the evidence stores.

The envelopes here have the shape the real tools return (`docs/contracts/tools.md`). The test marked
`slow` runs the `query_ledger` tool over the sample ledger and the real NLI model.
"""

from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from ledgerlens.schemas import Claim, Coherence, Evidence, InvestigationResult
from ledgerlens.verify import verify_result
from ledgerlens.verify.checks import load_thresholds
from ledgerlens.verify.claims import FOCUS_PREMISE_CHARS, render_premise

NOW = datetime(2026, 11, 8, tzinfo=UTC)

STATUS_QUERY = {
    "sql": "SELECT * FROM (SELECT status FROM transactions WHERE id = 'TX-0001') LIMIT 50",
    "columns": ["status"],
    "rows": [["captured"]],
    "row_count": 1,
    "truncated": False,
}


def sql(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False)


def test_a_query_with_one_column_still_says_which_record_it_is_about() -> None:
    # The NLI model does not relate `{"rows": [["captured"]]}` to "the status of TX-0001 is captured", and the
    # transaction id is only in the SQL text. The premise carries the column, the value and the filter, not the SQL.
    premise = render_premise(sql(STATUS_QUERY))
    assert premise == "id: TX-0001; status: captured."


def test_every_row_becomes_a_line_of_column_value_pairs() -> None:
    data = {
        "sql": "SELECT * FROM (SELECT kind, applied_rate FROM fx_applied WHERE transaction_id = 'TX-2048') LIMIT 50",
        "columns": ["kind", "applied_rate"],
        "rows": [["charge", "5.6679"], ["refund", "5.4931"]],
        "row_count": 2,
        "truncated": False,
    }
    assert render_premise(sql(data)).splitlines() == [
        "transaction_id: TX-2048; kind: charge; applied_rate: 5.6679.",
        "transaction_id: TX-2048; kind: refund; applied_rate: 5.4931.",
    ]


def test_a_column_the_row_already_has_is_not_repeated_from_the_filter() -> None:
    data = {
        "sql": "SELECT id, status FROM transactions WHERE id = 'TX-0001'",
        "columns": ["id", "status"],
        "rows": [["TX-0001", "captured"]],
        "row_count": 1,
        "truncated": False,
    }
    assert render_premise(sql(data)) == "id: TX-0001; status: captured."


def test_a_filter_that_does_not_hold_for_every_row_is_not_taken_as_a_fact() -> None:
    data = {
        "sql": "SELECT status FROM transactions WHERE id = 'TX-0001' OR id = 'TX-0002'",
        "columns": ["status"],
        "rows": [["captured"], ["failed"]],
        "row_count": 2,
        "truncated": False,
    }
    assert render_premise(sql(data)).splitlines() == ["status: captured.", "status: failed."]
    twice = {**data, "sql": "SELECT status FROM transactions WHERE id = 'TX-0001' AND id = 'TX-0002'"}
    assert render_premise(sql(twice)).splitlines() == ["status: captured.", "status: failed."]


def test_an_empty_result_says_the_record_does_not_exist() -> None:
    # `rows: []` read by the NLI model gives "contradicted" for "the record does not exist". The premise says so.
    data = {**STATUS_QUERY, "sql": STATUS_QUERY["sql"].replace("TX-0001", "TX-9999"), "rows": [], "row_count": 0}
    premise = render_premise(sql(data))
    assert "id = TX-9999" in premise and "row_count: 0" in premise and "does not exist" in premise
    assert "[" not in premise and "SELECT" not in premise
    everything = {**data, "sql": "SELECT status FROM transactions"}
    assert render_premise(sql(everything)).startswith("Zero rows found (row_count: 0).")


def test_a_ledger_record_reads_section_by_section() -> None:
    record = {
        "transaction": {"id": "TX-0001", "merchant_id": "M-20", "status": "captured", "captured_at": None},
        "refunds": [],
        "chargebacks": [{"id": "CB-0001", "stage": "opened"}],
        "fx_applied": [],
    }
    assert render_premise(sql(record)).splitlines() == [
        "transaction: id: TX-0001; merchant_id: M-20; status: captured; captured_at: null.",
        "refunds: none.",
        "chargebacks: id: CB-0001; stage: opened.",
        "fx_applied: none.",
    ]


def test_a_policy_chunk_is_its_text_as_is() -> None:
    chunk = {
        "chunk_id": "escalation-and-review#high-amount",
        "document": "escalation-and-review",
        "section": "High amounts",
        "topic": "escalation",
        "version": "2026-10-01",
        "text": "High amounts\nAny payment above 5,000 requires human review.",
        "score": 1.06,
    }
    assert render_premise(sql(chunk)) == chunk["text"]


def test_a_reference_rate_reads_as_a_sentence() -> None:
    rate = {
        "requested_date": "2026-10-20",
        "rate_date": "2026-10-20",
        "from_currency": "EUR",
        "to_currency": "BRL",
        "rate": "5.6339",
        "source": "frankfurter",
        "note": "It is a reference, not the rate any acquirer applied.",
        "from_cache": False,
    }
    premise = render_premise(sql(rate))
    assert premise.startswith("Reference rate from EUR to BRL on 2026-10-20")
    assert "5.6339" in premise and "frankfurter" in premise and rate["note"] in premise
    assert "from_cache" not in premise


def test_a_calculation_and_a_remembered_case_read_as_sentences() -> None:
    calc = {"operation": "convert", "result": "564", "formula": "100.00 * 5.6418 = 564"}
    assert render_premise(sql(calc)) == "Calculation convert: result 564. Formula: 100.00 * 5.6418 = 564."
    gap = {"operation": "fx_gap_breakdown", "result": {"gap": "17.48", "markup": "14.08"}, "formula": "gap = a - b"}
    assert render_premise(sql(gap)) == (
        "Calculation fx_gap_breakdown: result gap 17.48, markup 14.08. Formula: gap = a - b."
    )
    case = {
        "case_id": "CASE-0001",
        "kind": "semantic",
        "finding": "Merchant M-17 applies a 2.5% markup on refunds.",
        "created_at": "2026-11-07T09:00:00+00:00",
        "confidence": "high",
        "score": 0.78,
    }
    assert render_premise(sql(case)) == "Case CASE-0001 (semantic, 2026-11-07, confidence high): " + case["finding"]


def test_text_that_is_not_a_known_envelope_passes_through() -> None:
    assert render_premise("R-0412 paid") == "R-0412 paid"
    assert render_premise('{"unknown": 1}') == '{"unknown": 1}'  # JSON with no known shape is not rewritten
    assert render_premise("[1, 2]") == "[1, 2]"


def _result(content: str) -> InvestigationResult:
    evidence = Evidence(
        id="sql:1", source_type="sql", tool="query_ledger", content=content, ref="ref", retrieved_at=NOW
    )
    text = 'The status of transaction TX-0001 is "captured".'
    claim = Claim(id="CL1", text=text, kind="fact", evidence_ids=["sql:1"])
    return InvestigationResult(
        session_id="s",
        question="q",
        answer="a",
        claims=[claim],
        evidence=[evidence],
        verdicts=[],
        coherence=Coherence(passed=True),
        recommended_action="none",
        requires_human_review=False,
    )


class RecordingNli:
    def __init__(self) -> None:
        self.premises: list[str] = []

    def predict(self, premise: str, hypothesis: str) -> dict[str, float]:
        self.premises.append(premise)
        return {"entailment": 0.97, "neutral": 0.02, "contradiction": 0.01}


def test_the_verifier_gives_the_nli_the_rendered_premise_and_keeps_the_evidence_untouched() -> None:
    content = sql(STATUS_QUERY)
    nli = RecordingNli()
    out = verify_result(_result(content), nli=nli)
    assert nli.premises == ["id: TX-0001; status: captured."]
    assert out.evidence[0].content == content


def test_a_long_premise_keeps_only_the_lines_that_mention_the_claim_s_ids() -> None:
    # The NLI model reads only the start of the premise and calls a true claim "contradicted" when the other
    # lines (other payouts of the same merchant) come along. With 14 payouts, only ST-0044 stays.
    settlements = [
        {
            "id": f"ST-{n:04d}",
            "merchant_id": "M-03",
            "currency": "BRL",
            "net_minor": 1000 + n,
            "status": "paid",
            "paid_at": "2026-08-18T06:00:00Z",
            "expected_payout_date": "2026-08-18",
        }
        for n in range(31, 45)
    ]
    content = sql({"merchant_id": "M-03", "settlements": settlements})
    assert len(render_premise(content)) > FOCUS_PREMISE_CHARS
    text = "Payout ST-0044 of merchant M-03 had a net of 10.44."
    claim = Claim(id="CL1", text=text, kind="fact", evidence_ids=["sql:1"])
    nli = RecordingNli()
    verify_result(_result(content).model_copy(update={"claims": [claim]}), nli=nli)
    assert nli.premises == [
        "settlements: id: ST-0044; merchant_id: M-03; currency: BRL; net_minor: 1044; status: paid; "
        "paid_at: 2026-08-18T06:00:00Z; expected_payout_date: 2026-08-18."
    ]


def test_a_short_premise_keeps_every_line_and_a_claim_without_ids_keeps_them_too() -> None:
    record = {"transaction": {"id": "TX-0001", "status": "captured"}, "refunds": [{"id": "R-0001", "status": "paid"}]}
    both = "transaction: id: TX-0001; status: captured.\nrefunds: id: R-0001; status: paid."
    nli = RecordingNli()
    claim = Claim(id="CL1", text="Refund R-0001 was paid.", kind="fact", evidence_ids=["sql:1"])
    verify_result(_result(sql(record)).model_copy(update={"claims": [claim]}), nli=nli)
    assert nli.premises == [both]
    long_record = {"settlements": [{"id": f"ST-{n:04d}", "note": "x" * 60} for n in range(40)]}
    claim = Claim(id="CL1", text="There were payouts.", kind="fact", evidence_ids=["sql:1"])
    verify_result(_result(sql(long_record)).model_copy(update={"claims": [claim]}), nli=nli)
    assert len(nli.premises[1].splitlines()) == 40
    # no line cites ST-9999
    claim = Claim(id="CL1", text="Payout ST-9999 exists.", kind="fact", evidence_ids=["sql:1"])
    verify_result(_result(sql(long_record)).model_copy(update={"claims": [claim]}), nli=nli)
    assert len(nli.premises[2].splitlines()) == 40


def test_the_premise_is_cut_at_the_configured_size() -> None:
    nli = RecordingNli()
    verify_result(_result("x" * 9000), nli=nli)
    assert len(nli.premises[0]) == load_thresholds()["max_premise_chars"]


@pytest.mark.slow
@pytest.mark.skipif(importlib.util.find_spec("transformers") is None, reason="extra `verify` is not installed")
def test_the_real_nli_judges_claims_against_the_envelope_a_real_tool_returns(tmp_path: Path) -> None:
    from ledgerlens.agents.integrator import _assemble
    from ledgerlens.eval.dataset import build_sample_ledger
    from ledgerlens.offline import ScriptedChatModel
    from ledgerlens.tools.sql import build_query_ledger_tool
    from ledgerlens.verify.nli import get_nli

    ledger = build_sample_ledger(tmp_path / "ledger.db")
    queries = {
        "status": "SELECT status FROM transactions WHERE id = 'TX-0001'",
        "merchant": "SELECT merchant_id FROM transactions WHERE id = 'TX-0001'",
        "missing": "SELECT status FROM transactions WHERE id = 'TX-9999'",
    }
    evidence: dict[str, Evidence] = {}
    for name, query in queries.items():
        tool = build_query_ledger_tool(ScriptedChatModel(script=[query]), db_path=ledger)
        envelope = tool.invoke({"question": name})
        call = {"name": "query_ledger", "args": {"question": name}, "id": name, "type": "tool_call"}
        turn = [
            HumanMessage("q"),
            AIMessage(content="", tool_calls=[call]),
            ToolMessage(content=json.dumps(envelope), tool_call_id=name, name="query_ledger"),
        ]
        evidence[name] = _assemble("q", "s", turn, [0]).evidence[0]

    def label(name: str, text: str) -> str:
        ev = evidence[name].model_copy(update={"id": "sql:1"})
        claim = Claim(id="CL1", text=text, kind="fact", evidence_ids=["sql:1"])
        result = InvestigationResult(
            session_id="s",
            question="q",
            answer="a",
            claims=[claim],
            evidence=[ev],
            verdicts=[],
            coherence=Coherence(passed=True),
            recommended_action="none",
            requires_human_review=False,
        )
        return verify_result(result, nli=get_nli(False, require_real=True)).verdicts[0].label

    assert label("status", 'The status of transaction TX-0001 is "captured".') == "supported"
    assert label("merchant", "Transaction TX-0001 belongs to merchant M-20.") == "supported"
    assert label("merchant", "Transaction TX-0001 belongs to merchant M-05.") == "contradicted"
    assert label("missing", "No record was found for transaction TX-9999 in the ledger.") == "supported"
    assert label("missing", "Transaction TX-9999 is captured.") == "contradicted"
