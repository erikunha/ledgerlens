"""The archive of an experiment: the digests of the dataset, the commit and the report of the comparison.

Why an experiment that cannot be reproduced is an anecdote: the archive names the dataset by its path and by
the digest of its bytes, the commit of the code and the report of the comparison, so a reader can rebuild the
experiment and check it. An archive whose digest does not match the file of the dataset is an archive that
asks the reader to trust the name and not the bytes, and the check refuses it with the reason.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

__all__ = ["ExperimentArchive", "check_archive"]


@dataclass(frozen=True)
class ExperimentArchive:
    """The archive of one experiment: the dataset, the commit and the report, each named and checkable."""

    experiment_id: str
    dataset_path: str
    dataset_digest: str
    commit: str
    report_path: str
    created_at: str


def check_archive(archive: ExperimentArchive, root: Path) -> list[str]:
    """The problems of the archive, one line each. Empty when the archive can be reproduced.

    The digest of the dataset is checked against the file on the disk, because an experiment whose dataset
    moved is an experiment that cannot be reproduced, and the check refuses it with the reason.
    """
    problems: list[str] = []
    dataset = root / archive.dataset_path
    if not dataset.is_file():
        problems.append(
            f"the archive {archive.experiment_id} names the dataset {archive.dataset_path}, "
            "which is not on the disk"
        )
    else:
        digest = hashlib.sha256(dataset.read_bytes()).hexdigest()
        if digest != archive.dataset_digest:
            problems.append(
                f"the archive {archive.experiment_id} names the digest {archive.dataset_digest} "
                f"and the dataset on the disk has the digest {digest}"
            )
    if not (root / archive.report_path).is_file():
        problems.append(
            f"the archive {archive.experiment_id} names the report {archive.report_path}, "
            "which is not on the disk"
        )
    return problems
