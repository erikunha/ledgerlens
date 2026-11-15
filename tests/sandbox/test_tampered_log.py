"""The log of a branch that was tampered with: a payload that lost a field is refused, for every kind.

Why this file exists: the interpreter reads the payload of every event it applies, and a payload that lost a field
it reads is a log that cannot be projected. The rule is one rule for the whole catalog, not a rule of the two kinds
that came last, so the proof of the rule belongs in one place and covers every kind of the catalog (ADR-021, ADR-032).

Why the refusal has to be the one of the contract: a `KeyError` would leave the refusal unhandled, and the facade
would answer an error of the server instead of the 409 of the contract. A branch that cannot prove its own state is
never served, and the answer that says so is `HASH_MISMATCH` (ADR-021, ADR-032).

Why the field is removed from the stored event and not from the command: the visitor never sends a malformed event.
The log of the branch is what a crash or a corruption changes, so the test writes the tampered log straight into the
store and then reads the branch the way a request reads it.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from ledgerlens.run_context import canonical_session_id
from ledgerlens.sandbox.branch import BranchHashMismatch, BranchLayer
from ledgerlens.sandbox.mutation import MutationCommand
from ledgerlens.sandbox.snapshot import BaseResolver
from ledgerlens.sandbox.store import BranchStore

# The scenario of the kinds whose records live in S01.
SCENARIO = "S01"
# The scenario of the chargeback near its deadline.
DEADLINE_SCENARIO = "S03"
# The transaction of the case, and the refund of the case.
TRANSACTION_ID = "TX-2048"
REFUND_ID = "R-0731"
# The chargeback of the case.
CHARGEBACK_ID = "CB-0310"
# The error code the published schema declares for the outage of the FX tool.
ERROR_CODE = "UPSTREAM_UNAVAILABLE"


def _adjustment(effective_at: str) -> MutationCommand:
    """The command of an adjustment of the rate of a refund of S01."""
    return MutationCommand(
        kind="refund.apply_fx_adjustment",
        payload={"refund_id": REFUND_ID, "applied_rate": "5.41250000", "effective_at": effective_at},
        expected_revision=0,
        idempotency_key="cmd-0001",
    )


def _duplicate() -> MutationCommand:
    """The command of a duplicate of a payment of S02."""
    return MutationCommand(
        kind="payment.simulate_duplicate",
        payload={"transaction_id": TRANSACTION_ID, "elapsed_seconds": 45},
        expected_revision=0,
        idempotency_key="cmd-0001",
    )


def _deadline() -> MutationCommand:
    """The command of a change of the deadline of a chargeback of S03."""
    return MutationCommand(
        kind="chargeback.change_deadline",
        payload={"chargeback_id": CHARGEBACK_ID, "new_deadline": "2026-11-20"},
        expected_revision=0,
        idempotency_key="cmd-0001",
    )


def _outage() -> MutationCommand:
    """The command of an outage of the FX tool of S01."""
    return MutationCommand(
        kind="tool.fx_outage",
        payload={"enabled": True, "error_code": ERROR_CODE},
        expected_revision=0,
        idempotency_key="cmd-0001",
    )


def _note() -> MutationCommand:
    """The command of an untrusted note on a record of S01."""
    return MutationCommand(
        kind="record.inject_untrusted_note",
        payload={"record_id": TRANSACTION_ID, "text": "a note of an untrusted source"},
        expected_revision=0,
        idempotency_key="cmd-0001",
    )


# The kind, the scenario it needs, the command it sends, the field the interpreter reads and the field that is
# removed from the stored payload. The field is one the interpreter reads, so removing it is what makes the log
# impossible to project.
THE_KINDS = (
    ("refund.apply_fx_adjustment", SCENARIO, _adjustment, "refund_id"),
    ("refund.apply_fx_adjustment", SCENARIO, _adjustment, "applied_rate"),
    ("payment.simulate_duplicate", SCENARIO, _duplicate, "transaction_id"),
    ("chargeback.change_deadline", DEADLINE_SCENARIO, _deadline, "chargeback_id"),
    ("chargeback.change_deadline", DEADLINE_SCENARIO, _deadline, "new_deadline"),
    ("tool.fx_outage", SCENARIO, _outage, "enabled"),
    ("tool.fx_outage", SCENARIO, _outage, "error_code"),
    ("record.inject_untrusted_note", SCENARIO, _note, "record_id"),
    ("record.inject_untrusted_note", SCENARIO, _note, "text"),
)


def _the_command(kind: str, effective_at: str) -> MutationCommand:
    """The command of the kind, with the moment that the adjustment needs."""
    if kind == "refund.apply_fx_adjustment":
        return _adjustment(effective_at)
    if kind == "payment.simulate_duplicate":
        return _duplicate()
    if kind == "chargeback.change_deadline":
        return _deadline()
    if kind == "tool.fx_outage":
        return _outage()
    return _note()


@pytest.mark.parametrize(("kind", "scenario", "_builder", "missing"), THE_KINDS)
def test_a_log_whose_payload_lost_a_field_is_refused_with_HASH_MISMATCH(
    layer: BranchLayer,
    session_id: str,
    store: BranchStore,
    owner_session: str,
    tamper_events,
    effective_at: str,
    kind: str,
    scenario: str,
    _builder,
    missing: str,
) -> None:
    """A payload that lost a field the interpreter reads is a log that cannot be projected (ADR-021, ADR-032).

    The refusal is the one of the contract, `HASH_MISMATCH`, and not an error of the server: the rule covers every
    kind of the catalog, so a branch whose log was tampered with is refused the same way whatever the kind of the
    event that was changed.
    """
    branch = layer.fork(session_id, scenario).branch
    layer.commit_mutation(session_id, branch.branch_id, _the_command(kind, effective_at))
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


def test_a_log_whose_payload_lost_a_field_is_refused_by_the_route_with_409(
    store: BranchStore, base_resolver: BaseResolver, clock, tamper_events
) -> None:
    """The route answers the 409 of the contract and not an error of the server (ADR-021, ADR-032)."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from ledgerlens.api.sandbox import create_app

    app = create_app(store=store, base_resolver=base_resolver, clock=clock)
    client = TestClient(app, raise_server_exceptions=False)
    session = client.post("/v1/sessions")
    assert session.status_code == 201
    owner = canonical_session_id(session.json()["id"])
    forked = client.post("/v1/sandboxes", json={"scenario_id": SCENARIO})
    assert forked.status_code == 201
    branch_id = forked.json()["id"]
    commit = client.post(
        f"/v1/sandboxes/{branch_id}/mutations",
        json={"kind": "tool.fx_outage", "data": {"enabled": True, "error_code": ERROR_CODE}},
        headers={"Idempotency-Key": "cmd-0001", "If-Match": "0"},
    )
    assert commit.status_code == 200

    events = store.read_events(branch_id, owner)
    tampered = [
        replace(event, payload={name: value for name, value in event.payload.items() if name != "error_code"})
        for event in events
    ]
    tamper_events(branch_id, tampered)

    for path in ("", "/diff"):
        answer = client.get(f"/v1/sandboxes/{branch_id}{path}")
        assert answer.status_code == 409
        assert answer.json()["code"] == "HASH_MISMATCH"
