"""The route that takes the decision of a review.

What they guarantee, and why: (a) a decision of a session of another person is refused, because the session is the
identity of the reviewer; (b) the refusal of the route discloses nothing about the task, because a task that a
person may not see is a task that must not leak its case, its evidence or its state; (c) a decision over a stale
revision is refused with the code of a conflict; (d) the route reads the domain and the domain never imports the
route.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import ast
from pathlib import Path

from ledgerlens.review.routes import (
    CONFLICT,
    FORBIDDEN,
    NOT_FOUND,
    OK,
    decide,
    open_task,
    refusal_code_of,
)
from ledgerlens.review.state_machine import DECISION_APPROVED, STATE_QUEUED, apply_decision
from ledgerlens.review.task import new_task

# The session of the reviewer that owns the task.
OWNER = "reviewer-1"
# The session of somebody else.
STRANGER = "reviewer-2"


def _task(case_id: str = "EC-01", owner: str = OWNER):
    """A task in the queue, owned by one reviewer."""
    task = new_task(
        case_id=case_id,
        evidence="the payment came to BRL 566.79 and the refund to BRL 549.31",
        snapshot_digest="digest-of-the-case",
        branch_event="evt-0001",
    )
    return task, owner


def test_a_decision_of_the_session_that_owns_the_task_is_served() -> None:
    """The reviewer that opened the task decides it, and the task moves."""
    task, owner = _task()
    tasks = {"EC-01": (task, owner)}

    answer = decide(
        "EC-01",
        session=owner,
        tasks=tasks,
        decision=DECISION_APPROVED,
        reason="the difference is the markup of the plan",
        expected_revision=task.revision,
        evidence_hash_read=task.evidence_hash,
    )

    assert answer["code"] == OK
    assert answer["task"]["state"] == "approved_for_sandbox"
    assert answer["task"]["revision"] == 1


def test_a_decision_of_a_session_of_another_person_is_refused() -> None:
    """The session is the identity of the reviewer, and a decision of somebody else is refused.

    Why it matters: a task that anybody could decide is a task that no person decided.
    """
    task, owner = _task()
    tasks = {"EC-01": (task, owner)}

    answer = decide(
        "EC-01",
        session=STRANGER,
        tasks=tasks,
        decision=DECISION_APPROVED,
        reason="the case is right",
        expected_revision=task.revision,
        evidence_hash_read=task.evidence_hash,
    )

    assert answer["code"] == FORBIDDEN
    assert answer["task"] is None


def test_the_refusal_discloses_nothing_about_the_task() -> None:
    """The refusal of the route carries no case, no evidence and no state.

    Why it matters: a task that a person may not see must not leak through the answer of a refusal.
    """
    task, owner = _task()
    tasks = {"EC-01": (task, owner)}

    answer = decide(
        "EC-01",
        session=STRANGER,
        tasks=tasks,
        decision=DECISION_APPROVED,
        reason="the case is right",
        expected_revision=task.revision,
        evidence_hash_read=task.evidence_hash,
    )

    serialized = repr(answer)
    assert task.case_id not in serialized
    assert task.evidence not in serialized
    assert task.evidence_hash not in serialized
    assert "BRL" not in serialized


def test_a_decision_with_a_stale_revision_is_answered_with_a_conflict() -> None:
    """A decision over a revision that moved is a conflict, and the conflict is a code and not an exception.

    Why it matters: the caller of the route is a page of a person, and a page has to show what happened.
    """
    task, owner = _task()
    decided = apply_decision(
        task,
        decision=DECISION_APPROVED,
        reason="the difference is the markup of the plan",
        session=owner,
        expected_revision=task.revision,
        evidence_hash_read=task.evidence_hash,
    )
    tasks = {"EC-01": (decided, owner)}

    answer = decide(
        "EC-01",
        session=owner,
        tasks=tasks,
        decision=DECISION_APPROVED,
        reason="the case is right",
        expected_revision=task.revision,
        evidence_hash_read=decided.evidence_hash,
    )

    assert answer["code"] == CONFLICT
    assert answer["task"] is None


def test_a_task_that_does_not_exist_is_answered_with_not_found() -> None:
    """A task that no session opened is not found, and the answer says nothing else."""
    answer = open_task("EC-999", session=OWNER, tasks={})

    assert answer["code"] == NOT_FOUND
    assert answer["task"] is None


def test_opening_a_task_of_another_person_is_refused() -> None:
    """The task of another session is not opened, and the refusal says nothing about it."""
    task, owner = _task()
    tasks = {"EC-01": (task, owner)}

    answer = open_task("EC-01", session=STRANGER, tasks=tasks)

    assert answer["code"] == FORBIDDEN
    assert answer["task"] is None


def test_opening_the_task_of_its_owner_serves_it_with_the_evidence() -> None:
    """The reviewer sees the evidence, the verdict and the limits of what the case decided."""
    task, owner = _task()
    tasks = {"EC-01": (task, owner)}

    answer = open_task("EC-01", session=owner, tasks=tasks)

    assert answer["code"] == OK
    assert answer["task"]["evidence"]
    assert answer["task"]["evidence_hash"] == task.evidence_hash
    assert answer["task"]["state"] == STATE_QUEUED


def test_the_refusal_code_of_a_refusal_is_readable() -> None:
    """The code of a refusal is a word, and not a number that the caller has to know."""
    assert refusal_code_of("forbidden") == FORBIDDEN
    assert refusal_code_of("conflict") == CONFLICT
    assert refusal_code_of("not found") == NOT_FOUND


def test_a_refusal_that_the_route_does_not_understand_is_never_an_ok() -> None:
    """A reason that no table knows is a refusal, and never a decision that was served.

    Why it matters: a route that answered "ok" to a reason it did not read would serve a task that nobody decided.
    """
    assert refusal_code_of("a reason that no table knows") == FORBIDDEN
    assert refusal_code_of("") == FORBIDDEN


def test_the_domain_of_the_review_never_imports_the_route() -> None:
    """The route reads the domain and the domain never imports the route.

    Why it matters: a domain that imports its own facade cannot be tested without the facade, and the rule of the
    repository is that the domain never imports the API.
    """
    package = Path(__file__).resolve().parents[2] / "ledgerlens" / "review"
    domain = ("task.py", "state_machine.py")
    for module in sorted(package.glob("*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                assert "ledgerlens.api" not in name, f"{module.name} imports {name}"
                if module.name in domain:
                    # The domain is a leaf: it knows the task and the table and nothing of the facade.
                    assert "routes" not in name, f"{module.name} imports {name}"


def test_the_route_reads_the_domain_and_never_the_other_way_round() -> None:
    """The route is the only module of the package that knows the domain, and the domain does not know the route.

    Why it matters: the rule that holds the package together is that the facade reads the domain and the domain never
    reads the facade, and a test that only checked one side would let the other side grow unnoticed.
    """
    package = Path(__file__).resolve().parents[2] / "ledgerlens" / "review"
    route_source = (package / "routes.py").read_text(encoding="utf-8")
    assert "ledgerlens.review.state_machine" in route_source
    assert "ledgerlens.review.task" in route_source

    for module in sorted(package.glob("*.py")):
        if module.name == "routes.py":
            continue
        source = module.read_text(encoding="utf-8")
        assert "routes" not in source, f"{module.name} mentions the route"
