"""The versioned store: the versions of the records of a session, where a new version never overwrites an old one.

Why it exists: the case memory of `ledgerlens/memory/long_term.py` holds what a verified case concluded, but it
has no version: a record that changes under a run that points at it is a record that run can no longer check.
The versioned store keeps every version of a record, so the run of last week still reads the version it read.

Why the store lives in the folder of the memory of the session: the memory of a session lives in the folder of
that session (ADR-030), and the new records live in the same place, so the expiry of the session takes them
with it and no record outlives the session that owns it.

Why the store is append only: a version that could be rewritten is a version that a reader cannot trust, and
the store is the evidence of what the memory held and when.
"""

from __future__ import annotations

from pathlib import Path

from ledgerlens.schemas import MemoryRecord

__all__ = ["VersionedStore"]

# The file of the versions, inside the folder of the memory of the session. One line per version, append only.
RECORDS_FILE = "versioned_records.jsonl"


class VersionedStore:
    """The versions of the records of one session, in the folder of the memory of that session."""

    def __init__(self, memory_dir: Path | str) -> None:
        self.memory_dir = Path(memory_dir)
        self.records_file = self.memory_dir / RECORDS_FILE

    def write(self, record: MemoryRecord) -> MemoryRecord:
        """Appends a version of a record. A version that already exists is refused, never overwritten."""
        if self.version_of(record.record_id, record.version) is not None:
            raise ValueError(
                f"the version {record.version} of the record {record.record_id} already exists: "
                "a new version never overwrites an old one"
            )
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        with self.records_file.open("a", encoding="utf-8") as handle:
            handle.write(record.model_dump_json() + "\n")
        return record

    def records(self) -> list[MemoryRecord]:
        """Every version of every record of the session, in the order they were written."""
        if not self.records_file.is_file():
            return []
        return [
            MemoryRecord.model_validate_json(line)
            for line in self.records_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def version_of(self, record_id: str, version: int) -> MemoryRecord | None:
        """The version of a record, and None when the store has no such version."""
        for record in self.records():
            if record.record_id == record_id and record.version == version:
                return record
        return None

    def latest_of(self, record_id: str) -> MemoryRecord | None:
        """The latest version of a record, and None when the store has no such record."""
        latest: MemoryRecord | None = None
        for record in self.records():
            if record.record_id == record_id and (latest is None or record.version > latest.version):
                latest = record
        return latest

    def latest_records(self) -> list[MemoryRecord]:
        """The latest version of every record of the session, in the order of the first version of each."""
        latest: dict[str, MemoryRecord] = {}
        for record in self.records():
            seen = latest.get(record.record_id)
            if seen is None or record.version > seen.version:
                latest[record.record_id] = record
        return list(latest.values())
