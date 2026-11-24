"""The deduplication of the versioned memory: the same assertion from two cases is one record with two sources.

Why it exists: two cases that conclude the same fact propose the same assertion, and a memory that kept two
records of it would say the fact was observed twice when the reader asks how many records say it. The
deduplication is by the hash of the fact, and the record keeps the sources of both cases, because the
provenance of each observation is part of what the record says.

Why a different assertion is a second record: two facts that read alike are still two facts, and a
deduplication that merged them would lose one of them.
"""

from __future__ import annotations

import hashlib

from ledgerlens.memory.proposal import Proposal
from ledgerlens.memory.versioned_store import VersionedStore
from ledgerlens.schemas import MemoryRecord

__all__ = ["record_id_of", "source_key", "write_proposal"]


def record_id_of(assertion: str) -> str:
    """The id of the record of an assertion: the hash of the fact, so the same fact is the same record."""
    return f"REC-{hashlib.sha256(assertion.strip().encode('utf-8')).hexdigest()[:12]}"


def source_key(source: str) -> str:
    """The key of a source: the hash of it, so the same source is never added to a record twice."""
    return hashlib.sha256(source.strip().encode("utf-8")).hexdigest()[:12]


def write_proposal(store: VersionedStore, proposal: Proposal) -> MemoryRecord:
    """The record of a proposal: the first version of a new fact, or the next version with one more source.

    Why the second source raises the tier: a fact that two cases observed is corroborated, and the tier of the
    record says so. The provenance of both observations stays on the record, because a record that said a fact
    was observed once when it was observed twice would be believed.
    """
    record_id = record_id_of(proposal.assertion)
    latest = store.latest_of(record_id)
    if latest is None:
        return store.write(
            MemoryRecord(
                record_id=record_id,
                version=1,
                assertion=proposal.assertion,
                scope=proposal.scope,
                owner=proposal.scope,
                trust_tier="observed",
                sources=[proposal.source],
                valid_until=proposal.valid_until,
            )
        )
    if source_key(proposal.source) in {source_key(source) for source in latest.sources}:
        return latest  # the same source proposing the same fact adds nothing
    return store.write(
        latest.model_copy(
            update={
                "version": latest.version + 1,
                "trust_tier": "corroborated",
                "sources": [*latest.sources, proposal.source],
            }
        )
    )
