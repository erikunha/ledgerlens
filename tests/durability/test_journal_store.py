"""The store of the journal: the journal lives in the folder of the session, and the numbers grow without a gap.

What they guarantee, and why: (a) the journal of a run lives in the folder of the session that owns the run,
beside the folder of the branch, because the journal is evidence of the session and the folder of the session
dies with the session; (b) the numbers of the journal grow by one under a lock, and two writers never get the
same number and never leave a gap, because the order of a run is readable after the fact and a gap would be a
step that nobody can place.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import threading

from ledgerlens.durability.journal import JournalEntry
from ledgerlens.durability.store import JOURNAL_FILE, JournalStore


def _entry(step_id: str) -> JournalEntry:
    """An entry of the journal, with the number left for the store to assign."""
    return JournalEntry(
        number=0,
        kind="intent",
        step_id=step_id,
        attempt=1,
        inputs_hash="a" * 64,
        snapshot="snapshot-of-the-run",
        idempotency_key=f"key-{step_id}",
    )


def test_the_journal_lives_in_the_folder_of_the_session(tmp_path) -> None:
    """The journal is evidence of the session, and it lives in the folder of the session."""
    store = JournalStore(tmp_path / "session-a")
    store.append(_entry("read"))

    assert (tmp_path / "session-a" / JOURNAL_FILE).is_file()


def test_two_writers_grow_the_numbers_without_a_gap(tmp_path) -> None:
    """Two writers that append at the same time never get the same number and never leave a gap."""
    store = JournalStore(tmp_path)
    writers = 4
    per_writer = 25

    def write(writer: int) -> None:
        for index in range(per_writer):
            store.append(_entry(f"step-{writer}-{index}"))

    threads = [threading.Thread(target=write, args=(writer,)) for writer in range(writers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    numbers = [entry.number for entry in store.entries()]
    assert sorted(numbers) == list(range(1, writers * per_writer + 1))
    assert len(set(numbers)) == len(numbers)
