"""The two reads of the branch: the diff of the branch against its base, and the history of the log with its marks.

Why this file exists: ADR-028 declares the shape of the two answers, and the two reads are the last of the R2
sandbox. The promises around them are easy to state and easy to get wrong:

* the diff of the branch is the difference between the published base and the state the branch holds now, and not
  the diff of the last mutation (ADR-028);
* a branch that was mutated and then undone answers an empty diff and the hash of the base, because the state of
  the branch after the undo IS the state of the base, row for row: that is the cost ADR-024 already accepted;
* the history carries the events of the log in the order of the log, and every event carries the mark that says it
  was undone;
* the history carries the answers the branch remembers, and every answer carries the mark of the staleness of
  ADR-022 and the mark of the undo of ADR-024;
* the marks come from the log and never from a stored flag, so a corruption of the log moves them;
* both reads verify the branch before they answer it, exactly like every other read, so a branch that cannot prove
  its own state is refused with `HASH_MISMATCH` and is never served (ADR-021);
* the history reads the log once and uses that same log for the verification and for the marks.

The money of these answers is text: the values of the diff are decimal texts with their currency, and the interface
never reads a number and never calculates one.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from ledgerlens.sandbox.branch import (
    BranchHashMismatch,
    BranchLayer,
    SandboxBranch,
)
from ledgerlens.sandbox.mutation import UNDO_KIND, MutationCommand
from ledgerlens.sandbox.projector import (
    EVENT_BRANCH_UNDONE,
    EVENT_REFUND_FX_ADJUSTED,
)
from ledgerlens.sandbox.store import BranchStore, SandboxEventRow

# The kind of the undo of the branch, the one of the vocabulary of the sandbox (ADR-024).
UNDO_KIND_NAME = UNDO_KIND


def _undo(revision: int = 1, key: str = "undo-0001") -> MutationCommand:
    """The command of the undo: the kind, an empty payload, the key and the expected revision.

    Why the payload is empty: the undo does not change a record of the case, it changes the log of the branch
    (ADR-024).
    """
    return MutationCommand(
        kind=UNDO_KIND_NAME,
        payload={},
        expected_revision=revision,
        idempotency_key=key,
    )


def _unknown_event(branch_id: str) -> SandboxEventRow:
    """An event of a kind the interpreter of the vocabulary of the sandbox does not know.

    Why the event exists: no visitor can append one, because the only way to append an event is a mutation of the
    catalog or an undo, and a corruption of the log can. The branch then cannot prove its own state (ADR-021).
    """
    return SandboxEventRow(
        event_uid="evt-unknown-kind",
        branch_id=branch_id,
        event_type="sandbox.unknown.kind",
        aggregate_id="R-0731",
        occurred_at="2026-11-14T10:00:00Z",
        payload={"note": "an event of a kind the interpreter does not know"},
        origin="sandbox",
        command_id="cmd-unknown-kind",
    )


# --- the diff of the branch is the difference between the base and the state it holds now --------------------


def test_the_diff_of_a_branch_with_one_mutation_names_the_record_and_the_two_values(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment: MutationCommand,
) -> None:
    """The diff names the record that changed, the value it held and the value it holds now (ADR-028).

    Why the values are texts: the interface never calculates money, so the answer carries the values as the ledger
    writes them, with the currency of the amount.
    """
    layer.commit_mutation(session_id, forked_branch.branch_id, adjustment)

    answer = layer.diff(session_id, forked_branch.branch_id)

    payouts = [
        entry
        for entry in answer.diff
        if entry["record"] == "refunds" and entry["record_id"] == "R-0731" and entry["field"] == "payout_amount_minor"
    ]
    assert payouts, answer.diff
    entry = payouts[0]
    assert entry["before"] != entry["after"]
    assert isinstance(entry["before"], str)
    assert isinstance(entry["after"], str)
    assert entry["value_kind"] == "monetary"
    assert entry["currency"] == "BRL"


def test_the_diff_of_a_branch_with_one_mutation_carries_the_two_hashes_the_revision_the_invariants_and_the_verdict(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment: MutationCommand,
) -> None:
    """The answer of the diff carries everything a reader of the branch needs to place it (ADR-028).

    The hash of the base and the hash of the branch are two different things once the branch was mutated: the first
    names the published case the branch was forked from and the second names the state the branch holds now.
    """
    layer.commit_mutation(session_id, forked_branch.branch_id, adjustment)

    answer = layer.diff(session_id, forked_branch.branch_id)
    status = layer.status(session_id, forked_branch.branch_id)

    assert answer.base_canonical_hash == forked_branch.base_canonical_hash
    assert answer.canonical_hash == status.current_canonical_hash
    assert answer.canonical_hash != answer.base_canonical_hash
    assert answer.revision == 1
    assert answer.invariants
    assert all(entry["passed"] for entry in answer.invariants)
    assert answer.verdict["label"]
    assert answer.verdict["measure"]


def test_the_diff_of_a_branch_with_no_mutation_is_empty_and_the_two_hashes_are_the_same(
    layer: BranchLayer, session_id: str, forked_branch: SandboxBranch
) -> None:
    """A branch that was never mutated holds the state of the base, so there is nothing to tell (ADR-028)."""
    answer = layer.diff(session_id, forked_branch.branch_id)

    assert answer.diff == []
    assert answer.base_canonical_hash == answer.canonical_hash
    assert answer.canonical_hash == forked_branch.base_canonical_hash
    assert answer.revision == 0


def test_the_diff_of_a_branch_that_was_mutated_and_undone_is_empty_and_the_hash_is_the_hash_of_the_base(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment: MutationCommand,
) -> None:
    """The cost ADR-024 accepted, shown honestly: the state after the undo IS the state of the base (ADR-028).

    The history is the only thing that tells that something happened, and that is the point of the two reads.
    """
    layer.commit_mutation(session_id, forked_branch.branch_id, adjustment)
    layer.undo(session_id, forked_branch.branch_id, _undo(revision=1))

    answer = layer.diff(session_id, forked_branch.branch_id)

    assert answer.diff == []
    assert answer.canonical_hash == answer.base_canonical_hash
    assert answer.canonical_hash == forked_branch.base_canonical_hash


def test_the_diff_of_a_branch_that_was_mutated_and_undone_is_the_diff_of_the_base_and_not_the_diff_of_the_mutation(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment: MutationCommand,
) -> None:
    """The diff of the branch is not the diff of the last mutation: the two are different things (ADR-028).

    The diff of the mutation is in the answer of the commit, and the diff of the undo is in the answer of the undo.
    """
    committed = layer.commit_mutation(session_id, forked_branch.branch_id, adjustment)
    layer.undo(session_id, forked_branch.branch_id, _undo(revision=1))

    answer = layer.diff(session_id, forked_branch.branch_id)

    assert committed.diff
    assert answer.diff == []


# --- the history carries the log in the order of the log -------------------------------------------------------


def test_the_history_carries_the_events_of_the_log_in_the_order_of_the_log(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment: MutationCommand,
) -> None:
    """The log is append only, so the history of a branch holds its events in the order they were appended."""
    layer.commit_mutation(session_id, forked_branch.branch_id, adjustment)

    history = layer.history(session_id, forked_branch.branch_id)

    assert [event["event_type"] for event in history.events] == [EVENT_REFUND_FX_ADJUSTED]
    assert history.events[0]["event_uid"]
    assert history.events[0]["aggregate_id"] == "R-0731"
    assert history.events[0]["occurred_at"]
    assert isinstance(history.events[0]["payload"], dict)
    assert history.revision == 1
    assert history.canonical_hash == layer.status(session_id, forked_branch.branch_id).current_canonical_hash


def test_the_history_of_a_branch_that_was_mutated_and_undone_shows_the_mutation_and_the_marker(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment: MutationCommand,
) -> None:
    """The event that was undone stays in the log, and the marker of the undo is appended to it (ADR-024)."""
    layer.commit_mutation(session_id, forked_branch.branch_id, adjustment)
    layer.undo(session_id, forked_branch.branch_id, _undo(revision=1))

    history = layer.history(session_id, forked_branch.branch_id)

    assert [event["event_type"] for event in history.events] == [
        EVENT_REFUND_FX_ADJUSTED,
        EVENT_BRANCH_UNDONE,
    ]


def test_the_history_marks_the_undone_event_and_only_that_one(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment_payload: dict[str, object],
) -> None:
    """The mark of the undo comes from the log, so it cannot drift away from the truth (ADR-024).

    The marker of the undo is not an undone mutation: an undo can never be undone, because the undo only takes back
    a mutation and a marker of the log is not a mutation.
    """
    layer.commit_mutation(
        session_id,
        forked_branch.branch_id,
        MutationCommand(
            kind="refund.apply_fx_adjustment",
            payload=dict(adjustment_payload),
            expected_revision=0,
            idempotency_key="cmd-0001",
        ),
    )
    layer.commit_mutation(
        session_id,
        forked_branch.branch_id,
        MutationCommand(
            kind="refund.apply_fx_adjustment",
            payload={**adjustment_payload, "applied_rate": "5.45000000"},
            expected_revision=1,
            idempotency_key="cmd-0002",
        ),
    )
    layer.undo(session_id, forked_branch.branch_id, _undo(revision=2))

    history = layer.history(session_id, forked_branch.branch_id)

    assert [event["undone"] for event in history.events] == [False, True, False]
    assert history.events[1]["event_type"] == EVENT_REFUND_FX_ADJUSTED


def test_the_history_carries_the_answers_of_the_branch_with_the_two_marks(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment: MutationCommand,
) -> None:
    """The answers of the branch travel with the mark of the staleness and the mark of the undo (ADR-022, ADR-024).

    The two marks never overlap: the answer of a mutation that was undone says that it was undone and names no
    event, and the answer of the undo names the event it undid.
    """
    layer.commit_mutation(session_id, forked_branch.branch_id, adjustment)
    layer.undo(session_id, forked_branch.branch_id, _undo(revision=1))

    history = layer.history(session_id, forked_branch.branch_id)
    answers = {answer.idempotency_key: answer for answer in history.answers}

    assert set(answers) == {"cmd-0001", "undo-0001"}
    assert answers["cmd-0001"].undone is True
    assert answers["cmd-0001"].undone_event_uid is None
    assert answers["cmd-0001"].stale is False
    assert answers["undo-0001"].undone is False
    assert answers["undo-0001"].undone_event_uid == history.events[0]["event_uid"]


def test_the_history_marks_the_answers_of_the_past_as_stale_after_a_reset(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment: MutationCommand,
) -> None:
    """A reset closes the generation of the answers, and the history says that they are stale (ADR-022)."""
    layer.commit_mutation(session_id, forked_branch.branch_id, adjustment)
    layer.reset(session_id, forked_branch.branch_id)

    history = layer.history(session_id, forked_branch.branch_id)
    answers = {answer.idempotency_key: answer for answer in history.answers}

    assert answers["cmd-0001"].stale is True
    assert answers["cmd-0001"].stale_against == forked_branch.base_canonical_hash


def test_the_history_reads_the_log_once_and_uses_that_same_log_for_the_verification_and_the_marks(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment: MutationCommand,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The log is read once, so the marks of the history are the marks of the log that was verified (ADR-028).

    Why the number of the reads is the promise: the history verifies the branch with the log it reads and derives
    the marks of the undo from that same log, so a second read could answer with the marks of a log that was never
    verified. The spy counts the reads of the store, so the promise is pinned by the test and not only described by
    the docstring of the layer.
    """
    layer.commit_mutation(session_id, forked_branch.branch_id, adjustment)
    layer.undo(session_id, forked_branch.branch_id, _undo(revision=1))
    reads: list[str] = []
    store_class = type(layer.store)
    original = store_class.read_events

    def spy(implementation, branch_id: str, owner_session: str) -> list[SandboxEventRow]:
        reads.append(branch_id)
        return original(implementation, branch_id, owner_session)

    monkeypatch.setattr(store_class, "read_events", spy)

    history = layer.history(session_id, forked_branch.branch_id)

    assert reads == [forked_branch.branch_id]
    assert [event["undone"] for event in history.events] == [True, False]


