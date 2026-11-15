"""The duplicate of a payment: the copy of the row of the original, and the round trip of the kind.

Why this file exists: the catalog of the sandbox grows with a kind only when the kind has a round trip test
(ADR-021). The duplicate of a payment is the first kind of the catalog that adds a row to the ledger of a branch,
so the test proves the whole round trip: the preview writes nothing, the commit moves the revision by exactly one
and appends one event, the diff names the new row, the branch rebuilt from the events alone has the same canonical
hash, and the undo takes the row back (ADR-031).

Why the copy is a copy: the visitor of the sandbox asks what happens when a customer is charged twice, so the
sandbox has to be able to show a second charge of the same payment. The copy carries the merchant, the customer,
the amount, the currency, the method, the card brand, the fingerprint and the status of the original, it moves the
moments of the payment by the elapsed seconds, it takes the next free identifier of the branch, and it says which
payment it comes from.
"""

from __future__ import annotations

import shutil
import sqlite3
from contextlib import closing
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ledgerlens.run_context import canonical_session_id
from ledgerlens.sandbox.branch import BranchLayer, SandboxBranch
from ledgerlens.sandbox.mutation import MutationCommand, MutationRejected, status_for_code, validate_command
from ledgerlens.sandbox.projector import (
    EVENT_PAYMENT_DUPLICATED,
    ProjectedState,
    next_transaction_id,
    project,
)
from ledgerlens.sandbox.snapshot import BaseSnapshot
from ledgerlens.sandbox.store import BranchStore
from ledgerlens.sim.projector import canonical_hash

# The scenario of the duplicate: the case of the customer that was charged twice (S02).
DUPLICATE_SCENARIO = "S02"
# The transaction the case is about, and the one that is the copy of the other.
ORIGINAL_TRANSACTION = "TX-2051"
TAKEN_TRANSACTION = "TX-2052"


def _duplicate(
    transaction_id: str = "TX-2048",
    elapsed: int = 30,
    key: str = "cmd-0001",
    revision: int = 0,
    currency: str | None = None,
) -> MutationCommand:
    """The command of a duplicate of a payment.

    The currency is the optional assertion of the visitor about the record, and it is left out when it is None.
    """
    payload: dict[str, object] = {"transaction_id": transaction_id, "elapsed_seconds": elapsed}
    if currency is not None:
        payload["currency"] = currency
    return MutationCommand(
        kind="payment.simulate_duplicate",
        payload=payload,
        expected_revision=revision,
        idempotency_key=key,
    )


def _state_of_the_branch(base: BaseSnapshot, store: BranchStore, owner_session: str, branch_id: str) -> ProjectedState:
    """The rows of the branch, rebuilt from the base and from the events of the branch alone."""
    return project(base, store.read_events(branch_id, owner_session))


def _base_with(base: BaseSnapshot, folder: Path, statements: list[str]) -> BaseSnapshot:
    """A copy of the base with the given statements applied to it, for the case the published rows do not cover."""
    target = folder / "base.db"
    shutil.copyfile(base.db_path, target)
    conn = sqlite3.connect(target)
    for statement in statements:
        conn.execute(statement)
    conn.commit()
    conn.close()
    with closing(sqlite3.connect(target)) as check:
        digest = canonical_hash(check)
    return replace(base, db_path=target, canonical_hash=digest)


def _layer_over(store: BranchStore, base: BaseSnapshot, clock) -> BranchLayer:
    """A branch layer over a base the test chooses."""
    return BranchLayer(store, lambda scenario_id: base, clock=clock)


def _owner(session_id: str) -> str:
    """The canonical owner of the session, the name the store files the branch under."""
    return canonical_session_id(session_id)


# --- the preview computes and writes nothing -------------------------------------------------------------------


def test_the_preview_of_a_duplicate_writes_nothing(
    layer: BranchLayer, session_id: str, forked_branch: SandboxBranch, event_count
) -> None:
    """FR-016: the preview of a duplicate computes in memory and writes nothing."""
    before = layer.status(session_id, forked_branch.branch_id)
    events_before = event_count(forked_branch.branch_id)

    preview = layer.preview_mutation(session_id, forked_branch.branch_id, _duplicate())

    after = layer.status(session_id, forked_branch.branch_id)
    assert preview.valid is True
    assert after.revision == before.revision == 0
    assert after.current_canonical_hash == before.current_canonical_hash
    assert event_count(forked_branch.branch_id) == events_before == 0


