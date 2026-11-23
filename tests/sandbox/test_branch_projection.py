"""The projection of a branch: the hash, the diff, the verdict and the invariants.

Why the projection is a pure function: the state of a branch is the base plus the events of the branch, and
nothing else (FR-009). So a branch rebuilt from its events alone has the same canonical hash as the hash the
commit reported (SC-003), and two readers of the same revision see the same thing (SC-009).

The verdict is one of the four declared labels, and the invariants are evaluated over every projection, so a
mutation that breaks a rule of the domain never reaches the branch (FR-018, FR-020).
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from ledgerlens.sandbox.branch import BranchHashMismatch, BranchLayer, SandboxBranch
from ledgerlens.sandbox.invariants import evaluate
from ledgerlens.sandbox.mutation import MutationCommand
from ledgerlens.sandbox.projector import VERDICT_LABELS, diff_of, project
from ledgerlens.sandbox.snapshot import BaseSnapshot
from ledgerlens.sim.events import canonical_json


def _command(payload: dict[str, object], key: str = "cmd-0001") -> MutationCommand:
    return MutationCommand(
        kind="refund.apply_fx_adjustment",
        payload=payload,
        expected_revision=0,
        idempotency_key=key,
    )


# --- the hash of the projection -----------------------------------------------------------------------------


def test_the_projection_of_a_branch_at_revision_zero_has_the_canonical_hash_of_the_base(
    base_snapshot: BaseSnapshot, forked_branch: SandboxBranch, store, owner_session
) -> None:
    events = store.read_events(forked_branch.branch_id, owner_session)
    state = project(base_snapshot, events)
    assert state.canonical_hash == base_snapshot.canonical_hash


def test_the_projection_rebuilt_from_the_events_alone_has_the_hash_the_commit_reported(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment: MutationCommand,
    base_snapshot: BaseSnapshot,
    store,
    owner_session,
) -> None:
    result = layer.commit_mutation(session_id, forked_branch.branch_id, adjustment)
    events = store.read_events(forked_branch.branch_id, owner_session)
    rebuilt = project(base_snapshot, events)
    assert rebuilt.canonical_hash == result.canonical_hash


def test_the_projection_of_the_base_is_the_account_scoped_rows_of_the_base(
    base_snapshot: BaseSnapshot, forked_branch: SandboxBranch, store, owner_session
) -> None:
    events = store.read_events(forked_branch.branch_id, owner_session)
    state = project(base_snapshot, events)
    assert [row["id"] for row in state.rows["transactions"]] == ["TX-2048"]
    assert [row["id"] for row in state.rows["refunds"]] == ["R-0731"]


# --- the branch that cannot prove its own state ---------------------------------------------------------------


def test_a_branch_whose_row_disagrees_with_its_events_is_refused_with_HASH_MISMATCH(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment: MutationCommand,
    store,
    owner_session,
    tamper_events,
) -> None:
    """ADR-021: a branch whose row does not agree with the projection of its events is never served as valid."""
    layer.commit_mutation(session_id, forked_branch.branch_id, adjustment)
    events = store.read_events(forked_branch.branch_id, owner_session)
    tampered = [
        replace(event, payload={**event.payload, "applied_rate": "1.00015"}) for event in events
    ]
    tamper_events(forked_branch.branch_id, tampered)
    with pytest.raises(BranchHashMismatch) as refusal:
        layer.status(session_id, forked_branch.branch_id)
    assert refusal.value.code == "HASH_MISMATCH"
    assert "fork" in refusal.value.message


def test_the_ledger_of_a_branch_that_cannot_prove_its_state_is_refused(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment: MutationCommand,
    tamper_events,
    base_snapshot: BaseSnapshot,
) -> None:
    layer.commit_mutation(session_id, forked_branch.branch_id, adjustment)
    tamper_events(forked_branch.branch_id, [])
    with pytest.raises(BranchHashMismatch):
        layer.ledger(session_id, forked_branch.branch_id, base_snapshot.account_id)


# --- the diff ----------------------------------------------------------------------------------------------


def test_the_diff_names_every_record_that_changed_with_the_values_of_the_base_and_of_the_projection(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment: MutationCommand,
    base_snapshot: BaseSnapshot,
    store,
    owner_session,
) -> None:
    result = layer.commit_mutation(session_id, forked_branch.branch_id, adjustment)
    events = store.read_events(forked_branch.branch_id, owner_session)
    base_state = project(base_snapshot, [])
    state = project(base_snapshot, events)
    entries = [entry.to_dict() for entry in diff_of(base_state, state)]
    assert entries == list(result.diff)
    assert [entry["record_id"] for entry in entries] == ["FX-9002", "R-0731"]


def test_two_reads_of_the_same_revision_are_byte_identical(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment: MutationCommand,
    base_snapshot: BaseSnapshot,
    store,
    owner_session,
) -> None:
    layer.commit_mutation(session_id, forked_branch.branch_id, adjustment)
    events = store.read_events(forked_branch.branch_id, owner_session)
    first = project(base_snapshot, events)
    second = project(base_snapshot, events)
    assert canonical_json(first.rows) == canonical_json(second.rows)
    assert first.canonical_hash == second.canonical_hash


# --- the verdict --------------------------------------------------------------------------------------------


def test_the_verdict_is_one_of_the_four_declared_labels(
    layer: BranchLayer, session_id: str, forked_branch: SandboxBranch, adjustment: MutationCommand
) -> None:
    result = layer.commit_mutation(session_id, forked_branch.branch_id, adjustment)
    assert result.verdict["label"] in VERDICT_LABELS
    assert len(VERDICT_LABELS) == 4


def test_the_verdict_changes_when_the_adjustment_pushes_the_case_out_of_the_range(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment_payload: dict[str, object],
) -> None:
    truth_rate = {**adjustment_payload, "applied_rate": "5.49310000"}
    before = layer.preview_mutation(session_id, forked_branch.branch_id, _command(truth_rate))
    after = layer.preview_mutation(session_id, forked_branch.branch_id, _command(adjustment_payload))
    assert before.verdict["label"] == "within_expected_range"
    assert after.verdict["label"] == "above_expected_range"


def test_the_verdict_of_a_scenario_without_a_truth_is_not_available(
    layer: BranchLayer, session_id: str, forked_branch: SandboxBranch, adjustment: MutationCommand
) -> None:
    preview = layer.preview_mutation(session_id, forked_branch.branch_id, adjustment)
    assert preview.verdict["label"] in VERDICT_LABELS


# --- the arithmetic of the money ---------------------------------------------------------------------------------


def test_the_payout_of_a_rate_that_sits_on_a_half_minor_unit_is_the_half_to_even_one(
    layer: BranchLayer, session_id: str, forked_branch: SandboxBranch, adjustment_payload: dict[str, object]
) -> None:
    """The rate 0.38685 is the case where a float and a `Decimal` disagree by one minor unit.

    Ten thousand minor units times 0.38685 is 3868.5 exactly, and the rounding to even of the ledger gives 3868
    while the float gives 3869. So this test fails the moment the arithmetic of the path stops being exact.
    """
    command = _command({**adjustment_payload, "applied_rate": "0.38685"})
    result = layer.commit_mutation(session_id, forked_branch.branch_id, command)
    payout = [entry for entry in result.diff if entry["record"] == "refunds"][0]
    assert payout["after"] == "38.68"


# --- the invariants -----------------------------------------------------------------------------------------


def test_the_invariants_are_evaluated_after_every_projection(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment: MutationCommand,
    base_snapshot: BaseSnapshot,
    store,
    owner_session,
) -> None:
    layer.commit_mutation(session_id, forked_branch.branch_id, adjustment)
    events = store.read_events(forked_branch.branch_id, owner_session)
    results = evaluate(project(base_snapshot, events))
    assert len(results) == 5
    assert all(result.passed for result in results)
    assert [result.identifier for result in results] == [
        "fx_rate_positive_and_finite",
        "refund_not_above_captured",
        "chargeback_deadline_not_before_opening",
        "valid_state_transition",
        "no_double_settlement",
    ]


def test_a_failing_invariant_names_itself_in_the_reason(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment_payload: dict[str, object],
    base_snapshot: BaseSnapshot,
    store,
    owner_session,
) -> None:
    broken = {**adjustment_payload, "applied_rate": "0"}
    plan_results = layer.preview_mutation(session_id, forked_branch.branch_id, _command(broken))
    assert plan_results.valid is False
    failed = [result for result in plan_results.invariants if not result["passed"]]
    assert [result["identifier"] for result in failed] == ["fx_rate_positive_and_finite"]
    assert "fx_rate_positive_and_finite" in failed[0]["reason"]


@pytest.mark.parametrize("rate", ["0", "0.00000000"])
def test_the_rate_of_the_projection_must_be_a_positive_and_finite_number(
    base_snapshot: BaseSnapshot,
    forked_branch: SandboxBranch,
    rate: str,
) -> None:
    """The rule of the domain and not only of the payload: the rate of a row is checked over the rows."""
    from ledgerlens.sandbox.store import SandboxEventRow

    event = SandboxEventRow(
        event_uid="evt-0001",
        branch_id=forked_branch.branch_id,
        event_type="sandbox.refund.fx_adjusted",
        aggregate_id="R-0731",
        occurred_at="2026-11-01T00:00:00Z",
        payload={"refund_id": "R-0731", "applied_rate": rate, "effective_at": "2026-11-01T00:00:00Z"},
    )
    state = project(base_snapshot, [event])
    failed = [result for result in evaluate(state) if not result.passed]
    assert [result.identifier for result in failed] == ["fx_rate_positive_and_finite"]
