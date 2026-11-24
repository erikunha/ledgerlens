"""The fields of a record of the versioned memory: the version, the tier, the owner and the approval state.

What they guarantee, and why: (a) every record carries a version, a trust tier, an owner and an approval state,
because a record that says none of them is a record a reader cannot trust (the definition of done of the
milestone); (b) the version of a run of an old case still exists after a new version is written, because a run
of last week points at the version it read and a new version never overwrites the old one.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import pytest

from ledgerlens.memory.versioned_store import VersionedStore
from ledgerlens.schemas import MemoryRecord


def _record(**overrides) -> MemoryRecord:
    """A record of the versioned memory, with the fields a record carries."""
    fields = {
        "record_id": "REC-0123456789ab",
        "version": 1,
        "assertion": "the markup of M-17 is inside the limit",
        "scope": "session-a",
        "owner": "session-a",
        "trust_tier": "observed",
        "approval_state": "none",
        "sources": ["CASE-0001"],
    }
    fields.update(overrides)
    return MemoryRecord(**fields)


def test_every_record_carries_the_version_the_tier_the_owner_and_the_approval_state() -> None:
    """A record that says none of them is a record a reader cannot trust."""
    record = _record()

    assert record.version == 1
    assert record.trust_tier == "observed"
    assert record.owner == "session-a"
    assert record.approval_state == "none"
    assert record.state == "active"


def test_the_tier_and_the_state_of_a_record_are_the_ones_of_the_vocabulary() -> None:
    """A tier or a state outside the vocabulary is refused by the schema."""
    with pytest.raises(ValueError):
        _record(trust_tier="absolute")
    with pytest.raises(ValueError):
        _record(state="deleted")


def test_the_version_of_a_run_of_an_old_case_still_exists(tmp_path) -> None:
    """A new version never overwrites the old one: the run of last week still points at it."""
    store = VersionedStore(tmp_path / "session-a")
    store.write(_record(version=1, assertion="the first reading"))
    store.write(_record(version=2, assertion="the second reading", trust_tier="corroborated"))

    old = store.version_of("REC-0123456789ab", 1)
    assert old is not None
    assert old.assertion == "the first reading"
    assert store.latest_of("REC-0123456789ab").version == 2