def test_the_preview_of_a_duplicate_answers_the_row_of_the_copy_it_would_write(
    layer: BranchLayer, session_id: str, forked_branch: SandboxBranch
) -> None:
    """The preview and the commit see exactly the same row: the interpreter writes it in both cases (ADR-031)."""
    preview = layer.preview_mutation(session_id, forked_branch.branch_id, _duplicate())
    result = layer.commit_mutation(session_id, forked_branch.branch_id, _duplicate())

    assert preview.projected_canonical_hash == result.canonical_hash
    assert [(entry["record_id"], entry["field"], entry["after"]) for entry in preview.records] == [
        (entry["record_id"], entry["field"], entry["after"]) for entry in result.diff
    ]


# --- the commit moves the branch exactly once ------------------------------------------------------------------


def test_the_commit_of_a_duplicate_appends_one_event_and_moves_the_revision_by_exactly_one(
    layer: BranchLayer, session_id: str, forked_branch: SandboxBranch, event_count
) -> None:
    """FR-036: the revision of the branch is the number of the mutations that were really applied."""
    result = layer.commit_mutation(session_id, forked_branch.branch_id, _duplicate())
    status = layer.status(session_id, forked_branch.branch_id)

    assert result.revision == 1
    assert status.revision == 1
    assert event_count(forked_branch.branch_id) == 1


def test_the_commit_of_a_duplicate_moves_the_hash_of_the_branch(
    layer: BranchLayer, session_id: str, forked_branch: SandboxBranch
) -> None:
    """The hash of the branch is the hash of the state the mutation produced (FR-033)."""
    before = layer.status(session_id, forked_branch.branch_id)
    result = layer.commit_mutation(session_id, forked_branch.branch_id, _duplicate())
    after = layer.status(session_id, forked_branch.branch_id)

    assert result.canonical_hash != before.current_canonical_hash
    assert after.current_canonical_hash == result.canonical_hash


def test_the_event_of_a_duplicate_carries_the_published_payload_and_the_origin_of_the_sandbox(
    layer: BranchLayer, session_id: str, forked_branch: SandboxBranch, store: BranchStore, owner_session: str
) -> None:
    """The event of a branch is a `sandbox.*` event, and it carries the published payload of the command."""
    layer.commit_mutation(session_id, forked_branch.branch_id, _duplicate(elapsed=45))
    events = store.read_events(forked_branch.branch_id, owner_session)

    assert [event.event_type for event in events] == [EVENT_PAYMENT_DUPLICATED]
    assert [event.origin for event in events] == ["sandbox"]
    assert events[0].payload == {"transaction_id": "TX-2048", "elapsed_seconds": 45}


# --- the copy is a copy of the row of the original --------------------------------------------------------------


def test_the_duplicate_carries_the_merchant_the_customer_the_amount_and_the_method_of_the_original(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    base_snapshot: BaseSnapshot,
    store: BranchStore,
    owner_session: str,
) -> None:
    """The duplicate is a second charge of the same payment, so it carries what makes the payment the same one."""
    layer.commit_mutation(session_id, forked_branch.branch_id, _duplicate())
    state = _state_of_the_branch(base_snapshot, store, owner_session, forked_branch.branch_id)
    original = state.row("transactions", "TX-2048")
    copy = state.row("transactions", "TX-2049")

    assert copy is not None
    for column in (
        "merchant_id",
        "customer_id",
        "amount_minor",
        "currency",
        "method",
        "card_brand",
        "card_fingerprint",
        "status",
    ):
        assert copy[column] == original[column], column


def test_the_duplicate_says_that_it_is_a_simulated_row_and_which_payment_it_comes_from(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    base_snapshot: BaseSnapshot,
    store: BranchStore,
    owner_session: str,
) -> None:
    """The visitor tells the simulated row from the published one by its origin, and reads the payment it copies."""
    layer.commit_mutation(session_id, forked_branch.branch_id, _duplicate())
    state = _state_of_the_branch(base_snapshot, store, owner_session, forked_branch.branch_id)
    copy = state.row("transactions", "TX-2049")

    assert copy is not None
    assert copy["origin"] == "sandbox"
    assert copy["source_ref"] == "TX-2048"


def test_the_duplicate_moves_the_created_at_and_the_captured_at_by_the_elapsed_seconds(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    base_snapshot: BaseSnapshot,
    store: BranchStore,
    owner_session: str,
) -> None:
    """The copy happens the elapsed seconds later, so the two moments of the payment move by the same amount."""
    layer.commit_mutation(session_id, forked_branch.branch_id, _duplicate(elapsed=30))
    state = _state_of_the_branch(base_snapshot, store, owner_session, forked_branch.branch_id)
    original = state.row("transactions", "TX-2048")
    copy = state.row("transactions", "TX-2049")

    assert copy is not None
    assert original is not None
    assert copy["created_at"] == "2026-10-15T09:12:30Z"
    assert copy["captured_at"] == "2026-10-15T09:12:34Z"


