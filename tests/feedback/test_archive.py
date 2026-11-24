"""The archive of an experiment: it can be read again, and it refuses when the set moved.

What they guarantee, and why: the archive carries the digests of the dataset, the commit and the report of the
comparison, and the check refuses with a reason when the digest of the dataset does not match the file,
because an experiment that cannot be reproduced is an anecdote.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from ledgerlens.feedback.archive import ExperimentArchive, check_archive


def _archive(root: Path, **overrides) -> ExperimentArchive:
    dataset = root / "data" / "eval" / "feedback" / "training-set.json"
    dataset.parent.mkdir(parents=True, exist_ok=True)
    dataset.write_text('{"records": []}', encoding="utf-8")
    report = root / "data" / "eval" / "feedback" / "comparison.md"
    report.write_text("the comparison\n", encoding="utf-8")
    fields = {
        "experiment_id": "EXP-0001",
        "dataset_path": "data/eval/feedback/training-set.json",
        "dataset_digest": hashlib.sha256(dataset.read_bytes()).hexdigest(),
        "commit": "0ff2691",
        "report_path": "data/eval/feedback/comparison.md",
        "created_at": "2026-11-24T00:00:00+00:00",
    }
    fields.update(overrides)
    return ExperimentArchive(**fields)


def test_the_archive_carries_the_digests_the_commit_and_the_report(tmp_path) -> None:
    """The four fields of the archive, and the check passes when the disk matches them."""
    archive = _archive(tmp_path)

    assert archive.dataset_digest
    assert archive.commit
    assert check_archive(archive, tmp_path) == []


def test_the_check_refuses_when_the_digest_of_the_dataset_does_not_match_the_file(tmp_path) -> None:
    """An archive whose dataset moved is an archive that cannot be reproduced, and the check says so."""
    archive = _archive(tmp_path, dataset_digest="0" * 64)

    problems = check_archive(archive, tmp_path)

    assert any("digest" in problem and "EXP-0001" in problem for problem in problems)


def test_the_check_refuses_when_the_dataset_is_not_on_the_disk(tmp_path) -> None:
    """An archive that names a dataset that is not there is an archive that cannot be read again."""
    archive = _archive(tmp_path, dataset_path="data/eval/feedback/elsewhere.json")

    problems = check_archive(archive, tmp_path)

    assert any("not on the disk" in problem for problem in problems)
