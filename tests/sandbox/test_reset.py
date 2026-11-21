"""The reset of a branch: the events go, the branch returns to the base, and the answers of the past go stale.

Why this file exists: the reset is the escape hatch of the sandbox (ADR-022). A visitor changes their mind, or wants
to compare two variations from the same starting point, so the reset drops every event of the branch and gives the
branch the hash it had at fork time (FR-021, SC-002). Around that action sit two promises that are easy to state and
easy to get wrong: the answers produced before the reset are marked stale against the original snapshot and are never
presented as the current result of the branch (FR-022, SC-014), and a branch that cannot prove its own state is refused
with `HASH_MISMATCH` instead of being served (FR-032).

What the file proves:

* the reset drops every event, sets the revision back to zero and gives the branch the hash recorded at fork time;
* the ledger of the branch after the reset is the ledger of the base, row for row;
* the answers the branch remembered before the reset are marked stale, and an answer committed after the reset is not;
* the replay of a request of the past is marked stale too, and still carries the values of that request;
* the generation moves forward under the lock of the store, so two resets that cross do not lose one increment;
* the reset is atomic: a reset that cannot be written leaves the branch where it was, in the two stores alike, and
  the branch is still served;
* a branch whose stored base hash is wrong is refused with `HASH_MISMATCH` on every route, and the message offers a
  fresh fork;
* the reset of a branch of another session is refused with the same generic error as a branch that does not exist;
* the reset of an expired branch is refused with `BranchExpired`;
* the refresh of the deadline moves the deadline and nothing else, so it cannot lose a mutation that landed in
  between the read and the write (ADR-027);
* the reset writes nothing to a published artifact (FR-001);
* the route of the reset answers the resource of the contract, and the three refusals answer the codes of the facade.
"""

from __future__ import annotations

import hashlib
import threading
from collections.abc import Callable
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from ledgerlens.run_context import canonical_session_id
from ledgerlens.sandbox.branch import (
    BranchExpired,
    BranchHashMismatch,
    BranchLayer,
    SandboxBranch,
)
from ledgerlens.sandbox.mutation import MutationCommand
from ledgerlens.sandbox.postgres_store import PostgresBranchStore
from ledgerlens.sandbox.snapshot import BaseResolver
from ledgerlens.sandbox.store import BranchNotFound, BranchStore, FileBranchStore, SandboxCommandRow

# The resource `Sandbox` of the contract of the design package, field for field.
RESOURCE_KEYS = {"id", "base_snapshot_id", "snapshot_sha256", "revision", "expires_at"}


def _command(payload: dict[str, object], key: str, revision: int = 0) -> MutationCommand:
    """A command with the given payload, key and expected revision."""
    return MutationCommand(
        kind="refund.apply_fx_adjustment",
        payload=payload,
        expected_revision=revision,
        idempotency_key=key,
    )


def _refusal(action: Callable[[], Any]) -> str:
    """The name of the error of a refused action, or the mark of an action that was not refused.

    Why it exists: the two stores refuse a broken reset in two different ways, and the test is about the fact that
    they refused, not about the kind of the refusal.
    """
    try:
        action()
    except Exception as exc:  # noqa: BLE001 - the refusal of the store is what the test is about
        return type(exc).__name__
    return "no refusal"


@pytest.fixture
def tamper_base_hash(store: BranchStore, owner_session: str):
    """A writer that puts a wrong base hash in the row of a branch.

    Why the writer goes through the store and not through the files or the tables: the two stores keep their row in
    two different places, and the store is the one interface that reaches both of them. The writer works on a branch
    of any session, and the store of the test lives in a temporary folder or in the database of the suite, never in the
    published artifacts.
    """

    def write(branch_id: str, wrong_hash: str) -> None:
        row = store.get_branch(branch_id, owner_session)
        store.save_branch(replace(row, base_canonical_hash=wrong_hash))

    return write


# --- the reset moves the branch back to the base ------------------------------------------------------------


