"""The undo of the last mutation of a branch: the revision goes back, the history stays, and the log is the truth.

Why this file exists: the undo is the refinement of the reset (ADR-024). A visitor applies a mutation, sees that it
was a mistake, and asks for the branch to go back to the state it had before it. The promises around that action are
easy to state and easy to get wrong:

* the branch returns to the hash it had at the previous revision and the revision goes back to the previous value
  (FR-037, ADR-024);
* the history of the branch is append only, so the undone event stays in the log and the undo is recorded as a new
  event, and the answer of the undone mutation carries the mark that it was undone (FR-037);
* an undo on a branch that has nothing to undo is refused with `409` and the code `NOTHING_TO_UNDO`, and the branch
  stays untouched (FR-038);
* the undo is a request with a key and with an expected revision, exactly like a mutation, so the same request sends
  the same answer and appends nothing, and a stale expected revision is refused (FR-012, FR-013, FR-014);
* the mark of the undo is derived from the log of the branch and never from a stored flag, so a corruption of the log
  moves the mark and a log that cannot be projected is refused with `HASH_MISMATCH` like any other log that cannot
  prove the state of the branch (ADR-021, ADR-024);
* the key of a request that was undone stays bound to that request, so the same key is answered with the answer that
  was stored and never commits a second time (ADR-024).

The undo is an event of the vocabulary of the sandbox and the projector resolves the markers, so the state of the
branch stays a pure function of the base and of the log, and the hash of a branch can be recomputed from the log
alone (FR-009, FR-010).
"""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest

from ledgerlens.run_context import canonical_session_id
from ledgerlens.sandbox.branch import (
    BranchExpired,
    BranchHashMismatch,
    BranchLayer,
    SandboxBranch,
)
from ledgerlens.sandbox.mutation import (
    UNDO_KIND,
    MutationCommand,
    MutationRejected,
    status_for_code,
)
from ledgerlens.sandbox.projector import (
    EVENT_BRANCH_UNDONE,
    EVENT_REFUND_FX_ADJUSTED,
    UNDO_COMMAND_ID,
    project,
    undo_marks,
)
from ledgerlens.sandbox.snapshot import BaseSnapshot
from ledgerlens.sandbox.store import BranchNotFound, BranchStore, SandboxEventRow

# The resource `Error` of the contract of the design package.
ERROR_KEYS = {"code", "message", "retryable", "request_id"}


def _command(payload: dict[str, object], key: str, revision: int = 0) -> MutationCommand:
    """A command with the given payload, key and expected revision."""
    return MutationCommand(
        kind="refund.apply_fx_adjustment",
        payload=payload,
        expected_revision=revision,
        idempotency_key=key,
    )


def _undo(key: str = "undo-0001", revision: int = 1) -> MutationCommand:
    """The command of the undo: the kind of the undo, an empty payload, the key and the expected revision.

    Why the payload is empty: the undo does not change a record of the case, it changes the log of the branch, and
    the machinery of the idempotency only needs the key and the digest of the payload (ADR-024).
    """
    return MutationCommand(
        kind=UNDO_KIND,
        payload={},
        expected_revision=revision,
        idempotency_key=key,
    )


