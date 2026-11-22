"""The time to live of a branch: the two deadlines, the check of the expiry and the cleanup of the expired branches.

Why this file exists: the sixth story of the specification asks for a branch with a hard time to live. Every access
after the expiry answers `410` with the code `BRANCH_EXPIRED`, and the stored rows and the stored events of the
expired branch are deleted automatically, with a delay of at most sixty seconds between the expiry and the deletion
(FR-023, FR-024, SC-011). ADR-029 put the rule of the expiry in one module and made the cleanup a job of the
process, so these tests hold the rule and the job in place.

What the tests hold:

* the idle deadline moves with the activity of the visitor and the absolute deadline never moves, and the expiry of a
  branch is the earlier of the two;
* the layer asks the module for the expiry, so there is one rule of the time to live and not two;
* a read and a mutation of a branch that outlived its time to live answer `410` with the code `BRANCH_EXPIRED`, so a
  dead branch is never served and never written;
* the cleanup deletes the row of an expired branch, its events and its answers, and leaves the published artifacts
  of the repository untouched;
* the cleanup leaves a branch that is not expired alone, and the branch of a visitor that is still there is still
  served after the sweep;
* a fork after the expiry starts at revision zero with the hash of the base;
* the sweep is safe to run twice, because two workers of the facade may sweep at the same time;
* the thread of the cleanup runs the sweep, stops when it is told to stop and does not keep the process alive.

Why the clock is the one of the suite: the expiry is decided by the server and never by the visitor (FR-031), and a
test that waits for an hour proves nothing.
"""

from __future__ import annotations

import hashlib
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ledgerlens.run_context import canonical_session_id
from ledgerlens.sandbox.branch import BranchLayer
from ledgerlens.sandbox.mutation import MutationCommand
from ledgerlens.sandbox.snapshot import BaseResolver
from ledgerlens.sandbox.store import BranchNotFound, BranchStore, FileBranchStore, SandboxBranchRow
from ledgerlens.sandbox.ttl import (
    ABSOLUTE_TTL_SECONDS,
    IDLE_TTL_SECONDS,
    CleanupWorker,
    cleanup_expired_branches,
    expiry_of,
)
from tests.sandbox.conftest import FakeClock

# The published artifacts of the repository. The cleanup of a branch must never touch them (FR-001).
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PUBLISHED_FILES = (PROJECT_ROOT / "data" / "scenarios.json", PROJECT_ROOT / "data" / "ledger.db")
# The command of the cleanup, the second way of cleaning up (ADR-029).
CLEANUP_SCRIPT = PROJECT_ROOT / "scripts" / "cleanup_sandbox.py"
# The idle deadline of the branch of the case of the facade: one minute, so the case proves the rule without waiting
# an hour for the expiry.
SHORT_IDLE_TTL_SECONDS = 60
# The setting that names the idle deadline of a branch in the configuration of the deployment.
IDLE_TTL_ENV = "LEDGERLENS_SANDBOX_BRANCH_IDLE_TTL_SECONDS"


def _digests() -> dict[str, str | None]:
    """The digest of every published file, or None when the file is not there.

    Why the digests and not the size: a file that was rewritten with the same length is still a change, and the
    promise of the immutability of the published artifacts is about the bytes.
    """
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None for path in PUBLISHED_FILES
    }


class _CountingStore:
    """The store of the test with the sweeps counted and an event that says the sweep ran.

    Why the proxy: the thread of the cleanup has to be observed without a sleep that hopes for a race, and the
    protocol of the store has no place to put a signal. The proxy only carries what the sweep uses: the listing of
    the expired branches and the deletion of one of them.
    """

    def __init__(self, inner: BranchStore) -> None:
        self.inner = inner
        self.sweeps = 0
        self.deleted: list[str] = []
        self.swept = threading.Event()

    def list_expired(self, now: datetime) -> list[SandboxBranchRow]:
        self.sweeps += 1
        try:
            return self.inner.list_expired(now)
        finally:
            self.swept.set()

    def delete_branch(self, branch_id: str, owner_session: str) -> bool:
        deleted = self.inner.delete_branch(branch_id, owner_session)
        self.deleted.append(branch_id)
        return deleted


