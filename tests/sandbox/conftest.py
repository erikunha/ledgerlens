"""The fixtures of the sandbox suite: the published files, the base snapshot, the store, the branch layer and the clock.

Why the published files are hashed when this module is imported: the guard of the immutability of the published
artifacts has to see the state before anything was built and before the first fork. A fixture that builds the base
takes its digest too late, and a guard that is scoped to one module never covers the forks of the other modules.

Why the base is built once: the simulation is slow and deterministic, and the base is immutable, so one build per
test session is enough. Every test then reads the same bytes and the same canonical hash, which is what the isolation
and the immutability tests need.

The store lives in a temporary folder of the test, never in the repository: a test must not leave a branch behind.
The database store lives in the database of the sandbox, and every test starts with a database that holds nothing,
the way the file backed store starts with an empty folder of the test.

The database case is skipped with an explicit reason when the driver or the container is not there. A skip is never
silent, because a suite that quietly stops testing half of the protocol is a suite that lies (ADR-020).
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ledgerlens.sandbox.branch import BranchLayer
from ledgerlens.sandbox.postgres_store import DEFAULT_DATABASE_URL, PostgresBranchStore, apply_schema
from ledgerlens.sandbox.snapshot import BaseResolver, BaseSnapshot
from ledgerlens.sandbox.store import BranchStore, FileBranchStore

SCENARIO_ID = "S01"
OTHER_SCENARIO_ID = "S02"
# The first session has uppercase letters on purpose: the canonical form of the identifier is what names the folder.
SESSION_ID = "Visitor-A"
OTHER_SESSION_ID = "visitor-b"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
# The published artifacts of the repository. The manifest of the scenarios is tracked and the ledger is not, so on a
# fresh checkout the ledger is absent and the guard has to hold in that case as well.
PUBLISHED_FILES = (PROJECT_ROOT / "data" / "scenarios.json", PROJECT_ROOT / "data" / "ledger.db")

# The setting that names the database of the store, and the fallback of the container of `docker-compose.yml`.
DATABASE_URL_ENV = "LEDGERLENS_SANDBOX_DATABASE_URL"

# The tests that read the layout of the store on the disk. The layout is a property of the file backed store alone,
# so the database case of them is skipped with an explicit reason.
FILE_LAYOUT_TESTS = frozenset(
    {
        "test_the_folder_of_one_session_holds_no_branch_of_another_session",
        "test_the_two_sessions_have_two_different_folders",
        "test_the_end_of_the_session_purges_the_branches_of_the_session",
    }
)


def _digest(path: Path) -> str | None:
    """The digest of a published file, or None when the file does not exist."""
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


# The digest of the published files, taken when this module is imported: before any fixture and before any base is
# built. Nothing may move them while the suite runs (FR-001, SC-004).
PUBLISHED_DIGESTS_AT_IMPORT = {path.name: _digest(path) for path in PUBLISHED_FILES}


def _database_url() -> str:
    """The url of the database of the store: the setting first, the container of `docker-compose.yml` otherwise."""
    return os.environ.get(DATABASE_URL_ENV, "").strip() or DEFAULT_DATABASE_URL


def _database_store(root: Path) -> BranchStore:
    """The database store of the contract suite.

    The folder the file backed store would use is not used here: the branches of every test live in the database,
    and the test empties it before it starts.

    Why the skip: a machine without the driver or without the container cannot run this half of the suite. The reason
    is explicit, because a skip that says nothing is a suite that pretends to have tested both implementations.
    """
    url = _database_url()
    if importlib.util.find_spec("psycopg") is None:
        pytest.skip("the driver of the sandbox store is not installed; install the extra 'api'")
    try:
        apply_schema(url)
        store = PostgresBranchStore(url)
        # The database starts empty for every test, the way the folder of the file backed store does.
        store.truncate()
    except Exception as exc:
        pytest.skip(f"the database of the sandbox is not reachable at {url}: {exc}")
    return store


# The implementations of the `BranchStore` protocol that the contract suite runs against. The suite is written once
# and every implementation inherits it, so the two are compared by one suite (FR-040, SC-015).
STORE_IMPLEMENTATIONS: list[tuple[str, Callable[[Path], BranchStore]]] = [
    ("file", lambda root: FileBranchStore(root)),
    ("postgres", _database_store),
]



class FakeClock:
    """A clock the test moves by hand, so that the expiry of a branch can be tested without waiting an hour."""

    def __init__(self, now: datetime | None = None) -> None:
        self.now = now or datetime.now(UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, delta: timedelta) -> None:
        self.now += delta


@pytest.fixture(scope="session", autouse=True)
def the_published_files_stay_the_same() -> Iterator[None]:
    """The published files must be byte identical after the whole suite (FR-001, SC-004).

    A file that was absent at the import of this module must be absent at the end too, and a file that was there
    must have the same digest.
    """
    yield
    now = {path.name: _digest(path) for path in PUBLISHED_FILES}
    assert now == PUBLISHED_DIGESTS_AT_IMPORT, "the sandbox wrote to a published artifact"


@pytest.fixture(scope="session")
def published_digests() -> dict[str, str | None]:
    """The digest of the published files, taken when this module was imported."""
    return dict(PUBLISHED_DIGESTS_AT_IMPORT)


@pytest.fixture(scope="session")
def base_resolver(tmp_path_factory: pytest.TempPathFactory) -> BaseResolver:
    """The resolver of the immutable base, with its own working folder outside the repository."""
    return BaseResolver(tmp_path_factory.mktemp("sandbox_base"))


@pytest.fixture(scope="session")
def published_ledger(base_resolver: BaseResolver) -> Path:
    """The published ledger the base is cut from. It is read and never written."""
    base_resolver(SCENARIO_ID)
    return base_resolver.published_ledger_path


@pytest.fixture(scope="session")
def base_snapshot(base_resolver: BaseResolver) -> BaseSnapshot:
    """The base of the scenario S01, built once for the whole test session."""
    return base_resolver(SCENARIO_ID)


@pytest.fixture(params=STORE_IMPLEMENTATIONS, ids=[name for name, _ in STORE_IMPLEMENTATIONS])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[BranchStore]:
    """The branch store of the contract suite, once for every implementation of the protocol."""
    _, factory = request.param
    implementation = factory(tmp_path / "sandbox")
    yield implementation
    close = getattr(implementation, "close", None)
    if callable(close):
        close()


@pytest.fixture
def file_store(tmp_path: Path) -> BranchStore:
    """The file backed store alone, for the test that compares the two implementations."""
    return FileBranchStore(tmp_path / "sandbox_file")


@pytest.fixture
def database_store(tmp_path: Path) -> Iterator[BranchStore]:
    """The database store alone, for the test that compares the two implementations."""
    implementation = _database_store(tmp_path / "sandbox_database")
    yield implementation
    close = getattr(implementation, "close", None)
    if callable(close):
        close()


@pytest.fixture
def clock() -> FakeClock:
    """The clock of the layer and of the facade, moved by hand."""
    return FakeClock()


@pytest.fixture
def layer(store: BranchStore, base_resolver: BaseResolver, clock: FakeClock) -> BranchLayer:
    """The branch layer over the store and the shared base."""
    return BranchLayer(store, base_resolver, clock=clock)


@pytest.fixture
def session_id() -> str:
    return SESSION_ID


@pytest.fixture
def other_session_id() -> str:
    return OTHER_SESSION_ID


@pytest.fixture
def scenario_id() -> str:
    return SCENARIO_ID


@pytest.fixture
def other_scenario_id() -> str:
    return OTHER_SCENARIO_ID


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Skips the tests that read the layout of the store on the disk when the store is not the file backed one.

    Why: the layout on the disk is a property of the file backed store, and a test that reads it says nothing about
    the database one. The reason of the skip is explicit, so the report of the suite shows what did not run.
    """
    for item in items:
        name, _, parameter = item.name.partition("[")
        if name not in FILE_LAYOUT_TESTS or not parameter:
            continue
        implementation = parameter.rstrip("]")
        if implementation == "file":
            continue
        item.add_marker(
            pytest.mark.skip(
                reason=f"the layout on the disk belongs to the file backed store, not to the {implementation} one"
            )
        )
