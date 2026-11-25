"""The restart of a suspended run: the branch of the visitor does not move twice.

What they guarantee, and why: (a) a commit that is sent twice with the same idempotency key leaves one event of the
branch, because a crash and a retry of a run must not duplicate the events of the branch of the visitor (FR-007);
(b) the projection of the branch is the same after the second commit, because the projection is a pure function of
the base and the log of the branch.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ledgerlens.run_context import canonical_session_id
from ledgerlens.sandbox.branch import BranchLayer
from ledgerlens.sandbox.mutation import MutationCommand
from ledgerlens.sandbox.projector import project
from ledgerlens.sandbox.snapshot import BaseResolver
from ledgerlens.sandbox.store import FileBranchStore

SCENARIO_ID = "S01"
SESSION_ID = "Visitor-A"


@pytest.fixture(scope="module")
def base_resolver(tmp_path_factory: pytest.TempPathFactory) -> BaseResolver:
    """The resolver of the immutable base, with its own working folder outside the repository."""
    return BaseResolver(tmp_path_factory.mktemp("orchestration_base"))


@pytest.fixture(scope="module")
def base_snapshot(base_resolver: BaseResolver):
    """The base of the scenario S01, built once for the whole module."""
    return base_resolver(SCENARIO_ID)


@pytest.fixture()
def layer(tmp_path: Path, base_resolver: BaseResolver) -> BranchLayer:
    """The layer of the branches, with the store of the test."""
    store = FileBranchStore(tmp_path / "sandbox")
    return BranchLayer(store, base_resolver)


def _command() -> MutationCommand:
    """The command of the adjustment of the rate of the refund of S01, with its key."""
    return MutationCommand(
        kind="refund.apply_fx_adjustment",
        payload={"refund_id": "R-0731", "applied_rate": "5.41250000", "effective_at": "2026-11-24T00:00:00Z"},
        reason="the visitor tries another rate",
        expected_revision=0,
        idempotency_key="cmd-0001",
    )


def test_a_commit_that_is_sent_twice_leaves_one_event_of_the_branch(
    layer: BranchLayer, base_snapshot
) -> None:
    """A crash and a retry do not duplicate the events of the branch (FR-007)."""
    branch = layer.fork(SESSION_ID, SCENARIO_ID).branch
    command = _command()

    first = layer.commit_mutation(SESSION_ID, branch.branch_id, command)
    second = layer.commit_mutation(SESSION_ID, branch.branch_id, command)

    events = layer.store.read_events(branch.branch_id, canonical_session_id(SESSION_ID))
    assert len(events) == 1
    assert second.revision == first.revision
    assert second.canonical_hash == first.canonical_hash


def test_the_projection_of_the_branch_is_the_same_after_the_second_commit(
    layer: BranchLayer, base_snapshot
) -> None:
    """The projection is a pure function of the base and the log, and the log did not grow."""
    branch = layer.fork(SESSION_ID, SCENARIO_ID).branch
    command = _command()

    layer.commit_mutation(SESSION_ID, branch.branch_id, command)
    first = project(base_snapshot, layer.store.read_events(branch.branch_id, canonical_session_id(SESSION_ID)))
    layer.commit_mutation(SESSION_ID, branch.branch_id, command)
    second = project(base_snapshot, layer.store.read_events(branch.branch_id, canonical_session_id(SESSION_ID)))

    assert second.canonical_hash == first.canonical_hash
