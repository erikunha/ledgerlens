"""The approval of a promotion: a record leaves the tier of a case only with a recorded approval.

Why it exists: a record that becomes a policy by repetition is the risk the plan of the milestone names, and
the guard is that a promotion needs an approval that is recorded, with its date and with the flag that says
whether it was simulated. The repository has no human approval queue, so the first version simulates the
reviewer in the offline path, and the record says so in its own text: a simulation that hid itself would be a
fake reviewer.

Why the approval is a record of its own: the promotion of a record is a fact of the memory, and a fact of the
memory is a record with a date, an approver and the flag of the simulation, not a flag in the code.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from ledgerlens.memory.versioned_store import VersionedStore
from ledgerlens.schemas import MemoryRecord

__all__ = ["Approval", "PromotionRefused", "approve", "promote"]


class PromotionRefused(Exception):
    """The promotion is refused, and the message says why."""


@dataclass(frozen=True)
class Approval:
    """The recorded approval of a promotion: who approved, when, and whether it was simulated.

    Why the flag of the simulation is part of the approval: the repository has no review service, and an
    approval that hid that it was simulated would be a fake reviewer (the question the plan answers).
    """

    record_id: str
    approver: str
    approved_at: str
    simulated: bool


def approve(record_id: str, *, approver: str, simulated: bool, clock: datetime | None = None) -> Approval:
    """The recorded approval of a promotion, with its date and its flag of simulation."""
    moment = clock or datetime.now(UTC)
    return Approval(
        record_id=record_id,
        approver=approver,
        approved_at=moment.isoformat(timespec="seconds"),
        simulated=simulated,
    )


def promote(store: VersionedStore, record_id: str, approval: Approval | None) -> MemoryRecord:
    """The next version of a record with the tier and the approval state of a promotion.

    Why the approval is an argument and not a lookup: the caller records the approval and hands it over, so the
    promotion is the write of the next version and the approval is the evidence of it. A promotion without an
    approval is refused, because a record that leaves the tier of a case without one is a record that became a
    policy by repetition.
    """
    if approval is None:
        raise PromotionRefused(
            f"the promotion of the record {record_id} has no recorded approval, and a promotion without an "
            "approval is refused"
        )
    if approval.record_id != record_id:
        raise PromotionRefused(
            f"the approval names the record {approval.record_id} and the promotion names {record_id}"
        )
    latest = store.latest_of(record_id)
    if latest is None:
        raise PromotionRefused(f"the store has no record {record_id} to promote")
    promoted = latest.model_copy(
        update={
            "version": latest.version + 1,
            "trust_tier": "approved",
            "approval_state": "approved",
        }
    )
    return store.write(promoted)
