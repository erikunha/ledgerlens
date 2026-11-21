"""The sets of the verifier: the calibration metadata has to match the data files.

Why it exists: the repository has three different sets, and the number 30 appears in two of them with different
meanings. The NLI calibration was measured over 70 cases, the 30 text cases of the verification set plus the 40 live
sentences, while the verifier verification set has 43 records, because 7 are numeric and 6 are coherence ones, which the
code decides and the NLI does not see. The metadata in `thresholds.json` said "verification_set: 30", which read as if
the whole set had 30 cases. This test ties the metadata to the files, so the divergence does not come back without
anyone noticing.

What they guarantee, and why: (a) the denominators declared in the metadata match the real count of the files; (b) the
breakdown by type of the verification set is the one the metadata declares; (c) the declared combined accuracy is the
weighted mean of the two accuracies, with the right denominators; (d) the cases the NLI does not see, the numeric and
the coherence ones, are the ones the metadata says they are.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from ledgerlens.verify.checks import load_thresholds

ROOT = Path(__file__).resolve().parents[2]
EVAL = ROOT / "data" / "eval"


def _rows(name: str) -> list[dict]:
    """The records of a JSON lines file."""
    return [json.loads(line) for line in (EVAL / name).read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.fixture(scope="module")
def calibration() -> dict:
    """The calibration metadata the repository publishes."""
    return load_thresholds()["calibration"]


def test_the_declared_denominators_match_the_data_files(calibration: dict) -> None:
    """The metadata declares the right denominators, and the NLI sees 70 cases, not 43."""
    verification = _rows("verification_set.jsonl")
    live = _rows("verification_live.jsonl")
    text_cases = [case for case in verification if case["type"] == "text"]

    sets = calibration["sets"]
    assert sets["verification_set_total"] == len(verification)
    assert sets["verification_set_nli"] == len(text_cases)
    assert sets["verification_live"] == len(live)
    assert sets["nli_cases"] == len(text_cases) + len(live)


def test_the_declared_breakdown_by_type_matches_the_data(calibration: dict) -> None:
    """The breakdown by type of the verification set is the one the metadata declares."""
    verification = _rows("verification_set.jsonl")
    counted = Counter(case["type"] for case in verification)
    assert calibration["sets"]["verification_set_by_type"] == dict(counted)


def test_the_combined_accuracy_is_the_weighted_mean_of_the_two_sets(calibration: dict) -> None:
    """The combined accuracy is the weighted mean, and the weight of each set is its number of cases."""
    accuracy = calibration["accuracy"]
    sets = calibration["sets"]
    weighted = (
        accuracy["verification_set_nli"] * sets["verification_set_nli"]
        + accuracy["verification_live"] * sets["verification_live"]
    ) / sets["nli_cases"]
    assert accuracy["combined"] == pytest.approx(weighted, abs=0.001)


def test_the_cases_the_nli_does_not_see_are_declared(calibration: dict) -> None:
    """The cases decided by code are declared, because they do not enter the NLI accuracy."""
    verification = _rows("verification_set.jsonl")
    by_code = [case for case in verification if case["type"] != "text"]
    assert calibration["sets"]["verification_set_by_code"] == len(by_code)
    assert calibration["sets"]["verification_set_by_code"] == len(verification) - calibration["sets"][
        "verification_set_nli"
    ]


def test_the_live_set_has_the_labels_the_calibration_assumes(calibration: dict) -> None:
    """The live set has the three classes, which is what the calibration rule assumes."""
    live = _rows("verification_live.jsonl")
    labels = Counter(case["label"] for case in live)
    assert set(labels) == {"supported", "contradicted", "not_enough_evidence"}
    assert sum(labels.values()) == calibration["sets"]["verification_live"]
