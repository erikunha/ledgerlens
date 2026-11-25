#!/usr/bin/env python3
"""Runs a paired experiment: reads the manifest, computes the comparison, and writes the result, the gallery and
the manifest of the experiment under `data/eval/experiments/`.

Why it exists: a paired comparison is a measurement, and a measurement that is not published with its manifest
is a measurement that cannot be reproduced. The script reads the manifest of the experiment, reads the runs of
the two variants, computes the comparison and the gallery of the failures, and writes the three artifacts under
`data/eval/experiments/<experiment_id>/`.

Why the script refuses to overwrite an experiment that was published: a published experiment is a fact, and a
fact that can be rewritten is not a fact. The script never touches the historical reports of the variants A, B
and C: it writes under `data/eval/experiments/` and nowhere else.

Usage:

```bash
uv run python scripts/run_paired_experiment.py --manifest <manifest.json> --runs <runs.json> [--role tuning]
```

Exit code 0 when the artifacts were written, 1 when they could not be.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ledgerlens.eval.experiment import (  # noqa: E402
    ExperimentError,
    manifest_identifier,
    read_manifest,
    write_manifest,
)
from ledgerlens.eval.failures import GalleryError, build_gallery  # noqa: E402
from ledgerlens.eval.paired import ComparisonError, compare, read_runs  # noqa: E402

EXPERIMENTS_DIR = ROOT / "data" / "eval" / "experiments"


def build_result(manifest, comparison) -> dict:
    """The result of the experiment, as the publication writes it, with the hash of its own content.

    Why the function is apart from the publication: the rerun of a published experiment rebuilds the result
    from the same manifest and the same runs, and the rebuild is this function, so the rerun and the
    publication can never disagree about what the result is.
    """
    result = {
        "experiment_id": manifest_identifier(manifest),
        "cohort_sha256": comparison.cohort_sha256,
        "variants": list(comparison.variants),
        "paired_cases": comparison.paired_cases,
        "excluded": [case.__dict__ for case in comparison.excluded],
        "differences": [item.__dict__ for item in comparison.differences],
        "means": comparison.means,
        "mean_difference": comparison.mean_difference,
        "interval": comparison.interval.__dict__,
        "goal": comparison.goal,
        "goal_met": comparison.goal_met,
        "minimum_stratum": comparison.minimum_stratum,
        "strata": [stratum.__dict__ for stratum in comparison.strata],
        "reproduce": manifest.command,
    }
    # The hash of the result is the hash of the content of the result, so a reader checks the publication
    # against the content and not against the name of the file.
    result["sha256"] = hashlib.sha256(
        json.dumps(result, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return result


def publish(manifest_path: Path, runs_path: Path, role: str) -> Path:
    """Publishes the experiment of a manifest and of the runs of the measurement, and returns the folder.

    Why the function is apart from the command line: the publisher of an experiment that was measured by
    another script builds the manifest and the runs and calls this function, so the publication of every
    experiment goes through the same door and the refusal to overwrite is the same everywhere.
    """
    manifest = read_manifest(manifest_path)
    runs = read_runs(runs_path)
    comparison = compare(runs, goal=manifest.goal, method=manifest.method)
    gallery = build_gallery(comparison, runs, cohort_role=role)

    experiment_id = manifest_identifier(manifest)
    out_dir = EXPERIMENTS_DIR / experiment_id
    if out_dir.exists():
        raise ExperimentError(f"the experiment is already published and is never rewritten: {out_dir}")

    write_manifest(manifest, out_dir / "manifest.json")
    # The runs of the measurement travel with the experiment, so that a third party reruns the comparison from
    # the same runs and gets the same bytes.
    (out_dir / "runs.json").write_text(
        json.dumps(
            {"cohort_sha256": comparison.cohort_sha256, "runs": [run.__dict__ for run in runs]},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    result = build_result(manifest, comparison)
    (out_dir / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out_dir / "gallery.json").write_text(
        json.dumps(gallery, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return out_dir


def main() -> int:
    """Runs the command and returns the exit code of the answer."""
    parser = argparse.ArgumentParser(description="Runs a paired experiment and publishes the artifacts.")
    parser.add_argument("--manifest", required=True, help="the manifest of the experiment")
    parser.add_argument("--runs", required=True, help="the runs of the two variants over the cohort")
    parser.add_argument("--role", default="tuning", help="the role of the cohort, for the gallery")
    args = parser.parse_args()

    try:
        out_dir = publish(Path(args.manifest), Path(args.runs), args.role)
    except (ExperimentError, ComparisonError, GalleryError) as exc:
        print(f"run_paired_experiment: {exc}", file=sys.stderr)
        return 1
    print(f"the experiment was published: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
