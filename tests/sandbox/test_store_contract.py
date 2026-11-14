"""The contract of the branch store: one suite, run against every implementation of the protocol.

Why it exists: ADR-018 and ADR-020 ask for the file backed store and the database store to behave identically under
the same test suite (FR-040, SC-015). So the suite below is written once, and the `store` fixture of `conftest.py`
decides which implementation it runs against. Every test of this file therefore runs twice, once for each store.

The last test of the file is the comparison itself: the same sequence of operations is applied to the two stores and
the answers have to be the same, so the comparison is a real comparison and not two separate suites.

Five guards of the file are about one implementation alone, because the property they prove is a property of the
files on the disk or of the shape of the tables: the file store loads a file written before the generation existed,
the file of another visitor is never read, the commit of the file store writes the events before the row, the script
of the schema brings a database of the old shape to the shape of the code, and the product module of the database
store holds no scaffolding that only a test uses. That scaffolding lives in `tests/sandbox/postgres_tools.py`, the
module of the tests that carries the shape of the tables before the generation and the helpers that only the tests
need (ADR-022).

The file also holds the choice of the store: the configuration names the database, and the factory turns that name
into the implementation of the protocol.

The file holds the races as well: two writes that cross on the same branch have to leave one winner and one
refusal, in the two implementations alike (ADR-026). The races are run with two real threads and not with a mock
of the lock, because the lock is the promise and a mock would only prove that the mock works.
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from ledgerlens.config import Settings, get_settings
from ledgerlens.run_context import canonical_session_id
from ledgerlens.sandbox.branch import BranchHashMismatch, BranchLayer
from ledgerlens.sandbox.factory import build_branch_store
from ledgerlens.sandbox.mutation import (
    MutationCommand,
    build_undo_event,
    payload_digest,
    plan_mutation,
)
from ledgerlens.sandbox.postgres_store import PostgresBranchStore, apply_schema
from ledgerlens.sandbox.projector import EVENT_BRANCH_UNDONE
from ledgerlens.sandbox.store import (
    BranchNotFound,
    BranchRevisionConflict,
    BranchStore,
    FileBranchStore,
    SandboxBranchRow,
    SandboxCommandRow,
    SandboxEventRow,
)

from .postgres_tools import (
    columns_of,
    create_old_shape,
    drop_schema,
    url_with_search_path,
    write_answer_at,
)

# The moments of the fixtures. They are fixed and not the clock of the machine, so the two stores are compared on
# the same values.
NOW = datetime(2026, 11, 14, 12, 0, 0, tzinfo=UTC)
ALIVE_AT = NOW + timedelta(hours=1)
DEAD_AT = NOW - timedelta(hours=1)

OWNER = "Visitor-A"
OTHER_OWNER = "visitor-b"

# The time the two threads of a race wait for each other. It is long enough for a slow machine and short enough
# for a suite that runs offline.
BARRIER_TIMEOUT = 30.0

# The sessions of the races: one branch per round, so a round that does not cross does not decide the next one.
# The race is run more than once because two writes that cross is a race, and a race that does not happen in one
# round is not a proof that the store does not lose anything.
RACE_SESSIONS = ("race-visitor-1", "race-visitor-2", "race-visitor-3")


def _row(
    branch_id: str = "sb_" + "a" * 24,
    owner_session: str = OWNER,
    scenario_id: str = "S01",
    expires_at: datetime = ALIVE_AT,
) -> SandboxBranchRow:
    """A row of a branch, as the store keeps it."""
    return SandboxBranchRow(
        branch_id=branch_id,
        owner_session=owner_session,
        scenario_id=scenario_id,
        base_snapshot_id="sample-42",
        base_canonical_hash="0" * 64,
        revision=0,
        current_canonical_hash="0" * 64,
        created_at=NOW,
        last_activity_at=NOW,
        expires_at=expires_at,
        state="active",
    )


def _event(branch_id: str, event_uid: str = "evt-1") -> SandboxEventRow:
    """An event of a branch, as the store keeps it."""
    return SandboxEventRow(
        event_uid=event_uid,
        branch_id=branch_id,
        event_type="refund.fx_adjusted",
        aggregate_id="R-0731",
        occurred_at="2026-11-14T10:00:00Z",
        payload={"kind": "settlement", "rate": "5.41250000"},
    )


def _marker(branch_id: str, event_uid: str = "evt-2") -> SandboxEventRow:
    """The marker of an undo, as the store keeps it.

    The marker names the event it undoes and the command id of the request that produced it, and it changes no row
    (ADR-024). The store stores it and never reads it.
    """
    return SandboxEventRow(
        event_uid=event_uid,
        branch_id=branch_id,
        event_type="sandbox.branch.undone",
        aggregate_id="R-0731",
        occurred_at="2026-11-14T11:00:00Z",
        payload={"undone_event_uid": "evt-1", "undone_command_id": "cmd-0001"},
    )


def _answer(
    branch_id: str, key: str = "cmd-0001", revision: int = 1, canonical_hash: str = "1" * 64
) -> SandboxCommandRow:
    """The answer of a request, as the store keeps it."""
    return SandboxCommandRow(
        branch_id=branch_id,
        idempotency_key=key,
        payload_digest="d" * 64,
        revision=revision,
        canonical_hash=canonical_hash,
        response_diff=[
            {
                "record": "refunds",
                "record_id": "R-0731",
                "field": "payout_amount_minor",
                "before": "549.31",
                "after": "541.25",
                "value_kind": "monetary",
                "currency": "BRL",
            }
        ],
        response_verdict={"label": "above_expected_range"},
        response_invariants=[{"identifier": "fx_rate_positive_and_finite", "passed": True}],
    )


def _undo_answer(branch_id: str, key: str = "cmd-0002") -> SandboxCommandRow:
    """The answer of an undo, as the store keeps it: the revision goes back and the hash is the one of the base."""
    return _answer(branch_id, key, revision=0, canonical_hash="0" * 64)


def _refusal(action: Any) -> tuple[str, str]:
    """The name of the error and its message, or the mark of an answer that was not a refusal.

    Why it exists: the two stores refuse a broken reset in two different ways, and the test is about the fact that
    they refused and not about the kind of the refusal.
    """
    try:
        action()
    except Exception as exc:  # noqa: BLE001 - the answer of the store is what the comparison is about
        return (type(exc).__name__, str(exc))
    return ("no refusal", "")


def _write_fails_on(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    """Makes the write of the file with this name fail, the way a full disk or a permission error makes it fail.

    Why it exists: the promise of the store is that a commit that fails leaves the branch exactly where it was, and
    the only way to prove it is to make one of the writes of the store fail on purpose. The other writes go
    through, so the test sees a branch whose write of the row, of the events or of the answers failed, and not a
    store that is broken everywhere.
    """
    from ledgerlens.sandbox import store as store_module

    original = store_module._write_atomic

    def failing(path: Path, text: str) -> None:
        if path.name == name:
            raise OSError("the disk is full")
        original(path, text)

    monkeypatch.setattr(store_module, "_write_atomic", failing)


def _files_of_the_branch(file_store: FileBranchStore) -> dict[str, str | None]:
    """The content of the three files of the branch, as the store keeps them on the disk.

    Why it exists: the branch is proved by its files, and a branch that looks right through the store and is wrong
    on the disk is a broken branch. The content is read as text, because the file is compared with the file it was
    before the failure, and the name of a file that is not there is the mark of its absence.
    """
    folder = next(path for path in sorted(file_store.root.glob(f"{OWNER}/*")) if path.is_dir())
    files: dict[str, str | None] = {}
    for name in (FileBranchStore.EVENTS_FILE, FileBranchStore.COMMANDS_FILE, FileBranchStore.BRANCH_FILE):
        path = folder / name
        files[name] = path.read_text(encoding="utf-8") if path.exists() else None
    return files


def _unknown_event(branch_id: str) -> SandboxEventRow:
    """An event of a kind the interpreter of the vocabulary of the sandbox does not know.

    Why the event exists: the vocabulary is the one of `ledgerlens/sandbox/projector.py`, and an event of another
    kind cannot be applied to the projected rows. No visitor can append one, and a corruption of the log can.
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


