"""The branch store over Postgres: the second implementation of the `BranchStore` protocol.

Why it exists: ADR-020 put the branch data of the deployment in Postgres, so that the branches of every visitor live
in one database and the isolation is a condition of the query and not a folder on the disk. The file backed store
stays the one the fast unit tests use and the one that runs when no database is configured.

What this module guarantees, and what the contract suite proves:

* every method that names a branch also names the owner session, and the owner is a condition of the query: the row
  of another visitor is never read from the database;
* the refusal of a branch of another visitor is the same error as the refusal of a branch that does not exist, so
  nothing about the existence of a branch leaks;
* the append is idempotent on the uid of the event, because the unique key on `(branch_id, event_uid)` is in the
  schema of `schema.sql`;
* the payload of an event is written with the canonical serialisation of `ledgerlens.sim.events`, so the same event
  has the same bytes in both stores.

The store writes no domain rule and decides nothing: the fork, the owner check, the reuse rule and the expiry live in
`ledgerlens/sandbox/branch.py`.

The driver is imported inside the methods, and not at the top of the module, so that a machine without the `api`
extra can still import the package of the sandbox.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from ledgerlens.sandbox.store import BranchNotFound, SandboxBranchRow, SandboxEventRow, _safe_name
from ledgerlens.sim.events import AppendResult, canonical_json

# The schema of the store, versioned with the code. The script `scripts/apply_sandbox_schema.py` applies it.
SCHEMA_PATH = Path(__file__).with_name("schema.sql")

# The tables of the store, in the order of the dependency between them.
SCHEMA_TABLES = ("sandbox_branches", "sandbox_events", "sandbox_commands")

# The url of the container of `docker-compose.yml`. It is the fallback of the setting of the database url, so that
# the schema script and the suite of the store work on a machine with the container up and nothing else.
DEFAULT_DATABASE_URL = "postgresql://ledgerlens@127.0.0.1:5433/ledgerlens_sandbox"

# The columns of a branch, in the order the queries read them.
BRANCH_COLUMNS = (
    "branch_id",
    "owner_session",
    "scenario_id",
    "base_snapshot_id",
    "base_canonical_hash",
    "revision",
    "current_canonical_hash",
    "created_at",
    "last_activity_at",
    "expires_at",
    "state",
)

# The columns of an event, in the order the queries read them.
EVENT_COLUMNS = (
    "event_uid",
    "branch_id",
    "event_type",
    "aggregate_id",
    "occurred_at",
    "payload",
    "origin",
    "command_id",
)


class PostgresBranchStore:
    """The branch store over a Postgres database.

    The connection opens with the first operation and stays open for the life of the store, so a machine without the
    driver can still import this module and a test can decide to skip before the first call.
    """

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self._connection: Any = None

    # -- the branches ------------------------------------------------------------------------------

    def create_branch(self, branch: SandboxBranchRow) -> SandboxBranchRow:
        """Stores a new branch and returns it.

        The owner session is checked with the same guard as the file backed store, so the two implementations refuse
        the same names.
        """
        _safe_name(branch.owner_session)
        try:
            self._run(
                "INSERT INTO sandbox_branches ("
                "branch_id, owner_session, scenario_id, base_snapshot_id, base_canonical_hash, revision,"
                "current_canonical_hash, created_at, last_activity_at, expires_at, state"
                ") VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    branch.branch_id,
                    branch.owner_session,
                    branch.scenario_id,
                    branch.base_snapshot_id,
                    branch.base_canonical_hash,
                    branch.revision,
                    branch.current_canonical_hash,
                    branch.created_at,
                    branch.last_activity_at,
                    branch.expires_at,
                    branch.state,
                ),
            )
        except Exception as exc:
            if _unique_violation(exc):
                raise ValueError(f"the branch {branch.branch_id} already exists") from None
            raise
        return branch

    def get_branch(self, branch_id: str, owner_session: str) -> SandboxBranchRow:
        """The branch of this session. Raises `BranchNotFound` when it is not there or not its own.

        Why the owner is in the condition of the query and not in a comparison after the read: the row of another
        visitor must never leave the database.
        """
        _safe_name(owner_session)
        rows, _ = self._run(
            f"SELECT {', '.join(BRANCH_COLUMNS)} FROM sandbox_branches"
            " WHERE branch_id = %s AND owner_session = %s",
            (branch_id, owner_session),
        )
        if not rows:
            raise BranchNotFound()
        return _branch_from_record(rows[0])

    def list_branches(self, owner_session: str) -> list[SandboxBranchRow]:
        """Every branch of this session, in the order of the store."""
        _safe_name(owner_session)
        rows, _ = self._run(
            f"SELECT {', '.join(BRANCH_COLUMNS)} FROM sandbox_branches"
            " WHERE owner_session = %s ORDER BY created_at, branch_id",
            (owner_session,),
        )
        return [_branch_from_record(record) for record in rows]

    def save_branch(self, branch: SandboxBranchRow) -> SandboxBranchRow:
        """Stores the row of a branch of this session again.

        The owner never changes: the branch is found by its identifier and by its owner, and a branch of another
        visitor is not touched.
        """
        _safe_name(branch.owner_session)
        _, touched = self._run(
            "UPDATE sandbox_branches SET scenario_id = %s, base_snapshot_id = %s, base_canonical_hash = %s,"
            " revision = %s, current_canonical_hash = %s, created_at = %s, last_activity_at = %s, expires_at = %s,"
            " state = %s WHERE branch_id = %s AND owner_session = %s",
            (
                branch.scenario_id,
                branch.base_snapshot_id,
                branch.base_canonical_hash,
                branch.revision,
                branch.current_canonical_hash,
                branch.created_at,
                branch.last_activity_at,
                branch.expires_at,
                branch.state,
                branch.branch_id,
                branch.owner_session,
            ),
        )
        if not touched:
            raise BranchNotFound()
        return branch

    def delete_branch(self, branch_id: str, owner_session: str) -> bool:
        """Drops the branch and its events. Raises `BranchNotFound` when it is not there or not its own."""
        _safe_name(owner_session)
        _, touched = self._run(
            "DELETE FROM sandbox_branches WHERE branch_id = %s AND owner_session = %s",
            (branch_id, owner_session),
        )
        if not touched:
            raise BranchNotFound()
        # The events of the branch go with it: the key of the table of the events refers to the branch.
        return True

    def list_expired(self, now: datetime) -> list[SandboxBranchRow]:
        """Every branch whose expiry has passed, whatever its owner. The cleanup job uses it."""
        rows, _ = self._run(
            f"SELECT {', '.join(BRANCH_COLUMNS)} FROM sandbox_branches WHERE expires_at <= %s"
            " ORDER BY expires_at, branch_id",
            (now,),
        )
        return [_branch_from_record(record) for record in rows]

    # -- the events --------------------------------------------------------------------------------

    def append_events(self, branch_id: str, owner_session: str, events: Sequence[SandboxEventRow]) -> AppendResult:
        """Appends events to the branch. The append is idempotent on the uid of the event.

        The idempotence is in the database: the insert refuses the event whose key is already there, and the count of
        the rows that were not refused is the count of the appended ones.
        """
        _safe_name(owner_session)
        self._require_branch(branch_id, owner_session)
        if not events:
            return AppendResult(0, 0)
        for event in events:
            if event.branch_id != branch_id:
                raise ValueError(f"the event {event.event_uid} does not belong to the branch {branch_id}")
        values = []
        for event in events:
            values.append(
                (
                    event.branch_id,
                    event.event_uid,
                    event.event_type,
                    event.aggregate_id,
                    event.occurred_at,
                    # The canonical serialisation, so that the same event has the same bytes in both stores.
                    canonical_json(event.payload),
                    event.origin,
                    event.command_id,
                )
            )
        placeholders = ", ".join(["(%s, %s, %s, %s, %s, %s::jsonb, %s, %s)"] * len(values))
        _, appended = self._run(
            "INSERT INTO sandbox_events"
            " (branch_id, event_uid, event_type, aggregate_id, occurred_at, payload, origin, command_id)"
            f" VALUES {placeholders} ON CONFLICT (branch_id, event_uid) DO NOTHING",
            [value for row in values for value in row],
        )
        return AppendResult(appended, len(events) - appended)

    def read_events(self, branch_id: str, owner_session: str) -> list[SandboxEventRow]:
        """The events of the branch of this session, in the order they were appended."""
        _safe_name(owner_session)
        self._require_branch(branch_id, owner_session)
        rows, _ = self._run(
            f"SELECT {', '.join(EVENT_COLUMNS)} FROM sandbox_events WHERE branch_id = %s ORDER BY event_seq",
            (branch_id,),
        )
        return [_event_from_record(record) for record in rows]

    def delete_events(self, branch_id: str, owner_session: str) -> int:
        """Drops every event of the branch and returns how many were dropped."""
        _safe_name(owner_session)
        self._require_branch(branch_id, owner_session)
        _, dropped = self._run("DELETE FROM sandbox_events WHERE branch_id = %s", (branch_id,))
        return dropped

    # -- the maintenance ---------------------------------------------------------------------------

    def truncate(self) -> None:
        """Drops every row of the tables of the store.

        Why it exists: a test needs a database that holds nothing before it starts, and the cleanup of a deployment
        needs the same thing. It decides nothing about a branch, so it is not a domain rule.
        """
        self._run("TRUNCATE sandbox_events, sandbox_commands, sandbox_branches RESTART IDENTITY CASCADE")

    def close(self) -> None:
        """Closes the connection of the store, when there is one."""
        if self._connection is not None and not self._connection.closed:
            self._connection.close()

    # -- the internals -----------------------------------------------------------------------------

    def _connect(self) -> Any:
        """The connection of the store, opened with the first call that needs it."""
        if self._connection is None or self._connection.closed:
            # The driver comes with the `api` extra, so the import is here and not at the top of the module.
            import psycopg

            self._connection = psycopg.connect(self.database_url)
            with self._connection.cursor() as cursor:
                # The moments of the store are read and written in UTC, so the answer of a read does not depend on
                # the time zone of the server.
                cursor.execute("SET TIME ZONE 'UTC'")
            self._connection.commit()
        return self._connection

    def _run(self, sql: str, params: Sequence[Any] = ()) -> tuple[list[tuple[Any, ...]], int]:
        """Runs one statement, commits it, and returns the rows it read and the number of rows it touched."""
        connection = self._connect()
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall() if cursor.description is not None else []
            touched = cursor.rowcount
        connection.commit()
        return rows, touched

    def _require_branch(self, branch_id: str, owner_session: str) -> None:
        """Checks that the branch is there and that it belongs to this session.

        Why the owner is in the condition of the query: the branch of another visitor is not even read.
        """
        rows, _ = self._run(
            "SELECT 1 FROM sandbox_branches WHERE branch_id = %s AND owner_session = %s",
            (branch_id, owner_session),
        )
        if not rows:
            raise BranchNotFound()


def _unique_violation(error: Exception) -> bool:
    """True when the error of the driver is the refusal of a unique key.

    Why the name and not the class: the driver is an optional import, so the class of its error cannot be named at
    the top of the module.
    """
    return type(error).__name__ == "UniqueViolation"


def apply_schema(database_url: str | None = None) -> tuple[str, ...]:
    """Applies the schema of the store to the database and returns the tables that are there.

    Why it is safe to run twice: every statement of the schema carries `IF NOT EXISTS`, so a database that already has
    the shape is left as it is.
    """
    url = database_url or DEFAULT_DATABASE_URL
    # The driver comes with the `api` extra, so the import is here and not at the top of the module.
    import psycopg

    with psycopg.connect(url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
        connection.commit()
    return SCHEMA_TABLES


def _branch_from_record(record: Sequence[Any]) -> SandboxBranchRow:
    return SandboxBranchRow(
        branch_id=record[0],
        owner_session=record[1],
        scenario_id=record[2],
        base_snapshot_id=record[3],
        base_canonical_hash=record[4],
        revision=int(record[5]),
        current_canonical_hash=record[6],
        created_at=record[7],
        last_activity_at=record[8],
        expires_at=record[9],
        state=record[10],
    )


def _event_from_record(record: Sequence[Any]) -> SandboxEventRow:
    return SandboxEventRow(
        event_uid=record[0],
        branch_id=record[1],
        event_type=record[2],
        aggregate_id=record[3],
        occurred_at=record[4],
        payload=record[5],
        origin=record[6],
        command_id=record[7],
    )


__all__ = [
    "BRANCH_COLUMNS",
    "DEFAULT_DATABASE_URL",
    "EVENT_COLUMNS",
    "PostgresBranchStore",
    "SCHEMA_PATH",
    "SCHEMA_TABLES",
    "apply_schema",
]
