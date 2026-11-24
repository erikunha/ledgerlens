"""The rule of the verification status: a missing NLI model is not a pass.

What they guarantee, and why: the status of the verification is `available` with the real model and
`unavailable` with the stand-in, and a case whose verification is unavailable is a case without a verdict and
never a pass, because the stand-in decides by word rules and a verification that ran with the stand-in is not
a measurement of the model.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import json
from pathlib import Path

from ledgerlens.eval.case_reports import WITHOUT_VERDICT, render_verifier_report, verifier_cases
from ledgerlens.verify.nli import MODEL_ID, HuggingFaceNli, StubNli, verification_status

ROOT = Path(__file__).resolve().parents[2]
THRESHOLDS = json.loads((ROOT / "ledgerlens" / "verify" / "thresholds.json").read_text(encoding="utf-8"))

ROWS = [{"id": "t01", "claim": "The refund was paid.", "evidence": "The refund R-1 was paid.", "expected": "supported"}]


def test_the_status_is_unavailable_with_the_stand_in() -> None:
    """The stand-in is the sign that the real model is missing, and the status says so."""
    assert verification_status(StubNli()) == "unavailable"


def test_the_status_is_available_with_the_real_model() -> None:
    """The real model is the only verification that is a measurement of the model."""
    assert verification_status(HuggingFaceNli(MODEL_ID)) == "available"


def test_a_case_whose_verification_is_unavailable_is_without_a_verdict_and_never_a_pass() -> None:
    """A missing model is not a pass: the case is without a verdict and the count of the passes is zero."""
    cases = verifier_cases(ROWS, StubNli(), THRESHOLDS)
    report = render_verifier_report(cases, set_name="verification_set", role="tuning", status="unavailable")

    assert cases[0].outcome == WITHOUT_VERDICT
    assert cases[0].got == WITHOUT_VERDICT
    assert "Correct: 0" in report
    assert "Without a verdict: 1" in report
    assert "A missing model is not a pass" in report
