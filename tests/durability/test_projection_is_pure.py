"""The projection is pure: the same base and the same log give the same hash, whatever the order of the events was.

What they guarantee, and why: the state of a branch is a pure function of the base and of the log (ADR-032),
so two projections of the same log give the same hash, a rebuild of the projector gives the same hash as the
projection it rebuilt, and two branches that received the same events in the same order project to the same
hash. The order of the events of the log is the order they were appended, and the projection of that order is
deterministic: a reader that rebuilds the projection reads the same state.

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
    return BaseResolver(tmp_path_factory.mktemp("durability_projection_base"))


def _command(key: str, rate: str, revision: int = 0) -> MutationCommand:
    """A command of the adjustment of the rate of the refund of S01, with its key and its expected revision."""
    return MutationCommand(
        kind="refund.apply_fx_adjustment",
        payload={"refund_id": "R-0731", "applied_rate": rate, "effective_at": "2026-11-24T00:00:00Z"},
        reason="the visitor tries another rate",
        expected_revision=revision,
        idempotency_key=key,
    )


def test_a_rebuild_of_the_projector_gives_the_same_hash(tmp_path: Path, base_resolver: BaseResolver) -> None:
    """Two projections of the same log give the same hash, whenever the projector runs."""
    base = base_resolver(SCENARIO_ID)
    layer = BranchLayer(FileBranchStore(tmp_path / "sandbox"), base_resolver)
    branch = layer.fork(SESSION_ID, SCENARIO_ID).branch
    layer.commit_mutation(SESSION_ID, branch.branch_id, _command("cmd-0001", "5.41250000"))
    layer.commit_mutation(SESSION_ID, branch.branch_id, _command("cmd-0002", "5.40000000", revision=1))

    first = project(base, layer.store.read_events(branch.branch_id, canonical_session_id(SESSION_ID)))
    rebuilt = project(base, layer.store.read_events(branch.branch_id, canonical_session_id(SESSION_ID)))

    assert rebuilt.canonical_hash == first.canonical_hash


def test_two_branches_with_the_same_events_in_the_same_order_project_to_the_same_hash(
    tmp_path: Path, base_resolver: BaseResolver
) -> None:
    """The hash is of the base and of the log, and not of the branch that holds them."""
    base = base_resolver(SCENARIO_ID)
    layer = BranchLayer(FileBranchStore(tmp_path / "sandbox"), base_resolver)
    first_branch = layer.fork(SESSION_ID, SCENARIO_ID).branch
    second_branch = layer.fork("Visitor-B", SCENARIO_ID).branch
    for revision, (key, rate) in enumerate((("cmd-0001", "5.41250000"), ("cmd-0002", "5.40000000"))):
        layer.commit_mutation(SESSION_ID, first_branch.branch_id, _command(key, rate, revision=revision))
        layer.commit_mutation("Visitor-B", second_branch.branch_id, _command(key, rate, revision=revision))

    first = project(base, layer.store.read_events(first_branch.branch_id, canonical_session_id(SESSION_ID)))
    second = project(base, layer.store.read_events(second_branch.branch_id, canonical_session_id("Visitor-B")))

    assert second.canonical_hash == first.canonical_hash
