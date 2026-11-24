"""The detection of a document: the path is checked before the file is opened, and never after.

Why the refusal happens before the file is opened: ADR-P009 forbids the collection of real financial
documents, and a document that was never allowed to be read is never read. A check that happened after the
open would be a check of a document that was already read, and the pipeline reads only the fixtures of the
repository.

Why the check is of the path and not of the content: the path says where the document lives, and a path
outside `data/fixtures/documents/` is a path the pipeline refuses, whatever the content of the file is.
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["FIXTURES_DIR", "DocumentRefused", "check_path"]

# The folder of the fixtures of the documents: the only folder the pipeline reads.
FIXTURES_DIR = Path(__file__).resolve().parents[2] / "data" / "fixtures" / "documents"


class DocumentRefused(Exception):
    """The document is refused, and the message says why."""


def check_path(path: Path | str) -> Path:
    """The path of a document the pipeline may read, and the refusal of every other path.

    Why the refusal is before the open: a document that was never allowed to be read is never read, and the
    check of the path is the only check that happens before the file is opened.
    """
    resolved = Path(path).resolve()
    root = FIXTURES_DIR.resolve()
    if resolved != root and root not in resolved.parents:
        raise DocumentRefused(
            f"the path {path} is outside {root}, and the pipeline reads only the fixtures of the repository: "
            "the refusal happens before the file is opened"
        )
    if not resolved.is_file():
        raise DocumentRefused(f"the path {path} is not a file of the fixtures of the repository")
    return resolved
