"""The manifest of an experiment: one pinned object that says what a measurement was made of.

Why the manifest exists: a measurement of two variants over a cohort is a fact about the cohort, the variants,
the judge, the seed and the commit, and a measurement whose inputs are not all pinned is a measurement that
cannot be reproduced. The manifest pins every input of the measurement, and the identifier of the experiment is
the hash of the manifest, so two manifests that differ in any field are two experiments and never one.

Why a published experiment is never rewritten: a result that can be rewritten is a result that can be tuned
after the fact. The writer of the manifest refuses to overwrite a published one, and the experiment lives under
`data/eval/experiments/`, so the historical reports of the variants A, B and C are never touched by a new
experiment.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


class ExperimentError(Exception):
    """The manifest of the experiment is not usable, and the message says why."""


@dataclass(frozen=True)
class Variant:
    """One variant of the comparison: the name, the description and the model of the run."""

    name: str
    description: str
    model: str


@dataclass(frozen=True)
class ExperimentManifest:
    """The manifest of an experiment: every input of the measurement, pinned.

    The fields are the cohort (the path, the digest and the count of the cases), the variants, the judge, the
    seed, the commit and the command that produces the result. The identifier of the experiment is the hash of
    these fields, so the manifest carries no identifier of its own: the identifier is computed, never written.
    """

    cohort_path: str
    cohort_sha256: str
    cohort_cases: int
    variants: tuple[Variant, ...]
    judge: str
    seed: int
    commit: str
    command: str
    registered_on: str
    goal: float
    method: str


def manifest_identifier(manifest: ExperimentManifest) -> str:
    """The identifier of the experiment: the hash of the manifest.

    Why the identifier is computed and never written: a written identifier is a field like any other, and two
    manifests that differ in the judge and agree in the written identifier would be one experiment with two
    judges. The hash of the canonical form of the manifest is the name of the experiment, and a field that moves
    moves the name.
    """
    canonical = json.dumps(asdict(manifest), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def write_manifest(manifest: ExperimentManifest, path: Path) -> None:
    """Writes the manifest of the experiment, and refuses to overwrite a published one.

    Why the writer refuses to overwrite: a published experiment is a fact, and a fact that can be rewritten is
    not a fact. The refusal names the path, so the caller knows the experiment is already published.
    """
    if path.exists():
        raise ExperimentError(f"the experiment is already published and is never rewritten: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(manifest)
    payload["experiment_id"] = manifest_identifier(manifest)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_manifest(path: Path) -> ExperimentManifest:
    """Reads the manifest of a published experiment, and refuses a manifest with a field missing.

    Why the reader refuses a field that is missing: a measurement whose inputs are not all pinned is a
    measurement that cannot be reproduced, and a reader that accepted the manifest would be a reader that
    reproduces nothing.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExperimentError(f"the manifest of the experiment cannot be read: {path}") from exc
    if not isinstance(data, dict):
        raise ExperimentError(f"the manifest of the experiment is not an object: {path}")

    required = (
        "cohort_path",
        "cohort_sha256",
        "cohort_cases",
        "variants",
        "judge",
        "seed",
        "commit",
        "command",
        "registered_on",
        "goal",
        "method",
    )
    missing = [field for field in required if field not in data]
    if missing:
        raise ExperimentError(f"the manifest of the experiment has no {', '.join(missing)}: {path}")

    try:
        variants = tuple(
            Variant(name=str(variant["name"]), description=str(variant["description"]), model=str(variant["model"]))
            for variant in data["variants"]
        )
        return ExperimentManifest(
            cohort_path=str(data["cohort_path"]),
            cohort_sha256=str(data["cohort_sha256"]),
            cohort_cases=int(data["cohort_cases"]),
            variants=variants,
            judge=str(data["judge"]),
            seed=int(data["seed"]),
            commit=str(data["commit"]),
            command=str(data["command"]),
            registered_on=str(data["registered_on"]),
            goal=float(data["goal"]),
            method=str(data["method"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ExperimentError(f"the manifest of the experiment has a field of the wrong shape: {path}") from exc
