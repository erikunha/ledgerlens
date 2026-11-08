"""Verification set: the verifier finds every planted contradiction and does not flag what is right.

It runs with the NLI stand-in. A test marked `slow` repeats the measurement with the real model.
"""

from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ledgerlens.schemas import Claim, Coherence, Evidence, InvestigationResult
from ledgerlens.verify import verify_result
from ledgerlens.verify.claims import extract_claims
from ledgerlens.verify.nli import MODEL_ID, HuggingFaceNli, StubNli

SET_PATH = Path(__file__).resolve().parents[2] / "data" / "eval" / "verification_set.jsonl"
NOW = datetime(2026, 11, 8, tzinfo=UTC)
TOOLS = {"sql": "query_ledger", "policy": "search_policies", "calc": "calculate"}


def load_cases() -> list[dict]:
    return [json.loads(line) for line in SET_PATH.read_text().splitlines() if line.strip()]


def ev(evidence_id: str, content: str) -> Evidence:
    source = evidence_id.split(":")[0]
    return Evidence(
        id=evidence_id, source_type=source, tool=TOOLS[source], content=content, ref=evidence_id, retrieved_at=NOW
    )


def result_for(case: dict) -> InvestigationResult:
    """Builds a result with one claim (or several, in the coherence cases) from the case."""
    if case["type"] == "text":
        evidence = [ev("policy:1" if case["evidence"].startswith("Policy") else "sql:1", case["evidence"])]
        claims = [Claim(id="CL1", text=case["claim"], kind="fact", evidence_ids=[evidence[0].id])]
        action = "none"
    elif case["type"] == "numeric":
        evidence = [ev("calc:1", case["calc"])]
        claims = extract_claims(f"{case['claim']} [calc:1]", evidence)
        action = "none"
    else:
        evidence = [ev(e["id"], e["content"]) for e in case["evidence"]]
        claims = [
            Claim(id=f"CL{i}", text=c["text"], kind="fact", evidence_ids=c["evidence_ids"])
            for i, c in enumerate(case["claims"], 1)
        ]
        action = case["action"]
    return InvestigationResult(
        session_id="set",
        question="q",
        answer="a",
        claims=claims,
        evidence=evidence,
        verdicts=[],
        coherence=Coherence(passed=True),
        recommended_action=action,
        requires_human_review=False,
    )


def measure(nli) -> dict[str, float]:
    planted = flagged = supported = false_flags = 0
    misses: list[str] = []
    for case in load_cases():
        out = verify_result(result_for(case), nli=nli)
        if case["type"] == "coherence":
            hit = not out.coherence.passed
            if case["planted"]:
                planted += 1
                flagged += hit
                if not hit:
                    misses.append(case["id"])
            elif hit:
                misses.append(case["id"])
            continue
        label = out.verdicts[0].label
        if case["planted"]:
            planted += 1
            flagged += label == "contradicted"
            if label != "contradicted":
                misses.append(case["id"])
        if case["expected"] == "supported":
            supported += 1
            false_flags += label == "contradicted"
            if label != "supported":
                misses.append(case["id"])
        elif case["expected"] == "not_enough_evidence" and label != "not_enough_evidence":
            misses.append(case["id"])
    assert planted and supported
    return {
        "planted": planted,
        "flagged": flagged,
        "supported": supported,
        "false_flags": false_flags,
        "misses": misses,
    }


def test_the_set_has_every_kind_of_case() -> None:
    cases = load_cases()
    assert {c["type"] for c in cases} == {"text", "numeric", "coherence"}
    assert {c.get("expected") for c in cases if c["type"] != "coherence"} == {
        "supported",
        "contradicted",
        "not_enough_evidence",
    }
    assert any("2026-10-03" in c.get("claim", "") for c in cases)  # the planted date contradiction
    assert any(not c["expected_passed"] for c in cases if c["type"] == "coherence")


def test_every_planted_contradiction_is_flagged_with_the_stub() -> None:
    m = measure(StubNli())
    assert m["flagged"] == m["planted"], m["misses"]


def test_at_most_ten_percent_of_supported_claims_are_flagged_contradicted() -> None:
    m = measure(StubNli())
    assert m["false_flags"] / m["supported"] <= 0.10


def test_the_stub_labels_every_case_as_expected() -> None:
    assert measure(StubNli())["misses"] == []


@pytest.mark.slow
@pytest.mark.skipif(importlib.util.find_spec("transformers") is None, reason="extra `verify` is not installed")
def test_the_real_model_meets_the_same_targets() -> None:
    m = measure(HuggingFaceNli(MODEL_ID))
    assert m["flagged"] == m["planted"], m["misses"]
    assert m["false_flags"] / m["supported"] <= 0.10


def test_the_thresholds_record_the_model_they_were_calibrated_with() -> None:
    from ledgerlens.verify.checks import load_thresholds
    from ledgerlens.verify.nli import MODEL_ID

    assert load_thresholds()["calibrated_with"] == MODEL_ID