def test_the_duplicate_of_a_payment_without_a_capture_keeps_no_capture(
    store: BranchStore, clock, session_id: str, base_snapshot: BaseSnapshot, tmp_path: Path
) -> None:
    """A payment that was authorized has no capture moment, and the copy of it has none either."""
    base = _base_with(
        base_snapshot,
        tmp_path,
        ["UPDATE transactions SET status = 'authorized', captured_at = NULL WHERE id = 'TX-2048'"],
    )
    layer = _layer_over(store, base, clock)
    branch = layer.fork(session_id, "S01").branch

    layer.commit_mutation(session_id, branch.branch_id, _duplicate())
    state = _state_of_the_branch(base, store, _owner(session_id), branch.branch_id)
    copy = state.row("transactions", "TX-2049")

    assert copy is not None
    assert copy["status"] == "authorized"
    assert copy["captured_at"] is None


def test_the_duplicate_carries_no_row_of_the_applied_rate(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    base_snapshot: BaseSnapshot,
    store: BranchStore,
    owner_session: str,
) -> None:
    """The duplicate is a second charge of the same payment, and the rate belongs to the payment, which is the same.

    So the visitor reads the conversion of the rate in the row of the original, and the branch holds no second row
    of the rate for the copy (ADR-031).
    """
    layer.commit_mutation(session_id, forked_branch.branch_id, _duplicate())
    state = _state_of_the_branch(base_snapshot, store, owner_session, forked_branch.branch_id)

    assert [row["id"] for row in state.table("fx_applied")] == ["FX-9001", "FX-9002"]
    assert state.row("transactions", "TX-2049")["amount_minor"] == 10000
    assert state.row("transactions", "TX-2049")["currency"] == "EUR"


# --- the identifier of the copy --------------------------------------------------------------------------------


def test_the_identifier_of_the_duplicate_is_the_one_right_after_the_original(
    layer: BranchLayer, session_id: str, forked_branch: SandboxBranch
) -> None:
    """The identifier of the copy is the next free one of the branch, and it starts at the one after the original."""
    result = layer.commit_mutation(session_id, forked_branch.branch_id, _duplicate())

    assert {entry["record_id"] for entry in result.diff} == {"TX-2049"}


def test_the_identifier_of_the_duplicate_skips_the_identifiers_that_are_taken(
    layer: BranchLayer, session_id: str
) -> None:
    """The case of the customer that was charged twice holds TX-2052, so the copy of TX-2051 is TX-2053."""
    branch = layer.fork(session_id, DUPLICATE_SCENARIO).branch

    result = layer.commit_mutation(session_id, branch.branch_id, _duplicate(ORIGINAL_TRANSACTION))

    assert {entry["record_id"] for entry in result.diff} == {"TX-2053"}


def test_the_identifier_of_the_duplicate_wraps_around_the_space_of_the_identifiers() -> None:
    """The space of the identifiers is finite, and the search goes around it (ADR-031)."""
    assert next_transaction_id({ORIGINAL_TRANSACTION, TAKEN_TRANSACTION}, ORIGINAL_TRANSACTION) == "TX-2053"
    assert next_transaction_id({"TX-9999"}, "TX-9999") == "TX-0001"
    assert next_transaction_id({"TX-0001"}, "TX-9999") == "TX-0002"


def test_a_branch_with_no_free_identifier_refuses_the_duplicate() -> None:
    """When every identifier of the space is taken, there is no identifier left and the command is refused."""
    rows = [{"id": f"TX-{number:04d}", "status": "captured"} for number in range(1, 10000)]
    state = ProjectedState(conn=None, canonical_hash="", rows={"transactions": rows})

    with pytest.raises(MutationRejected) as refusal:
        validate_command(_duplicate(), state, datetime.now(UTC))

    assert refusal.value.code == "RESOURCE_LIMIT_EXCEEDED"


# --- the diff of the branch ------------------------------------------------------------------------------------


