"""The promotion of a record: it needs a recorded approval, and the approval says whether it was simulated.

What they guarantee, and why: (a) a promotion without an approval is refused, because a record that leaves the
tier of a case without a recorded approval is a record that became a policy by repetition; (b) the approval of
a promotion names its date and says whether it was simulated, because the repository has no review service and
a simulation that hid itself would be a fake reviewer.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ledgerlens.memory.approval import PromotionRefused, approve, promote
from ledgerlens.memory.dedup import write_proposal
from ledgerlens.memory.proposal import propose
from ledgerlens.memory.versioned_store import VersionedStore


def _store_with_a_record(tmp_path) -> tuple[VersionedStore, str]:
    """A store with one record, and the id of the record."""
    store = VersionedStore(tmp_path)
    proposal = propose(
        scope="session-a",
        assertion="the markup of M-17 is inside the limit",
        source="CASE-0001",
        source_verdict="supported",
    )
    record = write_proposal(store, proposal)
    return store, record.record_id


def test_a_promotion_without_an_approval_is_refused(tmp_path) -> None:
    """A record that leaves the tier of a case without a recorded approval is a policy by repetition."""
    store, record_id = _store_with_a_record(tmp_path)

    with pytest.raises(PromotionRefused, match="no recorded approval"):
        promote(store, record_id, None)

    assert store.latest_of(record_id).trust_tier == "observed"


def test_the_approval_of_a_promotion_names_the_date_and_the_simulation(tmp_path) -> None:
    """The approval is a record with a date and a flag, and the flag says the reviewer was simulated."""
    store, record_id = _store_with_a_record(tmp_path)
    moment = datetime(2026, 11, 24, 12, 0, 0, tzinfo=UTC)

    approval = approve(record_id, approver="reviewer-of-the-deployment", simulated=True, clock=moment)
    promoted = promote(store, record_id, approval)

    assert approval.approved_at == "2026-11-24T12:00:00+00:00"
    assert approval.simulated is True
    assert promoted.trust_tier == "approved"
    assert promoted.approval_state == "approved"
    assert promoted.version == 2


def test_the_approval_of_another_record_does_not_promote_this_one(tmp_path) -> None:
    """An approval names the record it approves, and it approves nothing else."""
    store, record_id = _store_with_a_record(tmp_path)
    approval = approve("REC-ffffffffffff", approver="reviewer", simulated=True)

    with pytest.raises(PromotionRefused, match="names the record"):
        promote(store, record_id, approval)
