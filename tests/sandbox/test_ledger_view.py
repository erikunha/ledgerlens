"""The ledger of the visitor, materialized in a file the tools of the agent can read.

Why this file exists: ADR-038 decides that the live run reads the ledger of the branch of the visitor, and that the
branch is the only truth of the visitor. The promises of that decision are easy to state and easy to get wrong:

* the file of the view holds the rows of the account of the branch and of no other account, and the counterparties
  of the transactions of that account;
* the file holds the state of the branch and not the state of the base, so the mutations of the visitor are in it;
* a branch of another session, a branch that cannot prove its own state, an account that is not the account of the
  branch and a revision that moved are all refused, and a refused branch leaves no file behind;
* the base is only ever read, so its canonical hash and its bytes are the same before and after the view;
* the view names the branch, the revision and the canonical hash of the state the run read;
* a view of the branch is an activity of the visitor on it, so the idle deadline of the branch moves.

Why the file is opened with the helper of the tools: the promise is that the tools of the agent can read the file, so
the tests read it the way the tools read it, in read only mode.
"""

from __future__ import annotations

import hashlib
from contextlib import closing
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from ledgerlens.sandbox.branch import (
    BranchHashMismatch,
    BranchLayer,
    BranchNotFound,
    SandboxBranch,
)
from ledgerlens.sandbox.ledger_view import (
    CODE_ACCOUNT_MISMATCH,
    CODE_REVISION_MOVED,
    LedgerAccountMismatch,
    LedgerRevisionMoved,
    LedgerView,
)
from ledgerlens.sandbox.mutation import MutationCommand
from ledgerlens.sandbox.snapshot import BaseResolver, BaseSnapshot
from ledgerlens.sandbox.store import BranchStore, SandboxEventRow
from ledgerlens.sim.projector import canonical_hash
from ledgerlens.tools.sql import open_readonly
from tests.sandbox.conftest import FakeClock

# The account of the request that is not the account of the branch of the scenario. The number is invented on
# purpose: the check of the account happens before anything is read, so the account does not have to exist.
ANOTHER_ACCOUNT = "C-0001"


def _query(path: Path, sql: str) -> list[tuple[Any, ...]]:
    """The rows of a query over a ledger file, opened the way the tools of the agent open it."""
    with closing(open_readonly(path)) as conn:
        return conn.execute(sql).fetchall()


def _canonical_hash_of(path: Path) -> str:
    """The canonical hash of a ledger file, read the way the base computes it."""
    with closing(open_readonly(path)) as conn:
        return canonical_hash(conn)


def _unknown_event(branch_id: str) -> SandboxEventRow:
    """An event of a kind the interpreter of the vocabulary of the sandbox does not know.

    Why the event exists: no visitor can append one, because the only way to append an event is a mutation of the
    catalog or an undo, and a corruption of the log can. The branch then cannot prove its own state (ADR-021).
    """
    return SandboxEventRow(
        event_uid="evt-unknown-kind",
        branch_id=branch_id,
        event_type="sandbox.unknown.kind",
        aggregate_id="R-0731",
        occurred_at="2026-11-14T10:00:00Z",
        payload={"note": "an event of a kind the interpreter does not know"},
        origin="sandbox",
        command_id="cmd-unknown-kind",
    )


# --- the file of the view holds the rows of the account of the branch -----------------------------------------


def test_the_ledger_of_the_view_holds_the_rows_of_the_account_of_the_branch_only(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    base_snapshot: BaseSnapshot,
    tmp_path: Path,
) -> None:
    """The file of the view holds the rows of the account of the branch and of no other account (ADR-038).

    Why the folder of the target does not exist yet: the run names a file in a folder of the runtime that the run
    itself creates, so the view has to create it.
    """
    target = tmp_path / "runs" / "ledger.db"

    view = layer.ledger_view(
        session_id,
        forked_branch.branch_id,
        account_id=base_snapshot.account_id,
        target=target,
    )

    assert _query(view.path, "SELECT DISTINCT customer_id FROM transactions") == [(base_snapshot.account_id,)]
    assert _query(view.path, "SELECT id FROM customers") == [(base_snapshot.account_id,)]