def _two_threads_that_cross(action: Callable[[], Any]) -> list[tuple[str, Any]]:
    """Runs the action in two threads that really cross, and returns what each one of them answered.

    Why the barrier: two writes that cross are the case the store has to refuse, and two writes that do not cross
    prove nothing. The barrier releases the two threads at the same moment, so the second one finds the branch in
    the state the first one is changing (ADR-026).

    Why the answer of every thread is kept: the test is about the loser of the race, so the refusal of the loser
    has to be seen and not only the state of the branch afterwards.
    """
    barrier = threading.Barrier(2)
    outcomes: list[tuple[str, Any]] = []

    def run() -> None:
        try:
            barrier.wait(timeout=BARRIER_TIMEOUT)
        except threading.BrokenBarrierError as failure:
            outcomes.append(("no answer", failure))
            return
        try:
            outcomes.append(("written", action()))
        except Exception as exc:  # noqa: BLE001 - the refusal of the loser is what the test is about
            outcomes.append(("refused", exc))

    threads = [threading.Thread(target=run) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=BARRIER_TIMEOUT)
    return outcomes


def _one_winner_and_one_refusal(outcomes: list[tuple[str, Any]]) -> None:
    """Asserts that one of the two writes won and that the other one was refused with the conflict of the revision."""
    written = [value for kind, value in outcomes if kind == "written"]
    refused = [value for kind, value in outcomes if kind == "refused"]
    assert len(written) == 1, f"the race had {len(written)} winners and {len(refused)} refusals: {outcomes}"
    assert len(refused) == 1, f"the race had {len(written)} winners and {len(refused)} refusals: {outcomes}"
    assert isinstance(refused[0], BranchRevisionConflict), f"the loser was refused with {refused[0]!r}"


def _two_commits_that_cross(
    store: BranchStore,
    branch_id: str,
    owner_session: str,
    events: tuple[SandboxEventRow, ...],
    moved: SandboxBranchRow,
    answer: SandboxCommandRow,
) -> list[tuple[str, Any]]:
    """Two commits of the same branch that cross, and what each one of them answered.

    Why the helper: the two commits are made by two threads, and the values of the race belong to the round that
    made them, so they travel as arguments and not as the variables of a loop.
    """
    return _two_threads_that_cross(
        lambda: store.commit_events(branch_id, owner_session, events, moved, answer)
    )


def _two_undos_that_cross(
    store: BranchStore,
    branch_id: str,
    owner_session: str,
    marker: SandboxEventRow,
    undone: SandboxBranchRow,
    answer: SandboxCommandRow,
) -> list[tuple[str, Any]]:
    """Two undos of the same branch that cross, and what each one of them answered."""
    return _two_threads_that_cross(
        lambda: store.commit_undo(branch_id, owner_session, marker, undone, answer)
    )


# --- the creation ---------------------------------------------------------------------------------


def test_the_store_creates_the_branch_and_returns_the_row(store: BranchStore) -> None:
    row = _row()
    assert store.create_branch(row) == row


def test_the_store_refuses_to_create_a_branch_that_already_exists(store: BranchStore) -> None:
    row = _row()
    store.create_branch(row)
    with pytest.raises(ValueError):
        store.create_branch(row)


# --- the read -------------------------------------------------------------------------------------


def test_the_store_reads_the_branch_of_its_owner(store: BranchStore) -> None:
    row = _row()
    store.create_branch(row)
    assert store.get_branch(row.branch_id, OWNER) == row


def test_the_store_reads_the_branch_that_does_not_exist_as_a_missing_one(store: BranchStore) -> None:
    with pytest.raises(BranchNotFound):
        store.get_branch("sb_" + "0" * 24, OWNER)


# --- the listing of the branches of a session -------------------------------------------------------


def test_the_store_lists_the_branches_of_the_session(store: BranchStore) -> None:
    first = _row(branch_id="sb_" + "a" * 24)
    second = _row(branch_id="sb_" + "b" * 24, scenario_id="S02")
    store.create_branch(first)
    store.create_branch(second)
    assert sorted(row.branch_id for row in store.list_branches(OWNER)) == [first.branch_id, second.branch_id]


def test_the_store_lists_no_branch_of_another_session(store: BranchStore) -> None:
    store.create_branch(_row(owner_session=OWNER))
    assert store.list_branches(OTHER_OWNER) == []


# --- the append -----------------------------------------------------------------------------------


def test_the_append_of_an_event_is_idempotent_on_the_event_uid(store: BranchStore) -> None:
    row = _row()
    store.create_branch(row)
    event = _event(row.branch_id)
    first = store.append_events(row.branch_id, OWNER, [event])
    second = store.append_events(row.branch_id, OWNER, [event])
    assert (first.appended, first.duplicates) == (1, 0)
    assert (second.appended, second.duplicates) == (0, 1)
    assert len(store.read_events(row.branch_id, OWNER)) == 1


def test_the_append_counts_the_duplicates_of_the_same_batch(store: BranchStore) -> None:
    row = _row()
    store.create_branch(row)
    event = _event(row.branch_id)
    result = store.append_events(row.branch_id, OWNER, [event, event])
    assert (result.appended, result.duplicates) == (1, 1)
    assert len(store.read_events(row.branch_id, OWNER)) == 1


def test_the_store_refuses_an_event_of_another_branch(store: BranchStore) -> None:
    row = _row()
    store.create_branch(row)
    with pytest.raises(ValueError):
        store.append_events(row.branch_id, OWNER, [_event("sb_" + "f" * 24)])


# --- the read of the events ------------------------------------------------------------------------


def test_the_store_reads_the_events_of_the_branch_in_the_order_of_the_append(store: BranchStore) -> None:
    row = _row()
    store.create_branch(row)
    store.append_events(row.branch_id, OWNER, [_event(row.branch_id, "evt-1")])
    store.append_events(row.branch_id, OWNER, [_event(row.branch_id, "evt-2")])
    read = store.read_events(row.branch_id, OWNER)
    assert [event.event_uid for event in read] == ["evt-1", "evt-2"]


def test_the_store_keeps_the_payload_of_the_event_as_it_was_given(store: BranchStore) -> None:
    row = _row()
    store.create_branch(row)
    event = _event(row.branch_id)
    store.append_events(row.branch_id, OWNER, [event])
    assert store.read_events(row.branch_id, OWNER)[0].payload == event.payload


def test_the_store_reads_no_event_of_a_branch_without_events(store: BranchStore) -> None:
    row = _row()
    store.create_branch(row)
    assert store.read_events(row.branch_id, OWNER) == []


# --- the deletion of the events ---------------------------------------------------------------------


def test_the_store_drops_the_events_of_the_branch(store: BranchStore) -> None:
    row = _row()
    store.create_branch(row)
    store.append_events(row.branch_id, OWNER, [_event(row.branch_id, "evt-1")])
    store.append_events(row.branch_id, OWNER, [_event(row.branch_id, "evt-2")])
    assert store.delete_events(row.branch_id, OWNER) == 2
    assert store.read_events(row.branch_id, OWNER) == []
    assert store.delete_events(row.branch_id, OWNER) == 0


# --- the listing of the expired branches -------------------------------------------------------------


def test_the_store_lists_the_branches_whose_expiry_passed(store: BranchStore) -> None:
    alive = _row(branch_id="sb_" + "a" * 24, expires_at=ALIVE_AT)
    dead = _row(branch_id="sb_" + "b" * 24, expires_at=DEAD_AT)
    store.create_branch(alive)
    store.create_branch(dead)
    expired = store.list_expired(NOW)
    assert [row.branch_id for row in expired] == [dead.branch_id]


def test_the_store_lists_the_expired_branches_of_any_owner(store: BranchStore) -> None:
    dead = _row(branch_id="sb_" + "b" * 24, owner_session=OTHER_OWNER, expires_at=DEAD_AT)
    store.create_branch(dead)
    assert [row.branch_id for row in store.list_expired(NOW)] == [dead.branch_id]