def test_the_diff_of_the_duplicate_names_the_new_row_with_the_value_before_empty(
    layer: BranchLayer, session_id: str, forked_branch: SandboxBranch
) -> None:
    """The diff of the branch shows the row that appeared, one entry per column, with the value before empty."""
    result = layer.commit_mutation(session_id, forked_branch.branch_id, _duplicate())
    entries = [entry for entry in result.diff if entry["record_id"] == "TX-2049"]

    assert [entry["field"] for entry in entries] == sorted(entry["field"] for entry in entries)
    assert {entry["field"] for entry in entries} == {
        "amount_minor",
        "captured_at",
        "card_brand",
        "card_fingerprint",
        "created_at",
        "currency",
        "customer_id",
        "id",
        "merchant_id",
        "method",
        "origin",
        "source_ref",
        "status",
    }
    assert all(entry["before"] == "" for entry in entries)
    assert {entry["record"] for entry in entries} == {"transactions"}
    by_field = {entry["field"]: entry for entry in entries}
    assert by_field["id"]["after"] == "TX-2049"
    assert by_field["origin"]["after"] == "sandbox"
    assert by_field["source_ref"]["after"] == "TX-2048"
    assert by_field["amount_minor"]["after"] == "100.00"
    assert by_field["amount_minor"]["currency"] == "EUR"


# --- the verdict of the case does not move ----------------------------------------------------------------------


def test_the_verdict_of_the_case_does_not_move(
    layer: BranchLayer, session_id: str, forked_branch: SandboxBranch
) -> None:
    """The measure of the case is the markup of the refund, and the duplicate does not touch the refund."""
    before = layer.diff(session_id, forked_branch.branch_id)
    result = layer.commit_mutation(session_id, forked_branch.branch_id, _duplicate())
    after = layer.diff(session_id, forked_branch.branch_id)

    assert before.verdict["label"] == "within_expected_range"
    assert result.verdict == before.verdict
    assert after.verdict == before.verdict


# --- the undo takes the copy back ------------------------------------------------------------------------------


def test_the_undo_takes_the_duplicate_back(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    base_snapshot: BaseSnapshot,
    store: BranchStore,
    owner_session: str,
) -> None:
    """ADR-024: the undo of the last mutation takes the row of the copy back, and the hash returns."""
    before = layer.status(session_id, forked_branch.branch_id)
    layer.commit_mutation(session_id, forked_branch.branch_id, _duplicate())

    result = layer.undo(
        session_id,
        forked_branch.branch_id,
        MutationCommand(kind="branch.undo", payload={}, expected_revision=1, idempotency_key="undo-0001"),
    )
    after = layer.status(session_id, forked_branch.branch_id)
    state = _state_of_the_branch(base_snapshot, store, owner_session, forked_branch.branch_id)

    assert result.revision == 0
    assert after.revision == 0
    assert after.current_canonical_hash == before.current_canonical_hash
    assert state.row("transactions", "TX-2049") is None
    assert state.row("transactions", "TX-2048") is not None


# --- the branch rebuilt from the events alone --------------------------------------------------------------------


def test_the_branch_rebuilt_from_the_events_alone_has_the_same_canonical_hash(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    base_snapshot: BaseSnapshot,
    store: BranchStore,
    owner_session: str,
) -> None:
    """FR-009 and FR-010: the state of a branch is a pure function of the base and of the log."""
    result = layer.commit_mutation(session_id, forked_branch.branch_id, _duplicate())
    rebuilt = _state_of_the_branch(base_snapshot, store, owner_session, forked_branch.branch_id)

    assert rebuilt.canonical_hash == result.canonical_hash


# --- the currency the visitor asserts --------------------------------------------------------------------------


def test_a_duplicate_with_a_currency_that_does_not_match_the_record_is_refused_with_CURRENCY_MISMATCH(
    layer: BranchLayer, session_id: str, forked_branch: SandboxBranch, event_count
) -> None:
    """The assertion of the visitor about the currency is checked against the record (ADR-021, ADR-031).

    The transaction TX-2048 is in euros, so an assertion in dollars does not match the record and is refused with its
    own code, and the branch keeps what it had.
    """
    with pytest.raises(MutationRejected) as refusal:
        layer.commit_mutation(session_id, forked_branch.branch_id, _duplicate(currency="USD"))

    assert refusal.value.code == "CURRENCY_MISMATCH"
    assert "USD" in refusal.value.message
    assert "EUR" in refusal.value.message
    assert event_count(forked_branch.branch_id) == 0
    assert layer.status(session_id, forked_branch.branch_id).revision == 0


def test_a_duplicate_with_the_currency_of_the_record_is_accepted(
    layer: BranchLayer, session_id: str, forked_branch: SandboxBranch
) -> None:
    """The assertion that matches the currency of the record is accepted, and the copy is written."""
    result = layer.commit_mutation(session_id, forked_branch.branch_id, _duplicate(currency="EUR"))

    assert {entry["record_id"] for entry in result.diff} == {"TX-2049"}


# --- the refusals of the kind ------------------------------------------------------------------------------------


