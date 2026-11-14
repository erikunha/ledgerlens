"""The commit of a typed mutation: the revision moves once, the hash follows, and the rules hold.

Why the commit is the only point where the branch moves: a preview writes nothing, and a commit that is refused
writes nothing either. So the revision of the branch is the number of the mutations that were really applied
(FR-036), and the canonical hash of the branch is the hash of the state those mutations produced (FR-033).

The three rules that protect the commit are proven here: the expected revision refuses a stale request (FR-014),
the idempotency key answers the same request the same way and refuses the same key with another payload
(FR-012, FR-013), and an invariant that does not hold rolls the whole mutation back (FR-018).
"""

from __future__ import annotations

import pytest

from ledgerlens.sandbox.branch import MAX_COMMITTED_MUTATIONS, BranchLayer, SandboxBranch
from ledgerlens.sandbox.mutation import MutationCommand, MutationRejected, status_for_code


def _command(payload: dict[str, object], key: str, revision: int = 0) -> MutationCommand:
    """A command with the given payload, key and expected revision."""
    return MutationCommand(
        kind="refund.apply_fx_adjustment",
        payload=payload,
        expected_revision=revision,
        idempotency_key=key,
    )


# --- the commit moves the branch exactly once ------------------------------------------------------------


def test_the_commit_appends_one_event_and_moves_the_revision_by_exactly_one(
    layer: BranchLayer, session_id: str, forked_branch: SandboxBranch, adjustment: MutationCommand, event_count
) -> None:
    result = layer.commit_mutation(session_id, forked_branch.branch_id, adjustment)
    status = layer.status(session_id, forked_branch.branch_id)
    assert status.revision == 1
    assert result.revision == 1
    assert event_count(forked_branch.branch_id) == 1


def test_the_commit_answers_the_new_hash_and_the_diff(
    layer: BranchLayer, session_id: str, forked_branch: SandboxBranch, adjustment: MutationCommand
) -> None:
    result = layer.commit_mutation(session_id, forked_branch.branch_id, adjustment)
    status = layer.status(session_id, forked_branch.branch_id)
    assert result.canonical_hash == status.current_canonical_hash
    assert result.canonical_hash != status.base_canonical_hash
    assert [(entry["record"], entry["record_id"], entry["field"]) for entry in result.diff] == [
        ("fx_applied", "FX-9002", "applied_rate"),
        ("refunds", "R-0731", "payout_amount_minor"),
    ]
    assert result.diff[0]["before"] == "5.4931"
    assert result.diff[0]["after"] == "5.4125"
    assert result.diff[1]["before"] == "549.31"
    assert result.diff[1]["after"] == "541.25"


def test_the_event_of_a_commit_carries_the_origin_of_the_sandbox(
    layer: BranchLayer, session_id: str, forked_branch: SandboxBranch, adjustment: MutationCommand, store, owner_session
) -> None:
    layer.commit_mutation(session_id, forked_branch.branch_id, adjustment)
    events = store.read_events(forked_branch.branch_id, owner_session)
    assert [event.origin for event in events] == ["sandbox"]
    assert [event.event_type for event in events] == ["sandbox.refund.fx_adjusted"]


# --- the expected revision refuses a stale request ---------------------------------------------------------


def test_a_commit_with_a_stale_expected_revision_is_refused_with_REVISION_CONFLICT(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment_payload: dict[str, object],
    event_count,
) -> None:
    layer.commit_mutation(session_id, forked_branch.branch_id, _command(adjustment_payload, "cmd-0001"))
    status = layer.status(session_id, forked_branch.branch_id)
    with pytest.raises(MutationRejected) as refusal:
        layer.commit_mutation(session_id, forked_branch.branch_id, _command(adjustment_payload, "cmd-0002"))
    assert refusal.value.code == "REVISION_CONFLICT"
    assert event_count(forked_branch.branch_id) == 1
    assert layer.status(session_id, forked_branch.branch_id).current_canonical_hash == status.current_canonical_hash


# --- the idempotency of the request -------------------------------------------------------------------------


def test_the_same_key_with_the_same_payload_answers_the_identical_revision_the_hash_and_the_diff(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment_payload: dict[str, object],
    event_count,
) -> None:
    first = layer.commit_mutation(session_id, forked_branch.branch_id, _command(adjustment_payload, "cmd-0001"))
    # The replay carries the request as it was sent the first time, and its expected revision is stale by then.
    second = layer.commit_mutation(session_id, forked_branch.branch_id, _command(adjustment_payload, "cmd-0001"))
    assert second.revision == first.revision
    assert second.canonical_hash == first.canonical_hash
    assert second.diff == first.diff
    assert second.replayed is True
    assert event_count(forked_branch.branch_id) == 1


