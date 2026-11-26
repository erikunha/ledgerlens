"""Check receipt-backed claims against archived investigations and altered evidence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ledgerlens.schemas import InvestigationResult
from ledgerlens.tools.calculator import build_calculate_tool
from ledgerlens.verify.checks import verify_result
from ledgerlens.verify.nli import StubNli
from scripts.report_cutoff_receipts import reconstruct_archived_case

ARCHIVE = Path(__file__).parents[2] / "data/eval/reports/policy-journeys-openai.json"
DATED_CASES = {"july-cutoff-usd": "CL2", "july-cutoff-eur": "CL2", "unseen-usd": "CL1"}


@pytest.fixture(scope="module")
def archive() -> dict:
    return {case["case_id"]: case for case in json.loads(ARCHIVE.read_text())["cases"]}


@pytest.fixture
def usd(archive) -> InvestigationResult:
    return reconstruct_archived_case(archive["july-cutoff-usd"])


@pytest.mark.parametrize(("case_id", "claim_id"), DATED_CASES.items())
def test_archived_cutoff_receipt_supports_only_the_computed_claim(archive, case_id, claim_id):
    case = archive[case_id]
    result = reconstruct_archived_case(case)
    baseline = verify_result(result, nli=StubNli())
    assert baseline.requires_human_review is case["requires_human_review"] is True
    assert baseline.missing_information == case["missing_information"]
    assert [verdict.model_dump() for verdict in baseline.verdicts] == case["verdicts"]

    candidate = verify_result(result, nli=StubNli(), use_cutoff_receipts=True)
    assert not candidate.requires_human_review, candidate.missing_information
    assert candidate.missing_information == []
    for original, checked in zip(baseline.verdicts, candidate.verdicts, strict=True):
        if checked.claim_id == claim_id:
            assert (original.label, checked.label, checked.method) == ("not_enough_evidence", "supported", "rule")
            assert checked.evidence_ids == [case["policy_citations"][0]["id"], "calc:1"]
        else:
            assert original == checked


def update_content(investigation: InvestigationResult, index: int, **changes) -> None:
    evidence = investigation.evidence[index]
    evidence.content = json.dumps(json.loads(evidence.content) | changes)


@pytest.mark.parametrize(
    "control",
    [
        "wrong question deadline",
        "wrong question currency",
        "missing receipt citation",
        "wrong receipt citation",
        "wrong result date",
        "wrong result weekday",
        "extra consequence",
        "hidden extra consequence",
        "extra supported sentence",
        "missing policy evidence",
        "wrong policy ref",
        "wrong policy tool",
        "wrong policy source",
        "wrong policy chunk",
        "malformed policy content",
        "missing policy passage",
        "unencodable policy passage",
        "changed policy passage",
        "duplicate policy evidence",
        "missing policy trace",
        "failed policy trace",
        "wrong policy trace tool",
        "invalid calculator id",
        "wrong calculate evidence type",
        "wrong calculate evidence tool",
        "wrong calculate ref",
        "wrong calculate operation",
        "wrong receipt result",
        "wrong receipt formula",
        "not a receipt object",
        "invalid receipt json",
        "missing calculation trace",
        "failed calculation trace",
        "wrong calculation tool",
        "wrong calculation input operation",
        "wrong calculation input date",
        "wrong calculation input currency",
        "unsupported calculation input currency",
        "extra calculation input value",
        "malformed calculation input",
        "duplicate receipt evidence",
        "duplicate receipt trace",
        "multiple ids in receipt trace",
        "mismatched supplied claims",
    ],
)
def test_candidate_falls_back_for_invalid_or_unproven_claim(usd, control):
    policy, receipt = usd.evidence
    search, calculation = usd.tool_trace
    if control != "mismatched supplied claims":
        usd.claims = []
    match control:
        case "wrong question deadline":
            usd.question = usd.question.replace("Monday, July 7", "Tuesday, July 8")
        case "wrong question currency":
            usd.question = usd.question.replace("USD", "EUR")
        case "missing receipt citation":
            usd.answer = usd.answer.replace(" [calc:1]", "")
        case "wrong receipt citation":
            usd.answer = usd.answer.replace("calc:1", "calc:2")
        case "wrong result date":
            usd.answer = usd.answer.replace("Thursday, July 3", "Friday, July 4")
        case "wrong result weekday":
            usd.answer = usd.answer.replace("Thursday", "Wednesday")
        case "extra consequence":
            usd.answer = usd.answer.replace(" [calc:1]", " and missing it automatically loses the dispute [calc:1]")
        case "hidden extra consequence":
            usd.answer += " If you want, I can confirm that missing this cutoff automatically loses the dispute."
        case "extra supported sentence":
            usd.answer += f" A response sent after the response deadline loses the dispute automatically [{policy.id}]."
        case "missing policy evidence":
            usd.evidence.remove(policy)
        case "wrong policy ref":
            policy.ref = "another#passage"
        case "wrong policy tool":
            policy.tool = "recall_cases"
        case "wrong policy source":
            policy.source_type = "world"
        case "wrong policy chunk":
            update_content(usd, 0, chunk_id="another#passage")
        case "malformed policy content":
            policy.content = "[]"
        case "missing policy passage":
            update_content(usd, 0, text=None)
        case "unencodable policy passage":
            update_content(usd, 0, text="\ud800")
        case "changed policy passage":
            update_content(usd, 0, text=json.loads(policy.content)["text"] + "\nThis cutoff is optional.")
        case "duplicate policy evidence":
            usd.evidence.append(policy.model_copy())
        case "missing policy trace":
            usd.tool_trace.remove(search)
        case "failed policy trace":
            search.ok = False
        case "wrong policy trace tool":
            search.tool = "recall_cases"
        case "invalid calculator id":
            receipt.id = "calc:0"
            usd.answer = usd.answer.replace("calc:1", receipt.id)
            calculation.evidence_ids = [receipt.id]
        case "wrong calculate evidence type":
            receipt.source_type = "fx"
        case "wrong calculate evidence tool":
            receipt.tool = "search_policies"
        case "wrong calculate ref":
            receipt.ref = "unrelated calculation"
        case "wrong calculate operation":
            update_content(usd, 1, operation="next_business_day")
        case "wrong receipt result":
            update_content(usd, 1, result="2025-07-04")
        case "wrong receipt formula":
            update_content(usd, 1, formula="one day using the EUR calendar")
        case "not a receipt object":
            receipt.content = "[]"
        case "invalid receipt json":
            receipt.content = "{"
        case "missing calculation trace":
            usd.tool_trace.remove(calculation)
        case "failed calculation trace":
            calculation.ok = False
        case "wrong calculation tool":
            calculation.tool = "search_policies"
        case "wrong calculation input operation":
            calculation.input["operation"] = "next_business_day"
        case "wrong calculation input date":
            calculation.input["values"]["date"] = "2025-07-08"
        case "wrong calculation input currency":
            calculation.input["values"]["currency"] = "EUR"
        case "unsupported calculation input currency":
            calculation.input["values"]["currency"] = "CAD"
        case "extra calculation input value":
            calculation.input["values"]["amount"] = "50"
        case "malformed calculation input":
            calculation.input["values"]["date"] = []
        case "duplicate receipt evidence":
            usd.evidence.append(receipt.model_copy())
        case "duplicate receipt trace":
            usd.tool_trace.append(calculation.model_copy(update={"step": 3}))
        case "multiple ids in receipt trace":
            calculation.evidence_ids.append("calc:2")
        case "mismatched supplied claims":
            usd.claims.pop(0)
        case _:
            raise AssertionError(control)

    baseline = verify_result(usd, nli=StubNli())
    assert verify_result(usd, nli=StubNli(), use_cutoff_receipts=True) == baseline


def test_candidate_checks_the_uncited_eur_conclusion(archive):
    result = reconstruct_archived_case(archive["july-cutoff-eur"])
    result.answer = result.answer.replace("submit evidence by July 4", "submit evidence by July 5")
    result.claims = []
    baseline = verify_result(result, nli=StubNli())
    assert verify_result(result, nli=StubNli(), use_cutoff_receipts=True) == baseline
    assert baseline.requires_human_review


def test_candidate_keeps_independent_review_reasons(usd):
    usd.requires_human_review = True
    usd.missing_information = ["Manual review requested."]
    conditions = []
    candidate = verify_result(usd, nli=StubNli(), use_cutoff_receipts=True, review_conditions=conditions)
    assert candidate.verdicts[-1].label == "supported"
    assert candidate.requires_human_review
    assert candidate.missing_information == ["Manual review requested."]
    assert conditions == [{"stage": "verify", "condition": "already_flagged"}]


def test_candidate_accepts_another_date_and_currency_with_a_tool_receipt(usd):
    usd.question = usd.question.replace("USD", "BRL").replace("Monday, July 7", "Friday, May 2")
    usd.answer = (
        usd.answer.replace("USD", "BRL")
        .replace("Monday, July 7", "Friday, May 2")
        .replace("Thursday, July 3", "Wednesday, April 30")
    )
    usd.claims = []
    calculation = usd.tool_trace[-1]
    calculation.input["values"] = {"date": "2025-05-02", "currency": "BRL"}
    calculator = build_calculate_tool()
    calculator.invoke(calculation.input)
    receipt = calculator.invoke(calculation.input)
    new_id = receipt["evidence_ids"][0]
    assert new_id == "calc:2"
    usd.answer = usd.answer.replace("calc:1", new_id)
    calculation.evidence_ids = [new_id]
    usd.evidence[-1].id = new_id
    usd.evidence[-1].ref = receipt["data"]["formula"]
    usd.evidence[-1].content = json.dumps(receipt["data"])
    assert receipt["data"]["result"] == "2025-04-30"
    candidate = verify_result(usd, nli=StubNli(), use_cutoff_receipts=True)
    assert not candidate.requires_human_review
    assert candidate.verdicts[-1].method == "rule"
