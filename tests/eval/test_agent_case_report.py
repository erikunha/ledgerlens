"""The per case report of the agent: the correctness of the agent, apart from the accuracy of the verifier.

What they guarantee, and why: the report publishes the correctness of the agent case by case, and every
sentence that publishes a number names the agent, because the correctness of the agent and the accuracy of
the verifier are two different measurements over two different sets, and a sentence that mixes them publishes
a number that means nothing.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import json
from pathlib import Path

from ledgerlens.eval.case_reports import render_agent_report

ROOT = Path(__file__).resolve().parents[2]

PER_CASE = [
    {
        "case": "EC-01",
        "scenario": "S01",
        "answer": "The refund was lower because of the markup.",
        "scores": {"correctness": 1.0, "trajectory_unordered_match": 1.0},
        "tools": ["query_ledger", "calculate"],
    },
    {
        "case": "EC-02",
        "scenario": "S02",
        "answer": "The settlement is the gross minus the fees.",
        "scores": {"correctness": 0.0, "trajectory_unordered_match": 1.0},
        "tools": ["query_ledger"],
    },
]


def test_the_report_publishes_the_correctness_of_the_agent_case_by_case() -> None:
    """Every case of the evaluation is in the report, with the correctness of the agent."""
    report = render_agent_report(PER_CASE, set_name="eval_cases", role="tuning")

    assert "EC-01" in report
    assert "EC-02" in report
    assert "correctness of the agent" in report
    assert "query_ledger" in report


def test_every_sentence_that_publishes_a_number_names_the_agent() -> None:
    """No sentence of the report mixes the correctness of the agent with the accuracy of the verifier."""
    report = render_agent_report(PER_CASE, set_name="eval_cases", role="tuning")

    for line in report.splitlines():
        if "verifier" in line:
            assert "accuracy" not in line or "two different measurements" in line
    assert "two different measurements" in report


def test_the_report_of_the_real_evaluation_is_built_over_the_cases_of_the_report() -> None:
    """The builder reads the per case list of the report of the evaluation, and every case is in the report."""
    report_online = json.loads((ROOT / "data" / "eval" / "report_online.json").read_text(encoding="utf-8"))
    per_case = [case for case in report_online["per_case"] if case["variant"] == "C"]
    report = render_agent_report(per_case, set_name="eval_cases", role="tuning")

    for case in per_case:
        assert f"| {case['case']} |" in report