def test_the_replay_after_a_later_mutation_is_the_answer_of_the_first_request(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment_payload: dict[str, object],
) -> None:
    """ADR-021: the store remembers the answer of a request, so the replay is the identical answer.

    The second mutation puts the case back inside the range of the truth, so the verdict of the current projection
    is not the verdict of the first request any more. The answer that was remembered is the answer of the first
    request, verdict and invariants included.
    """
    first = layer.commit_mutation(session_id, forked_branch.branch_id, _command(adjustment_payload, "cmd-0001"))
    layer.commit_mutation(
        session_id,
        forked_branch.branch_id,
        _command({**adjustment_payload, "applied_rate": "5.49310000"}, "cmd-0002", 1),
    )
    replay = layer.commit_mutation(session_id, forked_branch.branch_id, _command(adjustment_payload, "cmd-0001"))
    assert first.verdict["label"] == "above_expected_range"
    assert replay.verdict["label"] == "above_expected_range"
    assert replay.to_dict() == {**first.to_dict(), "replayed": True}


def test_a_replay_with_a_stale_expected_revision_answers_the_stored_answer(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment_payload: dict[str, object],
    event_count,
) -> None:
    """FR-012: the second delivery of a request returns the answer of the first one.

    The second delivery carries the request as it was sent the first time, and its expected revision is stale by
    then, because the first delivery moved the branch. The stored answer is the answer of the request, so a client
    that lost the answer of its first request still learns whether that request was applied.
    """
    first = layer.commit_mutation(session_id, forked_branch.branch_id, _command(adjustment_payload, "cmd-0001"))
    replay = layer.commit_mutation(session_id, forked_branch.branch_id, _command(adjustment_payload, "cmd-0001"))
    assert replay.revision == first.revision
    assert replay.canonical_hash == first.canonical_hash
    assert replay.diff == first.diff
    assert replay.replayed is True
    assert event_count(forked_branch.branch_id) == 1


def test_a_request_with_an_unseen_key_and_a_stale_expected_revision_is_refused_with_REVISION_CONFLICT(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment_payload: dict[str, object],
    event_count,
) -> None:
    """FR-014: a request that was never seen has to match the current revision of the branch."""
    layer.commit_mutation(session_id, forked_branch.branch_id, _command(adjustment_payload, "cmd-0001"))
    with pytest.raises(MutationRejected) as refusal:
        layer.commit_mutation(session_id, forked_branch.branch_id, _command(adjustment_payload, "cmd-0002"))
    assert refusal.value.code == "REVISION_CONFLICT"
    assert event_count(forked_branch.branch_id) == 1


def test_the_same_key_with_another_payload_is_refused_with_IDEMPOTENCY_MISMATCH(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment_payload: dict[str, object],
    event_count,
) -> None:
    """FR-013: the key is bound to the payload it was seen with, whatever the expected revision says."""
    layer.commit_mutation(session_id, forked_branch.branch_id, _command(adjustment_payload, "cmd-0001"))
    other = {**adjustment_payload, "applied_rate": "5.50000000"}
    with pytest.raises(MutationRejected) as refusal:
        layer.commit_mutation(session_id, forked_branch.branch_id, _command(other, "cmd-0001"))
    assert refusal.value.code == "IDEMPOTENCY_MISMATCH"
    assert event_count(forked_branch.branch_id) == 1


# --- the invariants roll the mutation back -------------------------------------------------------------------


def test_a_mutation_that_breaks_an_invariant_is_refused_and_the_event_is_rolled_back(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment_payload: dict[str, object],
    event_count,
) -> None:
    status = layer.status(session_id, forked_branch.branch_id)
    broken = {**adjustment_payload, "applied_rate": "0"}
    with pytest.raises(MutationRejected) as refusal:
        layer.commit_mutation(session_id, forked_branch.branch_id, _command(broken, "cmd-0001"))
    assert refusal.value.code == "INVARIANT_VIOLATION"
    assert "fx_rate_positive_and_finite" in refusal.value.message
    assert event_count(forked_branch.branch_id) == 0
    assert layer.status(session_id, forked_branch.branch_id).current_canonical_hash == status.current_canonical_hash