# --- the deletion of a branch -----------------------------------------------------------------------


def test_the_store_drops_the_branch(store: BranchStore) -> None:
    row = _row()
    store.create_branch(row)
    assert store.delete_branch(row.branch_id, OWNER) is True
    with pytest.raises(BranchNotFound):
        store.get_branch(row.branch_id, OWNER)


def test_the_store_drops_the_branch_with_its_events(store: BranchStore) -> None:
    row = _row()
    store.create_branch(row)
    store.append_events(row.branch_id, OWNER, [_event(row.branch_id)])
    store.delete_branch(row.branch_id, OWNER)
    assert store.list_branches(OWNER) == []


# --- the save of a branch ----------------------------------------------------------------------------


def test_the_store_saves_the_row_of_the_branch_again(store: BranchStore) -> None:
    row = _row()
    store.create_branch(row)
    moved = replace(row, revision=1, current_canonical_hash="1" * 64, last_activity_at=NOW, expires_at=ALIVE_AT)
    assert store.save_branch(moved) == moved
    assert store.get_branch(row.branch_id, OWNER) == moved


def test_the_store_refuses_to_save_the_row_of_a_branch_that_does_not_exist(store: BranchStore) -> None:
    with pytest.raises(BranchNotFound):
        store.save_branch(_row())


# --- the touch of the deadline -----------------------------------------------------------------------


def test_the_touch_of_the_deadline_moves_only_the_deadline(store: BranchStore) -> None:
    """ADR-027: the touch of the deadline writes the two fields of the deadline and no other field of the row.

    Why it matters: the deadline is part of the row of the branch, and a write that carries the whole row carries
    the revision and the hash a reader held a moment ago. A mutation that landed between the read and the write
    would be rolled back by it, and the branch would lose the proof of its own state (ADR-021).
    """
    row = _row()
    store.create_branch(row)
    moved = replace(
        row,
        revision=3,
        current_canonical_hash="2" * 64,
        base_canonical_hash="3" * 64,
        generation=2,
    )
    store.save_branch(moved)
    later = NOW + timedelta(minutes=10)
    expiry = later + timedelta(minutes=30)

    touched = store.touch_branch(row.branch_id, OWNER, later, expiry)

    # The state of the branch is the state it had: the revision, the hash, the generation and the base hash.
    assert touched.revision == 3
    assert touched.current_canonical_hash == "2" * 64
    assert touched.generation == 2
    assert touched.base_canonical_hash == "3" * 64
    # The deadline is the only thing that moved.
    assert touched.last_activity_at == later
    assert touched.expires_at == expiry
    # The row the store keeps is the row it handed back.
    assert store.get_branch(row.branch_id, OWNER) == touched


def test_the_store_refuses_to_touch_the_deadline_of_the_branch_of_another_session(store: BranchStore) -> None:
    """ADR-027: the touch of the deadline of a branch of another visitor is refused and writes nothing.

    Why the message is the same as the message of a branch that does not exist: a caller must not be able to tell a
    branch of another visitor from a branch that is not there.
    """
    row = _row()
    store.create_branch(row)
    with pytest.raises(BranchNotFound) as of_other:
        store.touch_branch(row.branch_id, OTHER_OWNER, NOW + timedelta(minutes=10), ALIVE_AT)
    with pytest.raises(BranchNotFound) as of_missing:
        store.touch_branch("sb_" + "0" * 24, OTHER_OWNER, NOW + timedelta(minutes=10), ALIVE_AT)
    assert str(of_other.value) == str(of_missing.value)
    # Nothing was written: the row of the owner is the row it had.
    assert store.get_branch(row.branch_id, OWNER) == row


# --- the refusal of the branch of another session ----------------------------------------------------


def test_the_refusal_of_the_branch_of_another_session_is_the_same_as_the_refusal_of_a_missing_branch(
    store: BranchStore,
) -> None:
    row = _row()
    store.create_branch(row)
    with pytest.raises(BranchNotFound) as of_other:
        store.get_branch(row.branch_id, OTHER_OWNER)
    with pytest.raises(BranchNotFound) as of_missing:
        store.get_branch("sb_" + "0" * 24, OTHER_OWNER)
    assert str(of_other.value) == str(of_missing.value)


def test_the_store_refuses_to_append_to_the_branch_of_another_session(store: BranchStore) -> None:
    row = _row()
    store.create_branch(row)
    with pytest.raises(BranchNotFound):
        store.append_events(row.branch_id, OTHER_OWNER, [_event(row.branch_id)])


def test_the_store_refuses_to_read_the_events_of_the_branch_of_another_session(store: BranchStore) -> None:
    row = _row()
    store.create_branch(row)
    with pytest.raises(BranchNotFound):
        store.read_events(row.branch_id, OTHER_OWNER)


def test_the_store_refuses_to_delete_the_events_of_the_branch_of_another_session(store: BranchStore) -> None:
    row = _row()
    store.create_branch(row)
    with pytest.raises(BranchNotFound):
        store.delete_events(row.branch_id, OTHER_OWNER)


def test_the_store_refuses_to_delete_the_branch_of_another_session(store: BranchStore) -> None:
    row = _row()
    store.create_branch(row)
    with pytest.raises(BranchNotFound):
        store.delete_branch(row.branch_id, OTHER_OWNER)
    # the branch of the owner is still there
    assert store.get_branch(row.branch_id, OWNER) == row


# --- the commit of the events and the answer of a request ------------------------------------------------------


def test_the_commit_appends_the_events_and_moves_the_row_of_the_branch(store: BranchStore) -> None:
    row = _row()
    store.create_branch(row)
    moved = replace(row, revision=1, current_canonical_hash="1" * 64)
    result = store.commit_events(row.branch_id, OWNER, [_event(row.branch_id)], moved, _answer(row.branch_id))
    assert result.appended == 1
    assert store.get_branch(row.branch_id, OWNER) == moved
    assert len(store.read_events(row.branch_id, OWNER)) == 1


def test_the_commit_remembers_the_answer_of_the_request(store: BranchStore) -> None:
    row = _row()
    store.create_branch(row)
    moved = replace(row, revision=1, current_canonical_hash="1" * 64)
    store.commit_events(row.branch_id, OWNER, [_event(row.branch_id)], moved, _answer(row.branch_id))
    answer = store.command_answer(row.branch_id, OWNER, "cmd-0001")
    assert answer is not None
    assert answer.revision == 1
    assert answer.canonical_hash == "1" * 64
    assert answer.payload_digest == "d" * 64
    assert answer.response_diff[0]["record_id"] == "R-0731"
    assert answer.response_verdict["label"] == "above_expected_range"
    assert answer.response_invariants[0]["identifier"] == "fx_rate_positive_and_finite"


def test_the_commit_refuses_a_branch_that_moved_and_writes_nothing(store: BranchStore) -> None:
    row = _row()
    store.create_branch(row)
    # The branch is at revision zero, so a row that claims revision two is a row of a request that is stale.
    moved = replace(row, revision=2, current_canonical_hash="2" * 64)
    with pytest.raises(BranchRevisionConflict):
        store.commit_events(row.branch_id, OWNER, [_event(row.branch_id)], moved, _answer(row.branch_id))
    assert store.get_branch(row.branch_id, OWNER) == row
    assert store.read_events(row.branch_id, OWNER) == []
    assert store.command_answer(row.branch_id, OWNER, "cmd-0001") is None


def test_the_store_reads_no_answer_of_a_request_that_was_not_made(store: BranchStore) -> None:
    row = _row()
    store.create_branch(row)
    assert store.command_answer(row.branch_id, OWNER, "cmd-0001") is None


def test_the_store_refuses_to_read_the_answer_of_the_branch_of_another_session(store: BranchStore) -> None:
    row = _row()
    store.create_branch(row)
    with pytest.raises(BranchNotFound):
        store.command_answer(row.branch_id, OTHER_OWNER, "cmd-0001")


