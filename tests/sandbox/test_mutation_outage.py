"""The outage of the FX tool: the state of the tools of a branch, and the round trip of the kind.

Why this file exists: the catalog of the sandbox grows with a kind only when the kind has a round trip test
(ADR-021). The outage of the FX tool is the fourth kind of the catalog, and the first kind that changes the state of
the branch and not the rows of the ledger: the tool of the branch is unavailable, or it is available again
(ADR-032).

Why the kind needs a decision about the hash: the rows of the ledger do not move, so the hash of the rows of the
branch does not move either, and a branch whose hash does not move when its state moves is a branch that cannot prove
its own state. The hash of a branch therefore covers the derived state of the branch, and a branch that holds no
derived state keeps the hash of the published base (FR-010, ADR-021, ADR-032).

Why the verdict of the case moves: with the source of the reference rate down, the measure of the case cannot be
computed, so the verdict is `not_available` and the detail of the answer names the outage and its error code.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from ledgerlens.run_context import canonical_session_id
from ledgerlens.sandbox.branch import BranchHashMismatch, BranchLayer
from ledgerlens.sandbox.mutation import MutationCommand, MutationRejected, status_for_code
from ledgerlens.sandbox.projector import EVENT_TOOL_FX_OUTAGE, ProjectedState, project
from ledgerlens.sandbox.snapshot import BaseSnapshot
from ledgerlens.sandbox.store import BranchStore

# The scenario of the case of the markup: it has a refund and a truth with a range, so the verdict is a real label.
SCENARIO = "S01"
# The error code the published schema declares for the outage.
ERROR_CODE = "UPSTREAM_UNAVAILABLE"


def _outage(
    enabled: bool = True,
    key: str = "cmd-0001",
    revision: int = 0,
    error_code: str = ERROR_CODE,
) -> MutationCommand:
    """The command of an outage of the FX tool.

    The `enabled` flag says whether the tool goes down or comes back, and the error code is the one the published
    schema declares.
    """
    return MutationCommand(
        kind="tool.fx_outage",
        payload={"enabled": enabled, "error_code": error_code},
        expected_revision=revision,
        idempotency_key=key,
    )


def _state_of_the_branch(base: BaseSnapshot, store: BranchStore, owner_session: str, branch_id: str) -> ProjectedState:
    """The state of the branch, rebuilt from the base and from the events of the branch alone."""
    return project(base, store.read_events(branch_id, owner_session))


# --- the preview computes and writes nothing -------------------------------------------------------------------


def test_the_preview_of_an_outage_writes_nothing(layer: BranchLayer, session_id: str, event_count) -> None:
    """FR-016: the preview of an outage computes in memory and writes nothing."""
    branch = layer.fork(session_id, SCENARIO).branch
    before = layer.status(session_id, branch.branch_id)
    events_before = event_count(branch.branch_id)

    preview = layer.preview_mutation(session_id, branch.branch_id, _outage())

    after = layer.status(session_id, branch.branch_id)
    assert preview.valid is True
    assert after.revision == before.revision == 0
    assert after.current_canonical_hash == before.current_canonical_hash
    assert event_count(branch.branch_id) == events_before == 0


def test_the_preview_and_the_commit_of_an_outage_see_the_same_state(layer: BranchLayer, session_id: str) -> None:
    """The preview and the commit see exactly the same state: the same projected hash and the same diff (ADR-031)."""
    branch = layer.fork(session_id, SCENARIO).branch
    preview = layer.preview_mutation(session_id, branch.branch_id, _outage())

    result = layer.commit_mutation(session_id, branch.branch_id, _outage())

    assert preview.projected_canonical_hash == result.canonical_hash
    assert list(preview.records) == list(result.diff)


# --- the commit moves the branch exactly once ------------------------------------------------------------------


def test_the_commit_of_an_outage_appends_one_event_and_moves_the_revision_by_exactly_one(
    layer: BranchLayer, session_id: str, event_count
) -> None:
    """FR-036: the revision of the branch is the number of the mutations that were really applied."""
    branch = layer.fork(session_id, SCENARIO).branch

    result = layer.commit_mutation(session_id, branch.branch_id, _outage())
    status = layer.status(session_id, branch.branch_id)

    assert result.revision == 1
    assert status.revision == 1
    assert event_count(branch.branch_id) == 1


def test_the_commit_of_an_outage_moves_the_hash_of_the_branch(layer: BranchLayer, session_id: str) -> None:
    """The hash of the branch covers the derived state, so an outage moves it (ADR-032)."""
    branch = layer.fork(session_id, SCENARIO).branch
    before = layer.status(session_id, branch.branch_id)

    result = layer.commit_mutation(session_id, branch.branch_id, _outage())
    after = layer.status(session_id, branch.branch_id)

    assert result.canonical_hash != before.current_canonical_hash
    assert after.current_canonical_hash == result.canonical_hash


def test_the_event_of_an_outage_carries_the_published_payload_and_the_origin_of_the_sandbox(
    layer: BranchLayer, session_id: str, store: BranchStore, owner_session: str
) -> None:
    """The event of a branch is a `sandbox.*` event, and it carries the published payload of the command (ADR-031)."""
    branch = layer.fork(session_id, SCENARIO).branch
    layer.commit_mutation(session_id, branch.branch_id, _outage())
    events = store.read_events(branch.branch_id, owner_session)

    assert [event.event_type for event in events] == [EVENT_TOOL_FX_OUTAGE]
    assert [event.origin for event in events] == ["sandbox"]
    assert events[0].payload == {"enabled": True, "error_code": ERROR_CODE}


# --- the state of the tool --------------------------------------------------------------------------------------


def test_the_diff_of_the_outage_names_the_tool_with_the_value_before_and_the_value_after(
    layer: BranchLayer, session_id: str
) -> None:
    """The diff of the branch shows the state of the tool: an empty value means the tool is available (ADR-032)."""
    branch = layer.fork(session_id, SCENARIO).branch

    result = layer.commit_mutation(session_id, branch.branch_id, _outage())

    assert [
        (entry["record"], entry["record_id"], entry["field"], entry["before"], entry["after"]) for entry in result.diff
    ] == [("tools", "fx", "outage", "", ERROR_CODE)]
    assert result.diff[0]["value_kind"] == "non_monetary"
    assert result.diff[0]["currency"] is None


def test_the_diff_of_the_end_of_the_outage_is_the_reverse_of_the_diff_of_the_outage(
    layer: BranchLayer, session_id: str
) -> None:
    """When the tool comes back the value before is the error code and the value after is empty."""
    branch = layer.fork(session_id, SCENARIO).branch
    layer.commit_mutation(session_id, branch.branch_id, _outage())

    result = layer.commit_mutation(
        session_id,
        branch.branch_id,
        _outage(enabled=False, key="cmd-0002", revision=1),
    )

    assert [
        (entry["record"], entry["record_id"], entry["field"], entry["before"], entry["after"]) for entry in result.diff
    ] == [("tools", "fx", "outage", ERROR_CODE, "")]


def test_the_outage_moves_no_row_of_the_ledger(layer: BranchLayer, session_id: str) -> None:
    """The outage changes the state of the tools of the branch and not the rows of the ledger (ADR-032)."""
    branch = layer.fork(session_id, SCENARIO).branch
    before = layer.diff(session_id, branch.branch_id)

    layer.commit_mutation(session_id, branch.branch_id, _outage())
    after = layer.diff(session_id, branch.branch_id)

    assert before.diff == []
    assert [entry["record"] for entry in after.diff] == ["tools"]


def test_the_state_of_the_tool_is_the_last_event_of_the_log(layer: BranchLayer, session_id: str) -> None:
    """The events are applied in the order of the log, so the last one decides the state of the tool (ADR-032)."""
    branch = layer.fork(session_id, SCENARIO).branch
    layer.commit_mutation(session_id, branch.branch_id, _outage())
    layer.commit_mutation(session_id, branch.branch_id, _outage(enabled=False, key="cmd-0002", revision=1))

    result = layer.commit_mutation(session_id, branch.branch_id, _outage(enabled=True, key="cmd-0003", revision=2))

    assert [(entry["before"], entry["after"]) for entry in result.diff] == [("", ERROR_CODE)]


# --- the hash of the branch ------------------------------------------------------------------------------------


def test_the_hash_of_a_branch_without_derived_state_is_the_hash_of_the_published_base(
    layer: BranchLayer, session_id: str
) -> None:
    """A branch that holds no derived state has the hash of its rows, and the rows are the rows of the base.

    The outage was ended, so the branch holds no derived state and its hash is the hash of the base again. The two
    hashes stay comparable, which is the promise of FR-010 (ADR-032).
    """
    branch = layer.fork(session_id, SCENARIO).branch
    before = layer.status(session_id, branch.branch_id)
    layer.commit_mutation(session_id, branch.branch_id, _outage())
    layer.commit_mutation(session_id, branch.branch_id, _outage(enabled=False, key="cmd-0002", revision=1))

    after = layer.status(session_id, branch.branch_id)

    assert after.current_canonical_hash == before.current_canonical_hash


def test_the_branch_rebuilt_from_the_events_alone_has_the_same_canonical_hash(
    layer: BranchLayer, session_id: str, base_snapshot: BaseSnapshot, store: BranchStore, owner_session: str
) -> None:
    """FR-009 and FR-010: the state of a branch is a pure function of the base and of the log."""
    branch = layer.fork(session_id, SCENARIO).branch

    result = layer.commit_mutation(session_id, branch.branch_id, _outage())
    rebuilt = _state_of_the_branch(base_snapshot, store, owner_session, branch.branch_id)

    assert rebuilt.canonical_hash == result.canonical_hash


def test_a_branch_whose_log_was_tampered_with_cannot_prove_its_own_state(
    layer: BranchLayer, session_id: str, store: BranchStore, owner_session: str, tamper_events
) -> None:
    """ADR-021 and ADR-032: a branch whose derived state was tampered with is refused with `HASH_MISMATCH`."""
    branch = layer.fork(session_id, SCENARIO).branch
    layer.commit_mutation(session_id, branch.branch_id, _outage())
    events = store.read_events(branch.branch_id, owner_session)
    tampered = [replace(event, payload={**event.payload, "enabled": False}) for event in events]
    tamper_events(branch.branch_id, tampered)

    with pytest.raises(BranchHashMismatch) as refusal:
        layer.status(session_id, branch.branch_id)

    assert refusal.value.code == "HASH_MISMATCH"


# --- the verdict of the case -----------------------------------------------------------------------------------


def test_the_verdict_of_the_case_with_the_fx_tool_down_is_not_available(layer: BranchLayer, session_id: str) -> None:
    """With the source of the reference rate down, the measure of the case cannot be computed (ADR-032)."""
    branch = layer.fork(session_id, SCENARIO).branch
    before = layer.diff(session_id, branch.branch_id)

    result = layer.commit_mutation(session_id, branch.branch_id, _outage())

    assert before.verdict["label"] == "within_expected_range"
    assert result.verdict["label"] == "not_available"
    assert ERROR_CODE in result.verdict["detail"]


def test_the_verdict_of_the_case_comes_back_when_the_tool_is_back(layer: BranchLayer, session_id: str) -> None:
    """With the tool back, the verdict is the one of the state of the rows, exactly as before."""
    branch = layer.fork(session_id, SCENARIO).branch
    before = layer.diff(session_id, branch.branch_id)
    layer.commit_mutation(session_id, branch.branch_id, _outage())

    result = layer.commit_mutation(session_id, branch.branch_id, _outage(enabled=False, key="cmd-0002", revision=1))

    assert result.verdict == before.verdict


# --- the undo takes the outage back ------------------------------------------------------------------------------


def test_the_undo_takes_the_outage_back(layer: BranchLayer, session_id: str) -> None:
    """ADR-024 and ADR-032: the undo takes the derived state back and the hash with it."""
    branch = layer.fork(session_id, SCENARIO).branch
    before = layer.status(session_id, branch.branch_id)
    layer.commit_mutation(session_id, branch.branch_id, _outage())

    result = layer.undo(
        session_id,
        branch.branch_id,
        MutationCommand(kind="branch.undo", payload={}, expected_revision=1, idempotency_key="undo-0001"),
    )
    after = layer.status(session_id, branch.branch_id)

    assert result.revision == 0
    assert after.revision == 0
    assert after.current_canonical_hash == before.current_canonical_hash


def test_the_undo_of_an_outage_leaves_no_outage_in_the_state_of_the_branch(
    layer: BranchLayer, session_id: str, base_snapshot: BaseSnapshot, store: BranchStore, owner_session: str
) -> None:
    """The state of the tools of the branch is derived from the log, so the undo takes it back (ADR-032)."""
    branch = layer.fork(session_id, SCENARIO).branch
    layer.commit_mutation(session_id, branch.branch_id, _outage())
    layer.undo(
        session_id,
        branch.branch_id,
        MutationCommand(kind="branch.undo", payload={}, expected_revision=1, idempotency_key="undo-0001"),
    )

    state = _state_of_the_branch(base_snapshot, store, owner_session, branch.branch_id)

    assert state.derived.outage_of("fx") == ""
    assert state.derived.is_empty() is True


# --- the refusals of the kind ------------------------------------------------------------------------------------


def test_an_outage_that_is_already_on_is_refused_with_INVALID_STATE(
    layer: BranchLayer, session_id: str, event_count
) -> None:
    """A command that changes nothing is refused: the hash of a branch only moves when its state moves (ADR-032)."""
    branch = layer.fork(session_id, SCENARIO).branch
    layer.commit_mutation(session_id, branch.branch_id, _outage())

    with pytest.raises(MutationRejected) as refusal:
        layer.commit_mutation(session_id, branch.branch_id, _outage(key="cmd-0002", revision=1))

    assert refusal.value.code == "INVALID_STATE"
    assert status_for_code("INVALID_STATE") == 422
    assert event_count(branch.branch_id) == 1


def test_the_end_of_an_outage_that_does_not_exist_is_refused_with_INVALID_STATE(
    layer: BranchLayer, session_id: str, event_count
) -> None:
    """There is no outage to end when the tool is available, so the command changes nothing (ADR-032)."""
    branch = layer.fork(session_id, SCENARIO).branch

    with pytest.raises(MutationRejected) as refusal:
        layer.commit_mutation(session_id, branch.branch_id, _outage(enabled=False))

    assert refusal.value.code == "INVALID_STATE"
    assert status_for_code("INVALID_STATE") == 422
    assert event_count(branch.branch_id) == 0


def test_the_refusal_of_an_outage_writes_nothing(layer: BranchLayer, session_id: str) -> None:
    """A refused command never appends an event and never moves the branch (SC-007)."""
    branch = layer.fork(session_id, SCENARIO).branch
    before = layer.status(session_id, branch.branch_id)

    with pytest.raises(MutationRejected):
        layer.commit_mutation(session_id, branch.branch_id, _outage(enabled=False))

    after = layer.status(session_id, branch.branch_id)
    assert after.revision == before.revision == 0
    assert after.current_canonical_hash == before.current_canonical_hash


# --- a log that was tampered with ------------------------------------------------------------------------------


@pytest.mark.parametrize("missing", ["enabled", "error_code"])
def test_an_outage_event_whose_payload_lost_a_field_is_refused_with_HASH_MISMATCH(
    layer: BranchLayer,
    session_id: str,
    store: BranchStore,
    owner_session: str,
    tamper_events,
    missing: str,
) -> None:
    """A payload that lost a field is a log that was tampered with, and the branch is refused (ADR-021, ADR-032).

    Why the error code matters as much as the flag: an outage with no error code is a tool that is down with
    nothing to say, and the verdict of the case would stay blind to it.
    """
    branch = layer.fork(session_id, SCENARIO).branch
    layer.commit_mutation(session_id, branch.branch_id, _outage())
    events = store.read_events(branch.branch_id, owner_session)
    tampered = [
        replace(event, payload={name: value for name, value in event.payload.items() if name != missing})
        for event in events
    ]
    tamper_events(branch.branch_id, tampered)

    with pytest.raises(BranchHashMismatch) as refusal:
        layer.status(session_id, branch.branch_id)

    assert refusal.value.code == "HASH_MISMATCH"
    # The log could not be projected at all, and not only hashed differently: the interpreter refused the event.
    assert "cannot be projected" in refusal.value.message


# --- the diff of a branch that holds both kinds of change ---------------------------------------------------------


def test_the_entries_of_the_derived_state_come_after_the_entries_of_the_rows(
    layer: BranchLayer, session_id: str, adjustment: MutationCommand
) -> None:
    """ADR-032: the entries of the derived state come after the entries of the rows.

    Why this proof: the diff of a branch that changed a row and that changed its state at the same time holds
    both kinds of entry, so the order of the entries is visible in one read.
    """
    branch = layer.fork(session_id, SCENARIO).branch
    layer.commit_mutation(session_id, branch.branch_id, adjustment)
    layer.commit_mutation(session_id, branch.branch_id, _outage(key="cmd-0002", revision=1))

    diff = layer.diff(session_id, branch.branch_id)

    assert [entry["record"] for entry in diff.diff] == ["fx_applied", "refunds", "tools"]
    assert diff.diff[-1]["field"] == "outage"


def test_two_branches_with_the_same_derived_state_and_different_rows_have_different_hashes(
    layer: BranchLayer,
    session_id: str,
    other_session_id: str,
    base_snapshot: BaseSnapshot,
    store: BranchStore,
    owner_session: str,
    adjustment: MutationCommand,
) -> None:
    """ADR-032: the hash of a branch that holds a derived state covers its rows and not only its derived state.

    Why this proof: the rows of a branch are not reachable through the public interface, so the proof is made
    with two branches of the same base. The two hold the same derived state, the outage of the FX tool, and
    different rows, the second one holds an adjusted refund. Their hashes have to be different, because a hash
    that covered the derived state alone would say that the two branches are the same branch.
    """
    first = layer.fork(session_id, SCENARIO).branch
    second = layer.fork(other_session_id, SCENARIO).branch
    layer.commit_mutation(session_id, first.branch_id, _outage())
    layer.commit_mutation(other_session_id, second.branch_id, _outage())
    layer.commit_mutation(
        other_session_id,
        second.branch_id,
        replace(adjustment, expected_revision=1, idempotency_key="cmd-0002"),
    )

    first_state = project(base_snapshot, store.read_events(first.branch_id, owner_session))
    second_state = project(
        base_snapshot,
        store.read_events(second.branch_id, canonical_session_id(other_session_id)),
    )

    assert first_state.derived == second_state.derived
    assert first_state.rows != second_state.rows
    assert first_state.canonical_hash != second_state.canonical_hash
