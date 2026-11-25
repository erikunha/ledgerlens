"""The artifact of the diff of a branch: the diff published as data, with a hash and with the command.

Why this test exists: the diff of a branch is a read of the branch under ADR-028, and the package of the sandbox
asks for the diff published as data and not as a picture. The artifact is a value, so the export of the diff moves
nothing, two exports of the same branch are byte identical, and the artifact carries the hash of the branch, the
hash of the base and the commands that reproduce the mutation. A diff that moved the branch would be a write
wearing the name of a read, and a diff that differed between two reads would be a picture and not a publication.
"""

from __future__ import annotations

import hashlib

from ledgerlens.sandbox.branch import BranchLayer
from ledgerlens.sandbox.diff_artifact import read_diff_artifact, render_diff_artifact
from ledgerlens.sandbox.mutation import MutationCommand


def _command(key: str, effective_at: str, revision: int = 0) -> MutationCommand:
    """The command of a valid adjustment of the rate of the refund of S01."""
    return MutationCommand(
        kind="refund.apply_fx_adjustment",
        payload={"refund_id": "R-0731", "applied_rate": "5.41250000", "effective_at": effective_at},
        reason="the visitor tries another rate",
        expected_revision=revision,
        idempotency_key=key,
    )


def test_the_export_of_the_diff_moves_neither_the_revision_nor_the_hash(
    layer: BranchLayer, session_id: str, forked_branch, effective_at: str
) -> None:
    """The export is a read: the branch is the same before and after it."""
    layer.commit_mutation(session_id, forked_branch.branch_id, _command("cmd-0001", effective_at))
    before = layer.status(session_id, forked_branch.branch_id)

    artifact = read_diff_artifact(layer, session_id, forked_branch.branch_id)
    render_diff_artifact(artifact)

    after = layer.status(session_id, forked_branch.branch_id)
    assert after.revision == before.revision
    assert after.current_canonical_hash == before.current_canonical_hash


def test_two_exports_of_the_same_branch_are_byte_identical(
    layer: BranchLayer, session_id: str, forked_branch, effective_at: str
) -> None:
    """The bytes of the artifact are a function of the branch and of nothing else."""
    layer.commit_mutation(session_id, forked_branch.branch_id, _command("cmd-0001", effective_at))

    first = render_diff_artifact(read_diff_artifact(layer, session_id, forked_branch.branch_id))
    second = render_diff_artifact(read_diff_artifact(layer, session_id, forked_branch.branch_id))

    assert first == second
    assert hashlib.sha256(first).hexdigest() == hashlib.sha256(second).hexdigest()


def test_the_artifact_carries_the_two_hashes_and_the_commands_that_reproduce_the_mutation(
    layer: BranchLayer, session_id: str, forked_branch, effective_at: str
) -> None:
    """The artifact names the hash of the branch, the hash of the base and the commands of the log."""
    layer.commit_mutation(session_id, forked_branch.branch_id, _command("cmd-0001", effective_at))

    artifact = read_diff_artifact(layer, session_id, forked_branch.branch_id)

    assert artifact["canonical_hash"] == layer.status(session_id, forked_branch.branch_id).current_canonical_hash
    assert artifact["base_canonical_hash"] == forked_branch.base_canonical_hash
    assert artifact["canonical_hash"] != artifact["base_canonical_hash"]
    assert len(artifact["commands"]) == 1
    command = artifact["commands"][0]
    assert command["event_type"] == "sandbox.refund.fx_adjusted"
    assert command["payload"]["refund_id"] == "R-0731"
    assert command["payload"]["applied_rate"] == "5.4125"
    assert "export_sandbox_diff.py" in artifact["reproduce"]


def test_the_artifact_of_a_branch_that_was_never_mutated_has_the_hash_of_the_base_twice(
    layer: BranchLayer, session_id: str, forked_branch
) -> None:
    """A branch with no mutation has the same hash twice, and the artifact says so honestly."""
    artifact = read_diff_artifact(layer, session_id, forked_branch.branch_id)

    assert artifact["revision"] == 0
    assert artifact["canonical_hash"] == artifact["base_canonical_hash"]
    assert artifact["commands"] == []
    assert artifact["diff"] == []
