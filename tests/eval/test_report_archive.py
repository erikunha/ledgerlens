"""The archive of the reports of the past: the versioned id, and the mark of the corpus that cannot be recovered.

What they guarantee, and why: a report of the past is preserved under a versioned id, the digest of its bytes,
and the corpus of a report that names no digest of the dataset is marked as unrecoverable, because a report
whose corpus cannot be recovered is a report whose number is a number of its time and not a number of the disk.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ledgerlens.eval.report_archive import CORPUS_UNRECOVERABLE, corpus_recoverable, preserve_report


def test_a_report_of_the_past_is_preserved_under_the_versioned_id(tmp_path) -> None:
    """The versioned id is the digest of the bytes, so the report is found by its content."""
    report = tmp_path / "report_online.md"
    report.write_text("# the report of the past\n", encoding="utf-8")
    digest = hashlib.sha256(report.read_bytes()).hexdigest()

    preserved = preserve_report(report, tmp_path / "archive", recoverable=True)

    assert preserved.name == f"report_online.{digest[:12]}.md"
    assert preserved.read_bytes() == report.read_bytes()
    assert not (tmp_path / "archive" / f"{preserved.name}.corpus.md").exists()


def test_a_report_whose_corpus_is_unrecoverable_is_marked(tmp_path) -> None:
    """The mark says that the number of the report is a number of its time."""
    report = tmp_path / "report_online.md"
    report.write_text("# the report of the past\n", encoding="utf-8")

    preserved = preserve_report(report, tmp_path / "archive", recoverable=False)
    mark = tmp_path / "archive" / f"{preserved.name}.corpus.md"

    assert mark.is_file()
    assert CORPUS_UNRECOVERABLE in mark.read_text(encoding="utf-8")


def test_a_report_that_names_no_digest_of_the_dataset_has_an_unrecoverable_corpus(tmp_path) -> None:
    """The report of the past names no digest of the dataset, and the corpus cannot be recovered."""
    assert not corpus_recoverable({"cases": 30}, tmp_path)


def test_a_report_whose_digest_matches_the_disk_has_a_recoverable_corpus(tmp_path) -> None:
    """The digest of the report is the digest of the dataset on the disk, and the corpus is recoverable."""
    dataset = tmp_path / "data" / "eval" / "eval_cases.jsonl"
    dataset.parent.mkdir(parents=True)
    dataset.write_text('{"case": 1}\n', encoding="utf-8")
    digest = hashlib.sha256(dataset.read_bytes()).hexdigest()

    assert corpus_recoverable({"dataset_path": "data/eval/eval_cases.jsonl", "dataset_sha256": digest}, tmp_path)
    assert not corpus_recoverable({"dataset_path": "data/eval/eval_cases.jsonl", "dataset_sha256": "0" * 64}, tmp_path)


def test_the_report_of_the_past_of_the_repository_is_preserved_with_the_mark() -> None:
    """The report of the past of the repository names no digest of the dataset, and the mark says so."""
    root = Path(__file__).resolve().parents[2]
    report = json.loads((root / "data" / "eval" / "report_online.json").read_text(encoding="utf-8"))

    assert not corpus_recoverable(report, root)
