"""The isolation between two visitors: the store refuses the branch of another session, and so does the domain.

The rule is proven in the data and not only in the path of the domain layer: a store asked for the branch of another
visitor returns nothing, whatever the caller does next, and the refusal is the same error as a branch that does not
exist at all (FR-004, FR-005, FR-027, SC-001).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ledgerlens.run_context import canonical_session_id
from ledgerlens.sandbox.branch import BranchLayer
from ledgerlens.sandbox.snapshot import BaseSnapshot
from ledgerlens.sandbox.store import BranchNotFound, FileBranchStore, SandboxEventRow


def _event(branch_id: str) -> SandboxEventRow:
    return SandboxEventRow(
        event_uid="evt-isolated",
        branch_id=branch_id,
        event_type="refund.fx_adjusted",
        aggregate_id="R-0731",
        occurred_at="2026-11-14T10:00:00Z",
        payload={"rate": "5.41250000"},
    )


def _text_under(folder: Path) -> str:
    """Every name and every text of the files under a folder, as one string."""
    parts: list[str] = []
    for path in sorted(folder.rglob("*")):
        parts.append(path.name)
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


# --- two visitors on the same scenario ------------------------------------------------------------


def test_two_sessions_fork_the_same_scenario_with_two_different_branches(
    layer: BranchLayer, session_id: str, other_session_id: str, scenario_id: str
) -> None:
    first = layer.fork(session_id, scenario_id).branch
    second = layer.fork(other_session_id, scenario_id).branch
    assert first.branch_id != second.branch_id


def test_the_two_branches_of_the_same_scenario_report_the_same_base_hash(
    layer: BranchLayer, session_id: str, other_session_id: str, scenario_id: str, base_snapshot: BaseSnapshot
) -> None:
    first = layer.fork(session_id, scenario_id).branch
    second = layer.fork(other_session_id, scenario_id).branch
    assert first.base_canonical_hash == second.base_canonical_hash == base_snapshot.canonical_hash


# --- the store refuses the branch of another session -----------------------------------------------


def test_the_store_refuses_to_read_the_branch_of_another_session(
    store: FileBranchStore, layer: BranchLayer, session_id: str, other_session_id: str, scenario_id: str
) -> None:
    branch = layer.fork(session_id, scenario_id).branch
    with pytest.raises(BranchNotFound):
        store.get_branch(branch.branch_id, canonical_session_id(other_session_id))


def test_the_refusal_of_a_branch_of_another_session_is_the_same_as_the_refusal_of_a_missing_branch(
    store: FileBranchStore, layer: BranchLayer, session_id: str, other_session_id: str, scenario_id: str
) -> None:
    branch = layer.fork(session_id, scenario_id).branch
    with pytest.raises(BranchNotFound) as of_other:
        store.get_branch(branch.branch_id, canonical_session_id(other_session_id))
    with pytest.raises(BranchNotFound) as of_missing:
        store.get_branch("sb_" + "0" * 24, canonical_session_id(other_session_id))
    assert str(of_other.value) == str(of_missing.value)


def test_the_store_refuses_to_read_the_events_of_the_branch_of_another_session(
    store: FileBranchStore, layer: BranchLayer, session_id: str, other_session_id: str, scenario_id: str
) -> None:
    branch = layer.fork(session_id, scenario_id).branch
    owner = canonical_session_id(session_id)
    store.append_events(branch.branch_id, owner, [_event(branch.branch_id)])
    with pytest.raises(BranchNotFound):
        store.read_events(branch.branch_id, canonical_session_id(other_session_id))


def test_the_branch_of_another_session_has_no_event(
    store: FileBranchStore, layer: BranchLayer, session_id: str, other_session_id: str, scenario_id: str
) -> None:
    mine = layer.fork(session_id, scenario_id).branch
    theirs = layer.fork(other_session_id, scenario_id).branch
    store.append_events(mine.branch_id, canonical_session_id(session_id), [_event(mine.branch_id)])
    assert len(store.read_events(mine.branch_id, canonical_session_id(session_id))) == 1
    # the event of one branch never shows up in the event log of the branch of the other session
    assert store.read_events(theirs.branch_id, canonical_session_id(other_session_id)) == []


def test_the_store_refuses_to_append_to_the_branch_of_another_session(
    store: FileBranchStore, layer: BranchLayer, session_id: str, other_session_id: str, scenario_id: str
) -> None:
    branch = layer.fork(session_id, scenario_id).branch
    with pytest.raises(BranchNotFound):
        store.append_events(branch.branch_id, canonical_session_id(other_session_id), [_event(branch.branch_id)])


# --- the domain refuses the branch of another session ----------------------------------------------


def test_the_domain_refuses_the_status_of_the_branch_of_another_session(
    layer: BranchLayer, session_id: str, other_session_id: str, scenario_id: str
) -> None:
    branch = layer.fork(session_id, scenario_id).branch
    with pytest.raises(BranchNotFound) as info:
        layer.status(other_session_id, branch.branch_id)
    message = str(info.value)
    assert session_id not in message
    assert canonical_session_id(session_id) not in message
    assert "exist" not in message.lower()


def test_the_domain_refuses_a_branch_that_does_not_exist_with_the_same_message(
    layer: BranchLayer, session_id: str, other_session_id: str, scenario_id: str
) -> None:
    branch = layer.fork(session_id, scenario_id).branch
    with pytest.raises(BranchNotFound) as of_other:
        layer.status(other_session_id, branch.branch_id)
    with pytest.raises(BranchNotFound) as of_missing:
        layer.status(other_session_id, "sb_" + "0" * 24)
    assert str(of_other.value) == str(of_missing.value)


# --- the folders on the disk -----------------------------------------------------------------------


def test_the_folder_of_one_session_holds_no_branch_of_another_session(
    store: FileBranchStore, layer: BranchLayer, session_id: str, other_session_id: str, scenario_id: str
) -> None:
    mine = layer.fork(session_id, scenario_id).branch
    theirs = layer.fork(other_session_id, scenario_id).branch
    folder = store.root / canonical_session_id(session_id)
    assert folder.is_dir()
    assert theirs.branch_id not in _text_under(folder)
    assert mine.branch_id in _text_under(folder)


def test_the_two_sessions_have_two_different_folders(
    store: FileBranchStore, layer: BranchLayer, session_id: str, other_session_id: str, scenario_id: str
) -> None:
    layer.fork(session_id, scenario_id)
    layer.fork(other_session_id, scenario_id)
    mine = store.root / canonical_session_id(session_id)
    theirs = store.root / canonical_session_id(other_session_id)
    assert mine.is_dir() and theirs.is_dir()
    assert mine != theirs
    assert theirs not in mine.parents
