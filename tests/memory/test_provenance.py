"""The provenance of a promoted record: the source, the approver, the date and the tier of trust.

What they guarantee, and why: a promoted record carries the source it came from, the approver that promoted it,
the date of the approval and the tier of trust, and they match the record of the approval, because a reader of
a recall has to see how the fact entered the memory and who let it in (the definition of done of the milestone).

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from datetime import UTC, datetime

from ledgerlens.memory.approval import approve, promote
from ledgerlens.memory.dedup import write_proposal
from ledgerlens.memory.proposal import propose
from ledgerlens.memory.versioned_store import VersionedStore


def test_a_promoted_record_carries_the_source_the_approver_the_date_and_the_tier(tmp_path) -> None:
    """The record and the approval say the same thing, and the reader can check it."""
    store = VersionedStore(tmp_path)
    proposal = propose(
        scope="session-a",
        assertion="the markup of M-17 is inside the limit",
        source="CASE-0001",
        source_verdict="supported",
        reviewer="reviewer-of-the-deployment",
    )
    record = write_proposal(store, proposal)
    moment = datetime(2026, 11, 24, 12, 0, 0, tzinfo=UTC)
    approval = approve(record.record_id, approver="reviewer-of-the-deployment", simulated=True, clock=moment)
    promoted = promote(store, record.record_id, approval)

    assert promoted.sources == ["CASE-0001"]
    assert promoted.trust_tier == "approved"
    assert promoted.approval_state == "approved"
    assert approval.approver == "reviewer-of-the-deployment"
    assert approval.approved_at == "2026-11-24T12:00:00+00:00"
    assert approval.simulated is True
    assert approval.record_id == promoted.record_id


def test_the_version_of_the_record_before_the_promotion_still_says_observed(tmp_path) -> None:
    """The promotion writes the next version, and the version the run read stays as it was."""
    store = VersionedStore(tmp_path)
    proposal = propose(
        scope="session-a",
        assertion="the markup of M-17 is inside the limit",
        source="CASE-0001",
        source_verdict="supported",
    )
    record = write_proposal(store, proposal)
    promote(store, record.record_id, approve(record.record_id, approver="reviewer", simulated=True))

    before = store.version_of(record.record_id, 1)
    assert before is not None
    assert before.trust_tier == "observed"
    assert before.approval_state == "none"
