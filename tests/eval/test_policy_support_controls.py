"""Check the denominators of the synthetic policy-support experiment."""

from ledgerlens.eval.case_reports import verifier_cases
from ledgerlens.verify.nli import StubNli
from scripts.report_policy_support import controls, summarize


def test_missing_model_leaves_both_rates_unmeasured():
    cases = verifier_cases(controls(), StubNli(), {})
    report = summarize(cases)
    assert report["without_verdict"] == len(cases)
    assert report["false_support"] == {"count": 0, "eligible": 0}
    assert report["supported_recall"] == {"count": 0, "eligible": 0}


def test_rates_count_each_claim_in_mixed_answer_separately():
    from dataclasses import replace

    rows = verifier_cases(controls(), StubNli(), {})
    cases = [replace(row, got="supported") for row in rows]
    report = summarize(cases)
    assert report["false_support"] == {"count": 3, "eligible": 3}
    assert report["supported_recall"] == {"count": 2, "eligible": 2}
    assert report["without_verdict"] == 0


def test_supported_amount_and_unsupported_deadline_share_the_same_evidence():
    rows = {row["id"]: row for row in controls()}
    assert rows["mixed-amount"]["evidence"] == rows["mixed-deadline"]["evidence"]
    assert rows["mixed-amount"]["expected"] == "supported"
    assert rows["mixed-deadline"]["expected"] == "not_enough_evidence"
