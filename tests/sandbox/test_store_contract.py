"""The contract of the branch store: one suite, run against every implementation of the protocol.

Why it exists: ADR-018 and ADR-020 ask for the file backed store and the database store to behave identically under
the same test suite (FR-040, SC-015). So the suite below is written once, and the `store` fixture of `conftest.py`
decides which implementation it runs against. Every test of this file therefore runs twice, once for each store.

The last test of the file is the comparison itself: the same sequence of operations is applied to the two stores and
the answers have to be the same, so the comparison is a real comparison and not two separate suites.

The file also holds the choice of the store: the configuration names the database, and the factory turns that name
into the implementation of the protocol.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from ledgerlens.config import Settings, get_settings
from ledgerlens.sandbox.factory import build_branch_store
from ledgerlens.sandbox.postgres_store import PostgresBranchStore
from ledgerlens.sandbox.store import BranchNotFound, BranchStore, FileBranchStore, SandboxBranchRow, SandboxEventRow

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


# --- the choice of the store ------------------------------------------------------------------------


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


def _refusal(action: Any) -> tuple[str, str]:
    """The name of the error and its message, or the mark of an answer that was not a refusal."""
    try:
        action()
    except Exception as exc:  # noqa: BLE001 - the answer of the store is what the comparison is about
        return (type(exc).__name__, str(exc))
    return ("no refusal", "")


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
    return answers


def test_the_two_implementations_answer_the_same_for_the_same_sequence_of_operations(
    file_store: BranchStore, database_store: BranchStore
) -> None:
    """The comparison itself: the same sequence of operations, the same answers.

    Why it exists: the contract suite says that both implementations answer the same about each operation. This test
    says it about the sequence, so a drift between the two shows up as one difference and not as two suites.
    """
    assert _answers(file_store) == _answers(database_store)
