"""Check that the offline lookup report separates argument accuracy from trajectory scores."""

import json
import subprocess
import sys


def test_synthetic_lookup_controls_expose_argument_errors() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "scripts.report_lookup_arguments"], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert set(report) == {"counts", "lookup_calls", "rows"}
    assert report["counts"] == {
        "declared": 6,
        "eligible": 4,
        "correct": 1,
        "incorrect": 1,
        "missing_lookup": 1,
        "mixed": 1,
        "missing_trace": 1,
        "unmeasurable_alternative": 1,
    }
    assert report["lookup_calls"] == {"eligible": 5, "correct": 2, "incorrect": 3}

    expected_rows = [
        ("expected_id", "correct", 1.0, 1.0, 1.0, 1, 0),
        ("swapped_id", "incorrect", 1.0, 1.0, 0.0, 0, 1),
        ("missing_lookup", "missing_lookup", 0.0, 0.0, 0.0, 0, 0),
        ("alternative_tool", "unmeasurable_alternative", 0.0, 1.0, None, None, None),
        ("missing_trace", "missing_trace", None, None, None, None, None),
        ("mixed_lookups", "mixed", 0.0, 0.0, 0.0, 1, 2),
    ]
    assert report["rows"] == [
        {
            "control": control,
            "argument_status": status,
            "trajectory_strict_match": strict,
            "trajectory_equivalent_strict_match": equivalent,
            "argument_score": argument,
            "correct_lookup_calls": correct,
            "incorrect_lookup_calls": incorrect,
        }
        for control, status, strict, equivalent, argument, correct, incorrect in expected_rows
    ]