def test_the_reset_drops_the_events_and_puts_the_branch_back_at_the_hash_of_the_base(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment_payload: dict[str, object],
    event_count,
) -> None:
    """FR-021: the reset drops every event and gives back the hash recorded at fork time."""
    layer.commit_mutation(session_id, forked_branch.branch_id, _command(adjustment_payload, "cmd-0001"))
    layer.commit_mutation(session_id, forked_branch.branch_id, _command(adjustment_payload, "cmd-0002", 1))
    assert event_count(forked_branch.branch_id) == 2

    reset = layer.reset(session_id, forked_branch.branch_id)
    assert reset.revision == 0
    assert reset.current_canonical_hash == forked_branch.base_canonical_hash
    assert event_count(forked_branch.branch_id) == 0
    assert layer.status(session_id, forked_branch.branch_id).current_canonical_hash == forked_branch.base_canonical_hash


def test_the_reset_moves_the_generation_of_the_branch_forward(
    layer: BranchLayer, session_id: str, forked_branch: SandboxBranch
) -> None:
    """The generation counts the resets the branch went through, and it is what marks the staleness."""
    assert forked_branch.generation == 0
    first = layer.reset(session_id, forked_branch.branch_id)
    assert first.generation == 1
    second = layer.reset(session_id, forked_branch.branch_id)
    assert second.generation == 2


