"""The registry of the feedback records: every record with its digest, its permission and its tier.

Why a record without a digest is a record that cannot be found: the registry is the door of the shared set,
and the digest of the file of the record is what lets the check find the record on the disk and refuse the
entry whose file moved. A record whose source is a session of a visitor never enters the registry, because the
feedback of a visitor stays in the session of the visitor under ADR-P009, and the shared set is reviewed by
the maintainers of the repository.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ledgerlens.feedback.record import PERMISSIONS
from ledgerlens.feedback.tiers import TIERS

__all__ = ["REGISTRY_PATH", "RegistryEntry", "check_registry", "load_registry"]

REGISTRY_PATH = Path("data/eval/feedback/registry.json")


@dataclass(frozen=True)
class RegistryEntry:
    """One entry of the registry: the record, the digest of its file, its permission, its tier and its source."""

    record_id: str
    path: str
    sha256: str
    permission: str
    tier: str
    source: str


def load_registry(path: Path) -> tuple[RegistryEntry, ...]:
    """The entries of the registry, as they are written."""
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return tuple(
        RegistryEntry(
            record_id=str(entry.get("record_id", "")),
            path=str(entry.get("path", "")),
            sha256=str(entry.get("sha256", "")),
            permission=str(entry.get("permission", "")),
            tier=str(entry.get("tier", "")),
            source=str(entry.get("source", "")),
        )
        for entry in data.get("records", [])
    )


def check_registry(entries: tuple[RegistryEntry, ...], root: Path) -> list[str]:
    """The problems of the registry, one line each, read from the disk. Empty when the registry is clean.

    The check refuses an entry whose digest does not match the file it names, an entry without a digest, an
    entry whose tier or permission is outside the vocabularies of the loop, and an entry whose source is a
    session of a visitor.
    """
    problems: list[str] = []
    for entry in entries:
        if not entry.sha256:
            problems.append(f"the entry {entry.record_id} has no digest, and a record without a digest cannot be found")
            continue
        if entry.permission not in PERMISSIONS:
            problems.append(f"the entry {entry.record_id} has the permission {entry.permission!r}")
        if entry.tier not in TIERS:
            problems.append(f"the entry {entry.record_id} has the tier {entry.tier!r}")
        if entry.source.startswith("visitor:"):
            problems.append(
                f"the entry {entry.record_id} has the source {entry.source!r}, "
                "and the feedback of a visitor stays in the session of the visitor"
            )
        record_path = root / entry.path
        if not record_path.is_file():
            problems.append(f"the entry {entry.record_id} names the file {entry.path}, which is not on the disk")
            continue
        digest = hashlib.sha256(record_path.read_bytes()).hexdigest()
        if digest != entry.sha256:
            problems.append(
                f"the entry {entry.record_id} names the digest {entry.sha256} "
                f"and the file on the disk has the digest {digest}"
            )
    return problems