def _unknown_event(branch_id: str) -> SandboxEventRow:
    """An event of a kind the interpreter of the vocabulary of the sandbox does not know.

    Why the event exists: the vocabulary is the one of `ledgerlens/sandbox/projector.py`, and an event of another kind
    cannot be applied to the projected rows. No visitor can append one, because the only way to append an event is a
    mutation of the catalog or an undo, and a corruption of the log can.
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


# --- the undo gives the branch the state it had before the mutation ------------------------------------------


def test_the_undo_gives_the_branch_the_hash_of_the_revision_zero_and_the_revision_back_at_zero(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment: MutationCommand,
) -> None:
    """FR-037: the canonical hash after the undo is the hash of the previous state, and the revision goes back."""
    before = layer.status(session_id, forked_branch.branch_id)
    layer.commit_mutation(session_id, forked_branch.branch_id, adjustment)
    result = layer.undo(session_id, forked_branch.branch_id, _undo(revision=1))
    after = layer.status(session_id, forked_branch.branch_id)

    assert result.revision == 0
    assert after.revision == 0
    assert result.canonical_hash == before.current_canonical_hash
    assert after.current_canonical_hash == before.current_canonical_hash


def test_the_undo_of_the_second_mutation_gives_the_state_the_branch_had_after_the_first_one(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment_payload: dict[str, object],
) -> None:
    """The undone event is the last live mutation, so the state the branch returns to is the state before it."""
    first = layer.commit_mutation(session_id, forked_branch.branch_id, _command(adjustment_payload, "cmd-0001"))
    layer.commit_mutation(
        session_id,
        forked_branch.branch_id,
        _command({**adjustment_payload, "applied_rate": "5.45000000"}, "cmd-0002", 1),
    )
    layer.undo(session_id, forked_branch.branch_id, _undo(revision=2))
    after = layer.status(session_id, forked_branch.branch_id)

    assert after.revision == 1
    assert after.current_canonical_hash == first.canonical_hash


# --- the history stays append only ---------------------------------------------------------------------------


def test_the_log_keeps_the_undone_event_and_adds_the_marker(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment: MutationCommand,
    store: BranchStore,
    owner_session: str,
) -> None:
    """FR-037: the history is append only, so the undone event stays and the undo is a new event."""
    layer.commit_mutation(session_id, forked_branch.branch_id, adjustment)
    layer.undo(session_id, forked_branch.branch_id, _undo(revision=1))
    events = store.read_events(forked_branch.branch_id, owner_session)

    assert [event.event_type for event in events] == [EVENT_REFUND_FX_ADJUSTED, EVENT_BRANCH_UNDONE]
    assert events[0].origin == "sandbox"
    assert events[1].origin == "sandbox"


def test_the_marker_names_the_event_it_undoes_and_the_request_that_produced_it(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment: MutationCommand,
    store: BranchStore,
    owner_session: str,
) -> None:
    """The marker carries the uid of the undone event and the command id of the request that produced it."""
    layer.commit_mutation(session_id, forked_branch.branch_id, adjustment)
    layer.undo(session_id, forked_branch.branch_id, _undo(revision=1))
    events = store.read_events(forked_branch.branch_id, owner_session)
    undone, marker = events

    assert marker.payload["undone_event_uid"] == undone.event_uid
    assert marker.payload["undone_command_id"] == undone.command_id
    assert marker.command_id != undone.command_id


def test_the_undone_event_is_marked_as_undone_in_the_history(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment: MutationCommand,
    store: BranchStore,
    owner_session: str,
) -> None:
    """The mark is derived from the log, so it cannot drift away from the truth (ADR-024).

    The history of the branch keeps the undone event, and the answer the branch remembers for the request that
    produced it carries the mark that it was undone. The two marks never overlap: the answer of the undone mutation
    says that it was undone and names no event, and the answer of the undo names the event it undid and says that it
    is not an undone mutation.
    """
    layer.commit_mutation(session_id, forked_branch.branch_id, adjustment)
    layer.undo(session_id, forked_branch.branch_id, _undo(revision=1))
    events = store.read_events(forked_branch.branch_id, owner_session)

    marks = undo_marks(events)
    assert events[0].event_uid in marks.undone_event_uids
    answers = layer.answers(session_id, forked_branch.branch_id)
    by_key = {answer.idempotency_key: answer for answer in answers}
    # The answer of the mutation that was undone says that the mutation was undone, and names no event.
    assert by_key["cmd-0001"].undone is True
    assert by_key["cmd-0001"].undone_event_uid is None
    # The answer of the undo names the event it undid, and it is not an undone mutation.
    assert by_key["undo-0001"].undone is False
    assert by_key["undo-0001"].undone_event_uid == events[0].event_uid


def test_the_answer_of_the_undo_names_the_event_it_undid_and_is_not_an_undone_mutation(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment: MutationCommand,
    store: BranchStore,
    owner_session: str,
) -> None:
    """The two marks of the undo are two fields with two meanings, and they never overlap (ADR-024).

    The answer of the undo carries the uid of the event it undid, because that is the event the reader of the
    history is looking for, and it says that it is not an undone mutation, because an undo can never be undone.
    """
    layer.commit_mutation(session_id, forked_branch.branch_id, adjustment)
    result = layer.undo(session_id, forked_branch.branch_id, _undo(revision=1))
    events = store.read_events(forked_branch.branch_id, owner_session)

    assert result.undone is False
    assert result.undone_event_uid == events[0].event_uid


# --- the refusal of an undo that has nothing to undo ----------------------------------------------------------


def test_an_undo_on_a_branch_at_revision_zero_is_refused_with_NOTHING_TO_UNDO(
    layer: BranchLayer, session_id: str, forked_branch: SandboxBranch, event_count
) -> None:
    """FR-038: the refusal is a conflict, and the branch stays untouched."""
    with pytest.raises(MutationRejected) as refusal:
        layer.undo(session_id, forked_branch.branch_id, _undo(revision=0))

    assert refusal.value.code == "NOTHING_TO_UNDO"
    assert status_for_code("NOTHING_TO_UNDO") == 409
    assert event_count(forked_branch.branch_id) == 0
    assert layer.status(session_id, forked_branch.branch_id).revision == 0


def test_an_undo_on_a_branch_whose_only_mutation_was_undone_is_refused_with_NOTHING_TO_UNDO(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment: MutationCommand,
    event_count,
) -> None:
    """A second undo has nothing left to undo, because the marker took the mutation out of the live log."""
    layer.commit_mutation(session_id, forked_branch.branch_id, adjustment)
    layer.undo(session_id, forked_branch.branch_id, _undo(key="undo-0001", revision=1))
    with pytest.raises(MutationRejected) as refusal:
        layer.undo(session_id, forked_branch.branch_id, _undo(key="undo-0002", revision=0))

    assert refusal.value.code == "NOTHING_TO_UNDO"
    assert event_count(forked_branch.branch_id) == 2


# --- the idempotency of the undo ------------------------------------------------------------------------------


def test_the_same_request_with_the_same_key_answers_the_identical_answer_and_appends_nothing(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment: MutationCommand,
    event_count,
) -> None:
    """FR-012: the second delivery of the undo is answered with the answer that was stored.

    The reason is concrete: a second delivery that was not answered with the stored answer would undo another
    mutation, because it would find another mutation to undo.
    """
    layer.commit_mutation(session_id, forked_branch.branch_id, adjustment)
    first = layer.undo(session_id, forked_branch.branch_id, _undo(key="undo-0001", revision=1))
    second = layer.undo(session_id, forked_branch.branch_id, _undo(key="undo-0001", revision=1))

    assert second.to_dict() == {**first.to_dict(), "replayed": True}
    assert second.revision == first.revision
    assert second.canonical_hash == first.canonical_hash
    assert event_count(forked_branch.branch_id) == 2


def test_the_same_key_with_another_payload_is_refused_with_IDEMPOTENCY_MISMATCH(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment: MutationCommand,
    event_count,
) -> None:
    """FR-013: the key is bound to the payload it was seen with, and nothing is written."""
    layer.commit_mutation(session_id, forked_branch.branch_id, adjustment)
    with pytest.raises(MutationRejected) as refusal:
        layer.undo(session_id, forked_branch.branch_id, _undo(key="cmd-0001", revision=1))

    assert refusal.value.code == "IDEMPOTENCY_MISMATCH"
    assert event_count(forked_branch.branch_id) == 1
    assert layer.status(session_id, forked_branch.branch_id).revision == 1


def test_an_undo_with_a_stale_expected_revision_is_refused_with_REVISION_CONFLICT(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment: MutationCommand,
    event_count,
) -> None:
    """FR-014: a request that was never seen has to carry the current revision of the branch."""
    layer.commit_mutation(session_id, forked_branch.branch_id, adjustment)
    with pytest.raises(MutationRejected) as refusal:
        layer.undo(session_id, forked_branch.branch_id, _undo(key="undo-0002", revision=0))

    assert refusal.value.code == "REVISION_CONFLICT"
    assert event_count(forked_branch.branch_id) == 1
    assert layer.status(session_id, forked_branch.branch_id).revision == 1


# --- the key of a request that was undone ---------------------------------------------------------------------


def test_the_key_of_a_request_that_was_undone_stays_bound_to_that_request(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment: MutationCommand,
    event_count,
) -> None:
    """The key of a request of the past stays bound to that request (ADR-024).

    The answers survive an undo, exactly as they survive a reset, so a request that arrives again with the key of a
    mutation that was undone is answered with the answer that was stored, marked as undone, and it never commits a
    second time. The visitor that wants to apply the same change again sends a new key.
    """
    committed = layer.commit_mutation(session_id, forked_branch.branch_id, adjustment)
    layer.undo(session_id, forked_branch.branch_id, _undo(revision=1))
    replayed = layer.commit_mutation(session_id, forked_branch.branch_id, adjustment)

    assert replayed.replayed is True
    assert replayed.revision == committed.revision
    assert replayed.canonical_hash == committed.canonical_hash
    assert replayed.diff == committed.diff
    # The answer is marked as undone, and it names no event, because it is the answer of a mutation.
    assert replayed.undone is True
    assert replayed.undone_event_uid is None
    # The branch did not commit a second time: the log still holds the mutation and the marker, and the revision of
    # the branch is the one the undo left.
    assert event_count(forked_branch.branch_id) == 2
    assert layer.status(session_id, forked_branch.branch_id).revision == 0


# --- the mark of the undo is the log ----------------------------------------------------------------------------


def test_the_mark_of_the_undo_follows_the_log_of_the_branch_and_not_a_stored_value(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment: MutationCommand,
    store: BranchStore,
    owner_session: str,
    tamper_events,
) -> None:
    """The mark of the undo is derived from the log, so a corruption of the log moves the mark (ADR-024).

    The tamper is one no visitor can make: the marker of the undo names another request as the one it undid. The
    projection of the branch does not change, because the marker still undoes the same event, but the truth of the log
    about the requests changed, and the marks of the answers follow the log and not a value stored with the answer.
    """
    layer.commit_mutation(session_id, forked_branch.branch_id, adjustment)
    layer.undo(session_id, forked_branch.branch_id, _undo(revision=1))
    events = store.read_events(forked_branch.branch_id, owner_session)
    before = {answer.idempotency_key: answer for answer in layer.answers(session_id, forked_branch.branch_id)}

    assert before["cmd-0001"].undone is True
    assert before["cmd-0001"].undone_event_uid is None
    assert before["undo-0001"].undone is False
    assert before["undo-0001"].undone_event_uid == events[0].event_uid

    marker = events[1]
    corrupted = replace(marker, payload={**marker.payload, UNDO_COMMAND_ID: "cmd-0002"})
    tamper_events(forked_branch.branch_id, [events[0], corrupted])

    # The state of the branch did not change, so the branch still proves its own state.
    assert layer.status(session_id, forked_branch.branch_id).revision == 0
    after = {answer.idempotency_key: answer for answer in layer.answers(session_id, forked_branch.branch_id)}

    # The log says that the request of the key cmd-0001 was not undone, so the answer says so.
    assert after["cmd-0001"].undone is False
    assert after["cmd-0001"].undone_event_uid is None
    # The log still says that the undo took back the event, so the answer of the undo still names it.
    assert after["undo-0001"].undone is False
    assert after["undo-0001"].undone_event_uid == events[0].event_uid


# --- a log that cannot be projected ------------------------------------------------------------------------------


def test_a_branch_whose_log_cannot_be_projected_is_refused_with_HASH_MISMATCH(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    store: BranchStore,
    owner_session: str,
) -> None:
    """A log that cannot be projected is a branch that cannot prove its own state (ADR-021, ADR-024).

    The event of an unknown kind is in the log of the branch, and the interpreter of the vocabulary cannot apply it
    to the projected rows. The branch therefore cannot prove its own state, and it is refused with the same code and
    the same message as a branch whose row does not agree with its events.
    """
    store.append_events(forked_branch.branch_id, owner_session, [_unknown_event(forked_branch.branch_id)])

    with pytest.raises(BranchHashMismatch) as refusal:
        layer.status(session_id, forked_branch.branch_id)

    assert refusal.value.code == "HASH_MISMATCH"
    assert "fork" in refusal.value.message


def test_the_undo_of_a_branch_whose_log_cannot_be_projected_is_refused_with_HASH_MISMATCH(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment: MutationCommand,
    store: BranchStore,
    owner_session: str,
) -> None:
    """The verification of the branch is shared, so the undo refuses the same log the status refuses."""
    layer.commit_mutation(session_id, forked_branch.branch_id, adjustment)
    store.append_events(forked_branch.branch_id, owner_session, [_unknown_event(forked_branch.branch_id)])

    with pytest.raises(BranchHashMismatch) as refusal:
        layer.undo(session_id, forked_branch.branch_id, _undo(revision=1))

    assert refusal.value.code == "HASH_MISMATCH"
    assert "fork" in refusal.value.message


# --- the log is the truth -------------------------------------------------------------------------------------


def test_the_hash_of_the_branch_after_the_undo_is_recomputed_from_the_log_alone(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment: MutationCommand,
    base_snapshot: BaseSnapshot,
    store: BranchStore,
    owner_session: str,
) -> None:
    """FR-009 and FR-010: the state is a pure function of the base and of the log, undo marker included."""
    layer.commit_mutation(session_id, forked_branch.branch_id, adjustment)
    result = layer.undo(session_id, forked_branch.branch_id, _undo(revision=1))
    events = store.read_events(forked_branch.branch_id, owner_session)
    rebuilt = project(base_snapshot, events)

    assert rebuilt.canonical_hash == result.canonical_hash
    assert rebuilt.canonical_hash == base_snapshot.canonical_hash


def test_the_invariants_and_the_verdict_after_the_undo_are_the_ones_of_the_state_before_the_undone_mutation(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment_payload: dict[str, object],
) -> None:
    """The undo returns a state the branch already held, so its rules and its verdict are the ones of that state.

    The state before the undone mutation is the state the branch was in after the first commit, so the rules and the
    verdict of the undo are the ones that commit reported.
    """
    first = layer.commit_mutation(session_id, forked_branch.branch_id, _command(adjustment_payload, "cmd-0001"))
    layer.commit_mutation(
        session_id,
        forked_branch.branch_id,
        _command({**adjustment_payload, "applied_rate": "5.45000000"}, "cmd-0002", 1),
    )
    result = layer.undo(session_id, forked_branch.branch_id, _undo(revision=2))

    assert list(result.invariants) == list(first.invariants)
    assert result.verdict == first.verdict


def test_the_diff_of_the_undo_is_the_reverse_of_the_diff_of_the_undone_mutation(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment: MutationCommand,
) -> None:
    """The diff of the undo names the values the undo put back, with the values of the two states on both sides."""
    committed = layer.commit_mutation(session_id, forked_branch.branch_id, adjustment)
    result = layer.undo(session_id, forked_branch.branch_id, _undo(revision=1))

    assert [(entry["record_id"], entry["field"]) for entry in result.diff] == [
        (entry["record_id"], entry["field"]) for entry in committed.diff
    ]
    assert result.diff[0]["before"] == committed.diff[0]["after"]
    assert result.diff[0]["after"] == committed.diff[0]["before"]


# --- the reset of a branch that carries an undo ---------------------------------------------------------------


def test_the_reset_of_a_branch_with_an_undo_in_its_log_leaves_the_branch_at_the_base(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment: MutationCommand,
    event_count,
) -> None:
    """The reset drops every event of the branch, the marker included, and gives the branch the hash of the fork."""
    layer.commit_mutation(session_id, forked_branch.branch_id, adjustment)
    layer.undo(session_id, forked_branch.branch_id, _undo(revision=1))
    branch = layer.reset(session_id, forked_branch.branch_id)

    assert branch.revision == 0
    assert branch.current_canonical_hash == branch.base_canonical_hash
    assert event_count(forked_branch.branch_id) == 0


# --- the refusals of the undo ----------------------------------------------------------------------------------


def test_the_undo_of_the_branch_of_another_session_is_refused_with_the_generic_error(
    layer: BranchLayer,
    session_id: str,
    other_session_id: str,
    forked_branch: SandboxBranch,
    adjustment: MutationCommand,
) -> None:
    """The refusal says nothing about the owner and nothing about the existence of the branch."""
    layer.commit_mutation(session_id, forked_branch.branch_id, adjustment)
    with pytest.raises(BranchNotFound):
        layer.undo(other_session_id, forked_branch.branch_id, _undo(revision=1))


def test_the_undo_of_an_expired_branch_is_refused_with_BranchExpired(
    layer: BranchLayer, session_id: str, forked_branch: SandboxBranch, adjustment: MutationCommand, clock
) -> None:
    """An expired branch is refused, and the refusal names the state of the branch."""
    layer.commit_mutation(session_id, forked_branch.branch_id, adjustment)
    clock.advance(timedelta(hours=2))
    with pytest.raises(BranchExpired):
        layer.undo(session_id, forked_branch.branch_id, _undo(revision=1))


def test_the_undo_of_a_branch_that_cannot_prove_its_state_is_refused_with_HASH_MISMATCH(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment: MutationCommand,
    tamper_events,
) -> None:
    """A branch that cannot prove its own state is refused before it moves anything (ADR-021, FR-032)."""
    layer.commit_mutation(session_id, forked_branch.branch_id, adjustment)
    # The crash of a commit that wrote the row of the branch and lost the events of the branch.
    tamper_events(forked_branch.branch_id, [])
    with pytest.raises(BranchHashMismatch) as refusal:
        layer.undo(session_id, forked_branch.branch_id, _undo(revision=1))

    assert refusal.value.code == "HASH_MISMATCH"
    assert "fork" in refusal.value.message


# --- the published artifacts -----------------------------------------------------------------------------------


def test_the_undo_writes_nothing_to_a_published_file(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment: MutationCommand,
    published_digests: dict[str, str | None],
) -> None:
    """FR-001: the undo works on the branch and never on the published snapshot."""
    project_root = Path(__file__).resolve().parents[2]
    layer.commit_mutation(session_id, forked_branch.branch_id, adjustment)
    layer.undo(session_id, forked_branch.branch_id, _undo(revision=1))

    for name, digest in published_digests.items():
        path = project_root / "data" / name
        current = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
        assert current == digest


# --- the route of the undo --------------------------------------------------------------------------------------


@pytest.fixture
def app(store: BranchStore, base_resolver, clock):
    """The facade of the contract, over the store of the test."""
    pytest.importorskip("fastapi")
    from ledgerlens.api.sandbox import create_app

    return create_app(store=store, base_resolver=base_resolver, clock=clock)


@pytest.fixture
def client(app):
    """A client of the facade with a session of its own."""
    from fastapi.testclient import TestClient

    http = TestClient(app)
    assert http.post("/v1/sessions").status_code == 201
    return http


def _fork(http, scenario_id: str) -> str:
    """The identifier of the branch the client owns."""
    return http.post("/v1/sandboxes", json={"scenario_id": scenario_id}).json()["id"]


def _commit(http, branch_id: str, payload: dict[str, object], key: str = "cmd-0001", revision: int = 0):
    """The commit of a mutation through the route of the contract."""
    return http.post(
        f"/v1/sandboxes/{branch_id}/mutations",
        json={"kind": "refund.apply_fx_adjustment", "data": payload},
        headers={"Idempotency-Key": key, "If-Match": str(revision)},
    )


def _undo_request(http, branch_id: str, key: str = "undo-0001", revision: int = 1):
    """The undo through the route of the contract."""
    return http.post(
        f"/v1/sandboxes/{branch_id}/undo",
        headers={"Idempotency-Key": key, "If-Match": str(revision)},
    )


def test_the_route_of_the_undo_answers_the_shape_of_the_answer_of_a_commit(
    client, scenario_id: str, adjustment_payload: dict[str, object]
) -> None:
    """The answer of the undo is the answer of a commit, plus the uid of the event it undid (ADR-024).

    The two marks of the undo never overlap: the answer of the undo names the event it undid and says that it is
    not an undone mutation, because an undo can never be undone.
    """
    branch_id = _fork(client, scenario_id)
    committed = _commit(client, branch_id, adjustment_payload).json()
    response = _undo_request(client, branch_id)
    assert response.status_code == 200
    body = response.json()

    assert set(body) == set(committed)
    assert body["revision"] == 0
    assert body["undone"] is False
    assert body["undone_event_uid"]
    assert body["kind"] == UNDO_KIND


def test_the_route_of_the_undo_answers_the_version_of_the_schema(client, scenario_id: str, adjustment_payload) -> None:
    """FR-042: every answer of the facade carries the version of the shape of the answers."""
    from ledgerlens.api.sandbox import SCHEMA_VERSION, SCHEMA_VERSION_HEADER

    branch_id = _fork(client, scenario_id)
    _commit(client, branch_id, adjustment_payload)
    response = _undo_request(client, branch_id)
    assert response.headers[SCHEMA_VERSION_HEADER] == SCHEMA_VERSION


def test_the_route_of_the_undo_answers_the_same_request_the_same_way(
    client, scenario_id: str, adjustment_payload: dict[str, object]
) -> None:
    """FR-012: the second delivery of the undo is answered with the answer that was stored.

    The route sends the key of the request in the `Idempotency-Key` header, so the second delivery is answered with
    the answer of the first one and the branch keeps one marker.
    """
    branch_id = _fork(client, scenario_id)
    _commit(client, branch_id, adjustment_payload)
    first = _undo_request(client, branch_id, key="undo-0001", revision=1)
    second = _undo_request(client, branch_id, key="undo-0001", revision=1)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == {**first.json(), "replayed": True}
    assert client.get(f"/v1/sandboxes/{branch_id}").json()["revision"] == 0
    # A request with another key is another request, and the branch is at revision zero, so the expected revision it
    # carries is stale and the request is refused. The key of the route is therefore the key of the request.
    other = _undo_request(client, branch_id, key="undo-0002", revision=1)
    assert other.status_code == 409
    assert other.json()["code"] == "REVISION_CONFLICT"


def test_the_route_of_the_undo_refuses_a_branch_that_has_nothing_to_undo_with_409(
    client, scenario_id: str
) -> None:
    """FR-038: the route answers the code of the contract."""
    branch_id = _fork(client, scenario_id)
    response = _undo_request(client, branch_id, revision=0)
    assert response.status_code == 409
    body = response.json()
    assert set(body) == ERROR_KEYS
    assert body["code"] == "NOTHING_TO_UNDO"


def test_the_route_of_the_undo_refuses_a_stale_expected_revision_with_409(
    client, scenario_id: str, adjustment_payload: dict[str, object]
) -> None:
    """FR-014: a stale expected revision is a conflict."""
    branch_id = _fork(client, scenario_id)
    _commit(client, branch_id, adjustment_payload)
    response = _undo_request(client, branch_id, key="undo-0002", revision=0)
    assert response.status_code == 409
    assert response.json()["code"] == "REVISION_CONFLICT"


def test_the_route_of_the_undo_refuses_the_branch_of_another_session_with_404(app, client, scenario_id: str) -> None:
    """The refusal says nothing about the owner and nothing about the existence of the branch."""
    from fastapi.testclient import TestClient

    branch_id = _fork(client, scenario_id)
    other = TestClient(app)
    assert other.post("/v1/sessions").status_code == 201
    response = other.post(
        f"/v1/sandboxes/{branch_id}/undo",
        headers={"Idempotency-Key": "undo-0001", "If-Match": "0"},
    )
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_the_route_of_the_undo_refuses_an_expired_branch_with_410(client, scenario_id: str, clock) -> None:
    """An expired branch answers 410 with the code of the contract."""
    branch_id = _fork(client, scenario_id)
    clock.advance(timedelta(hours=2))
    response = _undo_request(client, branch_id)
    assert response.status_code == 410
    assert response.json()["code"] == "BRANCH_EXPIRED"


def test_the_route_of_the_undo_refuses_a_branch_that_cannot_prove_its_state_with_409(
    client, scenario_id: str, adjustment_payload: dict[str, object], tamper_events
) -> None:
    """A branch that cannot prove its own state answers 409 with the code of the contract."""
    branch_id = _fork(client, scenario_id)
    _commit(client, branch_id, adjustment_payload)
    # The crash of a commit that wrote the row of the branch and lost the events of the branch.
    tamper_events(branch_id, [])
    response = _undo_request(client, branch_id)
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "HASH_MISMATCH"
    assert "fork" in body["message"]


# --- the route of a log that cannot be projected ------------------------------------------------------------------


def _client_that_shows_the_failures(app):
    """A client of the facade that answers with the error of the server instead of raising it.

    Why it exists: the answer of a branch that cannot prove its own state is a refusal with a status, and a client
    that raises the failure of the server cannot show that the status is a 409 and not a 500.
    """
    from fastapi.testclient import TestClient

    return TestClient(app, raise_server_exceptions=False)


def test_the_route_of_the_status_of_a_branch_whose_log_cannot_be_projected_answers_409(
    app, scenario_id: str, store: BranchStore
) -> None:
    """A log that cannot be projected is a branch that cannot prove its own state, and it answers 409 (ADR-024).

    The answer is the one of the contract, with the code `HASH_MISMATCH` and a message that offers a fresh fork. It
    is not a 500: a visitor must never see the failure of the server.
    """
    http = _client_that_shows_the_failures(app)
    session = http.post("/v1/sessions").json()["id"]
    branch_id = http.post("/v1/sandboxes", json={"scenario_id": scenario_id}).json()["id"]
    store.append_events(branch_id, canonical_session_id(session), [_unknown_event(branch_id)])

    response = http.get(f"/v1/sandboxes/{branch_id}")

    assert response.status_code == 409
    body = response.json()
    assert set(body) == ERROR_KEYS
    assert body["code"] == "HASH_MISMATCH"
    assert "fork" in body["message"]


def test_the_route_of_the_undo_of_a_branch_whose_log_cannot_be_projected_answers_409(
    app, scenario_id: str, store: BranchStore
) -> None:
    """The verification of the branch is shared, so the route of the undo refuses the log the status refuses."""
    http = _client_that_shows_the_failures(app)
    session = http.post("/v1/sessions").json()["id"]
    branch_id = http.post("/v1/sandboxes", json={"scenario_id": scenario_id}).json()["id"]
    store.append_events(branch_id, canonical_session_id(session), [_unknown_event(branch_id)])

    response = _undo_request(http, branch_id)

    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "HASH_MISMATCH"
    assert "fork" in body["message"]
