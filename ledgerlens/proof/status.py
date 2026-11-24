"""The status of the artifact: verified only when the evidence is all there, and draft with the reason.

Why no person promotes an artifact by hand: the status is decided by the presence of the evidence and by the
offline re-verification, and nothing else. The status is `verified` only when the digest of the dataset is
there, the commit is there, the digest of every file matches the disk and the offline re-verification passes.
A missing evidence makes a `draft` that names what is missing and carries no verified badge, because a badge
that a missing digest does not remove means nothing.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from ledgerlens.proof.provenance import Provenance

__all__ = ["DRAFT", "VERIFIED", "Status", "status_of"]

VERIFIED = "verified"
DRAFT = "draft"


@dataclass(frozen=True)
class Status:
    """The status of the artifact: verified, or draft with the names of the evidence that is missing."""

    value: str
    missing: tuple[str, ...] = ()

    @property
    def is_verified(self) -> bool:
        """The badge of the page exists only for the status verified."""
        return self.value == VERIFIED


def status_of(provenance: Provenance, *, reverified: bool, root: Path) -> Status:
    """The status of the artifact over its provenance and the offline re-verification.

    The four conditions of the verified status, in the order they are checked: the digest of the dataset, the
    commit, the digest of every file of the bundle against the disk, and the offline re-verification. The
    draft names every condition that is missing, so a reader of the artifact sees what is missing and not
    only that something is.
    """
    missing: list[str] = []
    if not provenance.dataset_digest:
        missing.append("the digest of the dataset")
    if not provenance.git_commit:
        missing.append("the commit")
    for name, digest in provenance.file_digests.items():
        path = root / provenance.bundle / name
        if not path.is_file():
            missing.append(f"the file {name} of the bundle")
            continue
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            missing.append(f"the digest of {name} does not match the disk")
    if not reverified:
        missing.append("the offline re-verification")
    if missing:
        return Status(DRAFT, tuple(missing))
    return Status(VERIFIED)