def test_the_ledger_of_the_view_holds_the_mutations_of_the_branch(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    base_snapshot: BaseSnapshot,
    adjustment: MutationCommand,
    tmp_path: Path,
) -> None:
    """The file of the view holds the state of the branch and not the state of the base (ADR-038).

    The ledger of the visitor is the branch with the events of the visitor applied, so the rate the visitor asked for
    is in the file and the rate of the base is not.
    """
    layer.commit_mutation(session_id, forked_branch.branch_id, adjustment)
    target = tmp_path / "ledger.db"

    view = layer.ledger_view(
        session_id,
        forked_branch.branch_id,
        account_id=base_snapshot.account_id,
        target=target,
    )

    rate_in_view = _query(view.path, "SELECT applied_rate FROM fx_applied WHERE refund_id = 'R-0731'")
    rate_in_base = _query(base_snapshot.db_path, "SELECT applied_rate FROM fx_applied WHERE refund_id = 'R-0731'")
    assert rate_in_view == [("5.4125",)]
    assert rate_in_view != rate_in_base
    payout_in_view = _query(view.path, "SELECT payout_amount_minor FROM refunds WHERE id = 'R-0731'")
    payout_in_base = _query(base_snapshot.db_path, "SELECT payout_amount_minor FROM refunds WHERE id = 'R-0731'")
    assert payout_in_view != payout_in_base
    assert view.revision == 1
    assert view.canonical_hash != forked_branch.base_canonical_hash


# --- the refusals of the view ------------------------------------------------------------------------------


def test_the_two_refusals_of_the_reader_carry_a_code_and_a_message() -> None:
    """The two refusals of the reader of the ledger have the shape of the other refusals of the sandbox.

    Why it matters: the facade maps the refusals by type, so nothing fails today, but a refusal of the sandbox that
    carries no code is a refusal of another family, and the caller cannot answer it the way it answers the others.
    """
    mismatch = LedgerAccountMismatch("the account of the request is not the account of the branch")
    moved = LedgerRevisionMoved("the branch moved to another revision")

    assert mismatch.code == CODE_ACCOUNT_MISMATCH
    assert mismatch.message == "the account of the request is not the account of the branch"
    assert moved.code == CODE_REVISION_MOVED
    assert moved.message == "the branch moved to another revision"


def test_the_ledger_of_a_branch_of_another_session_is_refused(
    layer: BranchLayer,
    other_session_id: str,
    forked_branch: SandboxBranch,
    base_snapshot: BaseSnapshot,
    tmp_path: Path,
) -> None:
    """A branch of another session is refused with the generic answer and writes no file (ADR-038).

    Why the same answer as a branch that does not exist: the caller must not be able to tell one from the other.
    """
    target = tmp_path / "ledger.db"

    with pytest.raises(BranchNotFound):
        layer.ledger_view(
            other_session_id,
            forked_branch.branch_id,
            account_id=base_snapshot.account_id,
            target=target,
        )

    assert not target.exists()


def test_a_branch_that_cannot_prove_its_state_has_no_ledger(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    base_snapshot: BaseSnapshot,
    store: BranchStore,
    owner_session: str,
    tmp_path: Path,
) -> None:
    """A branch whose log was tampered with cannot prove its own state, so it has no ledger (ADR-021, ADR-038)."""
    store.append_events(forked_branch.branch_id, owner_session, [_unknown_event(forked_branch.branch_id)])
    target = tmp_path / "ledger.db"

    with pytest.raises(BranchHashMismatch):
        layer.ledger_view(
            session_id,
            forked_branch.branch_id,
            account_id=base_snapshot.account_id,
            target=target,
        )

    assert not target.exists()


def test_the_account_of_another_one_is_refused_and_writes_no_file(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    tmp_path: Path,
) -> None:
    """The account of the request has to be the account of the branch (ADR-038).

    Why this refusal exists: the file of the view is the ledger the model reads, and a request that names another
    account is a request about records the visitor does not own.
    """
    target = tmp_path / "ledger.db"

    with pytest.raises(LedgerAccountMismatch):
        layer.ledger_view(
            session_id,
            forked_branch.branch_id,
            account_id=ANOTHER_ACCOUNT,
            target=target,
        )

    assert not target.exists()


def test_a_revision_that_moved_is_refused_and_writes_no_file(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    base_snapshot: BaseSnapshot,
    adjustment: MutationCommand,
    tmp_path: Path,
) -> None:
    """The request expects a revision the branch is not at any more, so it is refused (ADR-038).

    Why the revision matters: a run that answers about a state the visitor never saw answers a question nobody
    asked.
    """
    layer.commit_mutation(session_id, forked_branch.branch_id, adjustment)
    target = tmp_path / "ledger.db"

    with pytest.raises(LedgerRevisionMoved):
        layer.ledger_view(
            session_id,
            forked_branch.branch_id,
            account_id=base_snapshot.account_id,
            expected_revision=0,
            target=target,
        )

    assert not target.exists()


# --- the file is a copy and the base never moves --------------------------------------------------------------