def test_the_store_refuses_to_commit_on_the_branch_of_another_session(store: BranchStore) -> None:
    row = _row()
    store.create_branch(row)
    moved = replace(row, revision=1, current_canonical_hash="1" * 64)
    with pytest.raises(BranchNotFound):
        store.commit_events(row.branch_id, OTHER_OWNER, [_event(row.branch_id)], moved, _answer(row.branch_id))


# --- the commit of an undo ------------------------------------------------------------------------------------


def test_the_undo_appends_the_marker_and_moves_the_row_of_the_branch_back(store: BranchStore) -> None:
    """The undo appends the marker and puts the revision of the branch back to the previous value (ADR-024)."""
    row = _row()
    store.create_branch(row)
    moved = replace(row, revision=1, current_canonical_hash="1" * 64)
    store.commit_events(row.branch_id, OWNER, [_event(row.branch_id)], moved, _answer(row.branch_id))
    undone = replace(row, revision=0, current_canonical_hash="0" * 64)
    written = store.commit_undo(
        row.branch_id, OWNER, _marker(row.branch_id), undone, _undo_answer(row.branch_id)
    )

    assert written.revision == 0
    assert store.get_branch(row.branch_id, OWNER) == undone
    assert [event.event_uid for event in store.read_events(row.branch_id, OWNER)] == ["evt-1", "evt-2"]
    assert [event.event_type for event in store.read_events(row.branch_id, OWNER)] == [
        "refund.fx_adjusted",
        "sandbox.branch.undone",
    ]


def test_the_undo_remembers_the_answer_of_the_request(store: BranchStore) -> None:
    """The answer of the undo is remembered with the branch, so the same request is answered the same way."""
    row = _row()
    store.create_branch(row)
    moved = replace(row, revision=1, current_canonical_hash="1" * 64)
    store.commit_events(row.branch_id, OWNER, [_event(row.branch_id)], moved, _answer(row.branch_id))
    undone = replace(row, revision=0, current_canonical_hash="0" * 64)
    store.commit_undo(row.branch_id, OWNER, _marker(row.branch_id), undone, _undo_answer(row.branch_id))

    answer = store.command_answer(row.branch_id, OWNER, "cmd-0002")
    assert answer is not None
    assert answer.revision == 0
    assert answer.canonical_hash == "0" * 64
    assert answer.payload_digest == "d" * 64


def test_the_undo_refuses_a_branch_that_moved_and_writes_nothing(store: BranchStore) -> None:
    """The row of the branch is locked while the undo runs, so the loser of two undos is refused (ADR-024).

    The request was prepared against a branch at revision one, and the branch moved to revision two. Nothing is
    written: not the marker, not the answer, and not the row.
    """
    row = _row()
    store.create_branch(row)
    first = replace(row, revision=1, current_canonical_hash="1" * 64)
    store.commit_events(
        row.branch_id, OWNER, [_event(row.branch_id, "evt-1")], first, _answer(row.branch_id, "cmd-0001")
    )
    second = replace(row, revision=2, current_canonical_hash="2" * 64)
    store.commit_events(
        row.branch_id, OWNER, [_event(row.branch_id, "evt-2")], second, _answer(row.branch_id, "cmd-0002")
    )
    stale = replace(row, revision=0, current_canonical_hash="0" * 64)

    with pytest.raises(BranchRevisionConflict):
        store.commit_undo(
            row.branch_id, OWNER, _marker(row.branch_id, "evt-3"), stale, _undo_answer(row.branch_id, "cmd-0003")
        )

    assert store.get_branch(row.branch_id, OWNER) == second
    assert [event.event_uid for event in store.read_events(row.branch_id, OWNER)] == ["evt-1", "evt-2"]
    assert store.command_answer(row.branch_id, OWNER, "cmd-0003") is None


def test_the_store_refuses_to_undo_the_branch_of_another_session(store: BranchStore) -> None:
    """The branch of another visitor is refused with the generic error, like every other operation of the store."""
    row = _row()
    store.create_branch(row)
    moved = replace(row, revision=1, current_canonical_hash="1" * 64)
    store.commit_events(row.branch_id, OWNER, [_event(row.branch_id)], moved, _answer(row.branch_id))
    undone = replace(row, revision=0, current_canonical_hash="0" * 64)

    with pytest.raises(BranchNotFound):
        store.commit_undo(
            row.branch_id, OTHER_OWNER, _marker(row.branch_id), undone, _undo_answer(row.branch_id)
        )

    assert store.get_branch(row.branch_id, OWNER) == moved
    assert len(store.read_events(row.branch_id, OWNER)) == 1


def test_the_store_refuses_to_undo_a_branch_that_does_not_exist(store: BranchStore) -> None:
    missing = "sb_" + "0" * 24
    with pytest.raises(BranchNotFound):
        store.commit_undo(missing, OWNER, _marker(missing), _row(branch_id=missing), _answer(missing))


def test_the_undo_that_cannot_write_the_row_leaves_the_branch_where_it_was(store: BranchStore) -> None:
    """The marker, the move of the row and the answer of the request happen together (ADR-024, FR-040).

    The row handed over cannot be written, because its expiry is missing. The branch therefore keeps its events, its
    revision, its hash and its answers: an undo that did not happen is not an undo that happened halfway, and the two
    stores lose the same thing when an undo fails, which is nothing.

    Why the file backed store is proved the same way: it puts the content of the files of the events and of the
    answers back when the write of the row fails, and the test reads them again to say that it did.
    """
    row = _row()
    store.create_branch(row)
    moved = replace(row, revision=1, current_canonical_hash="1" * 64)
    store.commit_events(row.branch_id, OWNER, [_event(row.branch_id)], moved, _answer(row.branch_id))
    broken = replace(moved, revision=0, current_canonical_hash="0" * 64, expires_at=None)

    refusal = _refusal(
        lambda: store.commit_undo(
            row.branch_id, OWNER, _marker(row.branch_id), broken, _undo_answer(row.branch_id)
        )
    )

    assert refusal[0] != "no refusal"
    assert store.get_branch(row.branch_id, OWNER) == moved
    assert [event.event_uid for event in store.read_events(row.branch_id, OWNER)] == ["evt-1"]
    assert store.command_answer(row.branch_id, OWNER, "cmd-0001") is not None
    assert store.command_answer(row.branch_id, OWNER, "cmd-0002") is None


