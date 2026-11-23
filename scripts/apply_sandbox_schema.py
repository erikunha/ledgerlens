#!/usr/bin/env python3
"""Applies the schema of the store of the sandbox to the configured database.

Why it exists: the shape of the data of the branches travels with the code, in `ledgerlens/sandbox/schema.sql`, and a
deployment has to be able to bring its database to that shape with one command. The command is safe to run twice:
every statement of the schema carries `IF NOT EXISTS`, so a database that already has the shape is left as it is.

Where the database comes from: the setting `LEDGERLENS_SANDBOX_DATABASE_URL`, and the container of
`docker-compose.yml` when the setting is empty. The script needs no key and no network beyond the local container.

What it prints: the database it applied the schema to and the tables that are there. The exit code is 0 when the
schema was applied and 1 when it was not.

Usage:

    uv run python scripts/apply_sandbox_schema.py [--database-url URL]
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from ledgerlens.config import get_settings
from ledgerlens.sandbox.postgres_store import DEFAULT_DATABASE_URL, apply_schema


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Applies the schema of the sandbox store to the database.")
    parser.add_argument(
        "--database-url",
        default=None,
        help="url of the database (or use LEDGERLENS_SANDBOX_DATABASE_URL, or the container of docker-compose.yml)",
    )
    args = parser.parse_args(argv)

    url = args.database_url or get_settings().sandbox_database_url or DEFAULT_DATABASE_URL
    try:
        tables = apply_schema(url)
    except Exception as exc:
        print(f"apply_sandbox_schema: the schema was not applied: {exc}", file=sys.stderr)
        return 1

    print(f"schema applied to {url}")
    print("tables: " + ", ".join(tables))
    return 0


if __name__ == "__main__":
    sys.exit(main())
