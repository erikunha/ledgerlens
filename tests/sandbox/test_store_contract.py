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
"""

from __future__ import annotations

import json
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from ledgerlens.config import Settings, get_settings
from ledgerlens.sandbox.factory import build_branch_store
from ledgerlens.sandbox.postgres_store import PostgresBranchStore, apply_schema
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


def _answer(branch_id: str, key: str = "cmd-0001") -> SandboxCommandRow:
    """The answer of a request, as the store keeps it."""
    return SandboxCommandRow(
        branch_id=branch_id,
        idempotency_key=key,
        payload_digest="d" * 64,
        revision=1,
        canonical_hash="1" * 64,
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
    moved = replace(row, revision=1, current_canonical_hash="1" * 64)
    file_store.commit_events(row.branch_id, OWNER, [_event(row.branch_id)], moved, _answer(row.branch_id))

    assert written.index(FileBranchStore.EVENTS_FILE) < written.index(FileBranchStore.BRANCH_FILE)
    assert written[-1] == FileBranchStore.BRANCH_FILE


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