# --- the rule of the expiry ------------------------------------------------------------------------------


def test_the_expiry_of_a_branch_is_the_earlier_of_the_idle_deadline_and_the_absolute_deadline() -> None:
    """The expiry of a branch is the earlier of the two deadlines.

    Why two deadlines: a visitor that keeps working must not keep a branch forever, and a branch that nobody touches
    must not live longer than the day of the deployment (FR-023).
    """
    created = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)

    # The idle deadline is the earlier one: the branch dies of the silence of the visitor.
    assert expiry_of(created, created) == created + timedelta(seconds=IDLE_TTL_SECONDS)
    # Three hours and a half of idleness: the idle deadline would be four hours and a half, and the absolute one
    # holds the branch.
    assert expiry_of(created + timedelta(hours=3, minutes=30), created) == created + timedelta(
        seconds=ABSOLUTE_TTL_SECONDS
    )


def test_the_idle_deadline_moves_with_the_activity_of_the_visitor(
    store: BranchStore, base_resolver: BaseResolver, clock: FakeClock, session_id: str, scenario_id: str
) -> None:
    """A read of the branch is an activity, so the idle deadline moves with it.

    Why the deadline moves: a visitor that is still working must not lose the branch under the feet, and the idle
    deadline is the one that measures the silence of the visitor.
    """
    layer = BranchLayer(store, base_resolver, clock=clock)
    forked = layer.fork(session_id, scenario_id).branch
    assert forked.expires_at == clock.now + timedelta(seconds=IDLE_TTL_SECONDS)

    clock.advance(timedelta(minutes=30))
    served = layer.status(session_id, forked.branch_id)

    assert served.expires_at == clock.now + timedelta(seconds=IDLE_TTL_SECONDS)


def test_the_absolute_deadline_never_moves(
    store: BranchStore, base_resolver: BaseResolver, clock: FakeClock, session_id: str, scenario_id: str
) -> None:
    """The absolute deadline is counted from the creation and no activity of the visitor moves it.

    Why the absolute deadline exists: without it a visitor that never stops would keep a branch for as long as the
    process lives, and the promise of the deletion of the expired branches would never be kept (FR-024).
    """
    layer = BranchLayer(store, base_resolver, clock=clock, idle_ttl_seconds=3600, absolute_ttl_seconds=600)
    forked = layer.fork(session_id, scenario_id).branch
    assert forked.expires_at == clock.now + timedelta(seconds=600)

    clock.advance(timedelta(seconds=300))
    served = layer.status(session_id, forked.branch_id)

    # The idle deadline would be an hour away; the absolute one is the one that holds.
    assert served.expires_at == forked.expires_at


