"""The scaffolding of the tests of the database store: the shape of the tables before the generation and the writes
that only a test makes.

Why it exists: the product module of the store holds the SQL of the product, and the helpers that only a test uses
do not belong there. The migration of a database of the old shape has to be tested against a database of the old
shape, and the answer that carries a given moment has to be written with a statement of its own, because the moment
of the commit is the moment of the transaction and two requests committed in the same transaction share it. Keeping
that scaffolding here leaves the two implementations of the protocol with the same public surface (ADR-022).

The rule of the repository still holds: the SQL of the repository lives in the product modules that own it and, for
the things that only a test needs, in the tests themselves.
"""

from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import quote

from ledgerlens.sandbox.store import SandboxCommandRow
from ledgerlens.sim.events import canonical_json

# The shape of the tables of the store before the generation existed. The migration of a database of the old shape
# has to be tested against a database of the old shape, and this is that shape.
OLD_SHAPE_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS sandbox_branches (
        branch_id              text        PRIMARY KEY,
        owner_session          text        NOT NULL,
        scenario_id            text        NOT NULL,
        base_snapshot_id       text        NOT NULL,
        base_canonical_hash    text        NOT NULL,
        revision               integer     NOT NULL DEFAULT 0,
        current_canonical_hash text        NOT NULL,
        created_at             timestamptz NOT NULL,
        last_activity_at       timestamptz NOT NULL,
        expires_at             timestamptz NOT NULL,
        state                  text        NOT NULL DEFAULT 'active'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sandbox_events (
        branch_id    text        NOT NULL REFERENCES sandbox_branches (branch_id) ON DELETE CASCADE,
        event_uid    text        NOT NULL,
        event_type   text        NOT NULL,
        aggregate_id text        NOT NULL,
        occurred_at  text        NOT NULL,
        payload      jsonb       NOT NULL,
        origin       text        NOT NULL DEFAULT 'sandbox',
        command_id   text,
        event_seq    bigint      GENERATED ALWAYS AS IDENTITY,
        appended_at  timestamptz NOT NULL DEFAULT now(),
        CONSTRAINT sandbox_events_pkey PRIMARY KEY (branch_id, event_uid)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sandbox_commands (
        branch_id           text        NOT NULL REFERENCES sandbox_branches (branch_id) ON DELETE CASCADE,
        idempotency_key     text        NOT NULL,
        payload_digest      text        NOT NULL,
        revision            integer     NOT NULL,
        canonical_hash      text        NOT NULL,
        response_diff       jsonb       NOT NULL,
        response_verdict    jsonb       NOT NULL DEFAULT '{}'::jsonb,
        response_invariants jsonb       NOT NULL DEFAULT '[]'::jsonb,
        created_at          timestamptz NOT NULL DEFAULT now(),
        CONSTRAINT sandbox_commands_pkey PRIMARY KEY (branch_id, idempotency_key)
    )
    """,
)


def url_with_search_path(database_url: str, schema_name: str) -> str:
    """The url of the same database with the search path of the connection pointing at one schema.

    Why it exists: the script of the schema applies to the default schema of the connection, so a test that wants
    the script to run over a scratch schema has to point the connection at that schema.
    """
    separator = "&" if "?" in database_url else "?"
    option = quote(f"-csearch_path={_safe_schema_name(schema_name)}", safe="")
    return f"{database_url}{separator}options={option}"


def create_old_shape(database_url: str, schema_name: str) -> None:
    """Creates the tables of the store in the shape they had before the generation existed.

    Why it exists: the script of the schema has to bring a database of the old shape to the shape of the code, and
    the test of that migration needs a database of the old shape to run against. The schema is dropped by the test
    that created it, whatever happens.
    """
    # The driver comes with the `api` extra, so the import is here and not at the top of the module.
    import psycopg

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            # The schema comes first: the tables are created in it, and a table cannot be created in a schema that
            # does not exist.
            cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {_safe_schema_name(schema_name)}")
        connection.commit()
    with psycopg.connect(url_with_search_path(database_url, schema_name)) as connection:
        with connection.cursor() as cursor:
            for statement in OLD_SHAPE_STATEMENTS:
                cursor.execute(statement)
        connection.commit()


def drop_schema(database_url: str, schema_name: str) -> None:
    """Drops one schema of the database and everything it holds.

    Why it exists: the test of the migration works in a scratch schema, and the scratch schema has to go even when
    the test fails.
    """
    # The driver comes with the `api` extra, so the import is here and not at the top of the module.
    import psycopg

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"DROP SCHEMA IF EXISTS {_safe_schema_name(schema_name)} CASCADE")
        connection.commit()


def columns_of(database_url: str, schema_name: str, table_name: str) -> tuple[str, ...]:
    """The names of the columns of one table of one schema of the database.

    Why it exists: the test of the migration asks the database what shape its tables have after the script ran,
    because a script that reports success without migrating is the failure this guards against.
    """
    # The driver comes with the `api` extra, so the import is here and not at the top of the module.
    import psycopg

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT column_name FROM information_schema.columns"
                " WHERE table_schema = %s AND table_name = %s ORDER BY column_name",
                (schema_name, table_name),
            )
            return tuple(str(row[0]) for row in cursor.fetchall())


def write_answer_at(database_url: str, branch_id: str, answer: SandboxCommandRow, created_at: datetime) -> None:
    """Writes one answer of a branch with the moment of its commit given, without moving the row of the branch.

    Why it exists: the moment of the commit is the moment of the transaction, so two requests committed in the same
    transaction share it. The order of the answers cannot be taken from that moment when the moment is shared, and a
    test of that case has to write the moment itself.
    """
    # The driver comes with the `api` extra, so the import is here and not at the top of the module.
    import psycopg

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO sandbox_commands"
                " (branch_id, idempotency_key, payload_digest, revision, canonical_hash, response_diff,"
                " response_verdict, response_invariants, created_at, generation)"
                " VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s)"
                " ON CONFLICT (branch_id, idempotency_key) DO NOTHING",
                (
                    branch_id,
                    answer.idempotency_key,
                    answer.payload_digest,
                    answer.revision,
                    answer.canonical_hash,
                    canonical_json(answer.response_diff),
                    canonical_json(answer.response_verdict),
                    canonical_json(answer.response_invariants),
                    created_at,
                    answer.generation,
                ),
            )
        connection.commit()


def _safe_schema_name(schema_name: str) -> str:
    """A schema name that is one identifier, so that it can be named in a statement.

    Why the check: the name is put in a statement, and a name that is not an identifier would change the statement.
    """
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", schema_name):
        raise ValueError(f"not a usable schema name: {schema_name!r}")
    return schema_name