def test_the_file_of_the_view_is_a_copy_and_the_base_never_moves(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    base_snapshot: BaseSnapshot,
    base_resolver: BaseResolver,
    scenario_id: str,
    adjustment: MutationCommand,
    tmp_path: Path,
) -> None:
    """The base is only ever read: its canonical hash and its bytes are the same before and after the view (ADR-038).

    Why the branch is mutated first: a view of a branch that was never mutated holds the state of the base, and the
    proof that the base did not move would be the proof that nothing happened.
    """
    layer.commit_mutation(session_id, forked_branch.branch_id, adjustment)
    hash_before = _canonical_hash_of(base_snapshot.db_path)
    bytes_before = hashlib.sha256(base_snapshot.db_path.read_bytes()).hexdigest()

    view = layer.ledger_view(
        session_id,
        forked_branch.branch_id,
        account_id=base_snapshot.account_id,
        target=tmp_path / "ledger.db",
    )

    assert _canonical_hash_of(base_snapshot.db_path) == hash_before
    assert hashlib.sha256(base_snapshot.db_path.read_bytes()).hexdigest() == bytes_before
    assert base_resolver(scenario_id).canonical_hash == hash_before
    # The view holds the state of the branch, so its hash is not the hash of the base.
    assert view.canonical_hash != hash_before
    assert view.path != base_snapshot.db_path


# --- the view names what it read -------------------------------------------------------------------------------


def test_the_view_names_the_branch_the_revision_and_the_hash(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    base_snapshot: BaseSnapshot,
    tmp_path: Path,
) -> None:
    """The view names the branch, the revision and the canonical hash of the state the run read (ADR-038).

    Why the name matters: the trace of the run has to say which ledger answered the question, and a path alone does
    not say it.
    """
    target = tmp_path / "ledger.db"

    view = layer.ledger_view(
        session_id,
        forked_branch.branch_id,
        account_id=base_snapshot.account_id,
        target=target,
    )

    assert isinstance(view, LedgerView)
    assert view.path == target
    assert view.branch_id == forked_branch.branch_id
    assert view.revision == forked_branch.revision
    assert view.canonical_hash == forked_branch.current_canonical_hash
    assert view.account_id == base_snapshot.account_id


# --- the file holds the counterparty of the transactions of the account ---------------------------------------


def test_the_ledger_of_the_view_holds_the_counterparty_of_the_transactions_of_the_account(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    base_snapshot: BaseSnapshot,
    published_ledger: Path,
    tmp_path: Path,
) -> None:
    """The file holds the rows of the account of the branch and the counterparties of its transactions (ADR-038).

    Why the counterparty is there and is named out loud: a transaction names the merchant it is with, and the name
    of the merchant is part of the story the run reads. It is a third party, and it is on the disk of the server for
    the length of the run, so the words of the decision have to say it instead of claiming that the file holds the
    rows of the account and nothing else.

    Why the published ledger is read: the file of the view has to hold the counterparties of the account and not the
    counterparties of every account of the repository.
    """
    target = tmp_path / "ledger.db"

    view = layer.ledger_view(
        session_id,
        forked_branch.branch_id,
        account_id=base_snapshot.account_id,
        target=target,
    )

    counterparties = {row[0] for row in _query(view.path, "SELECT DISTINCT merchant_id FROM transactions")}
    merchants = _query(view.path, "SELECT id, name FROM merchants")
    assert counterparties, "the account of the scenario has transactions"
    assert {row[0] for row in merchants} == counterparties
    assert all(row[1] for row in merchants), "every counterparty of the view carries a name"
    # The customers of the view are the account of the branch and nobody else.
    assert _query(view.path, "SELECT id FROM customers") == [(base_snapshot.account_id,)]
    # The published ledger holds the counterparties of every account, and the view holds only those of this one.
    published_merchants = _query(published_ledger, "SELECT id FROM merchants")
    assert len(published_merchants) > len(merchants)
    assert {row[0] for row in published_merchants} > counterparties


def test_the_ledger_of_the_view_moves_the_idle_deadline_of_the_branch(
    layer: BranchLayer,
    session_id: str,
    forked_branch: SandboxBranch,
    base_snapshot: BaseSnapshot,
    store: BranchStore,
    owner_session: str,
    clock: FakeClock,
    tmp_path: Path,
) -> None:
    """A live run is an activity of the visitor on the branch, so the idle deadline moves (ADR-038).

    Why the row of the store and not the status: the status moves the deadline by itself, so reading it would
    measure the status and not the view.
    """
    clock.advance(timedelta(seconds=30))
    before = store.get_branch(forked_branch.branch_id, owner_session)

    layer.ledger_view(
        session_id,
        forked_branch.branch_id,
        account_id=base_snapshot.account_id,
        target=tmp_path / "ledger.db",
    )

    after = store.get_branch(forked_branch.branch_id, owner_session)
    assert after.last_activity_at > before.last_activity_at
    assert after.expires_at > before.expires_at
