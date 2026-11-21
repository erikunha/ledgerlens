"""The deadline of a chargeback: the interpreter writes it, and the round trip of the kind.

Why this file exists: the catalog of the sandbox grows with a kind only when the kind has a round trip test
(ADR-021). The change of the deadline of a chargeback is the second kind of the catalog, and it is the first kind
that makes an invariant of the domain reachable: the deadline of a chargeback is not before the day the case was
opened, and before this kind no visitor could ever break that rule (ADR-031).

Why the rule of the state of a record has its own code: the record exists and the payload has the shape of the
published schema, so what does not hold is the state of the record and not the shape of the payload. A chargeback
that was won or lost is a closed case, and its deadline may not move.
"""

from __future__ import annotations

import shutil
import sqlite3
from contextlib import closing
from dataclasses import replace
from pathlib import Path

import pytest

from ledgerlens.run_context import canonical_session_id
from ledgerlens.sandbox.branch import BranchLayer
from ledgerlens.sandbox.mutation import MutationCommand, MutationRejected, status_for_code
from ledgerlens.sandbox.projector import EVENT_CHARGEBACK_DEADLINE_CHANGED, ProjectedState, project
from ledgerlens.sandbox.snapshot import BaseSnapshot
from ledgerlens.sandbox.store import BranchStore
from ledgerlens.sim.projector import canonical_hash

# The scenario of the chargeback near its deadline (S03).
CHARGEBACK_SCENARIO = "S03"
# The chargeback of the case, and the day the case was opened.
CHARGEBACK_ID = "CB-0310"
OPENED_AT = "2026-10-28"
# The deadline the case holds, and the deadline the visitor asks for.
DEADLINE = "2026-11-09"
NEW_DEADLINE = "2026-11-20"


