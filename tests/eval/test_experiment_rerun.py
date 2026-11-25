"""The rerun of a published experiment: one command, and the same bytes.

What they guarantee, and why: (a) the rerun of a published experiment reproduces the published result, because
a publication that cannot be reproduced is a publication that asks for trust and not for a check; (b) the
manifest of the experiment carries the commit, the seed, the digest of the cohort and the command that produces
the result, because a measurement whose inputs are not all pinned is a measurement that cannot be reproduced;
(c) the published result carries a hash of its own and the command that reproduces it, so a reader checks the
publication against the content and not against the name of the file.

The rerun of a published experiment is marked slow, the way the repository marks the tests that rerun a
measurement: it recomputes the comparison of a published experiment, and it is run with `pytest -m slow`.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from ledgerlens.eval.experiment import read_manifest
from ledgerlens.eval.paired import compare, read_runs
from scripts.run_paired_experiment import build_result

ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS_DIR = ROOT / "data" / "eval" / "experiments"


def _published_experiments() -> list[Path]:
    """The experiments published under `data/eval/experiments/`."""
    if not EXPERIMENTS_DIR.is_dir():
        return []
    return sorted(path for path in EXPERIMENTS_DIR.iterdir() if (path / "manifest.json").is_file())


@pytest.mark.slow
def test_the_rerun_of_a_published_experiment_reproduces_the_published_result() -> None:
    """The rerun of a published experiment is the published result, byte for byte."""
    experiments = _published_experiments()
    assert experiments, "no experiment is published under data/eval/experiments/"

    for experiment in experiments:
        manifest = read_manifest(experiment / "manifest.json")
        runs = read_runs(experiment / "runs.json")
        comparison = compare(runs, goal=manifest.goal, method=manifest.method)
        rebuilt = build_result(manifest, comparison)
        published = json.loads((experiment / "result.json").read_text(encoding="utf-8"))

        assert rebuilt == published, f"the rerun of the experiment {experiment.name} differs from the published result"


@pytest.mark.slow
def test_the_manifest_carries_the_commit_the_seed_the_digest_and_the_command() -> None:
    """The manifest pins every input of the measurement, or the rerun reproduces nothing."""
    experiments = _published_experiments()
    assert experiments, "no experiment is published under data/eval/experiments/"

    for experiment in experiments:
        manifest = read_manifest(experiment / "manifest.json")
        assert manifest.commit, f"the manifest of {experiment.name} names no commit"
        assert manifest.seed is not None, f"the manifest of {experiment.name} names no seed"
        assert manifest.cohort_sha256, f"the manifest of {experiment.name} names no digest of the cohort"
        assert manifest.command, f"the manifest of {experiment.name} names no command"


def test_the_published_result_carries_a_hash_of_its_own_and_the_command_that_reproduces_it() -> None:
    """The result names the command that reproduces it, and the hash of the result is the hash of its content."""
    experiments = _published_experiments()
    assert experiments, "no experiment is published under data/eval/experiments/"

    for experiment in experiments:
        result = json.loads((experiment / "result.json").read_text(encoding="utf-8"))
        assert result["sha256"], f"the result of {experiment.name} carries no hash of its own"
        assert result["reproduce"], f"the result of {experiment.name} carries no command that reproduces it"
        content = {key: value for key, value in result.items() if key != "sha256"}
        digest = hashlib.sha256(json.dumps(content, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        assert digest == result["sha256"], f"the hash of the result of {experiment.name} is not the hash of its content"
