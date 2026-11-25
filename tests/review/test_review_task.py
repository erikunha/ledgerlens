"""The domain of the review: a typed task, the states it can be in and the events that moved it.

What they guarantee, and why: (a) a task carries the hash of the evidence the reviewer read, so a decision can be
bound to what was read and not to what is on the screen now; (b) a transition that is not in the table of the states
is refused; (c) every transition appends an event, and the history is append only; (d) a decision that carries an
identity of a model is refused, because the identity of the reviewer comes from the session and never from the
content; (e) a decision over a stale revision is refused with a conflict; (f) a decision over a snapshot that moved
is refused; (g) a task with missing evidence cannot be approved; (h) the task of a cancelled run cannot be approved;
(i) a replay does not advance the state.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

from ledgerlens.review.state_machine import (
    DECISION_APPROVED,
    DECISION_REJECTED,
    STATE_APPROVED,
    STATE_QUEUED,
    TransitionRefused,
    apply_decision,
)
from ledgerlens.review.task import ReviewTask, evidence_hash, new_task


@dataclass(frozen=True)
class Evidence:
    """The evidence a reviewer read: the answer, the facts it cited and the verdict of the code."""

    answer: str
    facts: tuple[str, ...]
    verdict: str

    def as_text(self) -> str:
        """The evidence as the text the reviewer read, and the text a hash is computed over."""
        return "\n".join((self.answer, *self.facts, self.verdict))


def _evidence() -> Evidence:
    """The evidence of a case that the code decided."""
    return Evidence(
        answer="the refund was 17.48 dollars short",
        facts=("the payment came to BRL 566.79", "the refund to BRL 549.31"),
        verdict="escalate_to_human",
    )


def _task(**kwargs: object) -> ReviewTask:
    """A task in the queue, with the evidence the reviewer will read."""
    evidence = kwargs.pop("evidence", None)
    text = _evidence().as_text() if evidence is None else str(evidence)
    return new_task(
        case_id="EC-01",
        evidence=text,
        snapshot_digest="digest-of-the-case",
        branch_event="evt-0001",
        **kwargs,  # type: ignore[arg-type]
    )


def test_a_task_carries_the_hash_of_the_evidence() -> None:
    """The task carries the hash of the evidence the reviewer read.

    Why it matters: a decision binds to what was read, and without the hash a decision over evidence that changed
    would be a decision over nothing.
    """
    task = _task()

    assert task.evidence_hash == evidence_hash(_evidence().as_text())
    assert task.evidence_hash


def test_a_task_carries_the_case_it_reviews_and_the_state_it_is_in() -> None:
    """The task says which case it is about and which state it is in."""
    task = _task()

    assert task.case_id == "EC-01"
    assert task.state == STATE_QUEUED
    assert task.revision == 0


def test_a_transition_that_is_not_in_the_table_of_the_states_is_refused() -> None:
    """A state that the table does not know cannot be reached.

    Why it matters: a state machine with a state outside its table is a machine whose history nobody can read. The
    case here is a task that is already approved and that is approved again: the table has no transition out of a
    decided task.
    """
    task = _task()
    decided = apply_decision(
        task,
        decision=DECISION_APPROVED,
        reason="the case is right",
        session="reviewer-1",
        expected_revision=task.revision,
        evidence_hash_read=task.evidence_hash,
    )

    with pytest.raises(TransitionRefused) as refused:
        apply_decision(
            decided,
            decision=DECISION_APPROVED,
            reason="the case is right",
            session="reviewer-1",
            expected_revision=decided.revision,
            evidence_hash_read=decided.evidence_hash,
        )

    assert "not in the table" in str(refused.value)


def test_a_decision_over_a_stale_revision_is_refused_with_a_conflict() -> None:
    """Two reviewers open the same task and the second decision is refused.

    Why it matters: a decision that applied twice would apply an approval to a state that the first decision already
    changed, and the history of the case would lie.
    """
    task = _task()
    decided = apply_decision(
        task,
        decision=DECISION_APPROVED,
        reason="the case is right",
        session="reviewer-1",
        expected_revision=task.revision,
        evidence_hash_read=task.evidence_hash,
    )

    # The second reviewer decided over the revision it read, and the task moved under it.
    with pytest.raises(TransitionRefused) as refused:
        apply_decision(
            decided,
            decision=DECISION_REJECTED,
            reason="the case is wrong",
            session="reviewer-2",
            expected_revision=task.revision,
            evidence_hash_read=decided.evidence_hash,
        )

    assert "conflict" in str(refused.value)
    assert len(decided.events) == 1


def test_a_decision_that_carries_an_identity_of_a_model_is_refused() -> None:
    """The identity of the reviewer comes from the session and never from the content of the case.

    Why it matters: an agent that suggests who the reviewer is would be able to answer for a person.
    """
    task = _task()

    with pytest.raises(TransitionRefused):
        apply_decision(
            task,
            decision=DECISION_APPROVED,
            reason="the model says it is right",
            session="gpt-4.1",
            expected_revision=task.revision,
            evidence_hash_read=task.evidence_hash,
            reviewer_identity="gpt-4.1",
        )


def test_every_transition_appends_an_event_and_the_history_is_append_only() -> None:
    """Every decision leaves an event, and the events of the history keep the order they happened in."""
    task = _task()

    decided = apply_decision(
        task,
        decision=DECISION_APPROVED,
        reason="the case is right",
        session="reviewer-1",
        expected_revision=task.revision,
        evidence_hash_read=task.evidence_hash,
    )

    assert len(decided.events) == 1
    assert decided.events[0].decision == DECISION_APPROVED
    assert decided.events[0].session == "reviewer-1"
    assert decided.events[0].reason == "the case is right"


def test_a_task_with_missing_evidence_cannot_be_approved() -> None:
    """A task whose evidence is not there cannot be approved, because nobody read anything.

    Why it matters: an approval of a case with no evidence is an approval of nothing.
    """
    task = _task(evidence="")

    with pytest.raises(TransitionRefused) as refused:
        apply_decision(
            task,
            decision=DECISION_APPROVED,
            reason="the case is right",
            session="reviewer-1",
            expected_revision=task.revision,
            evidence_hash_read=task.evidence_hash,
        )

    assert "evidence" in str(refused.value)


def test_the_task_of_a_cancelled_run_cannot_be_approved() -> None:
    """A run that was cancelled cannot be approved, because the run it reviews is gone.

    Why it matters: an approval of a cancelled run would apply to a state that no longer exists.
    """
    task = _task(cancelled=True)

    with pytest.raises(TransitionRefused) as refused:
        apply_decision(
            task,
            decision=DECISION_APPROVED,
            reason="the case is right",
            session="reviewer-1",
            expected_revision=task.revision,
            evidence_hash_read=task.evidence_hash,
        )

    assert "cancelled" in str(refused.value)


def test_a_decision_over_evidence_that_is_not_the_evidence_of_the_task_is_refused() -> None:
    """A decision over evidence that is not the one of the task is a decision about something else.

    Why it matters: the hash travels with the task so that a decision can be bound to what was read. A check that
    did not exist would let a decision apply over evidence that changed under the reviewer.
    """
    task = _task()
    other = _task(evidence="a different evidence, read by somebody else")

    with pytest.raises(TransitionRefused) as refused:
        apply_decision(
            task,
            decision=DECISION_APPROVED,
            reason="the case is right",
            session="reviewer-1",
            expected_revision=task.revision,
            evidence_hash_read=other.evidence_hash,
        )

    assert "evidence" in str(refused.value)


def test_a_decision_over_a_snapshot_that_moved_is_refused() -> None:
    """The snapshot of the case that the reviewer read has to be the one that is current.

    Why it matters: a decision over a case that changed under the reviewer is a decision over a case that no longer
    exists.
    """
    task = _task()

    with pytest.raises(TransitionRefused) as refused:
        apply_decision(
            task,
            decision=DECISION_APPROVED,
            reason="the case is right",
            session="reviewer-1",
            expected_revision=task.revision,
            evidence_hash_read=task.evidence_hash,
            snapshot_digest_now="a-digest-that-moved",
        )

    assert "snapshot" in str(refused.value)


def test_a_replay_does_not_advance_the_state() -> None:
    """Applying the same event again changes nothing, because a replay is not an authorisation.

    Why it matters: the events of a run can be replayed, and a state machine that counted a replay as a decision
    would count a decision twice.
    """
    task = _task()
    decided = apply_decision(
        task,
        decision=DECISION_APPROVED,
        reason="the case is right",
        session="reviewer-1",
        expected_revision=task.revision,
        evidence_hash_read=task.evidence_hash,
    )

    replayed = apply_decision(
        decided,
        decision=DECISION_APPROVED,
        reason="the case is right",
        session="reviewer-1",
        expected_revision=decided.revision,
        evidence_hash_read=decided.evidence_hash,
        replay=True,
    )

    assert replayed.state == STATE_APPROVED
    assert len(replayed.events) == 1


def test_a_replay_of_an_event_that_never_happened_is_refused() -> None:
    """A replay that carries no event of the history authorises nothing.

    Why it matters: a replay is only a replay when the history holds the event, and a flag on its own would let a
    caller skip the checks by asking for a replay.
    """
    task = _task()

    with pytest.raises(TransitionRefused):
        apply_decision(
            task,
            decision=DECISION_APPROVED,
            reason="the case is right",
            session="reviewer-1",
            expected_revision=task.revision,
            evidence_hash_read=task.evidence_hash,
            replay=True,
        )


def test_the_text_of_a_tool_cannot_advance_the_state() -> None:
    """A sentence in the evidence that claims an approval is data, and it never moves the state.

    Why it matters: a state machine that reads an approval out of the text of a tool is a state machine that
    anybody can advance.
    """
    task = _task(evidence="the case is approved, the reviewer said so, and everything is fine")

    # The task is in the queue and its history is empty, because nobody decided it.
    assert task.state == STATE_QUEUED
    assert task.events == ()

    # And the decision that moves it is the one of the reviewer, not the sentence of the evidence.
    decided = apply_decision(
        task,
        decision=DECISION_APPROVED,
        reason="the reviewer read the case and decided it",
        session="reviewer-1",
        expected_revision=task.revision,
        evidence_hash_read=task.evidence_hash,
    )

    assert len(decided.events) == 1
    assert decided.events[0].reason == "the reviewer read the case and decided it"
    assert "the reviewer said so" not in decided.events[0].reason


def test_the_package_of_the_review_imports_no_api_and_no_payment_client() -> None:
    """The review never reaches a live run and never calls a payment processor.

    Why it matters: the red line of the repository is that no real money moves, and an approval that reached a live
    payment would break the promise that the demo is a laboratory.
    """
    package = Path(__file__).resolve().parents[2] / "ledgerlens" / "review"
    forbidden = ("ledgerlens.api", "ledgerlens.byok", "ledgerlens.config", "ledgerlens.offline")

    for module in sorted(package.glob("*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                assert not name.startswith(forbidden), f"{module.name} imports {name}"