def _deadline(
    chargeback_id: str = CHARGEBACK_ID,
    deadline: str = NEW_DEADLINE,
    key: str = "cmd-0001",
    revision: int = 0,
    currency: str | None = None,
) -> MutationCommand:
    """The command of a change of the deadline of a chargeback.

    The currency is the optional assertion of the visitor about the record, and it is left out when it is None.
    """
    payload: dict[str, object] = {"chargeback_id": chargeback_id, "new_deadline": deadline}
    if currency is not None:
        payload["currency"] = currency
    return MutationCommand(
        kind="chargeback.change_deadline",
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


@pytest.fixture
def chargeback_base(base_resolver) -> BaseSnapshot:
    """The base of the scenario of the chargeback near its deadline (S03)."""
    return base_resolver(CHARGEBACK_SCENARIO)


# --- the preview computes and writes nothing -------------------------------------------------------------------


def test_the_preview_of_a_deadline_writes_nothing(layer: BranchLayer, session_id: str, event_count) -> None:
    """FR-016: the preview of a deadline computes in memory and writes nothing."""
    branch = layer.fork(session_id, CHARGEBACK_SCENARIO).branch
    before = layer.status(session_id, branch.branch_id)
    events_before = event_count(branch.branch_id)

    preview = layer.preview_mutation(session_id, branch.branch_id, _deadline())

    after = layer.status(session_id, branch.branch_id)
    assert preview.valid is True
    assert after.revision == before.revision == 0
    assert after.current_canonical_hash == before.current_canonical_hash
    assert event_count(branch.branch_id) == events_before == 0


def test_the_preview_of_a_deadline_answers_the_row_of_the_deadline_it_would_write(
    layer: BranchLayer, session_id: str
) -> None:
    """The preview and the commit see exactly the same row: the interpreter writes it in both cases (ADR-031)."""
    branch = layer.fork(session_id, CHARGEBACK_SCENARIO).branch
    preview = layer.preview_mutation(session_id, branch.branch_id, _deadline())
    result = layer.commit_mutation(session_id, branch.branch_id, _deadline())

    assert preview.projected_canonical_hash == result.canonical_hash
    assert list(preview.records) == list(result.diff)
    assert preview.records == (
        {
            "record": "chargebacks",
            "record_id": CHARGEBACK_ID,
            "field": "deadline",
            "before": DEADLINE,
            "after": NEW_DEADLINE,
            "value_kind": "non_monetary",
            "currency": None,
        },
    )


# --- the commit moves the branch exactly once ------------------------------------------------------------------


def test_the_commit_of_a_deadline_appends_one_event_and_moves_the_revision_by_exactly_one(
    layer: BranchLayer, session_id: str, event_count
) -> None:
    """FR-036: the revision of the branch is the number of the mutations that were really applied."""
    branch = layer.fork(session_id, CHARGEBACK_SCENARIO).branch

    result = layer.commit_mutation(session_id, branch.branch_id, _deadline())
    status = layer.status(session_id, branch.branch_id)

    assert result.revision == 1
    assert status.revision == 1
    assert event_count(branch.branch_id) == 1


def test_the_commit_of_a_deadline_moves_the_hash_of_the_branch(layer: BranchLayer, session_id: str) -> None:
    """The hash of the branch is the hash of the state the mutation produced (FR-033)."""
    branch = layer.fork(session_id, CHARGEBACK_SCENARIO).branch
    before = layer.status(session_id, branch.branch_id)

    result = layer.commit_mutation(session_id, branch.branch_id, _deadline())
    after = layer.status(session_id, branch.branch_id)

    assert result.canonical_hash != before.current_canonical_hash
    assert after.current_canonical_hash == result.canonical_hash


def test_the_event_of_a_deadline_carries_the_published_payload_and_the_origin_of_the_sandbox(
    layer: BranchLayer, session_id: str, store: BranchStore, owner_session: str
) -> None:
    """The event of a branch is a `sandbox.*` event, and it carries the published payload of the command."""
    branch = layer.fork(session_id, CHARGEBACK_SCENARIO).branch
    layer.commit_mutation(session_id, branch.branch_id, _deadline())
    events = store.read_events(branch.branch_id, owner_session)

    assert [event.event_type for event in events] == [EVENT_CHARGEBACK_DEADLINE_CHANGED]
    assert [event.origin for event in events] == ["sandbox"]
    assert events[0].payload == {"chargeback_id": CHARGEBACK_ID, "new_deadline": NEW_DEADLINE}


# --- the row of the chargeback ---------------------------------------------------------------------------------


def test_the_deadline_of_the_chargeback_is_written_and_nothing_else_of_the_row_moves(
    layer: BranchLayer, session_id: str, chargeback_base: BaseSnapshot, store: BranchStore, owner_session: str
) -> None:
    """The interpreter writes the deadline of the chargeback, and the rest of the row is the row of the base."""
    branch = layer.fork(session_id, CHARGEBACK_SCENARIO).branch
    before = _state_of_the_branch(chargeback_base, store, owner_session, branch.branch_id)
    original = before.row("chargebacks", CHARGEBACK_ID)

    layer.commit_mutation(session_id, branch.branch_id, _deadline())
    after = _state_of_the_branch(chargeback_base, store, owner_session, branch.branch_id)
    chargeback = after.row("chargebacks", CHARGEBACK_ID)

    assert original is not None
    assert chargeback is not None
    assert chargeback["deadline"] == NEW_DEADLINE
    for column, value in original.items():
        if column != "deadline":
            assert chargeback[column] == value, column


def test_the_diff_of_the_deadline_names_the_deadline_with_the_value_before_and_the_value_after(
    layer: BranchLayer, session_id: str
) -> None:
    """The diff of the branch shows the deadline of the chargeback, with the value before and the value after."""
    branch = layer.fork(session_id, CHARGEBACK_SCENARIO).branch

    result = layer.commit_mutation(session_id, branch.branch_id, _deadline())

    assert [
        (entry["record"], entry["record_id"], entry["field"], entry["before"], entry["after"]) for entry in result.diff
    ] == [("chargebacks", CHARGEBACK_ID, "deadline", DEADLINE, NEW_DEADLINE)]


# --- the verdict of the case does not move ----------------------------------------------------------------------


def test_the_verdict_of_the_case_does_not_move(
    store: BranchStore, clock, session_id: str, base_snapshot: BaseSnapshot, tmp_path: Path
) -> None:
    """The measure of the case is the markup of the refund, and the deadline does not touch the refund.

    The scenario of the case of the markup is the one that has a refund, and a chargeback is added to a copy of its
    base, so the verdict of the case is a real label and not the one of a case that has no measure.
    """
    base = _base_with(
        base_snapshot,
        tmp_path,
        [
            "INSERT INTO chargebacks (id, transaction_id, amount_minor, currency, reason_code, stage, opened_at,"
            " deadline, resolved_at)"
            " VALUES ('CB-9001', 'TX-2048', 10000, 'EUR', 'NRC', 'opened', '2026-10-28T10:00:00Z',"
            " '2026-11-09', NULL)"
        ],
    )
    layer = _layer_over(store, base, clock)
    branch = layer.fork(session_id, "S01").branch
    before = layer.diff(session_id, branch.branch_id)

    result = layer.commit_mutation(session_id, branch.branch_id, _deadline("CB-9001"))
    after = layer.diff(session_id, branch.branch_id)

    assert before.verdict["label"] == "within_expected_range"
    assert result.verdict == before.verdict
    assert after.verdict == before.verdict


# --- the undo takes the deadline back ---------------------------------------------------------------------------


def test_the_undo_takes_the_deadline_back_to_the_value_of_the_base(
    layer: BranchLayer, session_id: str, chargeback_base: BaseSnapshot, store: BranchStore, owner_session: str
) -> None:
    """ADR-024: the undo of the last mutation puts the deadline of the base back, and the hash returns."""
    branch = layer.fork(session_id, CHARGEBACK_SCENARIO).branch
    before = layer.status(session_id, branch.branch_id)
    layer.commit_mutation(session_id, branch.branch_id, _deadline())

    result = layer.undo(
        session_id,
        branch.branch_id,
        MutationCommand(kind="branch.undo", payload={}, expected_revision=1, idempotency_key="undo-0001"),
    )
    after = layer.status(session_id, branch.branch_id)
    state = _state_of_the_branch(chargeback_base, store, owner_session, branch.branch_id)

    assert result.revision == 0
    assert after.revision == 0
    assert after.current_canonical_hash == before.current_canonical_hash
    assert state.row("chargebacks", CHARGEBACK_ID)["deadline"] == DEADLINE


# --- the branch rebuilt from the events alone --------------------------------------------------------------------


def test_the_branch_rebuilt_from_the_events_alone_has_the_same_canonical_hash(
    layer: BranchLayer, session_id: str, chargeback_base: BaseSnapshot, store: BranchStore, owner_session: str
) -> None:
    """FR-009 and FR-010: the state of a branch is a pure function of the base and of the log."""
    branch = layer.fork(session_id, CHARGEBACK_SCENARIO).branch

    result = layer.commit_mutation(session_id, branch.branch_id, _deadline())
    rebuilt = _state_of_the_branch(chargeback_base, store, owner_session, branch.branch_id)

    assert rebuilt.canonical_hash == result.canonical_hash


# --- the rule of the deadline -----------------------------------------------------------------------------------


def test_a_deadline_before_the_day_the_chargeback_was_opened_is_refused_with_INVARIANT_VIOLATION(
    layer: BranchLayer, session_id: str, event_count
) -> None:
    """The deadline of a chargeback is not before the day the case was opened, and the rule refuses the commit."""
    branch = layer.fork(session_id, CHARGEBACK_SCENARIO).branch
    before = layer.status(session_id, branch.branch_id)

    with pytest.raises(MutationRejected) as refusal:
        layer.commit_mutation(session_id, branch.branch_id, _deadline(deadline="2026-10-01"))

    assert refusal.value.code == "INVARIANT_VIOLATION"
    assert "chargeback_deadline_not_before_opening" in refusal.value.message
    assert event_count(branch.branch_id) == 0
    assert layer.status(session_id, branch.branch_id).current_canonical_hash == before.current_canonical_hash


def test_the_preview_of_a_deadline_before_the_opening_answers_the_rule_that_does_not_hold(
    layer: BranchLayer, session_id: str
) -> None:
    """The preview names the rule of the domain that the change would break, and it writes nothing."""
    branch = layer.fork(session_id, CHARGEBACK_SCENARIO).branch

    preview = layer.preview_mutation(session_id, branch.branch_id, _deadline(deadline="2026-10-01"))

    assert preview.valid is False
    failed = [result for result in preview.invariants if not result["passed"]]
    assert [result["identifier"] for result in failed] == ["chargeback_deadline_not_before_opening"]


# --- the currency the visitor asserts --------------------------------------------------------------------------


def test_a_deadline_with_a_currency_that_does_not_match_the_record_is_refused_with_CURRENCY_MISMATCH(
    layer: BranchLayer, session_id: str, event_count
) -> None:
    """The assertion of the visitor about the currency is checked against the record (ADR-021, ADR-031).

    The chargeback CB-0310 is in dollars, so an assertion in euros does not match the record and is refused with its
    own code, and the branch keeps what it had.
    """
    branch = layer.fork(session_id, CHARGEBACK_SCENARIO).branch

    with pytest.raises(MutationRejected) as refusal:
        layer.commit_mutation(session_id, branch.branch_id, _deadline(currency="EUR"))

    assert refusal.value.code == "CURRENCY_MISMATCH"
    assert "EUR" in refusal.value.message
    assert "USD" in refusal.value.message
    assert event_count(branch.branch_id) == 0
    assert layer.status(session_id, branch.branch_id).revision == 0


def test_a_deadline_with_the_currency_of_the_record_is_accepted(layer: BranchLayer, session_id: str) -> None:
    """The assertion that matches the currency of the record is accepted, and the deadline is written."""
    branch = layer.fork(session_id, CHARGEBACK_SCENARIO).branch

    result = layer.commit_mutation(session_id, branch.branch_id, _deadline(currency="USD"))

    assert [(entry["record_id"], entry["field"], entry["after"]) for entry in result.diff] == [
        (CHARGEBACK_ID, "deadline", NEW_DEADLINE)
    ]


# --- the refusals of the kind ------------------------------------------------------------------------------------


def test_a_deadline_of_a_chargeback_that_is_not_in_the_branch_is_refused_with_UNKNOWN_RECORD(
    layer: BranchLayer, session_id: str, event_count
) -> None:
    """The record the command names has to be in the branch (ADR-031)."""
    branch = layer.fork(session_id, CHARGEBACK_SCENARIO).branch

    with pytest.raises(MutationRejected) as refusal:
        layer.preview_mutation(session_id, branch.branch_id, _deadline(chargeback_id="CB-9999"))

    assert refusal.value.code == "UNKNOWN_RECORD"
    assert event_count(branch.branch_id) == 0


def test_a_deadline_of_a_chargeback_that_was_won_is_refused_with_INVALID_STATE(
    store: BranchStore, clock, session_id: str, chargeback_base: BaseSnapshot, tmp_path: Path
) -> None:
    """A chargeback that was won or lost is a closed case, and its deadline may not move (ADR-031)."""
    base = _base_with(
        chargeback_base,
        tmp_path,
        [f"UPDATE chargebacks SET stage = 'won', resolved_at = '2026-11-01T10:00:00Z' WHERE id = '{CHARGEBACK_ID}'"],
    )
    layer = _layer_over(store, base, clock)
    branch = layer.fork(session_id, CHARGEBACK_SCENARIO).branch

    with pytest.raises(MutationRejected) as refusal:
        layer.commit_mutation(session_id, branch.branch_id, _deadline())

    assert refusal.value.code == "INVALID_STATE"
    assert status_for_code("INVALID_STATE") == 422
    assert layer.status(session_id, branch.branch_id).revision == 0


@pytest.mark.parametrize("deadline", ["2026-11-20T00:00:00Z", "the day after tomorrow", "2026-13-01"])
def test_a_deadline_that_is_not_a_day_is_refused_with_INVALID_PAYLOAD(
    layer: BranchLayer, session_id: str, deadline: str
) -> None:
    """The deadline is a day of the calendar, and a text that is not a day is a rule of the payload."""
    branch = layer.fork(session_id, CHARGEBACK_SCENARIO).branch

    with pytest.raises(MutationRejected) as refusal:
        layer.preview_mutation(session_id, branch.branch_id, _deadline(deadline=deadline))

    assert refusal.value.code == "INVALID_PAYLOAD"


def test_the_refusal_of_the_state_of_a_record_writes_nothing(
    store: BranchStore, clock, session_id: str, chargeback_base: BaseSnapshot, tmp_path: Path
) -> None:
    """A refused command never appends an event and never moves the branch (SC-007)."""
    base = _base_with(
        chargeback_base,
        tmp_path,
        [f"UPDATE chargebacks SET stage = 'lost', resolved_at = '2026-11-01T10:00:00Z' WHERE id = '{CHARGEBACK_ID}'"],
    )
    layer = _layer_over(store, base, clock)
    branch = layer.fork(session_id, CHARGEBACK_SCENARIO).branch
    before = layer.status(session_id, branch.branch_id)

    with pytest.raises(MutationRejected):
        layer.commit_mutation(session_id, branch.branch_id, _deadline())

    after = layer.status(session_id, branch.branch_id)
    assert after.revision == before.revision == 0
    assert after.current_canonical_hash == before.current_canonical_hash
    assert store.read_events(branch.branch_id, _owner(session_id)) == []