def test_two_resets_that_cross_move_the_generation_forward_twice(
    database_store: PostgresBranchStore,
    base_resolver: BaseResolver,
    session_id: str,
    scenario_id: str,
    clock,
) -> None:
    """ADR-022: the store moves the generation under its own lock, so two resets that cross do not lose one.

    Why the two barriers: the first one makes both threads read the row before either of them writes it, and the
    second one makes them write at the same time. Without them the test would only prove that one of the two resets
    happened, and the increment that the other one lost would go unnoticed.

    Why the answer is committed without events: the branch then keeps verifying against the base whatever the order
    of the two resets, and the race under test is the arithmetic of the generation and not the projection.
    """
    owner = canonical_session_id(session_id)
    other_store = PostgresBranchStore(database_store.database_url)
    try:
        layer = BranchLayer(database_store, base_resolver, clock=clock)
        branch = layer.fork(session_id, scenario_id).branch
        row = database_store.get_branch(branch.branch_id, owner)
        answer = SandboxCommandRow(
            branch_id=branch.branch_id,
            idempotency_key="cmd-0001",
            payload_digest="d" * 64,
            revision=1,
            canonical_hash=row.base_canonical_hash,
            response_diff=[],
            response_verdict={},
            response_invariants=[],
            generation=0,
        )
        database_store.commit_events(
            branch.branch_id,
            owner,
            [],
            replace(row, revision=1, current_canonical_hash=row.base_canonical_hash),
            answer,
        )

        read = threading.Barrier(2)
        write = threading.Barrier(2)
        failures: list[str] = []

        def reset(store: BranchStore) -> None:
            try:
                read.wait(timeout=10)
                current = store.get_branch(branch.branch_id, owner)
                write.wait(timeout=10)
                store.reset_branch(
                    branch.branch_id,
                    owner,
                    replace(current, revision=0, current_canonical_hash=current.base_canonical_hash),
                )
            except Exception as exc:  # noqa: BLE001 - the failure of a thread is the failure of the test
                failures.append(f"{type(exc).__name__}: {exc}")

        threads = [threading.Thread(target=reset, args=(store,)) for store in (database_store, other_store)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
        assert failures == []

        assert database_store.get_branch(branch.branch_id, owner).generation == 2
        answers = layer.answers(session_id, branch.branch_id)
        assert [recorded.stale for recorded in answers] == [True]
        assert answers[0].stale_against == branch.base_canonical_hash
    finally:
        other_store.close()


def test_the_reset_refreshes_the_idle_deadline_and_keeps_the_absolute_one(
    layer: BranchLayer, session_id: str, forked_branch: SandboxBranch, clock
) -> None:
    """The idle deadline moves with the activity of the visitor, and the absolute deadline never moves."""
    clock.advance(timedelta(minutes=10))
    reset = layer.reset(session_id, forked_branch.branch_id)
    assert reset.expires_at > forked_branch.expires_at
    assert reset.expires_at <= forked_branch.created_at + timedelta(seconds=layer.absolute_ttl_seconds)


# --- the refresh of the deadline --------------------------------------------------------------------


def test_the_refresh_of_the_deadline_cannot_lose_a_mutation_that_landed_in_between(
    layer: BranchLayer,
    store: BranchStore,
    owner_session: str,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment_payload: dict[str, object],
    clock,
) -> None:
    """ADR-027: the refresh of the deadline moves the deadline and nothing else.

    The sequence is the one the defect was reproduced with: a read of the status that refreshes the deadline, the
    row that the read held, a mutation that lands, and the refresh of the row that the read held.

    Why the branch is still served: the refresh of a read is allowed to move the deadline and to write nothing else,
    so the mutation stays in the branch and the branch still proves its own state. A refresh that writes the whole
    row rolls the branch back over the mutation, the row says that the branch holds no event and the log says that
    it holds one, and the branch is refused with `HASH_MISMATCH` on every route (ADR-021).
    """
    layer.status(session_id, forked_branch.branch_id)
    stale = store.get_branch(forked_branch.branch_id, owner_session)
    mutation = layer.commit_mutation(
        session_id, forked_branch.branch_id, _command(adjustment_payload, "cmd-0001")
    )
    # The visitor is active again, so the refresh of the row that the read held really writes.
    clock.advance(timedelta(minutes=10))
    layer._refresh(stale)

    served = layer.status(session_id, forked_branch.branch_id)
    assert served.revision == 1
    assert served.current_canonical_hash == mutation.canonical_hash
    assert served.expires_at > forked_branch.expires_at


def test_the_ledger_of_the_branch_after_the_reset_is_the_ledger_of_the_base(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment_payload: dict[str, object],
    base_snapshot,
) -> None:
    """The branch after the reset reads the rows of the base, row for row."""
    of_the_base = layer.ledger(session_id, forked_branch.branch_id, base_snapshot.account_id).items
    layer.commit_mutation(session_id, forked_branch.branch_id, _command(adjustment_payload, "cmd-0001"))
    of_the_mutation = layer.ledger(session_id, forked_branch.branch_id, base_snapshot.account_id).items
    assert of_the_mutation != of_the_base

    layer.reset(session_id, forked_branch.branch_id)
    assert layer.ledger(session_id, forked_branch.branch_id, base_snapshot.account_id).items == of_the_base


# --- the staleness of the answers of the past ---------------------------------------------------------------


def test_the_answers_of_the_past_are_marked_stale_against_the_base(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment_payload: dict[str, object],
) -> None:
    """FR-022: an answer of a generation behind the branch is stale, and it names the base it belongs to.

    Why the mutation after the reset: the reset puts the current hash of the branch back at the hash of the base, so
    a test that reads the answers right after the reset cannot tell the hash of the base from the current hash of the
    branch. The mutation committed after the reset moves the current hash away from the hash of the base, and the mark
    of the staleness has to name the base and not the current hash.
    """
    layer.commit_mutation(session_id, forked_branch.branch_id, _command(adjustment_payload, "cmd-0001"))
    layer.reset(session_id, forked_branch.branch_id)
    layer.commit_mutation(session_id, forked_branch.branch_id, _command(adjustment_payload, "cmd-0002"))

    answers = layer.answers(session_id, forked_branch.branch_id)
    assert [answer.idempotency_key for answer in answers] == ["cmd-0001", "cmd-0002"]
    assert answers[0].stale is True
    assert answers[0].stale_against == forked_branch.base_canonical_hash
    assert answers[0].revision == 1
    # The current hash of the branch moved away from the hash of the base, so the mark is not the current hash.
    current = layer.status(session_id, forked_branch.branch_id).current_canonical_hash
    assert current != forked_branch.base_canonical_hash
    assert answers[0].stale_against != current


def test_the_answers_of_a_branch_with_a_wrong_base_hash_are_refused(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    tamper_base_hash,
) -> None:
    """ADR-022: a branch whose recorded base hash is wrong is refused wherever it is asked for.

    The listing of the answers is one of those places, and the comparison of the base hash is part of the verification
    of the branch, not a rule of the reset alone.
    """
    tamper_base_hash(forked_branch.branch_id, "f" * 64)
    with pytest.raises(BranchHashMismatch) as refusal:
        layer.answers(session_id, forked_branch.branch_id)
    assert refusal.value.code == "HASH_MISMATCH"


def test_an_answer_committed_after_the_reset_is_not_stale(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment_payload: dict[str, object],
) -> None:
    """The answer of the current generation is the current result of the branch."""
    layer.commit_mutation(session_id, forked_branch.branch_id, _command(adjustment_payload, "cmd-0001"))
    layer.reset(session_id, forked_branch.branch_id)
    layer.commit_mutation(session_id, forked_branch.branch_id, _command(adjustment_payload, "cmd-0002"))

    answers = layer.answers(session_id, forked_branch.branch_id)
    assert [answer.stale for answer in answers] == [True, False]
    assert answers[1].stale_against is None


def test_the_replay_of_a_request_of_the_past_is_marked_stale(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment_payload: dict[str, object],
) -> None:
    """The answer of a request of the past is never presented as the current result of the branch.

    The values the answer carries are the ones of the request that was made: the revision, the hash, the diff and the
    verdict of that request, and not the ones of the branch of today.

    The mutation committed after the reset moves the current hash of the branch away from the hash of the base, so the
    mark of the staleness cannot be the current hash of the branch.
    """
    first = layer.commit_mutation(session_id, forked_branch.branch_id, _command(adjustment_payload, "cmd-0001"))
    layer.reset(session_id, forked_branch.branch_id)
    layer.commit_mutation(session_id, forked_branch.branch_id, _command(adjustment_payload, "cmd-0002"))

    replay = layer.commit_mutation(session_id, forked_branch.branch_id, _command(adjustment_payload, "cmd-0001"))
    assert replay.stale is True
    assert replay.stale_against == forked_branch.base_canonical_hash
    assert replay.revision == first.revision
    assert replay.canonical_hash == first.canonical_hash
    assert replay.diff == first.diff
    assert replay.verdict == first.verdict
    assert replay.replayed is True
    current = layer.status(session_id, forked_branch.branch_id).current_canonical_hash
    assert current != forked_branch.base_canonical_hash
    assert replay.stale_against != current


def test_the_answer_of_a_request_of_the_past_carries_the_mark_in_its_own_shape(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment_payload: dict[str, object],
) -> None:
    """The mark of the staleness travels in the answer of the mutation, so the interface can read it."""
    layer.commit_mutation(session_id, forked_branch.branch_id, _command(adjustment_payload, "cmd-0001"))
    layer.reset(session_id, forked_branch.branch_id)

    replay = layer.commit_mutation(session_id, forked_branch.branch_id, _command(adjustment_payload, "cmd-0001"))
    body = replay.to_dict()
    assert body["stale"] is True
    assert body["stale_against"] == forked_branch.base_canonical_hash


# --- the atomicity of the reset ----------------------------------------------------------------------------------


def test_the_reset_of_the_database_that_fails_leaves_the_events_of_the_branch(
    database_store: PostgresBranchStore,
    base_resolver: BaseResolver,
    session_id: str,
    scenario_id: str,
    clock,
    adjustment_payload: dict[str, object],
) -> None:
    """The drop of the events and the move of the row are one transaction (ADR-021, ADR-022).

    The row handed over cannot be written, because its expiry is missing. The transaction is rolled back, so the
    branch keeps its events and its revision: a reset that did not happen is not a reset that happened halfway.
    """
    layer = BranchLayer(database_store, base_resolver, clock=clock)
    branch = layer.fork(session_id, scenario_id).branch
    layer.commit_mutation(session_id, branch.branch_id, _command(adjustment_payload, "cmd-0001"))
    owner = canonical_session_id(session_id)
    row = database_store.get_branch(branch.branch_id, owner)
    broken = replace(row, revision=0, current_canonical_hash=row.base_canonical_hash, expires_at=None)

    assert _refusal(lambda: database_store.reset_branch(branch.branch_id, owner, broken)) != "no refusal"
    assert len(database_store.read_events(branch.branch_id, owner)) == 1
    assert database_store.get_branch(branch.branch_id, owner).revision == row.revision


def test_the_reset_of_the_file_store_that_fails_leaves_the_branch_where_it_was(
    file_store: FileBranchStore,
    base_resolver: BaseResolver,
    session_id: str,
    scenario_id: str,
    clock,
    adjustment_payload: dict[str, object],
) -> None:
    """A reset that did not happen leaves the branch exactly where it was (ADR-022).

    The file of the events is emptied before the row is written, and the content of the file is put back when the write
    of the row fails. The two stores therefore lose the same thing when a reset fails: nothing, and the branch is
    still served instead of being refused with `HASH_MISMATCH`.
    """
    layer = BranchLayer(file_store, base_resolver, clock=clock)
    branch = layer.fork(session_id, scenario_id).branch
    layer.commit_mutation(session_id, branch.branch_id, _command(adjustment_payload, "cmd-0001"))
    owner = canonical_session_id(session_id)
    row = file_store.get_branch(branch.branch_id, owner)
    broken = replace(row, expires_at=None)

    assert _refusal(lambda: file_store.reset_branch(branch.branch_id, owner, broken)) != "no refusal"
    # The events of the branch survived the failed reset, and the row of the branch did not move.
    assert len(file_store.read_events(branch.branch_id, owner)) == 1
    assert file_store.get_branch(branch.branch_id, owner).revision == row.revision
    # The branch can still prove its own state, so it is served.
    assert layer.status(session_id, branch.branch_id).revision == row.revision


# --- the refusals of the reset -------------------------------------------------------------------------------


def test_a_branch_with_a_wrong_base_hash_is_refused_with_HASH_MISMATCH(
    layer: BranchLayer, session_id: str, forked_branch: SandboxBranch, tamper_base_hash
) -> None:
    """FR-032: a branch that cannot prove its own state is refused, and the message offers a fresh fork."""
    tamper_base_hash(forked_branch.branch_id, "f" * 64)
    with pytest.raises(BranchHashMismatch) as refusal:
        layer.reset(session_id, forked_branch.branch_id)
    assert refusal.value.code == "HASH_MISMATCH"
    assert "fork" in refusal.value.message
    # The refusal names the base, so the test says that it is the comparison of the base that failed.
    assert "base" in refusal.value.message


def test_the_reset_of_the_branch_of_another_session_is_refused_with_the_generic_error(
    layer: BranchLayer, session_id: str, other_session_id: str, forked_branch: SandboxBranch
) -> None:
    """A branch of another visitor is refused the same way a branch that does not exist is refused."""
    with pytest.raises(BranchNotFound) as of_other:
        layer.reset(other_session_id, forked_branch.branch_id)
    with pytest.raises(BranchNotFound) as of_missing:
        layer.reset(other_session_id, "sb_" + "0" * 24)
    assert str(of_other.value) == str(of_missing.value)


def test_the_reset_of_an_expired_branch_is_refused_with_BranchExpired(
    layer: BranchLayer, session_id: str, forked_branch: SandboxBranch, clock
) -> None:
    """An expired branch is refused, and the refusal names the state of the branch."""
    clock.advance(timedelta(hours=2))
    with pytest.raises(BranchExpired):
        layer.reset(session_id, forked_branch.branch_id)


# --- the published artifacts ---------------------------------------------------------------------------------


def test_the_reset_writes_nothing_to_a_published_file(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    adjustment_payload: dict[str, object],
    published_digests: dict[str, str | None],
) -> None:
    """FR-001: the reset works on the branch and never on the published snapshot."""
    project_root = Path(__file__).resolve().parents[2]
    layer.commit_mutation(session_id, forked_branch.branch_id, _command(adjustment_payload, "cmd-0001"))
    layer.reset(session_id, forked_branch.branch_id)

    for name, digest in published_digests.items():
        path = project_root / "data" / name
        current = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
        assert current == digest


# --- the route of the reset ----------------------------------------------------------------------------------


@pytest.fixture
def app(store: BranchStore, base_resolver, clock):
    """The facade of the contract, over the store of the test."""
    pytest.importorskip("fastapi")
    from ledgerlens.api.sandbox import create_app

    return create_app(store=store, base_resolver=base_resolver, clock=clock)


@pytest.fixture
def client(app):
    """A client of the facade with a session of its own."""
    from fastapi.testclient import TestClient

    http = TestClient(app)
    assert http.post("/v1/sessions").status_code == 201
    return http


def _fork(http, scenario_id: str) -> str:
    """The identifier of the branch the client owns."""
    return http.post("/v1/sandboxes", json={"scenario_id": scenario_id}).json()["id"]


def test_the_route_of_the_reset_answers_the_resource_of_the_contract(client, scenario_id: str) -> None:
    """The body of the answer is the resource `Sandbox` of the contract, field for field."""
    from ledgerlens.api.sandbox import BRANCH_HASH_HEADER, SCHEMA_VERSION, SCHEMA_VERSION_HEADER

    branch_id = _fork(client, scenario_id)
    response = client.post(f"/v1/sandboxes/{branch_id}/reset")
    assert response.status_code == 200
    assert set(response.json()) == RESOURCE_KEYS
    assert response.json()["revision"] == 0
    assert response.headers[SCHEMA_VERSION_HEADER] == SCHEMA_VERSION
    assert response.headers[BRANCH_HASH_HEADER] == response.json()["snapshot_sha256"]


def test_the_route_of_the_reset_refuses_the_branch_of_another_session_with_404(
    app, client, scenario_id: str
) -> None:
    """The refusal says nothing about the owner and nothing about the existence of the branch."""
    from fastapi.testclient import TestClient

    branch_id = _fork(client, scenario_id)
    other = TestClient(app)
    assert other.post("/v1/sessions").status_code == 201
    response = other.post(f"/v1/sandboxes/{branch_id}/reset")
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_the_route_of_the_reset_refuses_a_branch_that_does_not_exist_with_404(client) -> None:
    """A branch that does not exist is refused the same way."""
    response = client.post("/v1/sandboxes/sb_" + "0" * 24 + "/reset")
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_the_route_of_the_reset_refuses_an_expired_branch_with_410(client, scenario_id: str, clock) -> None:
    """An expired branch answers 410 with the code of the contract."""
    branch_id = _fork(client, scenario_id)
    clock.advance(timedelta(hours=2))
    response = client.post(f"/v1/sandboxes/{branch_id}/reset")
    assert response.status_code == 410
    assert response.json()["code"] == "BRANCH_EXPIRED"


def test_the_route_of_the_reset_refuses_a_branch_that_cannot_prove_its_state_with_409(
    client, scenario_id: str, adjustment_payload: dict[str, object], tamper_events
) -> None:
    """A branch that cannot prove its own state answers 409 with the code of the contract."""
    branch_id = _fork(client, scenario_id)
    client.post(
        f"/v1/sandboxes/{branch_id}/mutations",
        json={"kind": "refund.apply_fx_adjustment", "data": adjustment_payload},
        headers={"Idempotency-Key": "cmd-0001", "If-Match": "0"},
    )
    # The crash of a commit that wrote the row of the branch and lost the events of the branch.
    tamper_events(branch_id, [])
    response = client.post(f"/v1/sandboxes/{branch_id}/reset")
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "HASH_MISMATCH"
    assert "fork" in body["message"]


def test_the_routes_refuse_a_branch_whose_recorded_base_hash_is_wrong(
    app, store: BranchStore, scenario_id: str, adjustment_payload: dict[str, object]
) -> None:
    """A branch whose recorded base hash is wrong is refused on every route, not only on the reset (ADR-022).

    The comparison of the base hash is part of the verification of the branch, so the status, the mutation and the
    reset all refuse the branch with the same code and with a message that offers a fresh fork.
    """
    from fastapi.testclient import TestClient

    http = TestClient(app)
    issued = http.post("/v1/sessions")
    assert issued.status_code == 201
    owner = canonical_session_id(issued.json()["id"])
    branch_id = http.post("/v1/sandboxes", json={"scenario_id": scenario_id}).json()["id"]

    row = store.get_branch(branch_id, owner)
    store.save_branch(replace(row, base_canonical_hash="f" * 64))

    status = http.get(f"/v1/sandboxes/{branch_id}")
    assert status.status_code == 409
    assert status.json()["code"] == "HASH_MISMATCH"
    assert "fork" in status.json()["message"]

    mutation = http.post(
        f"/v1/sandboxes/{branch_id}/mutations",
        json={"kind": "refund.apply_fx_adjustment", "data": adjustment_payload},
        headers={"Idempotency-Key": "cmd-0001", "If-Match": "0"},
    )
    assert mutation.status_code == 409
    assert mutation.json()["code"] == "HASH_MISMATCH"

    reset = http.post(f"/v1/sandboxes/{branch_id}/reset")
    assert reset.status_code == 409
    assert reset.json()["code"] == "HASH_MISMATCH"