def test_the_undo_of_the_file_store_writes_the_events_before_the_row(
    file_store: FileBranchStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The row of the branch is written last, so a reader that finds an older row refuses the branch (ADR-024).

    The order of the two writes is part of the promise of the store, and the test records the order the writes
    happen in.
    """
    from ledgerlens.sandbox import store as store_module

    written: list[str] = []
    original = store_module._write_atomic

    def record(path: Path, text: str) -> None:
        written.append(path.name)
        original(path, text)

    monkeypatch.setattr(store_module, "_write_atomic", record)

    row = _row()
    file_store.create_branch(row)
    moved = replace(row, revision=1, current_canonical_hash="1" * 64)
    file_store.commit_events(row.branch_id, OWNER, [_event(row.branch_id)], moved, _answer(row.branch_id))
    # The fork and the commit are not the operation under test: only the writes of the undo are watched.
    written.clear()
    undone = replace(row, revision=0, current_canonical_hash="0" * 64)
    file_store.commit_undo(row.branch_id, OWNER, _marker(row.branch_id), undone, _undo_answer(row.branch_id))

    assert written.index(FileBranchStore.EVENTS_FILE) < written.index(FileBranchStore.BRANCH_FILE)
    assert written[-1] == FileBranchStore.BRANCH_FILE


def test_the_undo_of_the_file_store_that_cannot_write_the_answers_leaves_the_branch_where_it_was(
    file_store: FileBranchStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The undo that cannot write the answers leaves the branch exactly where it was (ADR-024, FR-040).

    The write of the answers fails, the way it fails when the disk is full. The marker of the undo is not left in
    the log of the branch and the row does not move, so the branch still proves its own state and it is still
    served: an undo that did not happen is not an undo that happened halfway, and the two implementations of the
    protocol lose the same thing when an undo fails, which is nothing.

    Why the files are compared and not only the reads of the store: the promise is about the branch on the disk,
    and a branch that is right in the reads and wrong in the files is a broken branch.
    """
    row = _row()
    file_store.create_branch(row)
    moved = replace(row, revision=1, current_canonical_hash="1" * 64)
    file_store.commit_events(row.branch_id, OWNER, [_event(row.branch_id)], moved, _answer(row.branch_id))
    before = _files_of_the_branch(file_store)
    _write_fails_on(monkeypatch, FileBranchStore.COMMANDS_FILE)

    undone = replace(row, revision=0, current_canonical_hash="0" * 64)
    with pytest.raises(OSError):
        file_store.commit_undo(row.branch_id, OWNER, _marker(row.branch_id), undone, _undo_answer(row.branch_id))

    assert _files_of_the_branch(file_store) == before
    assert file_store.get_branch(row.branch_id, OWNER) == moved
    assert [event.event_uid for event in file_store.read_events(row.branch_id, OWNER)] == ["evt-1"]
    assert file_store.command_answer(row.branch_id, OWNER, "cmd-0001") is not None
    assert file_store.command_answer(row.branch_id, OWNER, "cmd-0002") is None


def test_the_undo_of_the_file_store_that_cannot_write_the_row_leaves_the_branch_where_it_was(
    file_store: FileBranchStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The undo that cannot write the row leaves the branch exactly where it was (ADR-024, FR-040).

    The row is written last on purpose, so a reader that finds an older row refuses the branch instead of
    serving it half applied. The marker of the undo goes back where it was with it, because an undo that did
    not happen is not an undo that happened halfway.
    """
    row = _row()
    file_store.create_branch(row)
    moved = replace(row, revision=1, current_canonical_hash="1" * 64)
    file_store.commit_events(row.branch_id, OWNER, [_event(row.branch_id)], moved, _answer(row.branch_id))
    before = _files_of_the_branch(file_store)
    _write_fails_on(monkeypatch, FileBranchStore.BRANCH_FILE)

    undone = replace(row, revision=0, current_canonical_hash="0" * 64)
    with pytest.raises(OSError):
        file_store.commit_undo(row.branch_id, OWNER, _marker(row.branch_id), undone, _undo_answer(row.branch_id))

    assert _files_of_the_branch(file_store) == before
    assert file_store.get_branch(row.branch_id, OWNER) == moved
    assert [event.event_uid for event in file_store.read_events(row.branch_id, OWNER)] == ["evt-1"]
    assert file_store.command_answer(row.branch_id, OWNER, "cmd-0001") is not None
    assert file_store.command_answer(row.branch_id, OWNER, "cmd-0002") is None


# --- the reset of a branch ------------------------------------------------------------------------------


def test_the_reset_drops_the_events_and_writes_the_row_of_the_branch(store: BranchStore) -> None:
    row = _row()
    store.create_branch(row)
    store.append_events(row.branch_id, OWNER, [_event(row.branch_id, "evt-1")])
    store.append_events(row.branch_id, OWNER, [_event(row.branch_id, "evt-2")])
    reset = replace(row, revision=0, current_canonical_hash=row.base_canonical_hash, generation=1)
    written = store.reset_branch(row.branch_id, OWNER, reset)
    assert store.read_events(row.branch_id, OWNER) == []
    assert store.get_branch(row.branch_id, OWNER) == written


def test_the_reset_moves_the_generation_of_the_branch_forward(store: BranchStore) -> None:
    """The store moves the generation and not the caller: it writes the generation it found plus one (ADR-022).

    Why it matters: the number is written under the lock of the store, so two resets that cross cannot write the
    same number twice and lose one increment.
    """
    row = _row()
    store.create_branch(row)
    first = store.reset_branch(row.branch_id, OWNER, replace(row, generation=0))
    assert first.generation == 1
    assert store.get_branch(row.branch_id, OWNER).generation == 1
    second = store.reset_branch(row.branch_id, OWNER, replace(row, generation=0))
    assert second.generation == 2
    assert store.get_branch(row.branch_id, OWNER).generation == 2


def test_the_reset_ignores_the_generation_of_the_row_it_is_given(store: BranchStore) -> None:
    """The generation of the row the caller hands over is ignored, because the store owns the number."""
    row = _row()
    store.create_branch(row)
    written = store.reset_branch(row.branch_id, OWNER, replace(row, generation=99))
    assert written.generation == 1


def test_the_reset_of_a_branch_without_events_drops_nothing(store: BranchStore) -> None:
    row = _row()
    store.create_branch(row)
    written = store.reset_branch(row.branch_id, OWNER, replace(row, generation=1))
    assert written.generation == 1
    assert store.read_events(row.branch_id, OWNER) == []


def test_the_reset_that_cannot_write_the_row_leaves_the_branch_where_it_was(store: BranchStore) -> None:
    """The drop of the events and the move of the row happen together (ADR-021, ADR-022).

    The row handed over cannot be written, because its expiry is missing. The branch therefore keeps its events, its
    revision and its hash: a reset that did not happen is not a reset that happened halfway, and the two stores lose
    the same thing when a reset fails, which is nothing.
    """
    row = _row()
    store.create_branch(row)
    store.append_events(row.branch_id, OWNER, [_event(row.branch_id)])
    moved = replace(row, revision=1, current_canonical_hash="1" * 64)
    store.save_branch(moved)
    broken = replace(moved, expires_at=None)
    assert _refusal(lambda: store.reset_branch(row.branch_id, OWNER, broken))[0] != "no refusal"
    assert store.get_branch(row.branch_id, OWNER) == moved
    assert store.read_events(row.branch_id, OWNER) == [_event(row.branch_id)]


def test_the_reset_keeps_the_answers_of_the_branch_with_their_generation(store: BranchStore) -> None:
    """The answers of the past survive the reset, because an answer that is deleted cannot be marked stale."""
    row = _row()
    store.create_branch(row)
    moved = replace(row, revision=1, current_canonical_hash="1" * 64)
    store.commit_events(row.branch_id, OWNER, [_event(row.branch_id)], moved, _answer(row.branch_id))
    store.reset_branch(row.branch_id, OWNER, replace(row, generation=1))
    answers = store.list_commands(row.branch_id, OWNER)
    assert [answer.idempotency_key for answer in answers] == ["cmd-0001"]
    assert answers[0].generation == 0


def test_the_store_refuses_the_reset_of_the_branch_of_another_session(store: BranchStore) -> None:
    row = _row()
    store.create_branch(row)
    with pytest.raises(BranchNotFound):
        store.reset_branch(row.branch_id, OTHER_OWNER, replace(row, generation=1))
    # the branch of the owner is still there
    assert store.get_branch(row.branch_id, OWNER) == row


def test_the_store_refuses_the_reset_of_a_branch_that_does_not_exist(store: BranchStore) -> None:
    missing = "sb_" + "0" * 24
    with pytest.raises(BranchNotFound):
        store.reset_branch(missing, OWNER, _row(branch_id=missing))


# --- the listing of the answers of a branch ----------------------------------------------------------------


def test_the_store_lists_the_answers_in_the_order_of_the_commits(store: BranchStore) -> None:
    row = _row()
    store.create_branch(row)
    first = replace(row, revision=1, current_canonical_hash="1" * 64)
    store.commit_events(
        row.branch_id, OWNER, [_event(row.branch_id, "evt-1")], first, _answer(row.branch_id, "cmd-0001")
    )
    second = replace(row, revision=2, current_canonical_hash="2" * 64)
    store.commit_events(
        row.branch_id, OWNER, [_event(row.branch_id, "evt-2")], second, _answer(row.branch_id, "cmd-0002")
    )
    assert [answer.idempotency_key for answer in store.list_commands(row.branch_id, OWNER)] == ["cmd-0001", "cmd-0002"]


def test_the_store_lists_the_answers_in_the_order_of_the_commits_and_not_of_their_keys(store: BranchStore) -> None:
    """The order of the answers is the order of the commits, not the order of the keys of the requests.

    Why it matters: the two stores have to answer the same. The file backed store keeps the order of the lines of
    its log, and the database one needs a sequence of its own to keep the same order.
    """
    row = _row()
    store.create_branch(row)
    first = replace(row, revision=1, current_canonical_hash="1" * 64)
    store.commit_events(
        row.branch_id, OWNER, [_event(row.branch_id, "evt-1")], first, _answer(row.branch_id, "cmd-0002")
    )
    second = replace(row, revision=2, current_canonical_hash="2" * 64)
    store.commit_events(
        row.branch_id, OWNER, [_event(row.branch_id, "evt-2")], second, _answer(row.branch_id, "cmd-0001")
    )
    assert [answer.idempotency_key for answer in store.list_commands(row.branch_id, OWNER)] == ["cmd-0002", "cmd-0001"]


def test_the_store_lists_the_answer_the_branch_remembers(store: BranchStore) -> None:
    row = _row()
    store.create_branch(row)
    moved = replace(row, revision=1, current_canonical_hash="1" * 64)
    store.commit_events(row.branch_id, OWNER, [_event(row.branch_id)], moved, _answer(row.branch_id))
    answers = store.list_commands(row.branch_id, OWNER)
    assert len(answers) == 1
    assert answers[0].payload_digest == "d" * 64
    assert answers[0].response_verdict["label"] == "above_expected_range"


def test_the_store_lists_no_answer_of_a_branch_without_answers(store: BranchStore) -> None:
    row = _row()
    store.create_branch(row)
    assert store.list_commands(row.branch_id, OWNER) == []


def test_the_store_refuses_to_list_the_answers_of_the_branch_of_another_session(store: BranchStore) -> None:
    row = _row()
    store.create_branch(row)
    with pytest.raises(BranchNotFound):
        store.list_commands(row.branch_id, OTHER_OWNER)


# --- the race of two writes that cross -----------------------------------------------------------------------


def test_the_store_refuses_the_loser_of_two_commits_that_cross(
    layer: BranchLayer,
    store: BranchStore,
    scenario_id: str,
    adjustment: MutationCommand,
    clock,
) -> None:
    """Two commits that cross on the same branch leave one winner and one refusal (ADR-026).

    The two requests carry the same key and the same expected revision, and they were prepared against the same
    state of the branch, so the loser of the race has nothing left to commit: it is refused with
    `BranchRevisionConflict` and it writes nothing. The log of the branch holds one event of the mutation and not
    two, and the branch still proves its own state.

    Why the threads are real: a store that serialises the writes of a branch is the promise, and a mock of the
    lock would only prove that the mock works.
    """
    for session in RACE_SESSIONS:
        owner = canonical_session_id(session)
        branch = layer.fork(session, scenario_id).branch
        row = store.get_branch(branch.branch_id, owner)
        base = layer.base_resolver(scenario_id)
        plan = plan_mutation(base, branch.branch_id, scenario_id, 0, [], adjustment, clock.now)
        moved = replace(row, revision=1, current_canonical_hash=plan.canonical_hash, last_activity_at=clock.now)
        answer = SandboxCommandRow(
            branch_id=branch.branch_id,
            idempotency_key=adjustment.idempotency_key or "cmd-0001",
            payload_digest=payload_digest(adjustment),
            revision=1,
            canonical_hash=plan.canonical_hash,
            response_diff=list(plan.diff),
            response_verdict=plan.verdict.to_dict(),
            response_invariants=list(plan.invariants),
            generation=row.generation,
        )

        outcomes = _two_commits_that_cross(store, branch.branch_id, owner, plan.events, moved, answer)

        _one_winner_and_one_refusal(outcomes)
        events = store.read_events(branch.branch_id, owner)
        assert [event.event_uid for event in events] == [plan.events[0].event_uid]
        assert store.get_branch(branch.branch_id, owner) == moved
        # The branch still proves its own state: the projection of its log agrees with its row (ADR-021).
        assert layer.status(session, branch.branch_id).revision == 1


def test_the_store_refuses_the_loser_of_two_undos_that_cross(
    layer: BranchLayer,
    store: BranchStore,
    scenario_id: str,
    adjustment: MutationCommand,
    clock,
) -> None:
    """Two undos that cross on the same branch leave one winner and one refusal (ADR-026).

    The two requests carry the same key and the same expected revision, and they were prepared against the same
    state of the branch, so the loser of the race has nothing left to undo: it is refused with
    `BranchRevisionConflict` and it writes nothing. The log of the branch holds one marker of the undo and not two,
    and the branch still proves its own state.
    """
    for session in RACE_SESSIONS:
        owner = canonical_session_id(session)
        branch = layer.fork(session, scenario_id).branch
        layer.commit_mutation(session, branch.branch_id, adjustment)
        row = store.get_branch(branch.branch_id, owner)
        target = store.read_events(branch.branch_id, owner)[-1]
        marker = build_undo_event(branch.branch_id, target, "cmd-undo-0001", clock.now)
        undone = replace(row, revision=0, current_canonical_hash=row.base_canonical_hash, last_activity_at=clock.now)
        answer = SandboxCommandRow(
            branch_id=branch.branch_id,
            idempotency_key="undo-0001",
            payload_digest="d" * 64,
            revision=0,
            canonical_hash=row.base_canonical_hash,
            response_diff=[],
            response_verdict={},
            response_invariants=[],
            generation=row.generation,
        )

        outcomes = _two_undos_that_cross(store, branch.branch_id, owner, marker, undone, answer)

        _one_winner_and_one_refusal(outcomes)
        events = store.read_events(branch.branch_id, owner)
        assert [event.event_type for event in events].count(EVENT_BRANCH_UNDONE) == 1
        assert store.get_branch(branch.branch_id, owner) == undone
        # The branch still proves its own state: the projection of its log agrees with its row (ADR-021).
        assert layer.status(session, branch.branch_id).revision == 0


def test_the_answers_of_a_branch_that_cannot_prove_its_state_are_refused(
    layer: BranchLayer,
    store: BranchStore,
    session_id: str,
    owner_session: str,
    scenario_id: str,
) -> None:
    """The answers of a branch that cannot prove its own state are never served (ADR-021, ADR-026).

    The log of the branch holds an event of a kind the interpreter does not know, so the branch cannot prove its
    own state. Every read of a branch verifies it, and the answers are a read like any other, so they are refused
    with `HASH_MISMATCH` and not served.
    """
    branch = layer.fork(session_id, scenario_id).branch
    store.append_events(branch.branch_id, owner_session, [_unknown_event(branch.branch_id)])

    with pytest.raises(BranchHashMismatch) as refusal:
        layer.answers(session_id, branch.branch_id)

    assert refusal.value.code == "HASH_MISMATCH"
    assert "fork" in refusal.value.message


# --- the shape of the store on the disk --------------------------------------------------------------------


def test_the_file_store_loads_a_file_written_before_the_generation_existed(file_store: FileBranchStore) -> None:
    """A file written by a version of the code that had no generation still loads, with the generation zero.

    Why it matters: a deployment that upgrades the code has a store with files of the old shape in it, and a store
    that refuses to read them loses the branches of every visitor (ADR-022).
    """
    folder = file_store.root / OWNER / "storage-token"
    folder.mkdir(parents=True)
    branch = {
        "branch_id": "sb_" + "a" * 24,
        "owner_session": OWNER,
        "scenario_id": "S01",
        "base_snapshot_id": "sample-42",
        "base_canonical_hash": "0" * 64,
        "revision": 0,
        "current_canonical_hash": "0" * 64,
        "created_at": NOW.isoformat(),
        "last_activity_at": NOW.isoformat(),
        "expires_at": ALIVE_AT.isoformat(),
        "state": "active",
    }
    answer = {
        "branch_id": "sb_" + "a" * 24,
        "idempotency_key": "cmd-0001",
        "payload_digest": "d" * 64,
        "revision": 1,
        "canonical_hash": "1" * 64,
        "response_diff": [],
        "response_verdict": {"label": "not_available"},
        "response_invariants": [],
    }
    (folder / FileBranchStore.BRANCH_FILE).write_text(json.dumps(branch), encoding="utf-8")
    (folder / FileBranchStore.COMMANDS_FILE).write_text(json.dumps(answer) + "\n", encoding="utf-8")

    assert file_store.get_branch("sb_" + "a" * 24, OWNER).generation == 0
    stored = file_store.list_commands("sb_" + "a" * 24, OWNER)
    assert [row.idempotency_key for row in stored] == ["cmd-0001"]
    assert stored[0].generation == 0


def test_the_commit_of_the_file_store_writes_the_events_before_the_row(
    file_store: FileBranchStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The row of the branch is written last, so a reader that finds an older row refuses the branch.

    Why it matters: a reader that finds a row that is older than the events refuses the branch instead of serving it
    half applied (ADR-021, ADR-022). The order of the two writes is therefore part of the promise of the store, and
    the test records the order the writes happen in.
    """
    from ledgerlens.sandbox import store as store_module

    written: list[str] = []
    original = store_module._write_atomic

    def record(path: Path, text: str) -> None:
        written.append(path.name)
        original(path, text)

    monkeypatch.setattr(store_module, "_write_atomic", record)

    row = _row()
    file_store.create_branch(row)
    # The fork is not the operation under test: only the writes of the commit are watched.
    written.clear()
    moved = replace(row, revision=1, current_canonical_hash="1" * 64)
    file_store.commit_events(row.branch_id, OWNER, [_event(row.branch_id)], moved, _answer(row.branch_id))

    assert written.index(FileBranchStore.EVENTS_FILE) < written.index(FileBranchStore.BRANCH_FILE)
    assert written[-1] == FileBranchStore.BRANCH_FILE


def test_the_commit_of_the_file_store_that_cannot_write_the_row_leaves_the_branch_where_it_was(
    file_store: FileBranchStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The commit that cannot write the row leaves the branch exactly where it was (FR-040).

    The write of the row fails, the way it fails when the disk is full. The events and the answers go back where
    they were, so the branch keeps its revision, its hash and its answers, and it still proves its own state: a
    commit that did not happen is not a commit that happened halfway, and the two implementations of the protocol
    lose the same thing when a commit fails, which is nothing.

    Why the files are compared and not only the reads of the store: the promise is about the branch on the disk,
    and a branch that is right in the reads and wrong in the files is a broken branch.
    """
    row = _row()
    file_store.create_branch(row)
    before = _files_of_the_branch(file_store)
    _write_fails_on(monkeypatch, FileBranchStore.BRANCH_FILE)

    moved = replace(row, revision=1, current_canonical_hash="1" * 64)
    with pytest.raises(OSError):
        file_store.commit_events(row.branch_id, OWNER, [_event(row.branch_id)], moved, _answer(row.branch_id))

    assert _files_of_the_branch(file_store) == before
    assert file_store.get_branch(row.branch_id, OWNER) == row
    assert file_store.read_events(row.branch_id, OWNER) == []
    assert file_store.command_answer(row.branch_id, OWNER, "cmd-0001") is None


def test_every_file_of_the_file_store_is_written_with_a_temporary_file(
    file_store: FileBranchStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every file of the store is written with a temporary file and a rename (ADR-025).

    The row of the fork and the row of the save write one file each, and they write it the way the other paths write
    theirs. The reason is the same: a reader that finds a row that is half written cannot read the branch at all,
    and the row is the one file a reader always needs.

    Why the test watches the writes instead of the result: a row that was written the wrong way is a row that is
    right until the moment the process dies in the middle of the write, and the only way to see that difference is
    to watch how the file is written.
    """
    from ledgerlens.sandbox import store as store_module

    written: list[str] = []
    original = store_module._write_atomic

    def record(path: Path, text: str) -> None:
        written.append(path.name)
        original(path, text)

    monkeypatch.setattr(store_module, "_write_atomic", record)
    row = _row()
    file_store.create_branch(row)
    file_store.save_branch(replace(row, revision=3))

    assert written == [FileBranchStore.BRANCH_FILE, FileBranchStore.BRANCH_FILE]
    # The temporary file of the write is gone: the rename carried it over.
    assert not list(file_store.root.glob(f"**/{FileBranchStore.BRANCH_FILE}.tmp"))
    assert file_store.get_branch(row.branch_id, OWNER).revision == 3


def test_the_file_of_another_session_is_never_read(file_store: FileBranchStore) -> None:
    """The file of another visitor is not even opened, because the lookup stays in the folder of the owner.

    Why it matters: the promise of the store is the isolation on the path, not only the owner check on the row. The
    file of the other visitor is unreadable and unreadable as a branch, so a lookup that scanned the whole root
    would fail with something else than the generic refusal.
    """
    mine = file_store.create_branch(_row(branch_id="sb_" + "a" * 24))
    theirs = file_store.create_branch(_row(branch_id="sb_" + "b" * 24, owner_session=OTHER_OWNER))
    path = next(file_store.root.glob(f"{OTHER_OWNER}/*/{FileBranchStore.BRANCH_FILE}"))
    path.write_text("this file is not a branch", encoding="utf-8")
    os.chmod(path, 0o000)
    try:
        assert file_store.get_branch(mine.branch_id, OWNER).branch_id == mine.branch_id
        with pytest.raises(BranchNotFound):
            file_store.get_branch(theirs.branch_id, OWNER)
    finally:
        os.chmod(path, 0o600)


# --- the migration of a database of the old shape -----------------------------------------------------------


def test_the_database_store_lists_the_answers_in_the_order_of_the_commits_when_two_share_one_instant(
    database_store: PostgresBranchStore,
) -> None:
    """The order of the answers is the order of the commits, even when two commits share the same instant.

    Why it matters: the tie cannot be broken by the key of the request, because the visitor chose the key, and the
    file backed store lists the answers in the order of the lines of its log. The moment of the commit is the moment
    of the transaction, so two requests committed in the same transaction share it.
    """
    row = _row()
    database_store.create_branch(row)
    write_answer_at(database_store.database_url, row.branch_id, _answer(row.branch_id, "cmd-0002"), NOW)
    write_answer_at(database_store.database_url, row.branch_id, _answer(row.branch_id, "cmd-0001"), NOW)
    assert [answer.idempotency_key for answer in database_store.list_commands(row.branch_id, OWNER)] == [
        "cmd-0002",
        "cmd-0001",
    ]


def test_the_schema_script_gives_a_database_of_the_old_shape_the_generation_column(
    database_store: PostgresBranchStore,
) -> None:
    """The script of the schema brings a database of the old shape to the shape of the code (ADR-022).

    Why it matters: the script reports success when it did not migrate, and the first visitor of the deployment is
    the one who finds out. The scratch schema is dropped at the end, whatever happens.
    """
    url = database_store.database_url
    scratch = "sandbox_scratch_migration"
    drop_schema(url, scratch)
    create_old_shape(url, scratch)
    try:
        apply_schema(url_with_search_path(url, scratch))
        assert "generation" in columns_of(url, scratch, "sandbox_branches")
        assert "generation" in columns_of(url, scratch, "sandbox_commands")
        assert "command_seq" in columns_of(url, scratch, "sandbox_commands")
    finally:
        drop_schema(url, scratch)


# --- the choice of the store ------------------------------------------------------------------------


def test_the_product_module_of_the_database_store_carries_no_scaffolding_of_the_tests() -> None:
    """The scaffolding of the tests lives in the tests and not in the product module (ADR-022).

    Why it matters: the two implementations of the protocol are read side by side, and a public name that only one of
    them has is a name a reader of the product may take for an operation of the store. The shape of the tables before
    the generation existed and the helpers that only a test uses belong to the tests.
    """
    from ledgerlens.sandbox import postgres_store

    for name in ("OLD_SHAPE_STATEMENTS", "columns_of", "create_old_shape", "drop_schema", "url_with_search_path"):
        assert not hasattr(postgres_store, name), f"{name} does not belong to the product module"
        assert name not in postgres_store.__all__
    assert not hasattr(PostgresBranchStore, "write_answer_at")


def test_the_two_stores_offer_the_same_public_operations(
    file_store: FileBranchStore, database_store: PostgresBranchStore
) -> None:
    """The two implementations of the protocol offer the same public operations (ADR-022).

    Why it matters: a public method that only one of them has is a method the product may call on one store and not
    on the other. The maintenance operations are the ones the store declares, and they are declared by both.
    """

    def operations(store: object) -> set[str]:
        return {name for name in dir(store) if not name.startswith("_") and callable(getattr(store, name))}

    assert operations(file_store) == operations(database_store)


def test_the_settings_read_the_database_url_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    url = "postgresql://ledgerlens@127.0.0.1:5433/ledgerlens_sandbox"
    monkeypatch.setenv("LEDGERLENS_SANDBOX_DATABASE_URL", url)
    assert get_settings().sandbox_database_url == url


def test_the_settings_keep_no_database_url_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    # The variable is removed, so the test says what the default is and not what the machine has.
    monkeypatch.delenv("LEDGERLENS_SANDBOX_DATABASE_URL", raising=False)
    assert get_settings().sandbox_database_url is None


def test_the_factory_picks_the_file_backed_store_without_a_database_url(tmp_path: Path) -> None:
    store = build_branch_store(Settings(runtime_dir=tmp_path))
    assert isinstance(store, FileBranchStore)


def test_the_factory_picks_the_database_store_with_a_database_url(tmp_path: Path) -> None:
    settings = Settings(runtime_dir=tmp_path, sandbox_database_url="postgresql://localhost:5432/ledgerlens_sandbox")
    assert isinstance(build_branch_store(settings), PostgresBranchStore)


# --- the comparison of the two implementations --------------------------------------------------------


def _answers(store: BranchStore) -> list[Any]:
    """The answers of one fixed sequence of operations, as values that two stores can be compared on."""
    row = _row(branch_id="sb_" + "a" * 24)
    other = _row(branch_id="sb_" + "b" * 24, owner_session=OTHER_OWNER, expires_at=DEAD_AT)
    event = _event(row.branch_id)
    answers: list[Any] = []

    answers.append(store.create_branch(row) == row)
    answers.append(store.get_branch(row.branch_id, OWNER) == row)
    answers.append(store.create_branch(other) == other)
    answers.append(sorted(item.branch_id for item in store.list_branches(OWNER)))
    answers.append([item.branch_id for item in store.list_branches(OTHER_OWNER)])
    first_append = store.append_events(row.branch_id, OWNER, [event])
    second_append = store.append_events(row.branch_id, OWNER, [event])
    answers.append((first_append.appended, first_append.duplicates))
    answers.append((second_append.appended, second_append.duplicates))
    answers.append([item.event_uid for item in store.read_events(row.branch_id, OWNER)])
    answers.append([item.payload for item in store.read_events(row.branch_id, OWNER)])
    answers.append(store.delete_events(row.branch_id, OWNER))
    answers.append(sorted(item.branch_id for item in store.list_expired(NOW)))
    moved = replace(row, revision=1, current_canonical_hash="1" * 64)
    answers.append(store.save_branch(moved) == moved)
    answers.append(store.get_branch(row.branch_id, OWNER) == moved)
    # The touch of the deadline moves the deadline and nothing else, and the two stores answer the same about it.
    touched = store.touch_branch(
        row.branch_id, OWNER, NOW + timedelta(minutes=10), ALIVE_AT + timedelta(minutes=10)
    )
    answers.append(touched)
    answers.append(store.get_branch(row.branch_id, OWNER) == touched)
    answers.append(_refusal(lambda: store.touch_branch(row.branch_id, OTHER_OWNER, NOW, ALIVE_AT)))
    answers.append(_refusal(lambda: store.get_branch(row.branch_id, OTHER_OWNER)))
    answers.append(_refusal(lambda: store.read_events(row.branch_id, OTHER_OWNER)))
    answers.append(_refusal(lambda: store.append_events(row.branch_id, OTHER_OWNER, [event])))
    answers.append(_refusal(lambda: store.delete_branch(row.branch_id, OTHER_OWNER)))
    answers.append(store.delete_branch(row.branch_id, OWNER))
    answers.append(store.list_branches(OWNER))
    # the commit of the events and the answer of the request
    committed = _row(branch_id="sb_" + "c" * 24)
    store.create_branch(committed)
    committed_event = _event(committed.branch_id, "evt-3")
    moved = replace(committed, revision=1, current_canonical_hash="1" * 64)
    answers.append(
        store.commit_events(
            committed.branch_id, OWNER, [committed_event], moved, _answer(committed.branch_id, "cmd-0002")
        )
    )
    answers.append(store.get_branch(committed.branch_id, OWNER) == moved)
    # a second request whose key is not in the order of the commits: the answers are listed in the order of the
    # commits, so the two stores have to answer the same.
    second = replace(committed, revision=2, current_canonical_hash="2" * 64)
    answers.append(
        store.commit_events(
            committed.branch_id,
            OWNER,
            [_event(committed.branch_id, "evt-4")],
            second,
            _answer(committed.branch_id, "cmd-0001"),
        )
    )
    answers.append([answer.idempotency_key for answer in store.list_commands(committed.branch_id, OWNER)])
    answers.append(store.command_answer(committed.branch_id, OWNER, "cmd-0001"))
    answers.append(store.command_answer(committed.branch_id, OWNER, "cmd-0002"))
    answers.append(_refusal(lambda: store.command_answer(committed.branch_id, OTHER_OWNER, "cmd-0001")))
    stale = replace(committed, revision=4, current_canonical_hash="4" * 64)
    answers.append(
        _refusal(
            lambda: store.commit_events(
                committed.branch_id, OWNER, [committed_event], stale, _answer(committed.branch_id)
            )
        )
    )
    answers.append(store.get_branch(committed.branch_id, OWNER) == second)
    answers.append(store.read_events(committed.branch_id, OWNER))
    # the undo of the last mutation: the marker is appended, the revision goes back and the answer is remembered
    undone = replace(committed, revision=1, current_canonical_hash="1" * 64)
    answers.append(
        store.commit_undo(
            committed.branch_id,
            OWNER,
            _marker(committed.branch_id, "evt-5"),
            undone,
            _undo_answer(committed.branch_id, "cmd-0003"),
        )
    )
    answers.append(store.get_branch(committed.branch_id, OWNER) == undone)
    answers.append([item.event_uid for item in store.read_events(committed.branch_id, OWNER)])
    answers.append([answer.idempotency_key for answer in store.list_commands(committed.branch_id, OWNER)])
    answers.append(
        _refusal(
            lambda: store.commit_undo(
                committed.branch_id,
                OTHER_OWNER,
                _marker(committed.branch_id, "evt-6"),
                undone,
                _undo_answer(committed.branch_id, "cmd-0004"),
            )
        )
    )
    # the reset of the branch and the listing of the answers it remembers
    reset = replace(committed, revision=0, current_canonical_hash=committed.base_canonical_hash, generation=1)
    written = store.reset_branch(committed.branch_id, OWNER, reset)
    answers.append(written)
    answers.append(store.get_branch(committed.branch_id, OWNER) == written)
    answers.append(store.read_events(committed.branch_id, OWNER))
    answers.append(store.list_commands(committed.branch_id, OWNER))
    answers.append(_refusal(lambda: store.reset_branch(committed.branch_id, OTHER_OWNER, reset)))
    answers.append(_refusal(lambda: store.list_commands(committed.branch_id, OTHER_OWNER)))
    return answers


def test_the_two_implementations_answer_the_same_for_the_same_sequence_of_operations(
    file_store: BranchStore, database_store: BranchStore
) -> None:
    """The comparison itself: the same sequence of operations, the same answers.

    Why it exists: the contract suite says that both implementations answer the same about each operation. This test
    says it about the sequence, so a drift between the two shows up as one difference and not as two suites.
    """
    assert _answers(file_store) == _answers(database_store)
