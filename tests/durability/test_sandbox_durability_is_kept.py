"""The durable side of the sandbox is kept: a commit sent twice leaves one event, and the projection does not move.

What they guarantee, and why: the branch of a visitor is already durable, and this milestone does not touch it.
A commit that is sent twice with the same idempotency key leaves one event of the branch and an unchanged
projection, so that a change of the sandbox in a later task of this milestone fails here (the first task of
the plan: the durable side of the sandbox is not rebuilt).

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
    return BaseResolver(tmp_path_factory.mktemp("durability_base"))


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


def test_a_commit_sent_twice_leaves_one_event_and_an_unchanged_projection(
    layer: BranchLayer, base_resolver: BaseResolver
) -> None:
    """The idempotent commit of the branch is the rule the journal of a run reuses."""
    base = base_resolver(SCENARIO_ID)
    branch = layer.fork(SESSION_ID, SCENARIO_ID).branch
    command = _command()

    first = layer.commit_mutation(SESSION_ID, branch.branch_id, command)
    second = layer.commit_mutation(SESSION_ID, branch.branch_id, command)

    events = layer.store.read_events(branch.branch_id, canonical_session_id(SESSION_ID))
    assert len(events) == 1
    assert second.revision == first.revision
    assert second.canonical_hash == first.canonical_hash

    projection = project(base, events)
    assert projection.canonical_hash == first.canonical_hash
