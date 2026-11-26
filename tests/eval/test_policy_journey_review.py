"""Bind development judgments and their denominators to the published investigator responses."""

import hashlib
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parents[2] / "data" / "eval"
DIMENSIONS = ("retrieval", "citation_use", "substantive_answer", "operational_action")


def test_review_identifies_the_published_answers_and_recorded_actions():
    raw = json.loads((EVAL_DIR / "reports" / "policy-journeys-openai.json").read_text())
    review = json.loads((EVAL_DIR / "policy_journey_review.json").read_text())
    assert review["source_report"] == "data/eval/reports/policy-journeys-openai.json"
    recorded = {case["case_id"]: case for case in raw["cases"]}
    evaluated = {case["case_id"]: case for case in review["cases"]}
    assert len(recorded) == len(raw["cases"]) == len(evaluated) == len(review["cases"]) == 17
    assert recorded.keys() == evaluated.keys()
    assert review["source_revision"] == raw["revision"]
    assert review["source_sha256"] == raw["source_sha256"]
    assert review["index_corpus_sha256"] == raw["index"]["corpus_sha256"]
    assert review["model"] == raw["model"]
    assert raw["verifier"] == "offline_stub"
    for case_id, case in recorded.items():
        judgment = evaluated[case_id]
        assert judgment["answer_sha256"] == hashlib.sha256(case["answer"].encode("utf-8")).hexdigest()
        assert judgment["recommended_action"] == case["recommended_action"]
        assert judgment["requires_human_review"] == case["requires_human_review"]
        assert judgment["reason"].strip()


def test_summary_uses_all_cases_and_only_definitive_resolutions():
    review = json.loads((EVAL_DIR / "policy_journey_review.json").read_text())
    raw = json.loads((EVAL_DIR / "reports" / "policy-journeys-openai.json").read_text())
    cases, summary = review["cases"], review["summary"]
    assert summary["total_cases"] == len(cases)
    counts = {dimension: Counter(case[dimension] for case in cases) for dimension in DIMENSIONS}
    assert summary["counts"] == counts
    assert counts == {
        "retrieval": {"pass": 15, "not_applicable": 2},
        "citation_use": {"pass": 13, "fail": 3, "not_applicable": 1},
        "substantive_answer": {"pass": 16, "fail": 1},
        "operational_action": {"pass": 10, "fail": 6, "indeterminate": 1},
    }
    unresolved_questions = {"verify-status", "unknown-currency", "pet-insurance"}
    for case in cases:
        passes = all(case[key] in {"pass", "not_applicable"} for key in DIMENSIONS)
        assert case["resolved"] == (passes and case["case_id"] not in unresolved_questions)
    resolutions = sum(case["resolved"] for case in cases)
    cost = sum(Decimal(case["estimated_online_usd"]) for case in raw["cases"])
    assert summary["resolved_cases"] == resolutions == 7
    assert Decimal(summary["estimated_online_usd"]) == cost
    assert Decimal(summary["estimated_online_usd_per_resolved_case"]) == (cost / resolutions).quantize(
        Decimal("0.00000001")
    )
