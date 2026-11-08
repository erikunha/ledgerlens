"""Offline report: the three variants over the cases, in the LangSmith format, with no key and no network.

What they guarantee, and why: (a) the report carries the three variants with correctness, groundedness and
the four trajectory modes; (b) two runs in a row give identical reports, so the committed file works as a
reference; (c) the text warns that offline numbers measure the plumbing with scripted answers, not a model's
quality; (d) the committed file is what the run produces today; (e) variant A, with no tools, gets no
trajectory right and C gets the scenarios' right; (f) `--online` with no key refuses and says why.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ledgerlens.eval import run as eval_run
from ledgerlens.eval.dataset import build_cases, build_sample_ledger

OUT_DIR = Path(__file__).resolve().parents[2] / "data" / "eval"
METRICS = [
    "correctness",
    "groundedness",
    "trajectory_strict_match",
    "trajectory_unordered_match",
    "trajectory_subset_match",
    "trajectory_superset_match",
    "trajectory_equivalent_strict_match",
    "trajectory_equivalent_unordered_match",
]


@pytest.fixture(scope="module")
def report(tmp_path_factory: pytest.TempPathFactory) -> dict:
    work = tmp_path_factory.mktemp("eval_report")
    cases = build_cases(build_sample_ledger(work / "ledger.db"))
    return eval_run.run_offline(cases, work / "world")


def test_the_report_has_the_three_variants_and_all_metrics(report: dict) -> None:
    assert report["mode"] == "offline" and report["cases"] == 30
    assert set(report["variants"]) == {"A", "B", "C"}
    for summary in report["variants"].values():
        assert list(summary["metrics"]) == METRICS
        assert all(0.0 <= value <= 1.0 for value in summary["metrics"].values())
    assert len(report["per_case"]) == 90


def test_the_report_says_offline_numbers_measure_the_plumbing(report: dict) -> None:
    note = report["note"]
    assert "scripted" in note and "plumbing" in note and "quality" in note
    assert "scripted" in eval_run.render_markdown(report)


def test_variant_a_has_no_tools_and_c_follows_the_scenarios(report: dict) -> None:
    a, c = report["variants"]["A"]["metrics"], report["variants"]["C"]["metrics"]
    assert a["trajectory_strict_match"] == 0.0 and a["correctness"] < 0.1
    scenario_rows = [r for r in report["per_case"] if r["variant"] == "C" and r["kind"] == "scenario"]
    assert all(r["scores"]["trajectory_strict_match"] == 1.0 for r in scenario_rows)
    assert c["correctness"] > a["correctness"]


def test_two_runs_give_the_same_report(report: dict, tmp_path: Path) -> None:
    cases = build_cases(build_sample_ledger(tmp_path / "ledger.db"))[:6]
    first = eval_run.run_offline(cases, tmp_path / "w1")
    second = eval_run.run_offline(cases, tmp_path / "w2")
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_the_committed_report_is_what_the_run_produces_today(report: dict) -> None:
    committed = json.loads((OUT_DIR / "report_offline.json").read_text("utf-8"))
    assert committed == json.loads(json.dumps(report))
    assert (OUT_DIR / "report_offline.md").read_text("utf-8") == eval_run.render_markdown(report)


def test_the_report_does_not_depend_on_the_ledger_of_the_machine(
    report: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without `data/ledger.db` (the CI case) the report is the same: the verifier reads the evaluation ledger."""
    monkeypatch.setenv("LEDGERLENS_LEDGER_DB", str(tmp_path / "missing.db"))
    cases = build_cases(build_sample_ledger(tmp_path / "ledger.db"))
    other = eval_run.run_offline(cases, tmp_path / "world")
    assert json.dumps(other, sort_keys=True) == json.dumps(report, sort_keys=True)


def test_the_files_are_written_where_asked(report: dict, tmp_path: Path) -> None:
    eval_run.write_report(report, tmp_path)
    assert json.loads((tmp_path / "report_offline.json").read_text("utf-8"))["cases"] == 30
    assert (tmp_path / "report_offline.md").read_text("utf-8").startswith("# ")


def test_online_without_a_key_is_refused(capsys: pytest.CaptureFixture[str]) -> None:
    assert eval_run.main(["--online"]) == 2
    assert "LANGSMITH_API_KEY" in capsys.readouterr().err


def test_the_offline_report_runs_the_verifier_over_the_verification_set(report: dict) -> None:
    v = report["verification"]
    assert v["cases"] == 43 and v["nli"] == "stub"
    assert v["contradiction_recall"] == 1.0 and v["false_positive_rate"] == 0.0 and v["accuracy"] == 1.0
    assert v["misses"] == [] and v["planted"] > 0 and v["supported"] > 0
    assert "## Verifier" in eval_run.render_markdown(report)


def test_the_report_keeps_the_old_expectation_of_the_changed_cases_visible(report: dict) -> None:
    text = eval_run.render_markdown(report)
    assert "## Answer key changes" in text
    assert "EC-19" in text and "EC-24" in text and "`query_ledger`, `calculate`" in text
    assert report["expectation_changes"][0]["before"] == ["query_ledger", "calculate"]
