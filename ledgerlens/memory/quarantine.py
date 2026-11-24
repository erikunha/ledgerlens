"""The quarantine of the versioned memory: a record that was meant to steer the agent is held aside with a reason.

Why it exists: a case can write a text that tries to steer the agent, and a memory that retrieved that text as
a fact would hand the attack to the next session. The quarantine holds the record aside with the reason written
down, and the record is not retrieved, not even when it is the best match of the set.

Why the quarantine is a state and not a deletion: a memory that quietly forgets a poisoned record teaches
nothing about the attack, and a reason that nobody can read is not a reason. A person may release the record,
and the release is a version of the record like any other, so the attempt and the release stay readable.

Why the detection is deterministic: the patterns that name an attempt to steer the agent are code of the
repository, and a detector that a model could talk out of its decision is not a detector.
"""

from __future__ import annotations

import re

from ledgerlens.memory.versioned_store import VersionedStore
from ledgerlens.schemas import MemoryRecord

__all__ = ["QuarantineRefused", "detect_steering", "quarantine", "release"]

# The patterns that name an attempt to steer the agent, with the reason each one gives. The patterns are tight
# on purpose: a memory that quarantines every text that mentions a refund would quarantine the memory itself.
_STEERING: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\bignore\b.{0,40}\b(instruction|instructions|policy|policies|rule|rules)\b", re.IGNORECASE),
        "the text asks the agent to ignore the instructions or the policies",
    ),
    (
        re.compile(r"\byou (must|shall) (call|use|run|invoke)\b", re.IGNORECASE),
        "the text tells the agent which tool to call",
    ),
    (
        re.compile(r"\b(system prompt|developer message)\b", re.IGNORECASE),
        "the text names the system prompt of the agent",
    ),
    (
        re.compile(r"\bdo not (verify|check|confirm)\b", re.IGNORECASE),
        "the text asks the agent to skip the verification",
    ),
    (
        re.compile(r"\b(approve|authorize|allow)\b.{0,30}\b(refund|payment|payout)\b", re.IGNORECASE),
        "the text claims the authority to approve a payment action",
    ),
)


class QuarantineRefused(Exception):
    """The quarantine or the release is refused, and the message says why."""


def detect_steering(text: str) -> str | None:
    """The reason the text is an attempt to steer the agent, and None when it is not.

    Why the reason is a sentence and not a code: the reason of a quarantine is read by a person, and a code
    would make the person read the code instead of the reason.
    """
    for pattern, reason in _STEERING:
        if pattern.search(text):
            return reason
    return None


def quarantine(store: VersionedStore, record_id: str, reason: str) -> MemoryRecord:
    """The next version of a record, held in the state of the quarantine with the reason written down.

    Why the quarantine is a version and not a flag: the record that was meant to steer the agent stays in the
    store with its reason, so the attempt is readable and the release of it is a version like any other.
    """
    if not reason.strip():
        raise QuarantineRefused("a quarantine with no reason is a deletion, and the quarantine is not a deletion")
    latest = store.latest_of(record_id)
    if latest is None:
        raise QuarantineRefused(f"the store has no record {record_id} to quarantine")
    return store.write(
        latest.model_copy(update={"version": latest.version + 1, "state": "quarantined", "quarantine_reason": reason})
    )


def release(store: VersionedStore, record_id: str, *, released_by: str) -> MemoryRecord:
    """The next version of a quarantined record, active again, with the person that released it named.

    Why the release names the person: a quarantine that a text could lift is not a quarantine, and the release
    of one is a decision of a person, with the name of the person written down.
    """
    if not released_by.strip():
        raise QuarantineRefused("the release of a quarantined record names the person that releases it")
    latest = store.latest_of(record_id)
    if latest is None:
        raise QuarantineRefused(f"the store has no record {record_id} to release")
    if latest.state != "quarantined":
        raise QuarantineRefused(f"the record {record_id} is not quarantined, so there is nothing to release")
    return store.write(
        latest.model_copy(
            update={"version": latest.version + 1, "state": "active", "quarantine_reason": None}
        )
    )
