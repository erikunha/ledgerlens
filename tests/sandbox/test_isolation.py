"""The isolation between two visitors: the store, the domain and the facade refuse the branch of another session.

The rule is proven in the data and not only in the path of the domain layer: a store asked for the branch of another
visitor returns nothing, whatever the caller does next, and the refusal is the same error as a branch that does not
exist at all (FR-004, FR-005, FR-027, SC-001).

The rule is proven with a real mutation and not only with a synthetic append: the work of one visitor is invisible to
the other one, and a write sent against the branch of another session is refused by the facade and leaves nothing
behind, neither an event nor a moved hash.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ledgerlens.memory.long_term import CaseMemory
from ledgerlens.run_context import canonical_session_id
from ledgerlens.sandbox.branch import BranchLayer
from ledgerlens.sandbox.memory import branch_run_context
from ledgerlens.sandbox.mutation import MutationCommand
from ledgerlens.sandbox.snapshot import BaseResolver, BaseSnapshot
from ledgerlens.sandbox.store import BranchNotFound, BranchStore, FileBranchStore, SandboxEventRow
from ledgerlens.schemas import Coherence, InvestigationResult, Verdict
from tests.sandbox.conftest import FakeClock


def _event(branch_id: str) -> SandboxEventRow:
    return SandboxEventRow(
        event_uid="evt-isolated",
        branch_id=branch_id,
        event_type="refund.fx_adjusted",
        aggregate_id="R-0731",
        occurred_at="2026-11-14T10:00:00Z",
        payload={"rate": "5.41250000"},
    )


def _supported_result(session_id: str) -> InvestigationResult:
    """A result whose verdicts are all supported, which is what the case memory accepts."""
    return InvestigationResult(
        session_id=session_id,
        question="the refund came in lower than the payment",
        answer="The difference is the refund fee.",
        claims=[],
        evidence=[],
        verdicts=[Verdict(claim_id="CL1", label="supported", method="rule")],
        coherence=Coherence(passed=True),
        recommended_action="explain_to_customer",
        requires_human_review=False,
    )


def _text_under(folder: Path) -> str:
    """Every name and every text of the files under a folder, as one string."""
    parts: list[str] = []
    for path in sorted(folder.rglob("*")):
        parts.append(path.name)
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


# --- two visitors on the same scenario ------------------------------------------------------------


def test_two_sessions_fork_the_same_scenario_with_two_different_branches(
    layer: BranchLayer, session_id: str, other_session_id: str, scenario_id: str
) -> None:
    first = layer.fork(session_id, scenario_id).branch
    second = layer.fork(other_session_id, scenario_id).branch
    assert first.branch_id != second.branch_id


def test_the_two_branches_of_the_same_scenario_report_the_same_base_hash(
    layer: BranchLayer, session_id: str, other_session_id: str, scenario_id: str, base_snapshot: BaseSnapshot
) -> None:
    first = layer.fork(session_id, scenario_id).branch
    second = layer.fork(other_session_id, scenario_id).branch
    assert first.base_canonical_hash == second.base_canonical_hash == base_snapshot.canonical_hash


# --- the store refuses the branch of another session -----------------------------------------------


def test_the_store_refuses_to_read_the_branch_of_another_session(
    store: FileBranchStore, layer: BranchLayer, session_id: str, other_session_id: str, scenario_id: str
) -> None:
    branch = layer.fork(session_id, scenario_id).branch
    with pytest.raises(BranchNotFound):
        store.get_branch(branch.branch_id, canonical_session_id(other_session_id))


def test_the_refusal_of_a_branch_of_another_session_is_the_same_as_the_refusal_of_a_missing_branch(
    store: FileBranchStore, layer: BranchLayer, session_id: str, other_session_id: str, scenario_id: str
) -> None:
    branch = layer.fork(session_id, scenario_id).branch
    with pytest.raises(BranchNotFound) as of_other:
        store.get_branch(branch.branch_id, canonical_session_id(other_session_id))
    with pytest.raises(BranchNotFound) as of_missing:
        store.get_branch("sb_" + "0" * 24, canonical_session_id(other_session_id))
    assert str(of_other.value) == str(of_missing.value)


def test_the_store_refuses_to_read_the_events_of_the_branch_of_another_session(
    store: FileBranchStore, layer: BranchLayer, session_id: str, other_session_id: str, scenario_id: str
) -> None:
    branch = layer.fork(session_id, scenario_id).branch
    owner = canonical_session_id(session_id)
    store.append_events(branch.branch_id, owner, [_event(branch.branch_id)])
    with pytest.raises(BranchNotFound):
        store.read_events(branch.branch_id, canonical_session_id(other_session_id))


def test_the_branch_of_another_session_has_no_event(
    store: FileBranchStore, layer: BranchLayer, session_id: str, other_session_id: str, scenario_id: str
) -> None:
    mine = layer.fork(session_id, scenario_id).branch
    theirs = layer.fork(other_session_id, scenario_id).branch
    store.append_events(mine.branch_id, canonical_session_id(session_id), [_event(mine.branch_id)])
    assert len(store.read_events(mine.branch_id, canonical_session_id(session_id))) == 1
    # the event of one branch never shows up in the event log of the branch of the other session
    assert store.read_events(theirs.branch_id, canonical_session_id(other_session_id)) == []


def test_the_store_refuses_to_append_to_the_branch_of_another_session(
    store: FileBranchStore, layer: BranchLayer, session_id: str, other_session_id: str, scenario_id: str
) -> None:
    branch = layer.fork(session_id, scenario_id).branch
    with pytest.raises(BranchNotFound):
        store.append_events(branch.branch_id, canonical_session_id(other_session_id), [_event(branch.branch_id)])


# --- the domain refuses the branch of another session ----------------------------------------------


def test_the_domain_refuses_the_status_of_the_branch_of_another_session(
    layer: BranchLayer, session_id: str, other_session_id: str, scenario_id: str
) -> None:
    branch = layer.fork(session_id, scenario_id).branch
    with pytest.raises(BranchNotFound) as info:
        layer.status(other_session_id, branch.branch_id)
    message = str(info.value)
    assert session_id not in message
    assert canonical_session_id(session_id) not in message
    assert "exist" not in message.lower()


def test_the_domain_refuses_a_branch_that_does_not_exist_with_the_same_message(
    layer: BranchLayer, session_id: str, other_session_id: str, scenario_id: str
) -> None:
    branch = layer.fork(session_id, scenario_id).branch
    with pytest.raises(BranchNotFound) as of_other:
        layer.status(other_session_id, branch.branch_id)
    with pytest.raises(BranchNotFound) as of_missing:
        layer.status(other_session_id, "sb_" + "0" * 24)
    assert str(of_other.value) == str(of_missing.value)


# --- the work of one visitor never reaches the branch of another ---------------------------------------


def test_the_mutation_of_the_first_session_is_not_read_by_the_second_session(
    store: BranchStore,
    layer: BranchLayer,
    session_id: str,
    other_session_id: str,
    scenario_id: str,
    base_snapshot: BaseSnapshot,
    adjustment: MutationCommand,
) -> None:
    """The real mutation of one visitor is invisible to the other one (FR-004, FR-005, SC-001).

    Why the real mutation and not an append to the store: a synthetic append writes an event that no command ever
    produced, so it proves that the store files the events of two branches apart, and not that the work of one
    visitor is invisible to another one. This case commits a command through the layer, the way the facade does, and
    then reads the branch of the second session.

    Why the diff of the branch and not only its revision: the state of the branch of the second session has to be the
    published case row for row, and the diff is what says that the values of the branch are the values of the base.

    Why the branch of the first session is read as well: a mutation that was refused would leave the first branch
    where it was, so the case proves that the mutation really happened before it proves that the other visitor does
    not see it.
    """
    mine = layer.fork(session_id, scenario_id).branch
    theirs = layer.fork(other_session_id, scenario_id).branch

    layer.commit_mutation(session_id, mine.branch_id, adjustment)

    # The mutation of the first visitor is a real one: its branch moved away from the base.
    served_mine = layer.status(session_id, mine.branch_id)
    assert served_mine.revision == 1
    assert served_mine.current_canonical_hash != served_mine.base_canonical_hash
    assert len(store.read_events(mine.branch_id, canonical_session_id(session_id))) == 1

    # The branch of the second visitor still holds the base, its hash and no event at all.
    served_theirs = layer.status(other_session_id, theirs.branch_id)
    assert served_theirs.revision == 0
    assert served_theirs.current_canonical_hash == served_theirs.base_canonical_hash
    assert served_theirs.current_canonical_hash == base_snapshot.canonical_hash
    assert layer.diff(other_session_id, theirs.branch_id).diff == []
    assert len(store.read_events(theirs.branch_id, canonical_session_id(other_session_id))) == 0


# --- the facade refuses the write of a branch of another session ---------------------------------------


def test_the_mutation_sent_against_the_branch_of_another_session_is_refused_with_404(
    store: BranchStore,
    base_resolver: BaseResolver,
    clock: FakeClock,
    scenario_id: str,
    adjustment_payload: dict[str, object],
    tmp_path: Path,
) -> None:
    """A write sent against the branch of another session is refused, and it leaves nothing behind (FR-004, SC-001).

    Why the facade and not the store: the store refuses the append to the branch of another session, but the promise
    is about the answer the visitor sees, and the answer is the one of the facade. The case therefore sends a real
    request, with the headers of the contract, from the session of the second visitor against the branch of the first
    one.

    Why nothing is written anywhere: the refusal happens before the work, so neither branch of the two visitors holds
    an event of the refused request, and the hash of the branch of the first visitor is the one it had before the
    request was sent.
    """
    from fastapi.testclient import TestClient

    from ledgerlens.api.sandbox import BRANCH_HASH_HEADER, create_app

    app = create_app(store=store, base_resolver=base_resolver, clock=clock, runtime_dir=tmp_path)
    first = TestClient(app)
    second = TestClient(app)
    mine_session = first.post("/v1/sessions").json()["id"]
    theirs_session = second.post("/v1/sessions").json()["id"]
    mine = first.post("/v1/sandboxes", json={"scenario_id": scenario_id}).json()
    theirs = second.post("/v1/sandboxes", json={"scenario_id": scenario_id}).json()

    before = first.get(f"/v1/sandboxes/{mine['id']}")
    assert before.status_code == 200

    refused = second.post(
        f"/v1/sandboxes/{mine['id']}/mutations",
        json={"kind": "refund.apply_fx_adjustment", "data": adjustment_payload},
        headers={"Idempotency-Key": "cmd-0002", "If-Match": "0"},
    )

    assert refused.status_code == 404
    body = refused.json()
    assert body["code"] == "NOT_FOUND"
    assert mine["id"] not in body["message"]
    # The refused request left no event in the branch of the first visitor and none in the branch of the second one.
    assert store.read_events(mine["id"], canonical_session_id(mine_session)) == []
    assert store.read_events(theirs["id"], canonical_session_id(theirs_session)) == []
    # The branch of the first visitor kept its hash and its revision.
    after = first.get(f"/v1/sandboxes/{mine['id']}")
    assert after.status_code == 200
    assert after.headers[BRANCH_HASH_HEADER] == before.headers[BRANCH_HASH_HEADER]
    assert after.json()["revision"] == before.json()["revision"] == 0


# --- the case memory of one session is not read by another -------------------------------------------


def test_the_case_written_in_the_first_session_is_not_found_by_the_second_session(
    layer: BranchLayer, session_id: str, other_session_id: str, scenario_id: str, tmp_path: Path
) -> None:
    """The case memory of a sandbox session is private (FR-027, T062).

    The seeded cases are shared and read-only by design, so both sessions see them. The proof is about what a
    session writes: the case of the first session does not appear in the records of the second one.
    """
    mine = branch_run_context(layer.fork(session_id, scenario_id).branch, runtime_dir=tmp_path)
    theirs = branch_run_context(layer.fork(other_session_id, scenario_id).branch, runtime_dir=tmp_path)

    memory_mine = CaseMemory(mine.resolve_memory_dir())
    memory_theirs = CaseMemory(theirs.resolve_memory_dir())

    written = memory_mine.write_case(_supported_result(session_id))
    assert written["written"] is True, written
    case_id = written["case_id"]

    ids_mine = {record["case_id"] for record in memory_mine.records()}
    ids_theirs = {record["case_id"] for record in memory_theirs.records()}
    assert case_id in ids_mine
    assert case_id not in ids_theirs
    assert not memory_theirs.runtime_file.exists()


# --- the folders on the disk -----------------------------------------------------------------------


def test_the_folder_of_one_session_holds_no_branch_of_another_session(
    store: FileBranchStore, layer: BranchLayer, session_id: str, other_session_id: str, scenario_id: str
) -> None:
    mine = layer.fork(session_id, scenario_id).branch
    theirs = layer.fork(other_session_id, scenario_id).branch
    folder = store.root / canonical_session_id(session_id)
    assert folder.is_dir()
    assert theirs.branch_id not in _text_under(folder)
    assert mine.branch_id in _text_under(folder)


def test_the_two_sessions_have_two_different_folders(
    store: FileBranchStore, layer: BranchLayer, session_id: str, other_session_id: str, scenario_id: str
) -> None:
    layer.fork(session_id, scenario_id)
    layer.fork(other_session_id, scenario_id)
    mine = store.root / canonical_session_id(session_id)
    theirs = store.root / canonical_session_id(other_session_id)
    assert mine.is_dir() and theirs.is_dir()
    assert mine != theirs
    assert theirs not in mine.parents