def test_a_duplicate_of_a_transaction_that_is_not_in_the_branch_is_refused_with_UNKNOWN_RECORD(
    layer: BranchLayer, session_id: str, forked_branch: SandboxBranch, event_count
) -> None:
    """The record the command names has to be in the branch (ADR-031)."""
    with pytest.raises(MutationRejected) as refusal:
        layer.preview_mutation(session_id, forked_branch.branch_id, _duplicate("TX-9999"))

    assert refusal.value.code == "UNKNOWN_RECORD"
    assert event_count(forked_branch.branch_id) == 0


def test_a_duplicate_of_a_failed_payment_is_refused_with_INVALID_STATE(
    store: BranchStore, clock, session_id: str, base_snapshot: BaseSnapshot, tmp_path: Path
) -> None:
    """A payment that failed is not charged twice, and the state of a record has its own code (ADR-031)."""
    base = _base_with(base_snapshot, tmp_path, ["UPDATE transactions SET status = 'failed' WHERE id = 'TX-2048'"])
    layer = _layer_over(store, base, clock)
    branch = layer.fork(session_id, "S01").branch

    with pytest.raises(MutationRejected) as refusal:
        layer.commit_mutation(session_id, branch.branch_id, _duplicate())

    assert refusal.value.code == "INVALID_STATE"
    assert status_for_code("INVALID_STATE") == 422
    assert layer.status(session_id, branch.branch_id).revision == 0


def test_the_refusal_of_the_state_of_a_record_writes_nothing(
    store: BranchStore, clock, session_id: str, base_snapshot: BaseSnapshot, tmp_path: Path
) -> None:
    """A refused command never appends an event and never moves the branch (SC-007)."""
    base = _base_with(base_snapshot, tmp_path, ["UPDATE transactions SET status = 'failed' WHERE id = 'TX-2048'"])
    layer = _layer_over(store, base, clock)
    branch = layer.fork(session_id, "S01").branch
    before = layer.status(session_id, branch.branch_id)

    with pytest.raises(MutationRejected):
        layer.commit_mutation(session_id, branch.branch_id, _duplicate())

    after = layer.status(session_id, branch.branch_id)
    assert after.revision == before.revision == 0
    assert after.current_canonical_hash == before.current_canonical_hash
    assert store.read_events(branch.branch_id, _owner(session_id)) == []


@pytest.mark.parametrize("elapsed", [0, 301, "30", 30.5])
def test_the_elapsed_seconds_outside_the_window_are_refused_with_INVALID_PAYLOAD(
    layer: BranchLayer, session_id: str, forked_branch: SandboxBranch, elapsed: object
) -> None:
    """The window of the elapsed seconds is the one of the published schema, and it is a rule of the payload."""
    with pytest.raises(MutationRejected) as refusal:
        layer.preview_mutation(session_id, forked_branch.branch_id, _duplicate(elapsed=elapsed))

    assert refusal.value.code == "INVALID_PAYLOAD"


# --- the catalog of the sandbox ----------------------------------------------------------------------------------


def test_the_kinds_that_stay_disabled_are_refused_with_UNKNOWN_MUTATION_TYPE(
    layer: BranchLayer, session_id: str, forked_branch: SandboxBranch
) -> None:
    """The two kinds that change the state of the branch and not its rows are not enabled yet (ADR-031)."""
    for kind, payload in (
        ("tool.fx_outage", {"enabled": True, "error_code": "UPSTREAM_UNAVAILABLE"}),
        ("record.inject_untrusted_note", {"record_id": "TX-2048", "text": "a note"}),
    ):
        command = MutationCommand(kind=kind, payload=payload, expected_revision=0, idempotency_key="cmd-0001")
        with pytest.raises(MutationRejected) as refusal:
            layer.preview_mutation(session_id, forked_branch.branch_id, command)
        assert refusal.value.code == "UNKNOWN_MUTATION_TYPE"


def test_the_refusal_of_a_kind_names_the_three_accepted_kinds(
    layer: BranchLayer, session_id: str, forked_branch: SandboxBranch
) -> None:
    """The message of the refusal names the kinds the sandbox can do, so the visitor knows what to send."""
    command = MutationCommand(
        kind="tool.fx_outage",
        payload={"enabled": True, "error_code": "UPSTREAM_UNAVAILABLE"},
        expected_revision=0,
        idempotency_key="cmd-0001",
    )

    with pytest.raises(MutationRejected) as refusal:
        layer.preview_mutation(session_id, forked_branch.branch_id, command)

    for kind in ("refund.apply_fx_adjustment", "payment.simulate_duplicate", "chargeback.change_deadline"):
        assert kind in refusal.value.message