def test_two_commits_with_the_same_expected_revision_apply_exactly_one(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment_payload: dict[str, object],
    event_count,
) -> None:
    first = layer.commit_mutation(session_id, forked_branch.branch_id, _command(adjustment_payload, "cmd-0001"))
    with pytest.raises(MutationRejected) as refusal:
        layer.commit_mutation(session_id, forked_branch.branch_id, _command(adjustment_payload, "cmd-0002"))
    assert refusal.value.code == "REVISION_CONFLICT"
    assert layer.status(session_id, forked_branch.branch_id).revision == first.revision == 1
    assert event_count(forked_branch.branch_id) == 1


# --- the resources of the branch -------------------------------------------------------------------------------


def test_the_commit_refuses_a_payload_that_is_too_big(
    layer: BranchLayer, session_id: str, forked_branch: SandboxBranch, adjustment_payload: dict[str, object]
) -> None:
    payload = {**adjustment_payload, "note": "x" * 40000}
    with pytest.raises(MutationRejected) as refusal:
        layer.commit_mutation(session_id, forked_branch.branch_id, _command(payload, "cmd-0001"))
    assert refusal.value.code == "PAYLOAD_TOO_LARGE"


def test_the_commit_refuses_a_note_that_is_too_long(
    layer: BranchLayer, session_id: str, forked_branch: SandboxBranch, adjustment_payload: dict[str, object]
) -> None:
    command = MutationCommand(
        kind="refund.apply_fx_adjustment",
        payload=dict(adjustment_payload),
        reason="y" * 301,
        expected_revision=0,
        idempotency_key="cmd-0001",
    )
    with pytest.raises(MutationRejected) as refusal:
        layer.commit_mutation(session_id, forked_branch.branch_id, command)
    assert refusal.value.code == "NOTE_TOO_LONG"


def test_the_commit_refuses_the_twenty_first_mutation(
    layer: BranchLayer, session_id: str, forked_branch: SandboxBranch, adjustment_payload: dict[str, object]
) -> None:
    for revision in range(MAX_COMMITTED_MUTATIONS):
        layer.commit_mutation(
            session_id, forked_branch.branch_id, _command(adjustment_payload, f"cmd-{revision:04d}", revision)
        )
    with pytest.raises(MutationRejected) as refusal:
        layer.commit_mutation(
            session_id,
            forked_branch.branch_id,
            _command(adjustment_payload, "cmd-9999", MAX_COMMITTED_MUTATIONS),
        )
    assert refusal.value.code == "RESOURCE_LIMIT_EXCEEDED"
    assert layer.status(session_id, forked_branch.branch_id).revision == MAX_COMMITTED_MUTATIONS


@pytest.mark.parametrize(
    "code,status",
    [
        ("REVISION_CONFLICT", 409),
        ("IDEMPOTENCY_MISMATCH", 409),
        ("PAYLOAD_TOO_LARGE", 413),
        ("RESOURCE_LIMIT_EXCEEDED", 429),
        ("UNKNOWN_MUTATION_TYPE", 422),
        ("READ_ONLY_FIELD", 422),
        ("INVALID_AMOUNT", 422),
        ("CURRENCY_MISMATCH", 422),
        ("INVALID_EFFECTIVE_DATE", 422),
        ("INVARIANT_VIOLATION", 422),
    ],
)
def test_every_refusal_carries_the_status_of_its_code(code: str, status: int) -> None:
    assert status_for_code(code) == status


# --- the facade of the contract -------------------------------------------------------------------------------


