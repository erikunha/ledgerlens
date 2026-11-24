"""The isolation of the versioned memory: no record of one session in the retrieval of another session.

What they guarantee, and why: (a) no record of one session shows up in the retrieval of another session,
because the memory of a session lives in the folder of that session and a record that crosses the folder is a
leak of one visitor into the answer of another (FR-027); (b) the folder of the memory of a branch is the folder
of the session that owns the branch, through `ledgerlens/sandbox/memory.py`, so the rule of the sandbox and the
rule of the memory cannot drift.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from ledgerlens.memory.versioned_store import VersionedStore
from ledgerlens.sandbox.memory import session_memory_dir
from ledgerlens.schemas import MemoryRecord


def _record(record_id: str, owner: str, assertion: str) -> MemoryRecord:
    """A record of the versioned memory, owned by a session."""
    return MemoryRecord(
        record_id=record_id,
        version=1,
        assertion=assertion,
        scope=owner,
        owner=owner,
        sources=["CASE-0001"],
    )


def test_no_record_of_one_session_is_in_the_retrieval_of_another_session(tmp_path) -> None:
    """The memory of one visitor never shows up in the answer of another one."""
    first = VersionedStore(session_memory_dir("session-a", tmp_path))
    second = VersionedStore(session_memory_dir("session-b", tmp_path))
    first.write(_record("REC-0123456789ab", "session-a", "the markup of M-17 is inside the limit"))
    second.write(_record("REC-abcdef012345", "session-b", "the payout of ST-0044 was late"))

    retrieved_a = [record.assertion for record in first.latest_records()]
    retrieved_b = [record.assertion for record in second.latest_records()]

    assert retrieved_a == ["the markup of M-17 is inside the limit"]
    assert retrieved_b == ["the payout of ST-0044 was late"]
    assert not set(retrieved_a) & set(retrieved_b)


def test_the_folder_of_the_memory_of_a_branch_is_the_folder_of_its_session(tmp_path) -> None:
    """The rule of the sandbox and the rule of the memory are the same rule."""
    folder = session_memory_dir("session-a", tmp_path)

    store = VersionedStore(folder)
    store.write(_record("REC-0123456789ab", "session-a", "the markup of M-17 is inside the limit"))

    assert folder.name == "session-a"
    assert folder.parent.name == "sessions"
    assert (folder / "versioned_records.jsonl").is_file()
