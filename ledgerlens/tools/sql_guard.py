"""SQL guard: decides whether a query written by the model may go to the ledger database.

Why it exists
--------------
The agent turns a question into SQL (`query_ledger`). A model can make mistakes, or be fooled by
a text read from a database row, and generate `UPDATE`, `DROP`, a query on the internal tables
(`events`, `projector_state`, `sqlite_*`) or a dangerous function such as `load_extension`. This guard is
the first of three layers of defense. The other two live in `sql.py`: the connection opened read-only
(`mode=ro`) and the 2-second time limit.

How it works (the flow, in order)
---------------------------------
::

    SQL text
      |
      v
    1. sqlglot parses the text (sqlite dialect). Comments vanish here, because the SQL that goes to the database is
      |   generated again from the tree, never the original text. Parse error -> "syntax".
      v
    2. drops the final semicolon and the empty statements. No statement -> "empty".
      |   More than one statement -> "multiple_statements".
      v
    3. the root must be SELECT or a union/intersect/except of SELECTs, and no write or
      |   command (INSERT, DROP, PRAGMA, ATTACH...) may appear anywhere -> "not_select".
      v
    4. every table cited, in any position (subquery, JOIN, CTE), is on the allowed list.
      |   A CTE name does not count as a table. A table function or a schema-qualified name -> "table_not_allowed".
      v
    5. every function called is on the allowed list -> else "function_not_allowed".
      v
    6. the query is wrapped: SELECT * FROM (<query>) LIMIT n. The wrap holds for any
       shape (UNION included) and limits what the query itself asked for.

A refused query never reaches the database. The reason goes to the model as data (`SqlRejected.rule`), and
it can try again. The function list needs maintenance: if a legitimate query is
refused, the reason says which function was missing.
"""

from __future__ import annotations

import logging
import re

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

# sqlglot logs a warning when it falls back to "Command" (EXPLAIN, VACUUM...). For us that is just a case
# of "not a SELECT", so the warning is noise.
logging.getLogger("sqlglot").setLevel(logging.ERROR)

DIALECT = "sqlite"
DEFAULT_MAX_ROWS = 50

# The seven readable tables. `events`, `projector_state` and every `sqlite_*` are left out on
# purpose: the agent sees the ledger's result, never the event log nor the SQLite catalog.
ALLOWED_TABLES = frozenset(
    {"merchants", "customers", "transactions", "refunds", "chargebacks", "settlements", "fx_applied"}
)

# Pure aggregate, date, text and conversion functions. Nothing that reads a file, loads an extension or
# reveals the SQLite version.
ALLOWED_FUNCTIONS = frozenset(
    {
        "count", "sum", "avg", "min", "max", "total", "group_concat",
        "date", "datetime", "strftime", "julianday",
        "round", "abs", "coalesce", "ifnull", "nullif",
        "lower", "upper", "substr", "substring", "length", "printf", "cast",
    }
)  # fmt: skip

# Nodes that are syntax (CASE, IF inside CASE, EXISTS) and not a function call: their children
# are checked on their own.
_SYNTAX_NODES = (exp.Case, exp.If, exp.Exists)

# Any of these anywhere in the tree means a write, a command or a schema change.
_FORBIDDEN_NODES = (exp.DML, exp.DDL, exp.Command, exp.Pragma, exp.Attach, exp.Detach)

_CALL = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(")


class SqlRejected(ValueError):
    """The guard refused the query. `rule` says which rule, `str(error)` says what broke it."""

    def __init__(self, rule: str, message: str) -> None:
        super().__init__(message)
        self.rule = rule


def _function_name(node: exp.Func) -> str | None:
    """The function name as SQLite would see it, or None if the node is not a call."""
    if isinstance(node, exp.Anonymous):
        return str(node.name).lower()
    # For the functions sqlglot knows, the name comes from the text it generates for SQLite. That way the
    # check holds for what will actually run.
    match = _CALL.match(node.sql(dialect=DIALECT, comments=False))
    return match.group(1).lower() if match else None


def _check_tables(root: exp.Expression) -> None:
    # A CTE name can be cited as if it were a table; its body is checked like the rest.
    cte_names = {cte.alias_or_name.lower() for cte in root.find_all(exp.CTE)}
    for table in root.find_all(exp.Table):
        if not isinstance(table.this, exp.Identifier):
            raise SqlRejected("table_not_allowed", "table functions (such as pragma_* or json_each) are not allowed")
        if table.db or table.catalog:
            qualified = table.sql(dialect=DIALECT)
            raise SqlRejected("table_not_allowed", f"schema-qualified table '{qualified}' is not allowed")
        name = table.name.lower()
        if name not in ALLOWED_TABLES and name not in cte_names:
            raise SqlRejected(
                "table_not_allowed",
                f"table '{table.name}' is not allowed; allowed tables: {', '.join(sorted(ALLOWED_TABLES))}",
            )


def _check_functions(root: exp.Expression) -> None:
    for node in root.find_all(exp.Func):
        if isinstance(node, _SYNTAX_NODES):
            continue
        name = _function_name(node)
        if name is not None and name not in ALLOWED_FUNCTIONS:
            raise SqlRejected(
                "function_not_allowed",
                f"function '{name}' is not allowed; allowed functions: {', '.join(sorted(ALLOWED_FUNCTIONS))}",
            )


def guard_sql(sql: str, *, max_rows: int = DEFAULT_MAX_ROWS) -> str:
    """Validates `sql` and returns the query ready to run, wrapped with `LIMIT max_rows`.

    Raises `SqlRejected` with the broken rule. `max_rows < 1` is the caller's error, not the model's,
    and raises `ValueError`.
    """
    if max_rows < 1:
        raise ValueError("max_rows must be at least 1")

    try:
        parsed = sqlglot.parse(sql, dialect=DIALECT)
    except SqlglotError as exc:
        raise SqlRejected("syntax", f"the SQL could not be parsed: {str(exc).splitlines()[0]}") from None

    # `SELECT 1; --` becomes [Select, Semicolon] and `SELECT 1;;` becomes [Select, None]: what is left after
    # the final semicolon is not a second statement.
    statements = [s for s in parsed if s is not None and not isinstance(s, exp.Semicolon)]
    if not statements:
        raise SqlRejected("empty", "the SQL is empty")
    if len(statements) > 1:
        raise SqlRejected("multiple_statements", "only one statement is allowed")

    root = statements[0]
    if not isinstance(root, (exp.Select, exp.SetOperation)) or root.find(*_FORBIDDEN_NODES) is not None:
        raise SqlRejected("not_select", "only a SELECT (or a UNION, INTERSECT or EXCEPT of SELECTs) is allowed")

    _check_tables(root)
    _check_functions(root)

    # The SQL that runs is the one generated from the already checked tree, with no comments. There is no way for
    # the original text to say one thing to the guard and another to SQLite.
    inner = root.sql(dialect=DIALECT, comments=False)
    return f"SELECT * FROM ({inner}) LIMIT {int(max_rows)}"