# --- the refusals of the two reads ------------------------------------------------------------------------------


def test_the_history_of_a_branch_whose_log_cannot_be_projected_is_refused_with_HASH_MISMATCH(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    store: BranchStore,
    owner_session: str,
) -> None:
    """The verification of the branch is shared, so the history refuses the log the status refuses (ADR-021).

    A log that cannot be projected is a branch that cannot prove its own state, and the refusal is the same one of
    a branch whose row does not agree with its events.
    """
    store.append_events(forked_branch.branch_id, owner_session, [_unknown_event(forked_branch.branch_id)])

    with pytest.raises(BranchHashMismatch) as refusal:
        layer.history(session_id, forked_branch.branch_id)

    assert refusal.value.code == "HASH_MISMATCH"
    assert "fork" in refusal.value.message


def test_the_diff_of_a_branch_whose_log_cannot_be_projected_is_refused_with_HASH_MISMATCH(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    store: BranchStore,
    owner_session: str,
) -> None:
    """The diff is a read of the branch, so it verifies the branch like every other read (ADR-021)."""
    store.append_events(forked_branch.branch_id, owner_session, [_unknown_event(forked_branch.branch_id)])

    with pytest.raises(BranchHashMismatch) as refusal:
        layer.diff(session_id, forked_branch.branch_id)

    assert refusal.value.code == "HASH_MISMATCH"


def test_the_history_of_a_branch_that_was_mutated_and_undone_keeps_the_answers_of_both_requests(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment: MutationCommand,
    clock,
) -> None:
    """The undo does not delete the answers: an answer that was deleted could not be marked (ADR-022, ADR-024)."""
    layer.commit_mutation(session_id, forked_branch.branch_id, adjustment)
    layer.undo(session_id, forked_branch.branch_id, _undo(revision=1))

    clock.advance(timedelta(seconds=1))
    history = layer.history(session_id, forked_branch.branch_id)

    assert len(history.answers) == 2
