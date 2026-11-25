"""The reader of the diff of a branch, published as data.

Why the diff is a read of the branch under ADR-028: the diff of a branch is the difference between the published
base of the branch and the state the branch holds now, and the reader computes it from the branch without moving
anything. The export of the diff copies and hashes and never writes: the revision and the canonical hash of the
branch are the same before and after the export, and the test of the artifact proves it.

Why the artifact carries the commands of the log: the diff says what the branch holds, and the commands say how
it got there. The events of the log are the reproduction of the mutation, because the projection of the branch
is rebuilt from the events alone, and a reader who wants the state replays the events over the base.

Why the domain never imports the facade: the reader works over the branch layer, and the layer is the domain of
the sandbox. The facade of the HTTP is a caller of the layer, and a domain that imported the facade would be a
domain that depends on its caller.
"""

from __future__ import annotations

import json
from typing import Any

from ledgerlens.sandbox.branch import BranchLayer
from ledgerlens.sandbox.projector import (
    EVENT_CHARGEBACK_DEADLINE_CHANGED,
    EVENT_PAYMENT_DUPLICATED,
    EVENT_RECORD_NOTE_INJECTED,
    EVENT_REFUND_FX_ADJUSTED,
    EVENT_TOOL_FX_OUTAGE,
)

# The version of the schema of the artifact, so that a reader of a later version knows the artifact is not of its
# version.
ARTIFACT_SCHEMA_VERSION = "1"

# The events of the log that are mutations of the branch. The marker of an undo is not a mutation: it takes a
# mutation back, and the artifact names the mutations and never the markers (ADR-024).
MUTATION_EVENT_TYPES = frozenset(
    {
        EVENT_REFUND_FX_ADJUSTED,
        EVENT_PAYMENT_DUPLICATED,
        EVENT_CHARGEBACK_DEADLINE_CHANGED,
        EVENT_TOOL_FX_OUTAGE,
        EVENT_RECORD_NOTE_INJECTED,
    }
)


def read_diff_artifact(layer: BranchLayer, session_id: str, branch_id: str) -> dict[str, Any]:
    """The artifact of the diff of the branch: the diff, the hash of the branch, the hash of the base and the
    commands that reproduce the mutation.

    The artifact is a value: it is built from the reads of the layer and it writes nothing, so the branch is the
    same before and after the read. The commands are the events of the log of the branch, because the projection
    of the branch is rebuilt from the events alone and a reader who wants the state replays them over the base.
    """
    diff = layer.diff(session_id, branch_id)
    history = layer.history(session_id, branch_id)
    status = layer.status(session_id, branch_id)
    return {
        "artifact": "sandbox_diff",
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "scenario": status.scenario_id,
        "branch_id": branch_id,
        "revision": diff.revision,
        "base_canonical_hash": diff.base_canonical_hash,
        "canonical_hash": diff.canonical_hash,
        "diff": list(diff.diff),
        "invariants": list(diff.invariants),
        "verdict": dict(diff.verdict),
        "commands": [
            {
                "event_type": event["event_type"],
                "aggregate_id": event["aggregate_id"],
                "payload": dict(event["payload"]),
            }
            for event in history.events
            if event["event_type"] in MUTATION_EVENT_TYPES
        ],
        "reproduce": (
            f"uv run python scripts/export_sandbox_diff.py --branch {branch_id} --session {session_id}"
        ),
    }


def render_diff_artifact(artifact: dict[str, Any]) -> bytes:
    """The bytes of the artifact, canonical: two renders of the same artifact are byte identical.

    Why the render is canonical: the artifact is published, and a publication whose bytes move between two reads
    of the same branch is a publication that cannot be hashed. The keys are sorted and the indent is fixed, so
    the bytes are a function of the artifact and of nothing else.
    """
    return (json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
