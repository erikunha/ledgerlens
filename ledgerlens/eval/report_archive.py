"""The archive of the reports of the past: every report preserved under a versioned id, with its corpus named.

Why the reports of the past are preserved under versioned ids: a report that is recomputed over a corpus that
moved is a report that says something about a corpus that is not on the disk anymore, and the report of the
past has to stay readable as what it was. The versioned id of a preserved report is the digest of its bytes,
so the preserved report is found by its content and not by the name someone gave it.

Why the corpus of a report is marked as unrecoverable when it cannot be recovered: a report that names no
digest of the dataset it was measured over is a report whose corpus cannot be recovered, because the dataset
of today is not the dataset of the report and nothing says which one it was. The mark says so, and a reader
of the report knows that the number is a number of its time and not a number of the disk.
"""

from __future__ import annotations

import hashlib
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any

__all__ = ["corpus_recoverable", "preserve_report"]

# The mark of a report whose corpus cannot be recovered, written next to the preserved report.
CORPUS_UNRECOVERABLE = "the corpus of this report is unrecoverable"


def corpus_recoverable(report: Mapping[str, Any], root: Path) -> bool:
    """Whether the corpus of the report can be recovered: the report pins the digest of the dataset, and it matches.

    A report that names no digest of the dataset is a report whose corpus cannot be recovered, and a report
    whose digest does not match the dataset on the disk is a report over a corpus that moved.
    """
    digest = report.get("dataset_sha256")
    path = report.get("dataset_path")
    if not digest or not path:
        return False
    dataset = root / str(path)
    if not dataset.is_file():
        return False
    return hashlib.sha256(dataset.read_bytes()).hexdigest() == digest


def preserve_report(report_path: Path, archive_dir: Path, *, recoverable: bool) -> Path:
    """The report of the past, preserved under its versioned id, with the mark of the corpus when it is lost.

    The versioned id is the digest of the bytes of the report, so the preserved report is found by its
    content. When the corpus of the report cannot be recovered, the mark is written next to it, because a
    reader of the report has to know that the number is a number of its time.
    """
    digest = hashlib.sha256(report_path.read_bytes()).hexdigest()
    archive_dir.mkdir(parents=True, exist_ok=True)
    target = archive_dir / f"{report_path.stem}.{digest[:12]}{report_path.suffix}"
    if not target.is_file():
        shutil.copyfile(report_path, target)
    if not recoverable:
        mark = target.with_name(f"{target.name}.corpus.md")
        mark.write_text(f"{CORPUS_UNRECOVERABLE}: {target.name}\n", encoding="utf-8")
    return target
