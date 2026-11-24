"""The change of the prompt parser: a change of the extraction, and never a rewrite of the reports of the past.

What they guarantee, and why: a change of the prompt parser with the model output unchanged is reported as a
change of the extraction, and the reports of the past are never rewritten, because the parser turns the output
of the model into the result, and a parser that moved with the output unchanged moves the numbers without the
model moving.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from ledgerlens.eval.case_reports import extraction_change, extraction_digest


def _report(extraction: str, answers: list[str]) -> dict:
    return {
        "extraction": extraction,
        "per_case": [{"case": f"EC-{index:02d}", "answer": answer} for index, answer in enumerate(answers)],
    }


def test_a_parser_that_moved_with_the_output_unchanged_is_a_change_of_the_extraction() -> None:
    """The report names the change of the extraction, with the two versions of the parser."""
    old = _report("digest-a", ["the same answer", "another answer"])
    new = _report("digest-b", ["the same answer", "another answer"])

    change = extraction_change(old, new)

    assert change is not None
    assert "the extraction changed" in change
    assert "digest-a" in change
    assert "digest-b" in change


def test_a_parser_that_moved_with_the_output_changed_is_not_an_extraction_change() -> None:
    """When the output of the model moved too, the change is not of the extraction alone."""
    old = _report("digest-a", ["the same answer"])
    new = _report("digest-b", ["a different answer"])

    assert extraction_change(old, new) is None


def test_a_parser_that_did_not_move_is_not_a_change_of_the_extraction() -> None:
    """The same parser with the same output is not a change of anything."""
    old = _report("digest-a", ["the same answer"])
    new = _report("digest-a", ["the same answer"])

    assert extraction_change(old, new) is None


def test_the_digest_of_the_parser_of_the_repository_is_the_version_of_the_extraction() -> None:
    """The version of the extraction is the digest of the bytes of the parser of the repository."""
    from pathlib import Path

    digest = extraction_digest(Path("ledgerlens/chains/parsers.py"))

    assert len(digest) == 64
    assert digest == extraction_digest(Path("ledgerlens/chains/parsers.py"))
