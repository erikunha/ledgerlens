"""The publisher of the orchestration experiment: the runs of the experiment say what the measurement said.

What they guarantee, and why: the runs of the experiment are built from the published result of the
orchestration measurement, and they say what the measurement said: the same cases, the same scores, the same
cohort, and the citations of the answers. The experiment never invents a number the measurement did not
record, and the intent of the triage, which the measurement did not record, is empty and never guessed.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.publish_orchestration_experiment import _citations_of, runs_of

ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / "data" / "runtime" / "orchestration" / "result.json"
CASES = ROOT / "data" / "eval" / "eval_cases.jsonl"


def _result() -> dict:
    return json.loads(RESULT.read_text(encoding="utf-8"))


def _cases() -> dict:
    return {
        json.loads(line)["id"]: json.loads(line)
        for line in CASES.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


def test_the_runs_say_what_the_measurement_said() -> None:
    """Every run of the experiment is a case of the measurement, with the score of the measurement."""
    result = _result()
    runs = runs_of(result, _cases())

    cohort = result["cohort"]["digest"]
    for arm in ("single_agent", "orchestration_studio"):
        measured = {case["case"]: case["correctness"] for case in result["arms"][arm]["cases"]}
        published = {run["case_id"]: run["score"] for run in runs if run["variant"] == arm}
        assert published == measured
    assert all(run["cohort_sha256"] == cohort for run in runs)


def test_the_runs_carry_the_expected_facts_of_the_cohort_and_the_citations_of_the_answer() -> None:
    """A run carries the expected facts of the case and the citations of the answer of the measurement."""
    result = _result()
    cases = _cases()
    runs = runs_of(result, cases)

    ec01 = next(run for run in runs if run["case_id"] == "EC-01" and run["variant"] == "single_agent")
    assert ec01["expected_facts"] == cases["EC-01"]["expected_facts"]
    assert "sql:1" in ec01["evidence_cited"]


def test_the_intent_the_measurement_did_not_record_is_empty_and_never_guessed() -> None:
    """The intent of the triage is not in the published result, so the runs say so instead of inventing it."""
    runs = runs_of(_result(), _cases())

    assert all(run["intent"] == "" for run in runs)
    assert all(run["complexity"] == "" for run in runs)


def test_the_citations_of_an_answer_are_read_in_the_order_the_answer_wrote_them() -> None:
    """The citations of an answer come out in the order the answer wrote them."""
    answer = "The refund was lower [sql:1, calc:1]. The rate was 5.6339 [fx:2026-10-20:EUR-BRL]."
    assert _citations_of(answer) == ("sql:1", "calc:1", "fx:2026-10-20:EUR-BRL")
