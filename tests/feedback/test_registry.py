"""The registry of the records: the digest, the permission and the tier of every entry, checked on the disk.

What they guarantee, and why: every entry of the registry carries the digest, the permission and the tier, an
entry whose digest does not match the file it names is refused, and a record whose source is a session of a
visitor is refused, because a record without a digest is a record that cannot be found and the feedback of a
visitor stays in the session of the visitor.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ledgerlens.feedback.registry import RegistryEntry, check_registry, load_registry


def _write_record(root: Path, record_id: str = "FR-0001") -> str:
    """A record file on the disk of the test, and the digest of its bytes."""
    path = root / "data" / "eval" / "feedback" / "records" / f"{record_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"record_id": record_id}), encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _entry(root: Path, **overrides) -> RegistryEntry:
    fields = {
        "record_id": "FR-0001",
        "path": "data/eval/feedback/records/FR-0001.json",
        "sha256": _write_record(root),
        "permission": "training",
        "tier": "gold",
        "source": "catalog",
    }
    fields.update(overrides)
    return RegistryEntry(**fields)


def test_every_entry_of_the_registry_carries_the_digest_the_permission_and_the_tier(tmp_path) -> None:
    """The three fields are the door of the shared set, and the check reads them on the disk."""
    entry = _entry(tmp_path)

    assert check_registry((entry,), tmp_path) == []


def test_an_entry_whose_digest_does_not_match_the_file_is_refused(tmp_path) -> None:
    """The digest is what lets the check find the record, and a file that moved is a file that moved."""
    entry = _entry(tmp_path, sha256="0" * 64)

    problems = check_registry((entry,), tmp_path)

    assert any("digest" in problem and "FR-0001" in problem for problem in problems)


def test_an_entry_without_a_digest_is_a_record_that_cannot_be_found(tmp_path) -> None:
    """A record without a digest is a record that cannot be found, and the check says so."""
    entry = _entry(tmp_path, sha256="")

    problems = check_registry((entry,), tmp_path)

    assert any("cannot be found" in problem for problem in problems)


def test_a_record_whose_source_is_a_session_of_a_visitor_is_refused(tmp_path) -> None:
    """The feedback of a visitor stays in the session of the visitor, and the registry says so."""
    entry = _entry(tmp_path, source="visitor:abc123")

    problems = check_registry((entry,), tmp_path)

    assert any("visitor" in problem for problem in problems)


def test_the_registry_on_the_disk_of_the_repository_is_clean() -> None:
    """The registry of the repository passes its own check, and the gate runs the same check."""
    from ledgerlens.feedback.registry import REGISTRY_PATH

    root = Path(__file__).resolve().parents[2]
    entries = load_registry(root / REGISTRY_PATH)

    assert entries
    assert check_registry(entries, root) == []
