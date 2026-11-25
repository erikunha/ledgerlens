"""The states of a review task, the table of the transitions and the checks that run before one of them applies.

What it decides: whether a decision of a person moves a task, and to which state. The agent prepares the evidence
and never decides, and the identity of the reviewer comes from the session of the request and never from the content
of the case.

Why the table is explicit: a state machine with a state outside its table is a machine whose history nobody can
read. Every transition of the table names the state it comes from, the state it goes to and the decision that
causes it, and a transition that is not in the table is refused.

Why the checks run before the transition and not after: a decision that was refused has to leave no trace. A task
that moved and then said it did not move is a task whose history lies, and the history of a case is the proof of
what happened to it.

Why a stale revision is a conflict and not a refusal of the case: the task is fine and the decision is late. Two
reviewers open the same task, the first one decides it and the second one is told that the state moved, which is a
different answer from the one that says the case cannot be decided.

Why a replay does not advance the state: the events of a run can be replayed, and a replay is not an authorisation.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from ledgerlens.review.task import ReviewEvent, ReviewTask

__all__ = [
    "DECISION_APPROVED",
    "DECISION_ESCALATED",
    "DECISION_REJECTED",
    "DECISION_REQUEST_MORE_EVIDENCE",
    "STATE_APPROVED",
    "STATE_ESCALATED",
    "STATE_IN_REVIEW",
    "STATE_QUEUED",
    "STATE_REJECTED",
    "STATE_REQUEST_MORE_EVIDENCE",
    "TRANSITIONS",
    "TransitionRefused",
    "apply_decision",
]

# The six states of a task.
STATE_QUEUED = "queued"
STATE_IN_REVIEW = "in_review"
STATE_APPROVED = "approved_for_sandbox"
STATE_REJECTED = "rejected"
STATE_REQUEST_MORE_EVIDENCE = "request_more_evidence"
STATE_ESCALATED = "escalated"

# The four decisions a reviewer can take.
DECISION_APPROVED = "approved"
DECISION_REJECTED = "rejected"
DECISION_REQUEST_MORE_EVIDENCE = "request_more_evidence"
DECISION_ESCALATED = "escalated"

# The table of the transitions: the state it comes from, the state it goes to and the decision that causes it.
TRANSITIONS: dict[tuple[str, str], str] = {
    (STATE_QUEUED, DECISION_APPROVED): STATE_APPROVED,
    (STATE_QUEUED, DECISION_REJECTED): STATE_REJECTED,
    (STATE_QUEUED, DECISION_REQUEST_MORE_EVIDENCE): STATE_REQUEST_MORE_EVIDENCE,
    (STATE_QUEUED, DECISION_ESCALATED): STATE_ESCALATED,
    (STATE_IN_REVIEW, DECISION_APPROVED): STATE_APPROVED,
    (STATE_IN_REVIEW, DECISION_REJECTED): STATE_REJECTED,
    (STATE_IN_REVIEW, DECISION_REQUEST_MORE_EVIDENCE): STATE_REQUEST_MORE_EVIDENCE,
    (STATE_IN_REVIEW, DECISION_ESCALATED): STATE_ESCALATED,
}


class TransitionRefused(Exception):
    """The decision does not apply, and the reason says why.

    Why it is an exception and not a return value: a decision that does not apply has to be handled, and a caller
    that forgot to check a boolean would decide a case twice.
    """

    reason = "the decision does not apply to the task"

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def apply_decision(
    task: ReviewTask,
    *,
    decision: str,
    reason: str,
    session: str,
    expected_revision: int,
    evidence_hash_read: str,
    snapshot_digest_now: str | None = None,
    reviewer_identity: str | None = None,
    replay: bool = False,
) -> ReviewTask:
    """The task after the decision, or a refusal with the reason why it does not apply.

    Why the checks come in this order: the permission of the reviewer comes first, because a decision of nobody is
    not a decision at all. The revision comes next, because a stale revision is a conflict and a conflict has to be
    reported as one and not as a broken case. The evidence and the snapshot come after, because a decision over
    something that moved is a decision about something else.

    Why the reason of the decision is required: a decision of a person without a reason is a decision that nobody
    can read six months later, and the reason is what tells the next person what was seen.
    """
    if reviewer_identity is not None:
        # The identity of the reviewer comes from the session of the request. An identity that arrives with the
        # content of the case is the content of the case, and the content of the case is data.
        raise TransitionRefused(
            "the identity of the reviewer comes from the session and not from the content of the case"
        )
    if not session:
        raise TransitionRefused("the decision carries no session, so it carries no reviewer")
    if replay:
        # A replay is not an authorisation. The events of a run can be replayed, and a state machine that counted a
        # replay as a decision would count a decision twice. The task keeps its state and its history, and the
        # caller sees the task it already had.
        if not any(event.decision == decision and event.session == session for event in task.events):
            raise TransitionRefused("the replay carries no event of the history, so it authorises nothing")
        return task
    if expected_revision != task.revision:
        raise TransitionRefused(
            f"conflict: the task is at the revision {task.revision} and the decision was taken over the revision "
            f"{expected_revision}"
        )
    if task.cancelled:
        raise TransitionRefused("the run of the case was cancelled, so the case cannot be approved")
    if not task.evidence:
        raise TransitionRefused("the task carries no evidence, so there is nothing to decide")
    if evidence_hash_read != task.evidence_hash:
        raise TransitionRefused(
            "the evidence the reviewer read is not the evidence of the task, so the decision is about something else"
        )
    if snapshot_digest_now is not None and snapshot_digest_now != task.snapshot_digest:
        raise TransitionRefused(
            "the snapshot of the case moved under the reviewer, so the decision is about a case that no longer exists"
        )
    if not reason:
        raise TransitionRefused("the decision carries no reason, so nobody can read it later")

    target = TRANSITIONS.get((task.state, decision))
    if target is None:
        raise TransitionRefused(
            f"the transition from the state {task.state!r} with the decision {decision!r} is not in the table of the "
            "states"
        )

    event = ReviewEvent(
        decision=decision,
        reason=reason,
        session=session,
        revision=task.revision + 1,
        evidence_hash=task.evidence_hash,
        at=datetime.now(UTC),
    )
    return replace(
        task,
        state=target,
        revision=task.revision + 1,
        events=(*task.events, event),
        reviewer_session=session,
    )


def states_of(task: ReviewTask) -> tuple[str, ...]:
    """The states the task went through, in the order they happened.

    Why it is a function and not a field: the history is the truth and this reads it, so the two can never
    disagree.
    """
    return (task.state, *(event.decision for event in task.events))


def to_dict(task: ReviewTask) -> dict[str, Any]:
    """The task as a dictionary, for the route that serves it."""
    return task.to_dict()
