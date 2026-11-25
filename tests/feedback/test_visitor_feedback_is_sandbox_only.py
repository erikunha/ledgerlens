"""The feedback of a visitor stays in the session of the visitor, and the shared set never sees it.

What they guarantee, and why: a comment sent through the sandbox of a visitor writes nothing under
`data/eval/feedback/`, and the registry refuses a record whose source is a session of a visitor, because
ADR-P009 is a safety invariant and not a preference, and a visitor that could write into the shared set could
poison the records the maintainers review.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from pathlib import Path

from ledgerlens.feedback.registry import RegistryEntry, check_registry
from ledgerlens.sandbox.feedback import record_visitor_feedback

ROOT = Path(__file__).resolve().parents[2]
SHARED_SET = ROOT / "data" / "eval" / "feedback"


def _shared_set_files() -> set[str]:
    """The files of the shared set, for the check that a comment of a visitor does not touch them."""
    return {str(path) for path in SHARED_SET.rglob("*") if path.is_file()}


def test_a_comment_through_the_sandbox_writes_nothing_under_the_shared_set(tmp_path) -> None:
    """The comment lands in the runtime of the sandbox, keyed by the session of the visitor."""
    before = _shared_set_files()
    path = record_visitor_feedback("sess-abc123", "the deadline of s02 looks wrong", root=tmp_path)

    assert path.is_file()
    assert str(path).startswith(str(tmp_path))
    assert _shared_set_files() == before


def test_the_registry_refuses_a_record_whose_source_is_a_session_of_a_visitor(tmp_path) -> None:
    """The door of the shared set is the registry, and the registry refuses the visitor."""
    entry = RegistryEntry(
        record_id="FR-VISITOR",
        path="data/eval/feedback/records/FR-VISITOR.json",
        sha256="0" * 64,
        permission="training",
        tier="gold",
        source="visitor:sess-abc123",
    )

    problems = check_registry((entry,), tmp_path)

    assert any("visitor" in problem for problem in problems)
