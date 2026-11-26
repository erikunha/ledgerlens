"""Exercise family splits, blinded trial assignment and failure-inclusive holdout reports."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "report_holdout_comparison.py"
BASELINE = "existing-verifier"
CANDIDATE = "receipt-verifier"
BLIND_SEED = "private synthetic evaluation seed"


def _write(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _run(
    command: str, manifest: Path, results: Path | None = None, seed: str = BLIND_SEED
) -> subprocess.CompletedProcess[str]:
    args = [sys.executable, str(SCRIPT), command, "--manifest", str(manifest), "--blind-seed", seed]
    if results is not None:
        args.extend(["--results", str(results)])
    return subprocess.run(args, capture_output=True, text=True, check=False)


def _get(result: subprocess.CompletedProcess[str]) -> dict:
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _manifest(path: Path, cases: dict[str, str], holdout_families: int = 1) -> Path:
    return _write(
        path,
        {
            "variants": [BASELINE, CANDIDATE],
            "cases": cases,
            "holdout_families": holdout_families,
            "repeats": 2,
            "split_seed": "registered split",
        },
    )


def test_plan_keeps_families_together_and_alternates_blinded_trials(tmp_path: Path) -> None:
    cases = {"a": "settlement", "b": "settlement", "c": "refund", "d": "refund", "e": "dispute"}
    manifest = _manifest(tmp_path / "manifest.json", cases, holdout_families=2)
    plan = _get(_run("plan", manifest))
    reordered = _manifest(tmp_path / "reordered.json", dict(reversed(list(cases.items()))), holdout_families=2)
    assert plan == _get(_run("plan", reordered))

    assert plan["development"] | plan["holdout"] == cases
    assert len(set(plan["holdout"].values())) == 2
    assert set(plan["development"].values()).isdisjoint(plan["holdout"].values())
    assignments = plan["assignments"]
    for case in plan["holdout"]:
        pair = [row["slots"] for row in assignments if row["case"] == case]
        assert {slot["variant"] for slot in pair[0]} == {BASELINE, CANDIDATE}
        assert [slot["arm"] for slot in pair[0]] == [slot["arm"] for slot in reversed(pair[1])]
    ids = [slot["id"] for row in assignments for slot in row["slots"]]
    assert len(ids) == len(set(ids)) == 4 * len(plan["holdout"])
    assert all(len(trial_id) == 64 and BASELINE not in trial_id and CANDIDATE not in trial_id for trial_id in ids)

    reblinded = _get(_run("plan", manifest, seed="separate blind seed"))
    assert reblinded["split_sha256"] == plan["split_sha256"]
    assert reblinded["manifest_sha256"] == plan["manifest_sha256"]
    assert not set(ids).intersection(slot["id"] for row in reblinded["assignments"] for slot in row["slots"])
    relabeled = _manifest(tmp_path / "relabeled.json", cases | {"a": "dispute"}, holdout_families=2)
    assert _get(_run("plan", relabeled))["split_sha256"] != plan["split_sha256"]
    revised = json.loads(manifest.read_text(encoding="utf-8")) | {"criteria_version": "v2"}
    revised_plan = _get(_run("plan", _write(tmp_path / "revised.json", revised)))
    assert revised_plan["split_sha256"] == plan["split_sha256"]
    assert revised_plan["manifest_sha256"] != plan["manifest_sha256"]


def test_report_pairs_families_and_penalizes_missing_trials(tmp_path: Path) -> None:
    cases = {"a": "large", "b": "large", "c": "large", "omitted": "large", "d": "small"}
    manifest = _manifest(tmp_path / "manifest.json", cases, holdout_families=2)
    plan = _get(_run("plan", manifest))
    arms = {slot["variant"]: slot["arm"] for row in plan["assignments"] for slot in row["slots"]}
    results = []
    omitted_ids = []
    candidate_outcomes = {"d": ["resolved", "resolved"], "a": ["clarified", "error"], "b": ["timeout", "failed"]}
    for row in plan["assignments"]:
        case, run = row["case"], row["run"]
        for slot in row["slots"]:
            if case == "omitted" or (case == "c" and run == 2 and slot["variant"] == CANDIDATE):
                omitted_ids.append(slot["id"])
                continue
            outcome = "failed"
            if slot["variant"] == CANDIDATE and case in candidate_outcomes:
                outcome = candidate_outcomes[case][run - 1]
            results.append({"id": slot["id"], "outcome": outcome, "cost_usd": "0.10"})
    input_path = _write(tmp_path / "results.json", results)

    completed = _run("report", manifest, input_path)
    report = _get(completed)
    assert report == _get(_run("report", manifest, _write(input_path, list(reversed(results)))))
    assert report["split_sha256"] == plan["split_sha256"]
    assert report["manifest_sha256"] == plan["manifest_sha256"]
    assert BASELINE not in completed.stdout and CANDIDATE not in completed.stdout and BLIND_SEED not in completed.stdout
    assert set(report["missing_trial_ids"]) == set(omitted_ids)
    assert report["shared_failure_cases"] == ["a", "b", "c", "omitted"]
    assert report["disagreement_cases"] == ["d"]

    candidate = report["arms"][arms[CANDIDATE]]
    assert candidate == {
        "trials": 10,
        "resolved": 2,
        "clarified": 1,
        "failed": 2,
        "error": 1,
        "timeout": 1,
        "missing": 3,
        "successful_trials": 2,
        "per_trial_success_rate": 0.2,
        "cases": 5,
        "all_trials_success": 1,
        "all_trial_success_rate": 0.2,
        "cost_usd": "0.70",
        "trials_with_cost": 7,
    }
    assert report["arms"][arms[BASELINE]]["missing"] == 2
    direction = 1 if arms[CANDIDATE] == "B" else -1
    assert report["paired"]["families"] == 2
    for metric in ("all_trial_success", "per_trial_success"):
        assert report["paired"][metric] == {
            "difference_b_minus_a": direction * 0.5,
            "interval_95": sorted((0.0, direction * 1.0)),
        }


def test_report_with_one_family_reports_no_interval(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path / "manifest.json", {"a": "family"})
    results = _write(tmp_path / "results.json", [])
    report = _get(_run("report", manifest, results))
    assert report["paired"]["families"] == 1
    assert report["paired"]["all_trial_success"] == {"difference_b_minus_a": 0.0, "interval_95": None}
    assert report["arms"]["A"]["cost_usd"] is None


def test_an_appropriate_clarification_can_succeed_without_resolution(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path / "manifest.json", {"a": "family"})
    plan = _get(_run("plan", manifest))
    slot = plan["assignments"][0]["slots"][0]
    rows = [{"id": slot["id"], "outcome": "clarified", "success": True}]
    report = _get(_run("report", manifest, _write(tmp_path / "results.json", rows)))
    arm = report["arms"][slot["arm"]]
    assert arm["resolved"] == 0
    assert arm["clarified"] == arm["successful_trials"] == 1
    assert arm["per_trial_success_rate"] == 0.5
    assert arm["all_trial_success_rate"] == 0
    direction = 1 if slot["arm"] == "B" else -1
    assert report["paired"]["per_trial_success"]["difference_b_minus_a"] == direction * 0.5


def test_plan_rejects_duplicate_case_ids_in_json(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path / "manifest.json", {"a": "family"})
    content = manifest.read_text(encoding="utf-8")
    manifest.write_text(content.replace('"a": "family"', '"a": "family", "a": "other"'), encoding="utf-8")
    result = _run("plan", manifest)
    assert result.returncode == 2
    assert not result.stdout
    assert "duplicate key in input JSON" in result.stderr


@pytest.mark.parametrize(
    ("problem", "error"),
    [
        ("duplicate", "duplicate trial ID"),
        ("unknown", "unknown trial ID"),
        ("missing-outcome", "invalid trial outcome"),
        ("invalid-cost", "cost_usd must be a nonnegative decimal string"),
        ("contradictory-success", "invalid trial success"),
    ],
)
def test_report_rejects_ambiguous_trial_rows(tmp_path: Path, problem: str, error: str) -> None:
    manifest = _manifest(tmp_path / "manifest.json", {"a": "family"})
    trial_id = _get(_run("plan", manifest))["assignments"][0]["slots"][0]["id"]
    row = {"id": trial_id, "outcome": "resolved"}
    invalid_rows = {
        "duplicate": [row, row],
        "unknown": [row | {"id": "outside this holdout"}],
        "missing-outcome": [{"id": trial_id}],
        "invalid-cost": [row | {"cost_usd": "NaN"}],
        "contradictory-success": [row | {"outcome": "timeout", "success": True}],
    }
    result = _run("report", manifest, _write(tmp_path / "results.json", invalid_rows[problem]))
    assert result.returncode == 2
    assert not result.stdout
    assert error in result.stderr


def test_missing_two_arm_evidence_has_no_interval(tmp_path):
    manifest = _manifest(tmp_path / "manifest.json", {"one": "x", "two": "y"}, holdout_families=2)
    results = _write(tmp_path / "results.json", [])
    paired = _get(_run("report", manifest, results))["paired"]
    assert paired["families_with_observed_pairs"] == 0
    assert paired["per_trial_success"]["interval_95"] is None
    slot = _get(_run("plan", manifest))["assignments"][0]["slots"][0]
    _write(results, [{"id": slot["id"], "outcome": "failed", "success": True}])
    assert _run("report", manifest, results).returncode != 0
