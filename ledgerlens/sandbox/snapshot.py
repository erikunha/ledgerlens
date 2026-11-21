"""The base of a branch: the account scoped copy of the published ledger, and the hash that identifies it.

Why it exists: every visitor of a scenario must start from the same bytes, and the identity of that base has to be
comparable with the identity of a branch. The base is therefore the account scoped copy of the published ledger, cut
with the same deterministic simulation the published replay uses, and its identity is the canonical hash of the
projector, never the hash of the bytes of the file: the bytes move with the layout of SQLite and with the vacuum,
so two branches of the same base could never be compared with them.

The base carries two names, and they mean two different things. The identifier of the published snapshot names the
dataset, as the source and the seed (`sample-42`), and the canonical hash names the account scoped projection the
branch reads. Two visitors of the same scenario report the same pair.

The published files are only ever read. The copy lives in the runtime folder of the process, and the result is cached
for the life of the resolver, because the base is immutable and the simulation is deterministic.
"""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from ledgerlens.api.accounts import scoped_ledger
from ledgerlens.config import get_settings
from ledgerlens.demo import accounts_of, load_manifest
from ledgerlens.sim.config import SimConfig
from ledgerlens.sim.pipeline import build_ledger
from ledgerlens.sim.projector import canonical_hash
from ledgerlens.tools.sql import open_readonly


class UnknownScenario(Exception):
    """The scenario is not one of the published ones. The message names it, because the caller asked for it."""


@dataclass(frozen=True)
class BaseSnapshot:
    """The immutable base of a branch: the scenario, the account, the hash and the file that holds the rows.

    `snapshot_id` names the published snapshot the base was cut from, as the source and the seed of the dataset, and
    `canonical_hash` is the hash of the account scoped projection the branch reads. The two are different things:
    the case is a curated question and the snapshot is the version of the ledger it reads.
    """

    scenario_id: str
    account_id: str
    canonical_hash: str
    db_path: Path
    snapshot_id: str = ""

    @property
    def base_snapshot_id(self) -> str:
        """The identifier of the published snapshot, the one the answer of the facade carries."""
        return self.snapshot_id


class BaseResolver:
    """Resolves the base of a scenario and keeps it for the life of the resolver.

    Why the cache: the simulation is slow and deterministic, and the base is immutable, so one build per scenario is
    enough. Two visitors of the same scenario therefore read the same file and report the same canonical hash.

    The published ledger is built in the working folder of the resolver, which is the runtime folder of the process by
    default, and it is only ever read.
    """

    def __init__(self, work_dir: Path | str | None = None) -> None:
        self.work_dir = Path(work_dir) if work_dir is not None else get_settings().runtime_dir / "sandbox-bases"
        self.config = SimConfig(source="sample")
        self._bases: dict[str, BaseSnapshot] = {}

    @property
    def published_ledger_path(self) -> Path:
        """The published ledger the bases are cut from. It is read and never written."""
        return self.work_dir / "ledger.db"

    @property
    def snapshot_id(self) -> str:
        """The identifier of the published snapshot: the source and the seed of the dataset."""
        return f"{self.config.source}-{self.config.seed}"

    def __call__(self, scenario_id: str) -> BaseSnapshot:
        """The base of the scenario, built once and then kept."""
        base = self._bases.get(scenario_id)
        if base is None:
            base = self._build(scenario_id)
            self._bases[scenario_id] = base
        return base

    def _build(self, scenario_id: str) -> BaseSnapshot:
        self.work_dir.mkdir(parents=True, exist_ok=True)
        ledger = self.published_ledger_path
        if not ledger.exists():
            build_ledger(self.config, ledger).conn.close()
        account_id = self._account_of(scenario_id)
        folder = self.work_dir / scenario_id
        folder.mkdir(parents=True, exist_ok=True)
        scoped = scoped_ledger(ledger, account_id, folder / f"{account_id}.db")
        with closing(open_readonly(scoped)) as conn:
            digest = canonical_hash(conn)
        return BaseSnapshot(
            scenario_id=scenario_id,
            account_id=account_id,
            canonical_hash=digest,
            db_path=scoped,
            snapshot_id=self.snapshot_id,
        )

    def _account_of(self, scenario_id: str) -> str:
        """The account under analysis of the scenario, the first one, the way the published replay takes it."""
        try:
            accounts = accounts_of(load_manifest(), scenario_id)
        except StopIteration:
            raise UnknownScenario(f"the scenario {scenario_id} is not published") from None
        if not accounts:
            raise UnknownScenario(f"the scenario {scenario_id} has no account")
        return accounts[0]


__all__ = ["BaseResolver", "BaseSnapshot", "UnknownScenario"]
