"""The deduplication of the versioned memory: the same assertion from two cases is one record with two sources.

What they guarantee, and why: (a) the same assertion proposed by two cases is one record with two sources,
because a memory that kept two records of one fact would say the fact was observed twice when the reader asks
how many records say it; (b) a different assertion is a second record, because two facts that read alike are
still two facts; (c) the same source proposing the same fact adds nothing, because the provenance of the record
is the set of its sources and not the count of its proposals.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from ledgerlens.memory.dedup import write_proposal
from ledgerlens.memory.proposal import propose
from ledgerlens.memory.versioned_store import VersionedStore


def _proposal(assertion: str, source: str) -> object:
    """A proposal of an assertion with a verified source."""
    return propose(scope="session-a", assertion=assertion, source=source, source_verdict="supported")


def test_the_same_assertion_from_two_cases_is_one_record_with_two_sources(tmp_path) -> None:
    """One record, two sources, and the tier that says the fact was corroborated."""
    store = VersionedStore(tmp_path)
    write_proposal(store, _proposal("the markup of M-17 is inside the limit", "CASE-0001"))
    record = write_proposal(store, _proposal("the markup of M-17 is inside the limit", "CASE-0002"))

    assert len(store.latest_records()) == 1
    assert record.sources == ["CASE-0001", "CASE-0002"]
    assert record.trust_tier == "corroborated"
    assert record.version == 2


def test_a_different_assertion_is_a_second_record(tmp_path) -> None:
    """Two facts that read alike are still two facts."""
    store = VersionedStore(tmp_path)
    write_proposal(store, _proposal("the markup of M-17 is inside the limit", "CASE-0001"))
    write_proposal(store, _proposal("the payout of ST-0044 was late", "CASE-0002"))

    assert len(store.latest_records()) == 2


def test_the_same_source_proposing_the_same_fact_adds_nothing(tmp_path) -> None:
    """The provenance of a record is the set of its sources, not the count of its proposals."""
    store = VersionedStore(tmp_path)
    write_proposal(store, _proposal("the markup of M-17 is inside the limit", "CASE-0001"))
    record = write_proposal(store, _proposal("the markup of M-17 is inside the limit", "CASE-0001"))

    assert record.sources == ["CASE-0001"]
    assert record.version == 1
