"""The deletion of the memory of a session: it takes the records of its owner and nothing else.

What they guarantee, and why: (a) a deletion of the memory of one session takes every record of that session,
so no record of it is retrievable after the deletion; (b) every record of another session is intact, because a
deletion that crosses the owner is a deletion of the memory of another visitor; (c) the folder of the session
is gone, with the expiry of `ledgerlens/sandbox/ttl.py` that takes the session with it.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from ledgerlens.memory.dedup import write_proposal
from ledgerlens.memory.proposal import propose
from ledgerlens.memory.retrieval import retrieve
from ledgerlens.memory.versioned_store import VersionedStore
from ledgerlens.sandbox.memory import purge_session_memory, session_memory_dir


def _store_of(tmp_path, session: str, assertion: str) -> VersionedStore:
    """A store of a session with one record, in the folder of the session."""
    store = VersionedStore(session_memory_dir(session, tmp_path))
    proposal = propose(scope=session, assertion=assertion, source="CASE-0001", source_verdict="supported")
    write_proposal(store, proposal)
    return store


def test_the_deletion_takes_the_records_of_its_owner_and_nothing_else(tmp_path) -> None:
    """The memory of one visitor dies with the session, and the memory of another one stays."""
    first = _store_of(tmp_path, "session-a", "the markup of M-17 is inside the limit")
    second = _store_of(tmp_path, "session-b", "the payout of ST-0044 was late")

    removed = purge_session_memory("session-a", tmp_path)

    assert removed is True
    assert retrieve(first) == []
    assert not (session_memory_dir("session-a", tmp_path)).exists()
    assert [record.assertion for record in retrieve(second)] == ["the payout of ST-0044 was late"]


def test_the_deletion_of_a_session_that_wrote_nothing_is_not_an_error(tmp_path) -> None:
    """A session that never wrote anything has no folder, and that is not an error."""
    assert purge_session_memory("session-that-never-wrote", tmp_path) is False
