"""The detection of a document: a path outside the fixtures is refused before the file is opened.

What they guarantee, and why: a path outside `data/fixtures/documents/` is refused with the reason, and the
file was not opened, because ADR-P009 forbids the collection of real financial documents, and a document that
was never allowed to be read is never read. The refusal happens before the file is opened and not after.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ledgerlens.documents.detect import DocumentRefused, check_path

FIXTURES = Path(__file__).resolve().parents[2] / "data" / "fixtures" / "documents"


def test_a_path_outside_the_fixtures_is_refused_before_the_file_is_opened(tmp_path, monkeypatch) -> None:
    """The refusal happens before the open: the file of a visitor is never read."""
    visitor_file = tmp_path / "receipt-of-a-visitor.txt"
    visitor_file.write_text("a document of a visitor", encoding="utf-8")
    opened = []
    real_open = Path.open

    def spy(self, *args, **kwargs):
        opened.append(self)
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", spy)

    with pytest.raises(DocumentRefused, match="outside"):
        check_path(visitor_file)

    assert visitor_file not in opened


def test_a_path_of_the_fixtures_is_accepted() -> None:
    """A fixture of the repository is read."""
    fixture = next(FIXTURES.glob("*.txt"))

    assert check_path(fixture) == fixture.resolve()


def test_a_path_that_is_not_a_file_is_refused() -> None:
    """A path that is not a file of the fixtures is refused."""
    with pytest.raises(DocumentRefused, match="not a file"):
        check_path(FIXTURES / "no-such-document.txt")
