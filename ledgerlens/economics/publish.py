"""The published result of the economics: the export, its hash and the digest of its cohort.

Why it exists: every published artifact of the repository is a file with a manifest and a hash, so a reader can
check that what they read is what was measured. The economics result is a number that a decision rests on, and a
number that nobody can check is a number that cannot be trusted.

Why the export copies, hashes and labels and never changes the content: the artifact is the evidence of a
computation, and an export that adjusted the numbers would be a second computation dressed as a publication.

Why the export is byte identical when it runs twice: an artifact that changes every time it is written is an artifact
nobody can compare with the one of the day before, and the digest of the content is over the sorted content and not
over the moment of the writing.

Why a cohort whose digest moved is refused: a result computed over one cohort and published over another describes
nothing, and the digest is what says that the two are the same.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ledgerlens.economics.cost import CohortComparison, CohortCost

__all__ = ["ARTIFACT_NAME", "COMPARISON_NAME", "export_comparison", "export_economics", "published_bytes", "publish"]

# The name of the artifact of the economics in the folder of the published results.
ARTIFACT_NAME = "economics.json"

# The name of the artifact of the comparison of two arms.
COMPARISON_NAME = "economics_comparison.json"


def published_bytes(cohort: CohortCost) -> dict[str, Any]:
    """The artifact of the cohort, with the hash of its content and the digest it was computed over.

    Why the hash covers the content and not the artifact: the hash of a file that carries its own hash is a hash
    that never matches, and the reader of the artifact has to be able to check it.
    """
    body = {
        "cohort": cohort.to_dict(),
        "cohort_digest": cohort.cohort_digest,
    }
    content = json.dumps(body, indent=2, sort_keys=True)
    return {**body, "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest()}


def export_economics(
    cohort: CohortCost,
    *,
    expected_digest: str,
    out_dir: Path,
) -> Path:
    """Writes the artifact of the cohort and returns where it wrote it.

    Why the digest is checked before anything is written: an artifact over a cohort that is not the one that was
    measured is a result that describes nothing, and a file that is already on the disk cannot be unread.
    """
    if cohort.cohort_digest != expected_digest:
        raise ValueError(
            "the digest of the cohort moved, so the export is refused: the cohort carries "
            f"{cohort.cohort_digest!r} and the measurement was over {expected_digest!r}"
        )
    payload = published_bytes(cohort)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / ARTIFACT_NAME
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def publish(cohort: CohortCost, *, expected_digest: str, out_dir: Path) -> Path:
    """The name the script calls, so that the export has one entry point and not two.

    Why it exists and not the other way round: the export is the function the tests exercise and the script is the
    way a person runs it, and a second entry point that does the same thing is a second thing to keep in step.
    """
    return export_economics(cohort, expected_digest=expected_digest, out_dir=out_dir)


def export_comparison(comparison: CohortComparison, *, out_dir: Path) -> Path:
    """Writes the artifact of the comparison of two arms, over the same cohort.

    Why the comparison is published apart from the cohorts: the number that matters to a reader is the difference,
    and the difference only exists when the two cohorts are the same.

    Why the hash is computed here and not in the script: the hashing of an artifact is one rule of this module, and
    a second place that computes it is a second place that can get it wrong.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / COMPARISON_NAME
    body = comparison.to_dict()
    content = json.dumps(body, indent=2, sort_keys=True)
    payload = {**body, "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest()}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
