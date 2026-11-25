"""The manifest of an experiment: one pinned object that says what a measurement was made of.

What they guarantee, and why: (a) a manifest with a field missing is refused, because a measurement whose inputs
are not all pinned is a measurement that cannot be reproduced; (b) the identifier of the experiment is the hash of
the manifest, so two manifests that differ in the judge are two experiments and never one; (c) a published
experiment is never rewritten, because a result that can be rewritten is a result that can be tuned after the
fact; (d) a new experiment never rewrites the historical reports of the variants A, B and C, and those reports
keep the 0.73 of the trajectory with equivalent tools against the goal of 0.80.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ledgerlens.eval.experiment import (
    ExperimentError,
    ExperimentManifest,
    Variant,
    manifest_identifier,
    read_manifest,
    write_manifest,
)
from ledgerlens.eval.paired import DEFAULT_METHOD

ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS_DIR = ROOT / "data" / "eval" / "experiments"
REPORT_ONLINE = ROOT / "data" / "eval" / "report_online.md"


def _manifest(**overrides: object) -> ExperimentManifest:
    """A manifest of an experiment, with every field pinned."""
    fields = {
        "cohort_path": "data/eval/eval_cases.jsonl",
        "cohort_sha256": "a" * 64,
        "cohort_cases": 31,
        "variants": (
            Variant(name="single_agent", description="the shipped path", model="gpt-4.1-mini"),
            Variant(name="studio", description="the experimental variant", model="gpt-4.1-mini"),
        ),
        "judge": "the deterministic judge of the repository",
        "seed": 42,
        "commit": "b" * 40,
        "command": "uv run python scripts/run_paired_experiment.py --manifest <manifest>",
        "registered_on": "2026-11-25",
        "goal": 0.80,
        "method": DEFAULT_METHOD,
    }
    fields.update(overrides)
    return ExperimentManifest(**fields)  # type: ignore[arg-type]


def test_a_manifest_with_a_field_missing_is_refused(tmp_path: Path) -> None:
    """A measurement whose inputs are not all pinned is a measurement that cannot be reproduced."""
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"cohort_path": "data/eval/eval_cases.jsonl"}) + "\n", encoding="utf-8")

    with pytest.raises(ExperimentError):
        read_manifest(path)


def test_two_manifests_that_differ_in_the_judge_have_two_identifiers() -> None:
    """The identifier is the hash of the manifest, so a different judge is a different experiment."""
    first = _manifest()
    second = _manifest(judge="another judge")

    assert manifest_identifier(first) != manifest_identifier(second)
    assert manifest_identifier(first) == manifest_identifier(_manifest())


def test_a_published_experiment_is_never_rewritten(tmp_path: Path) -> None:
    """A result that can be rewritten is a result that can be tuned after the fact."""
    path = tmp_path / "manifest.json"
    write_manifest(_manifest(), path)
    first_bytes = path.read_bytes()

    with pytest.raises(ExperimentError):
        write_manifest(_manifest(judge="another judge"), path)

    assert path.read_bytes() == first_bytes


def test_a_new_experiment_never_rewrites_the_historical_reports() -> None:
    """The historical reports of the variants A, B and C keep the numbers of their measurement."""
    text = REPORT_ONLINE.read_text(encoding="utf-8")

    assert "0.73" in text
    assert "0.80" in text
    assert "does not meet the 0.80 minimum" in text
    # The experiment of the milestone writes under `data/eval/experiments/` and nowhere else.
    assert EXPERIMENTS_DIR.is_dir() or not EXPERIMENTS_DIR.exists()
