"""The versioned store: two versions of one record coexist, and the version of an old run is readable.

What they guarantee, and why: (a) two versions of one record coexist, because a new version never overwrites
an old one (the definition of done of the milestone); (b) the version of a run of an old case is readable, so
the run of last week still reads the version it read; (c) a version that already exists is refused, because a
version that could be rewritten is a version a reader cannot trust.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import pytest

from ledgerlens.memory.versioned_store import VersionedStore
from ledgerlens.schemas import MemoryRecord


def _record(version: int, assertion: str, **overrides) -> MemoryRecord:
    """A version of a record of the versioned memory."""
    fields = {
        "record_id": "REC-0123456789ab",
        "version": version,
        "assertion": assertion,
        "scope": "session-a",
        "owner": "session-a",
        "sources": ["CASE-0001"],
    }
    fields.update(overrides)
    return MemoryRecord(**fields)


def test_two_versions_of_one_record_coexist(tmp_path) -> None:
    """A new version never overwrites the old one: the two of them are in the store."""
    store = VersionedStore(tmp_path)
    store.write(_record(1, "the first reading"))
    store.write(_record(2, "the second reading", trust_tier="corroborated"))

    versions = store.records()
    assert [record.version for record in versions] == [1, 2]
    assert versions[0].assertion == "the first reading"
    assert versions[1].trust_tier == "corroborated"


def test_the_version_of_a_run_of_an_old_case_is_readable(tmp_path) -> None:
    """The run of last week still reads the version it read."""
    store = VersionedStore(tmp_path)
    store.write(_record(1, "the first reading"))
    store.write(_record(2, "the second reading"))

    old = store.version_of("REC-0123456789ab", 1)
    assert old is not None
    assert old.assertion == "the first reading"
    assert store.latest_of("REC-0123456789ab").assertion == "the second reading"


def test_a_version_that_already_exists_is_refused(tmp_path) -> None:
    """A version that could be rewritten is a version a reader cannot trust."""
    store = VersionedStore(tmp_path)
    store.write(_record(1, "the first reading"))

    with pytest.raises(ValueError, match="never overwrites"):
        store.write(_record(1, "the first reading, rewritten"))

    assert store.version_of("REC-0123456789ab", 1).assertion == "the first reading"


def test_the_store_of_a_session_holds_only_the_records_of_that_session(tmp_path) -> None:
    """The store lives in the folder of the session, so two sessions have two stores."""
    first = VersionedStore(tmp_path / "session-a")
    second = VersionedStore(tmp_path / "session-b")
    first.write(_record(1, "the record of the first session"))

    assert [record.assertion for record in first.records()] == ["the record of the first session"]
    assert second.records() == []
