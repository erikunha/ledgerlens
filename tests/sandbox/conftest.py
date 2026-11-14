"""The fixtures of the sandbox suite: the published files, the base snapshot, the store, the branch layer and the clock.

Why the published files are hashed when this module is imported: the guard of the immutability of the published
artifacts has to see the state before anything was built and before the first fork. A fixture that builds the base
takes its digest too late, and a guard that is scoped to one module never covers the forks of the other modules.

Why the base is built once: the simulation is slow and deterministic, and the base is immutable, so one build per
test session is enough. Every test then reads the same bytes and the same canonical hash, which is what the isolation
and the immutability tests need.

The store lives in a temporary folder of the test, never in the repository: a test must not leave a branch behind.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ledgerlens.sandbox.branch import BranchLayer
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


def _digest(path: Path) -> str | None:
    """The digest of a published file, or None when the file does not exist."""
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


# The digest of the published files, taken when this module is imported: before any fixture and before any base is
# built. Nothing may move them while the suite runs (FR-001, SC-004).
PUBLISHED_DIGESTS_AT_IMPORT = {path.name: _digest(path) for path in PUBLISHED_FILES}

# The implementations of the `BranchStore` protocol that the contract suite runs against. The database one joins this
# list in the milestone that adds it, and it inherits the whole suite with no change to the tests.
STORE_IMPLEMENTATIONS: list[tuple[str, Callable[[Path], BranchStore]]] = [
    ("file", lambda root: FileBranchStore(root)),
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
def store(request: pytest.FixtureRequest, tmp_path: Path) -> BranchStore:
    """The branch store of the contract suite, once for every implementation of the protocol."""
    _, factory = request.param
    return factory(tmp_path / "sandbox")


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
