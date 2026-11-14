"""The fork of an immutable base: the identity of the branch, the reuse rule, the expiry and the store contract.

The published artifacts are hashed when the suite is imported and again when it ends, so a fork that wrote to the
published ledger or to the scenario manifest would fail the test (FR-001, SC-004).
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ledgerlens.config import get_settings
from ledgerlens.run_context import canonical_session_id
from ledgerlens.sandbox.branch import BranchExpired, BranchLayer, InvalidSessionId
from ledgerlens.sandbox.snapshot import BaseSnapshot
from ledgerlens.sandbox.store import (
    BranchNotFound,
    BranchStore,
    FileBranchStore,
    SandboxBranchRow,
    SandboxEventRow,
)

BRANCH_ID = re.compile(r"^sb_[0-9a-f]{24}$")
SCENARIOS_PATH = Path(__file__).resolve().parents[2] / "data" / "scenarios.json"
PUBLISHED_LEDGER_PATH = Path(__file__).resolve().parents[2] / "data" / "ledger.db"


def _sha256(path: Path) -> str | None:
    """The digest of a published file, or None when the file does not exist."""
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def _published_hashes() -> dict[str, str | None]:
    """The hashes of the published artifacts: the manifest of the scenarios and the published ledger."""
    return {
        "scenarios.json": _sha256(SCENARIOS_PATH),
        "ledger.db": _sha256(PUBLISHED_LEDGER_PATH),
    }


# --- the identity of the branch -------------------------------------------------------------------


def test_the_branch_id_is_opaque_and_carries_no_session_no_scenario_and_no_path(
    layer: BranchLayer, session_id: str, scenario_id: str
) -> None:
    branch = layer.fork(session_id, scenario_id).branch
    assert BRANCH_ID.match(branch.branch_id)
    assert session_id not in branch.branch_id
    assert canonical_session_id(session_id) not in branch.branch_id
    assert scenario_id not in branch.branch_id
    assert "/" not in branch.branch_id


def test_the_branch_starts_at_revision_zero_with_the_hash_of_the_base(
    layer: BranchLayer, session_id: str, scenario_id: str, base_snapshot: BaseSnapshot
) -> None:
    branch = layer.fork(session_id, scenario_id).branch
    assert branch.revision == 0
    assert branch.base_canonical_hash == base_snapshot.canonical_hash
    assert branch.base_snapshot_id == base_snapshot.snapshot_id


def test_the_base_of_the_branch_is_the_published_snapshot_and_the_hash_is_the_projection(
    layer: BranchLayer, session_id: str, scenario_id: str, base_snapshot: BaseSnapshot
) -> None:
    branch = layer.fork(session_id, scenario_id).branch
    # The identifier of the base names the published snapshot, the source and the seed of the dataset.
    assert branch.base_snapshot_id == "sample-42"
    # The hash is the one of the account scoped projection the branch reads.
    assert branch.base_canonical_hash == base_snapshot.canonical_hash
    assert branch.scenario_id == scenario_id


def test_the_hash_of_the_branch_at_revision_zero_is_the_hash_of_the_base(
    layer: BranchLayer, session_id: str, scenario_id: str, base_snapshot: BaseSnapshot
) -> None:
    branch = layer.fork(session_id, scenario_id).branch
    assert branch.current_canonical_hash == base_snapshot.canonical_hash
    assert branch.current_canonical_hash == branch.base_canonical_hash


def test_the_branch_belongs_to_the_canonical_form_of_the_session(
    layer: BranchLayer, session_id: str, scenario_id: str
) -> None:
    branch = layer.fork(session_id, scenario_id).branch
    assert branch.owner_session == canonical_session_id(session_id)


# --- the reuse rule -------------------------------------------------------------------------------


def test_the_second_fork_of_the_same_scenario_returns_the_branch_that_already_exists(
    layer: BranchLayer, session_id: str, scenario_id: str
) -> None:
    first = layer.fork(session_id, scenario_id)
    second = layer.fork(session_id, scenario_id)
    assert second.branch.branch_id == first.branch.branch_id
    assert second.branch.revision == first.branch.revision == 0


def test_the_fork_reports_whether_it_created_the_branch_or_reused_it(
    layer: BranchLayer, session_id: str, scenario_id: str
) -> None:
    first = layer.fork(session_id, scenario_id)
    second = layer.fork(session_id, scenario_id)
    assert first.created is True
    assert second.created is False


def test_the_second_fork_does_not_grow_the_number_of_branches_of_the_session(
    layer: BranchLayer, store: FileBranchStore, session_id: str, scenario_id: str
) -> None:
    layer.fork(session_id, scenario_id)
    layer.fork(session_id, scenario_id)
    layer.fork(session_id, scenario_id)
    assert len(store.list_branches(canonical_session_id(session_id))) == 1


# --- the expiry -----------------------------------------------------------------------------------


def test_the_expiry_of_the_branch_is_in_the_future(layer: BranchLayer, session_id: str, scenario_id: str) -> None:
    branch = layer.fork(session_id, scenario_id).branch
    assert branch.expires_at > datetime.now(UTC)


def test_the_expiry_never_passes_the_absolute_limit(layer: BranchLayer, session_id: str, scenario_id: str) -> None:
    settings = get_settings()
    assert settings.sandbox_branch_absolute_ttl_seconds == 14400
    branch = layer.fork(session_id, scenario_id).branch
    limit = branch.created_at + timedelta(seconds=settings.sandbox_branch_absolute_ttl_seconds)
    assert branch.expires_at <= limit


def test_the_idle_limit_of_a_branch_is_the_default_of_one_hour(
    layer: BranchLayer, session_id: str, scenario_id: str
) -> None:
    settings = get_settings()
    assert settings.sandbox_branch_idle_ttl_seconds == 3600
    branch = layer.fork(session_id, scenario_id).branch
    assert branch.expires_at == branch.created_at + timedelta(seconds=settings.sandbox_branch_idle_ttl_seconds)


# --- the store contract ---------------------------------------------------------------------------


def test_the_file_store_implements_the_protocol(store: FileBranchStore) -> None:
    assert isinstance(store, BranchStore)


def test_the_append_of_an_event_is_idempotent_on_the_event_uid(
    store: FileBranchStore, layer: BranchLayer, session_id: str, scenario_id: str
) -> None:
    branch = layer.fork(session_id, scenario_id).branch
    owner = canonical_session_id(session_id)
    event = SandboxEventRow(
        event_uid="evt-1",
        branch_id=branch.branch_id,
        event_type="refund.fx_adjusted",
        aggregate_id="R-0731",
        occurred_at="2026-11-14T10:00:00Z",
        payload={"rate": "5.41250000"},
    )
    first = store.append_events(branch.branch_id, owner, [event])
    second = store.append_events(branch.branch_id, owner, [event])
    assert (first.appended, first.duplicates) == (1, 0)
    assert (second.appended, second.duplicates) == (0, 1)
    assert len(store.read_events(branch.branch_id, owner)) == 1


# --- the published artifacts stay the same --------------------------------------------------------

def test_the_published_artifacts_are_unchanged_by_the_forks(
    layer: BranchLayer,
    session_id: str,
    other_session_id: str,
    scenario_id: str,
    published_digests: dict,
) -> None:
    layer.fork(session_id, scenario_id)
    layer.fork(other_session_id, scenario_id)
    layer.fork(session_id, scenario_id)
    assert _published_hashes() == published_digests


def test_the_published_artifacts_have_a_hash_before_and_after_the_forks(published_digests: dict) -> None:
    assert published_digests["scenarios.json"]
    assert published_digests["ledger.db"] or not PUBLISHED_LEDGER_PATH.exists()


# --- the owner is a session identifier and nothing else ---------------------------------------------


def test_the_layer_refuses_a_session_identifier_outside_the_pattern(layer: BranchLayer, scenario_id: str) -> None:
    with pytest.raises(InvalidSessionId):
        layer.fork("a%2eb", scenario_id)
    with pytest.raises(InvalidSessionId):
        layer.fork("not an identifier", scenario_id)


def test_the_layer_refuses_a_session_identifier_outside_the_pattern_on_a_read(
    layer: BranchLayer, session_id: str, scenario_id: str
) -> None:
    branch = layer.fork(session_id, scenario_id).branch
    with pytest.raises(InvalidSessionId):
        layer.status("a%2eb", branch.branch_id)


def test_two_identifiers_that_differ_only_in_the_marker_never_share_an_owner(
    layer: BranchLayer, scenario_id: str
) -> None:
    """`canonical_session_id("a.b")` and `canonical_session_id("a%2eb")` are the same string.

    The marker is not in the pattern of an identifier, so the second one is refused instead of becoming the same
    owner and receiving the branch of the first visitor.
    """
    first = layer.fork("a.b", scenario_id)
    with pytest.raises(InvalidSessionId):
        layer.fork("a%2eb", scenario_id)
    other = layer.fork("a-c", scenario_id)
    assert first.created is True and other.created is True
    assert first.branch.branch_id != other.branch.branch_id


# --- the idle deadline and the absolute deadline -----------------------------------------------------


def test_an_activity_inside_the_first_hour_keeps_the_branch_alive_past_the_first_hour(
    layer: BranchLayer, clock, session_id: str, scenario_id: str
) -> None:
    branch = layer.fork(session_id, scenario_id).branch
    clock.advance(timedelta(minutes=30))
    layer.status(session_id, branch.branch_id)  # the activity of the visitor
    clock.advance(timedelta(minutes=40))  # seventy minutes after the creation
    assert layer.status(session_id, branch.branch_id).branch_id == branch.branch_id


def test_nothing_keeps_the_branch_alive_past_the_absolute_limit(
    layer: BranchLayer, clock, session_id: str, scenario_id: str
) -> None:
    branch = layer.fork(session_id, scenario_id).branch
    for _ in range(7):  # three and a half hours, with an activity every half hour
        clock.advance(timedelta(minutes=30))
        layer.status(session_id, branch.branch_id)
    clock.advance(timedelta(minutes=31))  # past the fourth hour
    with pytest.raises(BranchExpired):
        layer.status(session_id, branch.branch_id)


def test_the_idle_deadline_of_the_branch_is_the_last_activity_and_not_the_creation(
    layer: BranchLayer, clock, session_id: str, scenario_id: str
) -> None:
    branch = layer.fork(session_id, scenario_id).branch
    clock.advance(timedelta(minutes=30))
    moved = layer.status(session_id, branch.branch_id)
    assert moved.last_activity_at == clock.now
    assert moved.expires_at == clock.now + timedelta(hours=1)


def test_an_expired_branch_is_refused_by_the_layer(
    layer: BranchLayer, clock, session_id: str, scenario_id: str
) -> None:
    branch = layer.fork(session_id, scenario_id).branch
    clock.advance(timedelta(hours=2))
    with pytest.raises(BranchExpired):
        layer.status(session_id, branch.branch_id)


# --- the guard of the paths of the store --------------------------------------------------------------


@pytest.mark.parametrize("name", ["a/b", "../escape", "a\\b", "with\0null", "..", ".", ""])
def test_the_store_refuses_a_session_name_that_is_not_usable(store: BranchStore, name: str) -> None:
    with pytest.raises(ValueError):
        store.list_branches(name)


def test_the_store_refuses_a_branch_identifier_with_a_separator(
    store: BranchStore, layer: BranchLayer, session_id: str, scenario_id: str
) -> None:
    layer.fork(session_id, scenario_id)
    owner = canonical_session_id(session_id)
    with pytest.raises(BranchNotFound):
        store.get_branch("sb_../../etc/passwd", owner)
    with pytest.raises(BranchNotFound):
        store.read_events("sb_/etc/passwd", owner)


def test_the_store_writes_nothing_outside_its_root(
    store: BranchStore, tmp_path: Path, session_id: str, scenario_id: str
) -> None:
    if not isinstance(store, FileBranchStore):
        pytest.skip("the files of the store are only meaningful for the file backed one")
    row = SandboxBranchRow(
        branch_id="sb_a/b",
        owner_session=canonical_session_id(session_id),
        scenario_id=scenario_id,
        base_snapshot_id="sample-42",
        base_canonical_hash="0" * 64,
        revision=0,
        current_canonical_hash="0" * 64,
        created_at=datetime.now(UTC),
        last_activity_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    before = {path.name for path in tmp_path.iterdir()}
    store.create_branch(row)
    assert {path.name for path in tmp_path.iterdir()} == before


def test_a_read_of_a_branch_does_not_open_the_file_of_another_visitor(
    store: BranchStore,
    layer: BranchLayer,
    session_id: str,
    other_session_id: str,
    scenario_id: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not isinstance(store, FileBranchStore):
        pytest.skip("the files of the store are only meaningful for the file backed one")
    mine = layer.fork(session_id, scenario_id).branch
    layer.fork(other_session_id, scenario_id)
    opened: list[Path] = []
    original = Path.read_text

    def record(self: Path, *args: object, **kwargs: object) -> str:
        opened.append(self)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", record)
    store.get_branch(mine.branch_id, canonical_session_id(session_id))
    other = store.root / canonical_session_id(other_session_id)
    assert not [path for path in opened if other in path.parents]


def test_the_store_refuses_a_row_whose_owner_is_not_the_session_of_its_folder(
    store: BranchStore, layer: BranchLayer, session_id: str, scenario_id: str
) -> None:
    """The owner of the row decides, not only the folder it sits in."""
    if not isinstance(store, FileBranchStore):
        pytest.skip("the files of the store are only meaningful for the file backed one")
    branch = layer.fork(session_id, scenario_id).branch
    owner = canonical_session_id(session_id)
    path = next(store.root.glob(f"{owner}/*/branch.json"))
    row = json.loads(path.read_text(encoding="utf-8"))
    row["owner_session"] = "someone-else"
    path.write_text(json.dumps(row), encoding="utf-8")
    with pytest.raises(BranchNotFound):
        store.get_branch(branch.branch_id, owner)