def test_the_layer_asks_the_module_for_the_expiry(
    store: BranchStore,
    base_resolver: BaseResolver,
    clock: FakeClock,
    session_id: str,
    scenario_id: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The layer does not compute the expiry by itself, so there is one rule of the time to live (ADR-029).

    Why the promise matters: the job that deletes the expired branches and the layer that refuses them have to
    agree on the same moment, and two copies of the rule would drift apart.

    Why the test watches the CALL and not only the result: a layer that computed the same expiry with its own
    arithmetic would answer the very same value, and a test of the value alone would not see the second copy of the
    rule. The test therefore watches the module of the layer and counts the calls.
    """
    from ledgerlens.sandbox import branch as branch_module

    calls: list[tuple[datetime, datetime, int, int]] = []
    original = branch_module.expiry_of

    def spy(
        last_activity_at: datetime,
        created_at: datetime,
        *,
        idle_ttl_seconds: int = IDLE_TTL_SECONDS,
        absolute_ttl_seconds: int = ABSOLUTE_TTL_SECONDS,
    ) -> datetime:
        """The call of the layer, recorded, and then answered by the module itself."""
        calls.append((last_activity_at, created_at, idle_ttl_seconds, absolute_ttl_seconds))
        return original(
            last_activity_at,
            created_at,
            idle_ttl_seconds=idle_ttl_seconds,
            absolute_ttl_seconds=absolute_ttl_seconds,
        )

    monkeypatch.setattr(branch_module, "expiry_of", spy)
    layer = BranchLayer(store, base_resolver, clock=clock)
    forked = layer.fork(session_id, scenario_id).branch

    assert calls, "the layer did not ask the module for the expiry"
    last_activity_at, created_at, idle_ttl_seconds, absolute_ttl_seconds = calls[0]
    assert last_activity_at == forked.last_activity_at
    assert created_at == forked.created_at
    assert idle_ttl_seconds == layer.idle_ttl_seconds
    assert absolute_ttl_seconds == layer.absolute_ttl_seconds
    assert forked.expires_at == expiry_of(forked.last_activity_at, forked.created_at)


# --- the refusal of the facade for an expired branch ---------------------------------------------------


def test_a_read_and_a_mutation_of_an_expired_branch_answer_410(
    store: BranchStore,
    base_resolver: BaseResolver,
    clock: FakeClock,
    scenario_id: str,
    adjustment_payload: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A branch that outlived its time to live answers `410` with the code of the contract, on a read and on a write.

    Why the facade and not the layer: the promise of the time to live is about the answer the visitor sees, and the
    answer of the facade is the one that carries a status and a code (FR-023, SC-011). The case therefore forks through
    the route of the contract and asks for the branch twice: once with a read and once with a mutation.

    Why a mutation and not only a read: a read that is refused proves that the branch is not served, and a mutation
    that is refused proves that the branch is not written either, so a branch that is dead cannot change anything.

    Why the deadline is short: the branch of this case is given one minute of life, and the case waits for the expiry
    with the clock of the suite and not for an hour (FR-031).

    Why the client is not a context manager: the job of the cleanup runs in the lifespan of the application, and the
    sweep would delete the branch that this case wants to see refused. The branch outlives its deadline here, so the
    answer of the facade is the one of the expiry and not the one of a branch that does not exist any more.
    """
    from fastapi.testclient import TestClient

    from ledgerlens.api.sandbox import create_app

    monkeypatch.setenv(IDLE_TTL_ENV, str(SHORT_IDLE_TTL_SECONDS))
    app = create_app(store=store, base_resolver=base_resolver, clock=clock, runtime_dir=tmp_path)
    client = TestClient(app)
    issued = client.post("/v1/sessions")
    assert issued.status_code == 201
    created = client.post("/v1/sandboxes", json={"scenario_id": scenario_id}).json()

    clock.advance(timedelta(seconds=SHORT_IDLE_TTL_SECONDS * 2))

    read = client.get(f"/v1/sandboxes/{created['id']}")
    mutation = client.post(
        f"/v1/sandboxes/{created['id']}/mutations",
        json={"kind": "refund.apply_fx_adjustment", "data": adjustment_payload},
        headers={"Idempotency-Key": "cmd-0001", "If-Match": "0"},
    )

    assert read.status_code == 410
    assert read.json()["code"] == "BRANCH_EXPIRED"
    assert mutation.status_code == 410
    assert mutation.json()["code"] == "BRANCH_EXPIRED"
    # The refused mutation wrote nothing: a dead branch holds no event at all.
    assert store.read_events(created["id"], canonical_session_id(issued.json()["id"])) == []


# --- the cleanup of the expired branches -------------------------------------------------------------------


def test_the_cleanup_deletes_the_row_the_events_and_the_answers_of_an_expired_branch(
    store: BranchStore,
    base_resolver: BaseResolver,
    clock: FakeClock,
    session_id: str,
    scenario_id: str,
    adjustment: MutationCommand,
) -> None:
    """The cleanup drops the branch with everything it remembers (FR-023).

    Why the events and the answers go with the row: they are the work of the visitor, and a branch that is gone
    must leave nothing behind that another one could read.
    """
    layer = BranchLayer(store, base_resolver, clock=clock)
    forked = layer.fork(session_id, scenario_id).branch
    layer.commit_mutation(session_id, forked.branch_id, adjustment)
    assert store.read_events(forked.branch_id, forked.owner_session)
    assert store.list_commands(forked.branch_id, forked.owner_session)

    before = _digests()
    clock.advance(timedelta(hours=2))
    deleted = cleanup_expired_branches(store, clock=clock)

    assert deleted == [forked.branch_id]
    with pytest.raises(BranchNotFound):
        store.get_branch(forked.branch_id, forked.owner_session)
    with pytest.raises(BranchNotFound):
        store.read_events(forked.branch_id, forked.owner_session)
    with pytest.raises(BranchNotFound):
        store.list_commands(forked.branch_id, forked.owner_session)
    # The published artifacts of the repository are read by the cleanup and never written.
    assert _digests() == before


def test_the_cleanup_leaves_a_branch_that_is_not_expired_alone(
    store: BranchStore, base_resolver: BaseResolver, clock: FakeClock, session_id: str, scenario_id: str
) -> None:
    """A branch that is still alive is not the business of the cleanup.

    Why: the sweep lists the branches whose expiry has passed, and a branch that did not pass the expiry is not in
    the list at all.
    """
    layer = BranchLayer(store, base_resolver, clock=clock)
    forked = layer.fork(session_id, scenario_id).branch

    deleted = cleanup_expired_branches(store, clock=clock)

    assert deleted == []
    assert store.get_branch(forked.branch_id, forked.owner_session).branch_id == forked.branch_id


def test_the_cleanup_does_not_delete_the_branch_of_a_visitor_that_is_still_there(
    store: BranchStore, base_resolver: BaseResolver, clock: FakeClock, session_id: str, scenario_id: str
) -> None:
    """The branch of a visitor that is still there is still served after the sweep.

    Why the promise matters: the cleanup names the owner of every branch it deletes, so the isolation of the owner
    is never bypassed, and a branch that is alive survives the sweep (ADR-029).
    """
    layer = BranchLayer(store, base_resolver, clock=clock)
    forked = layer.fork(session_id, scenario_id).branch

    cleanup_expired_branches(store, clock=clock)

    served = layer.status(session_id, forked.branch_id)
    assert served.branch_id == forked.branch_id
    # The reuse rule still finds it, so the visitor keeps the same branch.
    again = layer.fork(session_id, scenario_id)
    assert again.created is False
    assert again.branch.branch_id == forked.branch_id


def test_a_new_fork_after_the_expiry_starts_at_revision_zero_with_the_hash_of_the_base(
    store: BranchStore,
    base_resolver: BaseResolver,
    clock: FakeClock,
    session_id: str,
    scenario_id: str,
    adjustment: MutationCommand,
) -> None:
    """A visitor that comes back after the expiry gets a fresh branch, at revision zero and with the hash of the base.

    Why the revision is zero and the hash is the one of the base: the work of the expired branch is gone, and the new
    branch is the published case, row for row.
    """
    layer = BranchLayer(store, base_resolver, clock=clock)
    forked = layer.fork(session_id, scenario_id).branch
    layer.commit_mutation(session_id, forked.branch_id, adjustment)

    clock.advance(timedelta(hours=2))
    cleanup_expired_branches(store, clock=clock)

    # The work of the expired branch is gone, and not only hidden.
    with pytest.raises(BranchNotFound):
        store.get_branch(forked.branch_id, forked.owner_session)
    again = layer.fork(session_id, scenario_id)
    assert again.created is True
    assert again.branch.branch_id != forked.branch_id
    assert again.branch.revision == 0
    assert again.branch.current_canonical_hash == forked.base_canonical_hash


def test_the_cleanup_is_safe_to_run_twice(
    store: BranchStore, base_resolver: BaseResolver, clock: FakeClock, session_id: str, scenario_id: str
) -> None:
    """The second sweep finds nothing and raises nothing.

    Why: two workers of the facade may sweep at the same time, and the branch that one of them deleted is already
    gone when the other one reaches it (ADR-029).
    """
    layer = BranchLayer(store, base_resolver, clock=clock)
    forked = layer.fork(session_id, scenario_id).branch
    clock.advance(timedelta(hours=2))

    first = cleanup_expired_branches(store, clock=clock)
    second = cleanup_expired_branches(store, clock=clock)

    assert first == [forked.branch_id]
    assert second == []


# --- the thread of the cleanup ----------------------------------------------------------------------------


def test_the_thread_of_the_cleanup_runs_the_sweep_and_stops_when_it_is_told_to_stop(
    store: BranchStore,
    base_resolver: BaseResolver,
    clock: FakeClock,
    session_id: str,
    scenario_id: str,
) -> None:
    """The thread runs the sweep, it stops when it is told to stop, and it does not keep the process alive.

    Why the thread is a daemon: a process that is killed does not wait for the sweep, and the sweep of a facade that
    is stopped leaves nothing behind (ADR-029).
    """
    layer = BranchLayer(store, base_resolver, clock=clock)
    forked = layer.fork(session_id, scenario_id).branch
    clock.advance(timedelta(hours=2))
    counting = _CountingStore(store)
    worker = CleanupWorker(counting, interval_seconds=0.01, clock=clock)

    worker.start()
    # The event is the signal of the sweep itself, so the test never waits for a race.
    assert counting.swept.wait(timeout=10.0), "the thread of the cleanup did not run the sweep"
    worker.stop()

    assert counting.deleted == [forked.branch_id]
    assert worker.thread is not None
    assert not worker.thread.is_alive()
    assert worker.thread.daemon is True


# --- the command of the cleanup -----------------------------------------------------------------------------


def test_the_command_deletes_the_expired_branches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The command runs the sweep of the cleanup and deletes what it says it deletes (ADR-029).

    Why the command has a test of its own: the command is the second way of cleaning up, and a command that printed
    "0 expired branch(es) deleted" and deleted nothing would keep the promise of the thread and break the promise of
    the deployment that schedules the command. The test therefore watches the STORE and not only the output.

    Why the store of the test is handed to the command: the command opens the store of the configuration, and the
    test needs a store it can look at before and after the sweep.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("cleanup_sandbox", CLEANUP_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    store = FileBranchStore(tmp_path / "store")
    owner = canonical_session_id("Visitor-A")
    expired = SandboxBranchRow(
        branch_id="sb_" + "9" * 24,
        owner_session=owner,
        scenario_id="S01",
        base_snapshot_id="sample-42",
        base_canonical_hash="0" * 64,
        revision=0,
        current_canonical_hash="0" * 64,
        created_at=datetime.now(UTC) - timedelta(hours=5),
        last_activity_at=datetime.now(UTC) - timedelta(hours=5),
        expires_at=datetime.now(UTC) - timedelta(hours=4),
    )
    store.create_branch(expired)
    monkeypatch.setattr(module, "build_branch_store", lambda settings: store)

    code = module.main([])

    assert code == 0
    with pytest.raises(BranchNotFound):
        store.get_branch(expired.branch_id, owner)
    assert "1 expired branch(es) deleted" in capsys.readouterr().out


def test_the_lifespan_of_the_app_starts_the_worker_and_stops_it(
    store: BranchStore, base_resolver: BaseResolver, clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The job of the cleanup runs while the app is up, and it stops when the app goes down (ADR-029).

    Why the test watches the worker and not the clock: the promise is that the facade cleans up by itself, and a
    facade whose lifespan never starts the worker would clean up never, with a green suite. The test therefore counts
    the calls of the worker.

    Why the client is used as a context manager: starlette only sends the lifespan of the app when the client enters
    the context, and that is the only way to see the lifespan at all.
    """
    from fastapi.testclient import TestClient

    from ledgerlens.api import sandbox as sandbox_api

    calls: list[str] = []

    class _Worker:
        """The worker of the cleanup, with its two moments recorded and nothing else."""

        def __init__(self, store: BranchStore, *, clock=None) -> None:
            self.store = store
            self.clock = clock

        def start(self) -> None:
            calls.append("start")

        def stop(self, timeout: float = 5.0) -> None:
            calls.append("stop")

    monkeypatch.setattr(sandbox_api, "CleanupWorker", _Worker)
    app = sandbox_api.create_app(store=store, base_resolver=base_resolver, clock=clock)

    with TestClient(app):
        assert calls == ["start"], "the lifespan of the app did not start the job of the cleanup"

    assert calls == ["start", "stop"], "the lifespan of the app did not stop the job of the cleanup"
