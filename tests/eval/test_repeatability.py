"""Exercise the offline repeatability report using the same CLI as readers."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "scripts" / "report_repeatability.py"


def _run(report: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI), "--report", str(report)],
        capture_output=True,
        text=True,
        check=False,
    )


def _write_report(path: Path, rows: list[dict], cases: int = 1, repeats: int = 2) -> Path:
    path.write_text(
        json.dumps({"cases": cases, "repeats": repeats, "variants": {"A": {}, "B": {}}, "per_case": rows}),
        encoding="utf-8",
    )
    return path


def test_counts_only_cases_with_scores_for_every_trial(tmp_path: Path) -> None:
    measurements = {
        "all": [(1, 1), (1, 0)],
        "some": [(0.5, 1), (1, 1)],
        "none": [(0, 0), (0.5, 0.5)],
        "missing-trial": [(1, 1)],
        "missing-correctness": [(1, 1), (None, 1)],
        "unmeasured": [(1, 1), ("1", True)],
        "scores-out-of-range": [(1, 1), (-0.5, 1.5)],
        "missing-scores": [(1, 1)],
    }
    rows = [
        {
            "variant": "A",
            "case": case,
            "run": trial,
            "scores": {"correctness": correctness, "groundedness": groundedness},
            "answer": "answer-that-must-stay-private",
        }
        for case, scores in measurements.items()
        for trial, (correctness, groundedness) in enumerate(scores, start=1)
    ]
    rows.append({"variant": "A", "case": "missing-scores", "run": 2})
    completed = _run(_write_report(tmp_path / "report.json", list(reversed(rows)), cases=9))

    assert completed.returncode == 0, completed.stderr
    assert completed.stderr == ""
    assert json.loads(completed.stdout) == {
        "repeats": 2,
        "variants": {
            "A": {
                "correctness": {"declared": 9, "eligible": 3, "excluded": 6, "all": 1, "any": 2},
                "groundedness": {"declared": 9, "eligible": 4, "excluded": 5, "all": 2, "any": 3},
            },
            "B": {
                "correctness": {"declared": 9, "eligible": 0, "excluded": 9, "all": 0, "any": 0},
                "groundedness": {"declared": 9, "eligible": 0, "excluded": 9, "all": 0, "any": 0},
            },
        },
    }


@pytest.mark.parametrize(
    ("content", "error"),
    [
        ("{", "report is not valid JSON"),
        ("[]", "report must be a JSON object"),
        ('{"cases": -1}', "cases must be a nonnegative integer"),
        ('{"cases": 1, "repeats": 0}', "repeats must be a positive integer"),
        ('{"cases": 1, "repeats": 2, "variants": []}', "variants must be a mapping"),
        ('{"cases": 1, "repeats": 2, "variants": {}, "per_case": {}}', "per_case must be a list"),
        ('{"cases": 1, "repeats": 2, "variants": {}, "per_case": [null]}', "trial must be an object"),
    ],
)
def test_malformed_report_fails_with_diagnostic(tmp_path: Path, content: str, error: str) -> None:
    path = tmp_path / "report.json"
    path.write_text(content, encoding="utf-8")

    completed = _run(path)

    assert completed.returncode == 2
    assert completed.stdout == ""
    assert error in completed.stderr


def test_missing_report_fails_with_diagnostic(tmp_path: Path) -> None:
    completed = _run(tmp_path / "missing.json")

    assert completed.returncode == 2
    assert completed.stdout == ""
    assert "cannot read report" in completed.stderr


@pytest.mark.parametrize(
    ("update", "error"),
    [
        ({"run": 1}, "duplicate trial identity"),
        ({"run": 0}, "trial number must be an integer from 1 to 2"),
        ({"run": 3}, "trial number must be an integer from 1 to 2"),
        ({"run": True}, "trial number must be an integer from 1 to 2"),
        ({"variant": "C"}, "trial uses an undeclared variant"),
        ({"variant": []}, "trial uses an undeclared variant"),
        ({"case": " "}, "trial case must be a nonempty string"),
        ({"case": None}, "trial case must be a nonempty string"),
        ({"case": "extra"}, "report has more distinct cases than declared"),
        ({"variant": "B", "case": "extra"}, "report has more distinct cases than declared"),
    ],
)
def test_invalid_trial_identities_fail_without_emitting_report(tmp_path: Path, update: dict, error: str) -> None:
    row = {"variant": "A", "case": "some-case", "run": 1, "answer": "answer-that-must-stay-private"}
    completed = _run(_write_report(tmp_path / "report.json", [row, {**row, **update}]))

    assert completed.returncode == 2
    assert completed.stdout == ""
    assert error in completed.stderr
    assert row["answer"] not in completed.stderr


def test_archived_online_report_variant_c_repeatability() -> None:
    completed = _run(ROOT / "data" / "eval" / "report_online.json")

    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["repeats"] == 3
    assert set(report["variants"]) == {"A", "B", "C"}
    assert report["variants"]["C"] == {
        "correctness": {"declared": 30, "eligible": 30, "excluded": 0, "all": 20, "any": 24},
        "groundedness": {"declared": 30, "eligible": 30, "excluded": 0, "all": 16, "any": 20},
    }
