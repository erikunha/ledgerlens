"""`query_ledger`: the tool that answers questions about payments with a SQL query.

Why it exists: the agent needs ledger facts (a transaction's status, refunds, chargebacks,
settlements, applied rates) and the most flexible way to ask for them is natural language. The tool
uses a chat model to write the SQL, but never trusts it. The path of a call::

    question
      -> opens the database READ-ONLY (layer 2; with no file, DB_UNAVAILABLE)
      -> the model writes the SQL (the prompt carries the columns read from the database itself)
      -> the guard in `sql_guard.py` checks and rewrites it (layer 1; a refusal becomes SQL_REJECTED)
      -> runs it with a time limit (layer 3; running over becomes SQL_TIMEOUT)
      -> returns columns, rows and the SQL that ran

Text that is not SQL, SQL that does not read and a database error (a column that does not exist) get a single
repair: the model gets the reason and tries again. If it fails again, the error is SQL_GENERATION_FAILED. A
guard refusal is not repaired: the agent gets the broken rule as data and decides.

Money: the ledger keeps amounts in minor units (`54931` is 549.31). A language model read that number
in major units ("54,931.00 BRL"), so every `<name>_minor` column comes back with `<name>_major`, the same value in
major units as text with two places (`"549.31"`), computed here with `Decimal`. The model never converts. The
`_minor` columns stay in the output, because the verifier checks numbers and coherence on them.

What the tool returns is always a dictionary in the common format of `docs/contracts/tools.md`
(`ok`, `evidence_ids`, `data` or `ok`, `error`). An error is data, not an exception, so the agent can
reason about it. Rows come back as data: a refund reason that says "ignore the
instructions" is text to be reported, never an order.
"""

from __future__ import annotations

import itertools
import logging
import re
import sqlite3
import time
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ConfigDict, Field

from ledgerlens.config import get_chat_model, get_settings
from ledgerlens.tools.envelope import error, invalid_input, ok
from ledgerlens.tools.sql_guard import ALLOWED_TABLES, DEFAULT_MAX_ROWS, SqlRejected, guard_sql

log = logging.getLogger(__name__)

TIMEOUT_SECONDS = 2.0
# SQLite calls the progress hook every so many instructions of its virtual machine. 1000 is fine
# enough for the 2 s limit to hold and coarse enough not to weigh on the query.
PROGRESS_STEP = 1000

DESCRIPTION = (
    "Answer a question about payments data by running one read-only SQL query on the ledger database. "
    "Use it for transactions, refunds, chargebacks, settlements and the exchange rates the acquirer applied. "
    'Pass the question in plain English with any ids you know (for example "refunds for TX-2048"). '
    "Amounts come back in minor units (10000 means 100.00), and every column ending in _minor is followed by a "
    "column ending in _major with the same amount in major units: report the _major value, never the _minor one "
    "as money. Do not use it for policy rules (use search_policies) or for market exchange rates "
    "(use get_reference_fx). It cannot change data."
)

SYSTEM_PROMPT = """You write one SQLite SELECT statement that answers a question about a payments ledger.

Rules:
- Reply with the SQL only, no explanation.
- Use only the tables and columns listed below. Do not use any other table.
- Amounts are integers in minor units (10000 means 100.00). Exchange rates (applied_rate) are text.
- Select the currency column next to every amount (currency, requested_currency or payout_currency). Give a
  sum, average or other computed amount an alias that ends in _minor, for example SUM(amount_minor) AS total_minor.
- Dates and times are ISO 8601 UTC text (for example 2026-10-20T14:30:00Z).
- Ids look like TX-2048 (transaction), R-0731 (refund), CB-0310 (chargeback), ST-0001 (settlement),
  M-17 (merchant), C-0291 (customer), FX-9002 (applied rate). Match them exactly.
- transactions.status is one of authorized, captured, failed, refunded, partially_refunded, disputed,
  charged_back. refunds.status is requested, paid or rejected. chargebacks.stage is opened,
  evidence_requested, evidence_submitted, won or lost. fx_applied.kind is charge or refund.
- Do the filtering and joining in SQL. Do not try to do money arithmetic beyond sums and counts.

Tables and columns:
{schema}"""

