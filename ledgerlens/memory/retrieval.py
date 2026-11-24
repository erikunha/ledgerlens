"""The retrieval of the versioned memory: typed references with their tier of trust, and never a quarantined one.

Why it exists: the reader of a recall has to see how the fact entered the memory, so the retrieval returns
typed references with the tier of trust of each record, and a record in the state of the quarantine is never
returned, not even when it is the best match of the set.

Why the retrieval is over the latest versions: a run reads the version of its generation through the snapshot
of the run, and a retrieval of the memory of today reads the latest version of each record, with the tier and
the state that the latest version carries.
"""

from __future__ import annotations

from dataclasses import dataclass

from ledgerlens.memory.versioned_store import VersionedStore

__all__ = ["RetrievedRecord", "retrieve"]


@dataclass(frozen=True)
class RetrievedRecord:
    """A reference of the memory: the record, its version, its tier of trust and its sources.

    Why the tier travels with the reference and not with the answer: the reader of a recall must be able to see
    how the fact entered the memory, and a tier that stayed in the store would be a tier nobody sees.
    """

    record_id: str
    version: int
    assertion: str
    trust_tier: str
    sources: tuple[str, ...]


def retrieve(store: VersionedStore, query: str | None = None) -> list[RetrievedRecord]:
    """The references of the memory, and never a record in the state of the quarantine.

    Why the quarantined record is absent from every retrieval: a quarantine that only catches the queries the
    record matches best is a quarantine that the attack reads as a filter, and the plan names that risk.
    """
    records = [record for record in store.latest_records() if record.state == "active"]
    if query is not None:
        words = {word for word in query.lower().split() if word}
        records = [record for record in records if words & set(record.assertion.lower().split())]
    return [
        RetrievedRecord(
            record_id=record.record_id,
            version=record.version,
            assertion=record.assertion,
            trust_tier=record.trust_tier,
            sources=tuple(record.sources),
        )
        for record in records
    ]
