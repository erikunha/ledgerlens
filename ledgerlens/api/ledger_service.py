"""The internal ledger API: reading a record by id, with no route that writes.

Why it exists: the agent looks at the ledger in two ways. `query_ledger` writes SQL (flexible, goes through
a guard); `get_ledger_record` asks this service for a record by id (fixed contract, no SQL generated
by a model). It is the "internal service" kind in the tool catalog (`docs/tools.md`).

Routes (all `GET`)::

    /transactions/{id}                     the transaction with refunds, chargebacks and applied FX
    /settlements/{id}                      a payout by its own id
    /merchants/{id}/settlements?from&to    the merchant's payouts, optionally within a period
    /webhooks/replay?aggregate_id=...      a record's events, in order, as webhook bodies
    /health                                {"status": "ok", "events": <total>}

Protections: the SQLite file opens in `mode=ro` on each request (SQLite itself refuses writes and does not
create the file); no route accepts `POST`, `PUT`, `PATCH` or `DELETE` (FastAPI answers 405); ids
are validated against a pattern before reaching the SQL, and every query uses parameters. The replay only reads
and returns: nothing is delivered to anyone.

Needs the `api` extra (`fastapi`, `uvicorn`). To start the service: `ledgerlens-api --port 8000`.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections.abc import Sequence
from contextlib import closing
from datetime import date
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, HTTPException, Query
from fastapi import Path as PathParam

from ledgerlens.config import get_settings
from ledgerlens.tools.sql import open_readonly

TX_ID = r"^TX-[0-9]{4}$"
SETTLEMENT_ID = r"^ST-[0-9]{4}$"
MERCHANT_ID = r"^M-[0-9]{2}$"
AGGREGATE_ID = r"^(TX|R|CB|ST)-[0-9]{4}$|^M-[0-9]{2}$|^C-[0-9]{4}$"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def open_ledger(db_path: Path | str) -> sqlite3.Connection:
    """Opens the ledger read-only, with rows accessible by column name."""
    conn = open_readonly(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _rows(conn: sqlite3.Connection, sql: str, *params: Any) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def create_app(db_path: Path | str | None = None) -> FastAPI:
    """Builds the app. Without `db_path`, the database is the one in `LEDGERLENS_LEDGER_DB`, read on each request."""
    app = FastAPI(title="LedgerLens ledger service", description="Read-only access to the payments ledger.")

    def connect() -> sqlite3.Connection:
        path = Path(db_path) if db_path is not None else get_settings().ledger_db
        try:
            return open_ledger(path)
        except sqlite3.Error as exc:
            detail = f"the ledger database cannot be opened read-only: {exc}"
            raise HTTPException(status_code=503, detail=detail) from None

    @app.get("/transactions/{transaction_id}")
    def transaction(transaction_id: Annotated[str, PathParam(pattern=TX_ID)]) -> dict[str, Any]:
        with closing(connect()) as conn:
            rows = _rows(conn, "SELECT * FROM transactions WHERE id = ?", transaction_id)
            if not rows:
                raise HTTPException(status_code=404, detail=f"no transaction {transaction_id}")
            return {
                "transaction": rows[0],
                "refunds": _rows(
                    conn, "SELECT * FROM refunds WHERE transaction_id = ? ORDER BY created_at, id", transaction_id
                ),
                "chargebacks": _rows(
                    conn, "SELECT * FROM chargebacks WHERE transaction_id = ? ORDER BY opened_at, id", transaction_id
                ),
                "fx_applied": _rows(
                    conn, "SELECT * FROM fx_applied WHERE transaction_id = ? ORDER BY applied_at, id", transaction_id
                ),
            }

    @app.get("/settlements/{settlement_id}")
    def settlement(settlement_id: Annotated[str, PathParam(pattern=SETTLEMENT_ID)]) -> dict[str, Any]:
        with closing(connect()) as conn:
            rows = _rows(conn, "SELECT * FROM settlements WHERE id = ?", settlement_id)
            if not rows:
                raise HTTPException(status_code=404, detail=f"no settlement {settlement_id}")
            return {"settlement": rows[0]}

    @app.get("/merchants/{merchant_id}/settlements")
    def settlements(
        merchant_id: Annotated[str, PathParam(pattern=MERCHANT_ID)],
        date_from: Annotated[date | None, Query(alias="from")] = None,
        date_to: Annotated[date | None, Query(alias="to")] = None,
    ) -> dict[str, Any]:
        # With a period, the payouts that overlap it come in (ending after the start and starting before the end).
        with closing(connect()) as conn:
            if not _rows(conn, "SELECT 1 FROM merchants WHERE id = ?", merchant_id):
                raise HTTPException(status_code=404, detail=f"no merchant {merchant_id}")
            sql, params = "SELECT * FROM settlements WHERE merchant_id = ?", [merchant_id]
            if date_from is not None:
                sql, params = sql + " AND period_end >= ?", [*params, date_from.isoformat()]
            if date_to is not None:
                sql, params = sql + " AND period_start <= ?", [*params, date_to.isoformat()]
            return {"merchant_id": merchant_id, "settlements": _rows(conn, sql + " ORDER BY period_start, id", *params)}

    @app.get("/webhooks/replay")
    def replay(aggregate_id: Annotated[str, Query(pattern=AGGREGATE_ID)]) -> dict[str, Any]:
        with closing(connect()) as conn:
            events = _rows(
                conn,
                "SELECT event_id, type, occurred_at, payload FROM events WHERE aggregate_id = ? ORDER BY event_id",
                aggregate_id,
            )
        if not events:
            raise HTTPException(status_code=404, detail=f"no events for {aggregate_id}")
        return {"aggregate_id": aggregate_id, "events": [{**e, "payload": json.loads(e["payload"])} for e in events]}

    @app.get("/health")
    def health() -> dict[str, Any]:
        with closing(connect()) as conn:
            return {"status": "ok", "events": conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]}

    return app


def _serve(app: Any, *, host: str, port: int) -> None:
    import uvicorn

    uvicorn.run(app, host=host, port=port)


def main(argv: Sequence[str] | None = None) -> None:
    """The `ledgerlens-api` command."""
    parser = argparse.ArgumentParser(prog="ledgerlens-api", description="Serve the read-only ledger API.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    _serve(create_app(), host=args.host, port=args.port)
