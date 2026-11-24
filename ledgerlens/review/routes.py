"""The route that takes the decision of a review: it reads the domain and the domain never reads it.

What it does: it opens the task of the session that owns it and it takes the decision of the session that owns it.
The route is a facade over the domain of the review, and it holds no rule of its own: every refusal comes from the
state machine and the route only carries it.

Why the session is the identity: the reviewer of a task is the person whose session opened it. An identity that
arrives in the body of the request is data, and the domain refuses it (ADR-087 and the rule of the package).

Why a refusal carries no task: a person who may not see a task must not learn anything about it from the answer of
a refusal. The refusal carries the code and nothing else, so a caller cannot read the case, the evidence or the
state of a task out of the error.

Why the code of a refusal is a word: the caller of the route is a page of a person, and a page has to show what
happened. A number that only the route knows is a number that the page cannot read.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ledgerlens.review.state_machine import TransitionRefused, apply_decision
from ledgerlens.review.task import ReviewTask

__all__ = [
    "CONFLICT",
    "FORBIDDEN",
    "NOT_FOUND",
    "OK",
    "REFUSAL_CODES",
    "decide",
    "open_task",
    "refusal_code_of",
]

# The four answers of the route.
OK = "ok"
FORBIDDEN = "forbidden"
CONFLICT = "conflict"
NOT_FOUND = "not_found"

# The words of the refusals, and the code each one carries.
REFUSAL_CODES: dict[str, str] = {
    "conflict": CONFLICT,
    "forbidden": FORBIDDEN,
    "not found": NOT_FOUND,
    "the identity of the reviewer": FORBIDDEN,
    "the decision carries no session": FORBIDDEN,
}


def refusal_code_of(reason: str) -> str:
    """The code of a refusal, read from the reason the domain gave.

    Why it reads the words of the reason and not the exception type: the domain owns the reasons and the route
    carries them, and a route that knew every reason of the domain would be a second place where a rule lives.

    Why a reason that no table knows is forbidden and not ok: a refusal that the route does not understand is a
    refusal, and a route that answered "ok" to a reason it did not read would serve a task that nobody decided.
    """
    lowered = reason.lower()
    for word in sorted(REFUSAL_CODES, key=len, reverse=True):
        if word in lowered:
            return REFUSAL_CODES[word]
    return FORBIDDEN


def _refusal(code: str, reason: str) -> dict[str, Any]:
    """The answer of a refusal: the code and the reason, and no task at all."""
    return {"code": code, "reason": reason, "task": None}


def open_task(
    case_id: str,
    *,
    session: str,
    tasks: Mapping[str, tuple[ReviewTask, str]],
) -> dict[str, Any]:
    """The task of a case for the session that owns it, or a refusal.

    Why the owner of the task is carried with it: the owner is the session that opened it, and it is the only thing
    that says that this person may see this task.
    """
    found = tasks.get(case_id)
    if found is None:
        return _refusal(NOT_FOUND, "there is no task for this case")
    task, owner = found
    if owner != session:
        return _refusal(FORBIDDEN, "the task belongs to another session")
    return {"code": OK, "reason": "", "task": task.to_dict()}


def decide(
    case_id: str,
    *,
    session: str,
    tasks: Mapping[str, tuple[ReviewTask, str]],
    decision: str,
    reason: str,
    expected_revision: int,
    evidence_hash_read: str,
    snapshot_digest_now: str | None = None,
    reviewer_identity: str | None = None,
) -> dict[str, Any]:
    """The decision of the session that owns the task, or a refusal.

    Why the route looks the task up instead of taking it: the owner of the task is the session that opened it, and
    the owner is the only thing that says that this person may decide it. A route that took the task as it was
    would have no owner to check.

    Why the route does not decide: the rules of the review are in the state machine, and the route only carries the
    answer of the domain to the page of a person.
    """
    found = tasks.get(case_id)
    if found is None:
        return _refusal(NOT_FOUND, "there is no task for this case")
    task, owner = found
    if owner != session:
        return _refusal(FORBIDDEN, "the task belongs to another session")
    try:
        decided = apply_decision(
            task,
            decision=decision,
            reason=reason,
            session=session,
            expected_revision=expected_revision,
            evidence_hash_read=evidence_hash_read,
            snapshot_digest_now=snapshot_digest_now,
            reviewer_identity=reviewer_identity,
        )
    except TransitionRefused as refused:
        return _refusal(refusal_code_of(refused.reason), refused.reason)
    return {"code": OK, "reason": "", "task": decided.to_dict()}
