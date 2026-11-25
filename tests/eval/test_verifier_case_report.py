"""The per case report of the verifier: the claim, the evidence, the two verdicts and the cases that failed.

What they guarantee, and why: the report names the claim, the evidence, the expected verdict and the verdict
that came out for every case, and it counts the false supported, the false contradicted and the case without a
verdict, because an aggregate hides the cases that failed and a release that publishes only the aggregate
publishes a tendency and calls it a significance.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import json
from pathlib import Path

from ledgerlens.eval.case_reports import render_verifier_report, verifier_cases
from ledgerlens.verify.nli import StubNli

ROOT = Path(__file__).resolve().parents[2]
THRESHOLDS = json.loads((ROOT / "ledgerlens" / "verify" / "thresholds.json").read_text(encoding="utf-8"))

ROWS = [
    {"id": "t01", "claim": "The refund was paid.", "evidence": "The refund R-1 was paid.", "expected": "supported"},
    {
        "id": "t02",
        "claim": "The refund was paid.",
        "evidence": "The refund R-1 was rejected.",
        "expected": "contradicted",
    },
]


class _RealShapedNli:
    """An NLI with the shape of the real model, for the tests of the report with the model available."""

    def __init__(self, scores):
        self._scores = scores

    def predict(self, premise: str, hypothesis: str) -> dict[str, float]:
        return self._scores[(premise, hypothesis)]


def _available_nli() -> _RealShapedNli:
    return _RealShapedNli(
        {
            ("The refund R-1 was paid.", "The refund was paid."): {
                "entailment": 0.99,
                "neutral": 0.005,
                "contradiction": 0.005,
            },
            ("The refund R-1 was rejected.", "The refund was paid."): {
                "entailment": 0.005,
                "neutral": 0.005,
                "contradiction": 0.99,
            },
        }
    )


def test_the_report_names_the_claim_the_evidence_and_the_two_verdicts() -> None:
    """Every case of the report carries the claim, the evidence and the two verdicts."""
    nli = _available_nli()
    cases = verifier_cases(ROWS, nli, THRESHOLDS)
    report = render_verifier_report(cases, set_name="verification_set", role="tuning", status="available")

    assert cases[0].got == "supported"
    assert cases[0].outcome == "correct"
    assert cases[1].got == "contradicted"
    assert cases[1].outcome == "correct"
    assert "The refund was paid." in report
    assert "The refund R-1 was rejected." in report
    assert "False supported: 0" in report
    assert "False contradicted: 0" in report


def test_a_false_supported_and_a_false_contradicted_are_counted() -> None:
    """The report counts the two kinds of error, because the two kinds are not the same error."""
    nli = _RealShapedNli(
        {
            ("The refund R-1 was paid.", "The refund was paid."): {
                "entailment": 0.005,
                "neutral": 0.005,
                "contradiction": 0.99,
            },
            ("The refund R-1 was rejected.", "The refund was paid."): {
                "entailment": 0.99,
                "neutral": 0.005,
                "contradiction": 0.005,
            },
        }
    )
    cases = verifier_cases(ROWS, nli, THRESHOLDS)
    report = render_verifier_report(cases, set_name="verification_set", role="tuning", status="available")

    assert "False supported: 1" in report
    assert "False contradicted: 1" in report


def test_the_report_of_the_real_verification_set_is_built_over_the_rows_of_the_set() -> None:
    """The builder reads the text rows of the set, and the count of the cases is the count of the text rows."""
    rows = [
        json.loads(line)
        for line in (ROOT / "data" / "eval" / "verification_set.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    text_rows = [row for row in rows if "claim" in row and "evidence" in row]
    cases = verifier_cases(rows, StubNli(), THRESHOLDS)

    assert len(cases) == len(text_rows)
