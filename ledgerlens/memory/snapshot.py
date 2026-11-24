"""The frozen snapshot of the memory of a run: a replay of an old case reads the memory of its generation.

Why it exists: a run reads the memory of its generation, and a replay of an old case that read the memory of
today would produce an answer that is not the answer of its generation. The snapshot freezes the records the
run read, and the digest of the snapshot travels with the run and with the published bundle, so the reader of
the bundle can check that the replay read the memory of the generation (ADR-073).

Why the digest is over the canonical bytes: the canonical form has no clock and no path of the machine, so two
freezes of the same records produce the same bytes on two machines, and the digest of the snapshot is a digest
of the records and not of the afternoon of one machine.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = ["MemorySnapshot", "canonical_bytes", "freeze", "read_snapshot", "snapshot_of_memory", "write_snapshot"]

# The file of the snapshot inside the bundle, declared in the manifest like every other file of the bundle.
SNAPSHOT_FILE = "memory_snapshot.json"


@dataclass(frozen=True)
class MemorySnapshot:
    """The frozen set of the records of a run, with the digest of the canonical bytes of it."""

    records: tuple[dict[str, Any], ...]
    digest: str


def canonical_bytes(records: list[dict[str, Any]] | tuple[dict[str, Any], ...]) -> bytes:
    """The canonical form of the records: sorted by the id of each record, with sorted keys and no clock.

    Why the records are sorted by the id: the order of the file of the memory is the order of the writes, and
    the snapshot is of the set of the records and not of the order they were written in.
    """
    ordered = sorted(records, key=lambda record: str(record.get("case_id") or record.get("record_id") or ""))
    return json.dumps({"records": ordered}, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def freeze(records: list[dict[str, Any]]) -> MemorySnapshot:
    """The frozen set of the records, with the digest of the canonical bytes of it."""
    return MemorySnapshot(
        records=tuple(sorted(records, key=lambda record: str(record.get("case_id") or record.get("record_id") or ""))),
        digest=hashlib.sha256(canonical_bytes(records)).hexdigest(),
    )


def snapshot_of_memory(memory_dir: Path | str) -> MemorySnapshot:
    """The snapshot of the case memory of a run: the records of the file of the memory, frozen.

    Why the snapshot is of the file of the memory and not of the index: the index is a derived thing, and the
    records are what the run read.
    """
    memory_file = Path(memory_dir) / "cases.jsonl"
    if not memory_file.is_file():
        return freeze([])
    records = [
        json.loads(line)
        for line in memory_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return freeze(records)


def write_snapshot(path: Path, snapshot: MemorySnapshot) -> None:
    """Writes the snapshot as the canonical bytes, so the digest of the file is the digest of the snapshot."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(list(snapshot.records)))


def read_snapshot(path: Path) -> MemorySnapshot:
    """The snapshot back, from the file, with the digest recomputed from the bytes of the file."""
    raw = path.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    records = data.get("records") if isinstance(data, dict) else None
    if not isinstance(records, list):
        raise ValueError(f"the snapshot of {path} is not a set of records")
    return MemorySnapshot(records=tuple(records), digest=hashlib.sha256(raw).hexdigest())
