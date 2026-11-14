"""The preview of a typed mutation: the numbers it would produce, and the rules it refuses.

Why the preview is the safety promise of the feature: a sandbox that writes before it explains is a sandbox that
destroys evidence. So the preview computes in memory, over a copy of the state, and the branch keeps its revision,
its canonical hash and its events (FR-016, SC-008).

The rules are checked before anything is written, and each one has its own code and a reason in plain English that
names the rule that failed (FR-015). A refused command never appends an event (SC-007).
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from ledgerlens.sandbox.branch import BranchLayer, SandboxBranch
from ledgerlens.sandbox.mutation import MutationCommand, MutationRejected


def _command(kind: str, payload: dict[str, object], key: str = "cmd-0001") -> MutationCommand:
    """A command of the given kind and payload, on the revision zero of the branch."""
    return MutationCommand(kind=kind, payload=payload, expected_revision=0, idempotency_key=key)


# --- the preview computes and writes nothing ------------------------------------------------------------


def test_the_preview_answers_the_payout_before_and_after_as_decimal_strings_with_the_currency(
    layer: BranchLayer, session_id: str, forked_branch: SandboxBranch, adjustment: MutationCommand
) -> None:
    preview = layer.preview_mutation(session_id, forked_branch.branch_id, adjustment)
    assert preview.valid is True
    assert preview.before.value == "549.31"
    assert preview.before.currency == "BRL"
    assert preview.after.value == "541.25"
    assert preview.after.currency == "BRL"


def test_the_preview_does_not_move_the_revision_the_hash_or_the_count_of_the_events(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment: MutationCommand,
    event_count,
) -> None:
    before = layer.status(session_id, forked_branch.branch_id)
    events_before = event_count(forked_branch.branch_id)
    layer.preview_mutation(session_id, forked_branch.branch_id, adjustment)
    after = layer.status(session_id, forked_branch.branch_id)
    assert after.revision == before.revision == 0
    assert after.current_canonical_hash == before.current_canonical_hash
    assert event_count(forked_branch.branch_id) == events_before == 0


def test_the_preview_answers_the_records_the_invariants_and_the_verdict(
    layer: BranchLayer, session_id: str, forked_branch: SandboxBranch, adjustment: MutationCommand
) -> None:
    preview = layer.preview_mutation(session_id, forked_branch.branch_id, adjustment)
    assert [entry["record_id"] for entry in preview.records] == ["FX-9002", "R-0731"]
    assert preview.invariants
    assert all(result["passed"] for result in preview.invariants)
    assert preview.verdict["label"] in (
        "within_expected_range",
        "below_expected_range",
        "above_expected_range",
        "not_available",
    )


# --- the rules of the payload ---------------------------------------------------------------------------


def test_the_preview_refuses_an_unknown_kind_and_names_the_kinds_that_are_accepted(
    layer: BranchLayer, session_id: str, forked_branch: SandboxBranch, adjustment_payload: dict[str, object]
) -> None:
    command = _command("refund.explode", dict(adjustment_payload))
    with pytest.raises(MutationRejected) as refusal:
        layer.preview_mutation(session_id, forked_branch.branch_id, command)
    assert refusal.value.code == "UNKNOWN_MUTATION_TYPE"
    assert "refund.apply_fx_adjustment" in refusal.value.message


def test_the_preview_refuses_a_kind_that_is_not_enabled_with_the_same_code(
    layer: BranchLayer, session_id: str, forked_branch: SandboxBranch
) -> None:
    command = _command("payment.simulate_duplicate", {"transaction_id": "TX-2048", "elapsed_seconds": 30})
    with pytest.raises(MutationRejected) as refusal:
        layer.preview_mutation(session_id, forked_branch.branch_id, command)
    assert refusal.value.code == "UNKNOWN_MUTATION_TYPE"
    assert "refund.apply_fx_adjustment" in refusal.value.message


@pytest.mark.parametrize(
    "field",
    ["origin", "branch_id", "event_uid", "base_canonical_hash", "payout_amount_minor"],
)
def test_the_preview_refuses_a_read_only_field_of_the_payload(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment_payload: dict[str, object],
    field: str,
) -> None:
    payload = {**adjustment_payload, field: "sandbox"}
    command = _command("refund.apply_fx_adjustment", payload)
    with pytest.raises(MutationRejected) as refusal:
        layer.preview_mutation(session_id, forked_branch.branch_id, command)
    assert refusal.value.code == "READ_ONLY_FIELD"
    assert field in refusal.value.message


@pytest.mark.parametrize("rate", ["5.412500001", "five", "5,4125", 5.4125])
def test_the_preview_refuses_an_amount_with_a_wrong_precision(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment_payload: dict[str, object],
    rate: object,
) -> None:
    payload = {**adjustment_payload, "applied_rate": rate}
    command = _command("refund.apply_fx_adjustment", payload)
    with pytest.raises(MutationRejected) as refusal:
        layer.preview_mutation(session_id, forked_branch.branch_id, command)
    assert refusal.value.code == "INVALID_AMOUNT"


def test_the_preview_refuses_a_currency_that_does_not_match_the_record(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment_payload: dict[str, object],
) -> None:
    payload = {**adjustment_payload, "currency": "USD"}
    command = _command("refund.apply_fx_adjustment", payload)
    with pytest.raises(MutationRejected) as refusal:
        layer.preview_mutation(session_id, forked_branch.branch_id, command)
    assert refusal.value.code == "CURRENCY_MISMATCH"
    assert "BRL" in refusal.value.message


def test_the_preview_refuses_an_effective_date_outside_the_window(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment_payload: dict[str, object],
    clock,
) -> None:
    outside = (clock.now + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {**adjustment_payload, "effective_at": outside}
    command = _command("refund.apply_fx_adjustment", payload)
    with pytest.raises(MutationRejected) as refusal:
        layer.preview_mutation(session_id, forked_branch.branch_id, command)
    assert refusal.value.code == "INVALID_EFFECTIVE_DATE"


def test_the_preview_refuses_an_effective_date_that_is_not_a_moment(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment_payload: dict[str, object],
) -> None:
    payload = {**adjustment_payload, "effective_at": "the day before yesterday"}
    command = _command("refund.apply_fx_adjustment", payload)
    with pytest.raises(MutationRejected) as refusal:
        layer.preview_mutation(session_id, forked_branch.branch_id, command)
    assert refusal.value.code == "INVALID_EFFECTIVE_DATE"


# --- a refusal never appends an event -------------------------------------------------------------------


@pytest.mark.parametrize(
    "kind,payload",
    [
        ("refund.explode", {}),
        ("payment.simulate_duplicate", {"transaction_id": "TX-2048", "elapsed_seconds": 30}),
        ("refund.apply_fx_adjustment", {"refund_id": "R-0731", "applied_rate": "5.412500001", "effective_at": "x"}),
        ("refund.apply_fx_adjustment", {"refund_id": "R-0731", "applied_rate": "5.4125", "effective_at": "x"}),
    ],
)
def test_no_refusal_appends_an_event(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    event_count,
    kind: str,
    payload: dict[str, object],
) -> None:
    command = _command(kind, payload)
    with pytest.raises(MutationRejected):
        layer.preview_mutation(session_id, forked_branch.branch_id, command)
    assert event_count(forked_branch.branch_id) == 0