@pytest.fixture
def client(store, base_resolver, clock):
    """A client of the facade with a session of its own."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from ledgerlens.api.sandbox import create_app

    http = TestClient(create_app(store=store, base_resolver=base_resolver, clock=clock))
    assert http.post("/v1/sessions").status_code == 201
    return http


def _fork(http, scenario_id: str) -> str:
    """The identifier of the branch the client owns."""
    return http.post("/v1/sandboxes", json={"scenario_id": scenario_id}).json()["id"]


def test_the_preview_route_answers_the_preview_and_writes_nothing(
    client, scenario_id: str, adjustment_payload: dict[str, object]
) -> None:
    branch_id = _fork(client, scenario_id)
    response = client.post(
        f"/v1/sandboxes/{branch_id}/mutations/preview",
        json={"kind": "refund.apply_fx_adjustment", "data": adjustment_payload},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["before"] == {"value": "549.31", "currency": "BRL"}
    assert body["after"] == {"value": "541.25", "currency": "BRL"}
    assert client.get(f"/v1/sandboxes/{branch_id}").json()["revision"] == 0


def test_the_commit_route_answers_the_new_revision_the_hash_and_the_diff(
    client, scenario_id: str, adjustment_payload: dict[str, object]
) -> None:
    branch_id = _fork(client, scenario_id)
    response = client.post(
        f"/v1/sandboxes/{branch_id}/mutations",
        json={"kind": "refund.apply_fx_adjustment", "data": adjustment_payload},
        headers={"Idempotency-Key": "cmd-0001", "If-Match": "0"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["revision"] == 1
    assert len(body["canonical_hash"]) == 64
    assert [entry["record_id"] for entry in body["diff"]] == ["FX-9002", "R-0731"]


def test_the_commit_route_with_a_stale_if_match_is_409_with_the_code_of_the_contract(
    client, scenario_id: str, adjustment_payload: dict[str, object]
) -> None:
    branch_id = _fork(client, scenario_id)
    client.post(
        f"/v1/sandboxes/{branch_id}/mutations",
        json={"kind": "refund.apply_fx_adjustment", "data": adjustment_payload},
        headers={"Idempotency-Key": "cmd-0001", "If-Match": "0"},
    )
    response = client.post(
        f"/v1/sandboxes/{branch_id}/mutations",
        json={"kind": "refund.apply_fx_adjustment", "data": adjustment_payload},
        headers={"Idempotency-Key": "cmd-0002", "If-Match": "0"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "REVISION_CONFLICT"


def test_the_preview_route_with_an_unknown_kind_is_422_with_the_code_of_the_rule(
    client, scenario_id: str, adjustment_payload: dict[str, object]
) -> None:
    branch_id = _fork(client, scenario_id)
    response = client.post(
        f"/v1/sandboxes/{branch_id}/mutations/preview",
        json={"kind": "refund.explode", "data": adjustment_payload},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "UNKNOWN_MUTATION_TYPE"


def test_the_ledger_route_answers_the_items_and_the_next_cursor(client, scenario_id: str, base_snapshot) -> None:
    branch_id = _fork(client, scenario_id)
    response = client.get(f"/v1/sandboxes/{branch_id}/ledger", params={"account_id": base_snapshot.account_id})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"items", "next_cursor"}
    assert body["next_cursor"] is None
    assert [item["id"] for item in body["items"]] == ["TX-2048", "R-0731"]


def test_the_ledger_route_refuses_the_account_of_another_visitor(client, scenario_id: str) -> None:
    branch_id = _fork(client, scenario_id)
    response = client.get(f"/v1/sandboxes/{branch_id}/ledger", params={"account_id": "C-9999"})
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_the_facade_answers_409_with_the_code_when_the_branch_cannot_prove_its_state(
    client, scenario_id: str, adjustment_payload: dict[str, object], tamper_events
) -> None:
    branch_id = _fork(client, scenario_id)
    client.post(
        f"/v1/sandboxes/{branch_id}/mutations",
        json={"kind": "refund.apply_fx_adjustment", "data": adjustment_payload},
        headers={"Idempotency-Key": "cmd-0001", "If-Match": "0"},
    )
    # The crash of a commit that wrote the row of the branch and lost the events of the branch.
    tamper_events(branch_id, [])
    response = client.get(f"/v1/sandboxes/{branch_id}")
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "HASH_MISMATCH"
    assert "fork" in body["message"]


def test_every_answer_of_the_facade_carries_the_version_of_the_schema(
    client, scenario_id: str, adjustment_payload: dict[str, object]
) -> None:
    from ledgerlens.api.sandbox import SCHEMA_VERSION, SCHEMA_VERSION_HEADER

    branch_id = _fork(client, scenario_id)
    answers = [
        client.post("/v1/sessions"),
        client.get(f"/v1/sandboxes/{branch_id}"),
        client.post(
            f"/v1/sandboxes/{branch_id}/mutations/preview",
            json={"kind": "refund.apply_fx_adjustment", "data": adjustment_payload},
        ),
        client.post(
            f"/v1/sandboxes/{branch_id}/mutations",
            json={"kind": "refund.apply_fx_adjustment", "data": adjustment_payload},
            headers={"Idempotency-Key": "cmd-0001", "If-Match": "0"},
        ),
        client.get(f"/v1/sandboxes/{branch_id}/ledger", params={"account_id": "C-0412"}),
        client.get("/v1/sandboxes/sb_" + "0" * 24),
        client.post(
            f"/v1/sandboxes/{branch_id}/mutations/preview",
            json={"kind": "refund.explode", "data": {}},
        ),
        client.delete("/v1/sessions/current"),
    ]
    for answer in answers:
        assert answer.headers.get(SCHEMA_VERSION_HEADER) == SCHEMA_VERSION, answer.request.url
