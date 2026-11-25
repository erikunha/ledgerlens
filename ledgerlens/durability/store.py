"""The store of the journal of a run: the journal lives in the folder of the session, and the numbers grow by one.

Why the journal lives in the folder of the session that owns the run: the journal of a run is evidence of the
session, like the branch of the visitor, and the folder of the session dies with the session, so the journal
never outlives the session that owns it.

Why the numbers grow by one under a lock: the order of a run is readable after the fact, and two writers that
append to the same journal must never get the same number and never leave a gap, or the order of the run would
be a guess.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from ledgerlens.durability.journal import JournalEntry

__all__ = ["JOURNAL_FILE", "JournalStore", "JournalWriteFailed"]


class JournalWriteFailed(Exception):
    """The write of the journal failed, and the run that cannot write its journal stops with the reason."""


# The file of the journal, inside the folder of the session that owns the run.
JOURNAL_FILE = "run_journal.jsonl"


class JournalStore:
    """The journal of a run, in the folder of the session that owns the run."""

    def __init__(self, folder: Path | str) -> None:
        self.folder = Path(folder)
        self.file = self.folder / JOURNAL_FILE
        self._lock = threading.Lock()

    def append(self, entry: JournalEntry) -> JournalEntry:
        """Appends an entry to the journal, with the next number, under the lock.

        Why the number is assigned under the lock: two writers that append at the same time must never get the
        same number and never leave a gap, and the lock is what makes the assignment and the write one act.

        Why a failure of the write is a `JournalWriteFailed` and not a silent skip: a run that continues
        without a journal is a run that cannot be restarted, and the run stops with the reason.
        """
        with self._lock:
            number = self._next_number()
            numbered = JournalEntry(
                number=number,
                kind=entry.kind,
                step_id=entry.step_id,
                attempt=entry.attempt,
                inputs_hash=entry.inputs_hash,
                snapshot=entry.snapshot,
                idempotency_key=entry.idempotency_key,
                output_ref=entry.output_ref,
                status=entry.status,
                spend_usd=entry.spend_usd,
            )
            try:
                self.folder.mkdir(parents=True, exist_ok=True)
                with self.file.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(numbered.to_dict(), ensure_ascii=False) + "\n")
            except OSError as exc:
                raise JournalWriteFailed(
                    f"the journal of the run could not be written: {exc}, and a run that continues without a "
                    "journal is a run that cannot be restarted"
                ) from exc
            return numbered

    def entries(self) -> list[JournalEntry]:
        """Every entry of the journal, in the order of the numbers."""
        if not self.file.is_file():
            return []
        entries = [
            JournalEntry.from_dict(json.loads(line))
            for line in self.file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        return sorted(entries, key=lambda entry: entry.number)

    def _next_number(self) -> int:
        """The next number of the journal: one more than the greatest number in it, or one."""
        entries = self.entries()
        return max((entry.number for entry in entries), default=0) + 1