REPAIR_PROMPT = "That did not work: {problem}\nReply again with one corrected SQLite SELECT statement and nothing else."

# The first word of any SQL statement. An answer that does not start with one of them is not SQL (the
# model explained instead of answering) and goes to the repair. A DELETE, on the other hand, is SQL and goes to
# the guard.
_SQL_KEYWORDS = frozenset(
    "select with values insert update delete replace drop create alter pragma attach detach vacuum "
    "explain reindex analyze begin commit rollback savepoint release".split()
)
_FENCE = re.compile(r"```(?:sql)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


class QueryLedgerInput(BaseModel):
    """Tool input: validated before any work."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=3, max_length=500)
    max_rows: int = Field(default=DEFAULT_MAX_ROWS, ge=1, le=200)


_MINOR_SUFFIX = "_minor"
_CENT = Decimal("0.01")


def major_amount(minor: Any) -> str | None:
    """A minor-unit value as major-unit text (`54931` becomes `"549.31"`), or `None`.

    Every ledger currency has two decimal places. Only a number becomes a value: `None`, text and booleans do not.
    An average (float) rounds half to even, like `calculate`.
    """
    if isinstance(minor, bool) or not isinstance(minor, (int, float)):
        return None
    return str((Decimal(str(minor)) / 100).quantize(_CENT, ROUND_HALF_EVEN))


def with_major_units(columns: list[str], rows: list[list[Any]]) -> tuple[list[str], list[list[Any]]]:
    """Puts, right after each `x_minor` column, the `x_major` column with the same value in major units."""
    if not any(c.endswith(_MINOR_SUFFIX) for c in columns):
        return columns, rows
    out_columns: list[str] = []
    for column in columns:
        out_columns.append(column)
        if column.endswith(_MINOR_SUFFIX):
            out_columns.append(column.removesuffix(_MINOR_SUFFIX) + "_major")
    out_rows = []
    for row in rows:
        out_row: list[Any] = []
        for column, value in zip(columns, row, strict=True):
            out_row.append(value)
            if column.endswith(_MINOR_SUFFIX):
                out_row.append(major_amount(value))
        out_rows.append(out_row)
    return out_columns, out_rows


def add_major_units(node: Any) -> Any:
    """The same for a JSON record: each `x_minor` key gets `x_major` beside it, at any depth."""
    if isinstance(node, list):
        return [add_major_units(item) for item in node]
    if not isinstance(node, dict):
        return node
    out: dict[str, Any] = {}
    for key, value in node.items():
        out[key] = add_major_units(value)
        if key.endswith(_MINOR_SUFFIX):
            out[key.removesuffix(_MINOR_SUFFIX) + "_major"] = major_amount(value)
    return out


class _Timeout(Exception):
    """The query went over the time limit and was interrupted."""


def open_readonly(db_path: str | Path) -> sqlite3.Connection:
    """Opens the database with `mode=ro`: SQLite itself refuses INSERT, UPDATE and DROP and does not create the file."""
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _schema_text(conn: sqlite3.Connection) -> str:
    """The columns of the allowed tables, read from the database: the prompt never lags behind the schema."""
    lines = []
    for table in sorted(ALLOWED_TABLES):
        columns = conn.execute(f"PRAGMA table_info({table})").fetchall()
        lines.append(f"{table}({', '.join(f'{c[1]} {c[2]}' for c in columns)})")
    return "\n".join(lines)


def _extract_sql(reply: str) -> str | None:
    """The SQL in the model's answer (inside ``` if there is a fence), or None if it does not look like SQL."""
    fenced = _FENCE.search(reply)
    text = (fenced.group(1) if fenced else reply).strip()
    first = re.match(r"\s*\(?\s*([A-Za-z]+)", text)
    if first is None or first.group(1).lower() not in _SQL_KEYWORDS:
        return None
    return text


def _run_with_timeout(conn: sqlite3.Connection, sql: str, limit: int, timeout_s: float):
    """Runs and reads up to `limit` rows; past the deadline, the progress hook interrupts it."""
    deadline = time.monotonic() + timeout_s
    state = {"timed_out": False}

    def stop_when_late() -> int:
        if time.monotonic() > deadline:
            state["timed_out"] = True
            return 1  # any value other than zero interrupts the query
        return 0

    conn.set_progress_handler(stop_when_late, PROGRESS_STEP)
    try:
        cursor = conn.execute(sql)
        columns = [d[0] for d in cursor.description]
        rows = cursor.fetchmany(limit)
    except sqlite3.OperationalError:
        if state["timed_out"]:
            raise _Timeout from None
        raise
    finally:
        conn.set_progress_handler(None, 0)
    return columns, rows


def run_query_ledger(
    question: str,
    max_rows: int,
    *,
    model: BaseChatModel,
    db_path: str | Path,
    timeout_s: float,
    evidence_id: Any,
) -> dict[str, Any]:
    """A full call. `evidence_id` is called only on success, to number `sql:<n>`."""
    try:
        conn = open_readonly(db_path)
    except sqlite3.Error as exc:
        return error("DB_UNAVAILABLE", f"the ledger database cannot be opened read-only: {exc}", False)

    try:
        messages: list[BaseMessage] = [
            SystemMessage(SYSTEM_PROMPT.format(schema=_schema_text(conn))),
            HumanMessage(question),
        ]
        for attempt in (1, 2):
            reply = str(model.invoke(messages).content)
            problem = None
            sql = _extract_sql(reply)
            if sql is None:
                problem = "the reply did not contain an SQL statement"
            else:
                try:
                    # Two versions of the same SQL: the one that runs asks for one more row, only to know if
                    # there was a cut; the one that goes back to the model shows the limit it asked for.
                    to_run = guard_sql(sql, max_rows=max_rows + 1)
                    shown = guard_sql(sql, max_rows=max_rows)
                except SqlRejected as rejection:
                    if rejection.rule not in ("syntax", "empty"):
                        log.warning("query_ledger rejected (%s): %s | sql=%r", rejection.rule, rejection, sql)
                        return error("SQL_REJECTED", f"{rejection.rule}: {rejection}", True)
                    problem = str(rejection)
                else:
                    try:
                        columns, rows = _run_with_timeout(conn, to_run, max_rows + 1, timeout_s)
                    except _Timeout:
                        return error("SQL_TIMEOUT", f"the query ran longer than {timeout_s:g} seconds", False)
                    except sqlite3.Error as exc:
                        problem = f"the database said: {exc}"
                    else:
                        columns, shown_rows = with_major_units(columns, [list(r) for r in rows[:max_rows]])
                        return ok(
                            [f"sql:{evidence_id()}"],
                            {
                                "sql": shown,
                                "columns": columns,
                                "rows": shown_rows,
                                "row_count": min(len(rows), max_rows),
                                "truncated": len(rows) > max_rows,
                            },
                        )
            if attempt == 2:
                return error("SQL_GENERATION_FAILED", f"no usable SQL after one repair: {problem}", True)
            messages += [AIMessage(reply), HumanMessage(REPAIR_PROMPT.format(problem=problem))]
        raise AssertionError("unreachable")  # the loop always returns on the second round
    finally:
        conn.close()


def build_query_ledger_tool(
    model: BaseChatModel | None = None,
    *,
    db_path: str | Path | None = None,
    timeout_s: float = TIMEOUT_SECONDS,
) -> StructuredTool:
    """Builds the tool. Without `model` and `db_path`, it uses the configured ones at call time."""
    counter = itertools.count(1)

    def query_ledger(question: str, max_rows: int = DEFAULT_MAX_ROWS) -> dict[str, Any]:
        return run_query_ledger(
            question,
            max_rows,
            model=model or get_chat_model(),
            db_path=db_path or get_settings().ledger_db,
            timeout_s=timeout_s,
            evidence_id=lambda: next(counter),
        )

    return StructuredTool.from_function(
        func=query_ledger,
        name="query_ledger",
        description=DESCRIPTION,
        args_schema=QueryLedgerInput,
        handle_validation_error=invalid_input,
    )
