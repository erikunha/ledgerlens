"""The review of a case by a person: the task, the evidence it carries and the history of what happened to it.

What a task is: a case that the code sent to a person, the evidence that the reviewer read, the hash of that
evidence, the state the task is in, the revision that state is at and the events that moved it there.

Why the hash of the evidence travels with the task: a decision binds to what was read and not to what is on the
screen now. A reviewer who reads evidence, waits and then decides has to be sure that the evidence did not change
under them, and the hash is what says that. The decision of a task whose hash does not match the evidence the
reviewer read is refused, because the reviewer decided about something else.

Why the history is append only: the history of a case is the proof of what happened to it, and a history that can be
edited is not a proof. Every transition appends an event and nothing rewrites one.

Why the task never carries the identity of the reviewer: the identity of the person who decided comes from the
session of the request, and never from the content of the case. An agent that suggests who the reviewer is would be
able to answer for a person.

Why the package imports no API and no payment client: the red line of the repository is that no real money moves,
and the approval of a review applies to a branch of the sandbox and never to a live payment.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

__all__ = [
    "ReviewEvent",
    "ReviewTask",
    "evidence_hash",
    "new_task",
]


def evidence_hash(evidence: str) -> str:
    """The hash of the evidence a reviewer read.

    Why a hash and not the evidence itself in the decision: the evidence of a case can be long, and the decision
    binds to the hash of it. The hash is over the exact text the reviewer read, so any change to it changes the
    hash.
    """
    return hashlib.sha256(evidence.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ReviewEvent:
    """One event of the history of a task: a decision that was taken and the moment it was taken.

    Why the event carries the hash of the evidence and the revision: a reader of the history has to be able to see
    what was decided, over which evidence, and at which state of the task.
    """

    decision: str
    reason: str
    session: str
    revision: int
    evidence_hash: str
    at: datetime

    def to_dict(self) -> dict[str, Any]:
        """The event as a dictionary, for the history that is published."""
        return {
            "decision": self.decision,
            "reason": self.reason,
            "session": self.session,
            "revision": self.revision,
            "evidence_hash": self.evidence_hash,
            "at": self.at.isoformat(),
        }


@dataclass(frozen=True)
class ReviewTask:
    """A case that waits for a person, with everything the person needs to decide it.

    Why the task is frozen: the state of a task moves through transitions, and a task that could be edited in place
    would be a task whose history could disagree with its state.
    """

    case_id: str
    evidence: str
    evidence_hash: str
    snapshot_digest: str
    branch_event: str
    state: str
    revision: int
    events: tuple[ReviewEvent, ...] = ()
    # The identity of the reviewer of the current state, when the task is with one.
    reviewer_session: str | None = None
    # Whether the run of the case was cancelled, because a cancelled run cannot be approved.
    cancelled: bool = False
    # The moment the task was opened, and the moment it was last decided.
    opened_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """The task as a dictionary, for the route that serves it.

        Why the evidence is in it: the reviewer has to read what they decide about, and a task without its evidence
        is a task that cannot be decided. The route that refuses never carries a task, so nothing leaks.
        """
        return {
            "case_id": self.case_id,
            "evidence": self.evidence,
            "evidence_hash": self.evidence_hash,
            "snapshot_digest": self.snapshot_digest,
            "branch_event": self.branch_event,
            "state": self.state,
            "revision": self.revision,
            "events": [event.to_dict() for event in self.events],
            "reviewer_session": self.reviewer_session,
            "cancelled": self.cancelled,
            "opened_at": self.opened_at.isoformat(),
        }


def new_task(
    *,
    case_id: str,
    evidence: str,
    snapshot_digest: str,
    branch_event: str,
    cancelled: bool = False,
) -> ReviewTask:
    """A task in the queue, with the evidence the reviewer will read and the hash of it.

    Why the task is opened in the queue and nowhere else: the code of the escalation decides that a case goes to a
    person, and the task is the envelope of that decision. The agent prepares the evidence and never decides.
    """
    return ReviewTask(
        case_id=case_id,
        evidence=evidence,
        evidence_hash=evidence_hash(evidence),
        snapshot_digest=snapshot_digest,
        branch_event=branch_event,
        state="queued",
        revision=0,
        events=(),
        reviewer_session=None,
        cancelled=cancelled,
    )
