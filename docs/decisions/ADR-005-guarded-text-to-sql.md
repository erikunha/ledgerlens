---
type: adr
status: accepted
date: 2026-11-07
---

# ADR-005: Text-to-SQL with a guard and a read-only connection

Status: accepted. Date: 2026-11-07.

## Context

The agent needs to query structured data through natural language. A model can generate `UPDATE`, `DROP`, queries on internal tables or slow queries. The `create_sql_agent` documentation warns about dangerous queries, and the literature on prompt injection through SQL shows that row content can try to give orders to the agent. The agent may only have read-only access.

## Decision

Defense in layers in the `query_ledger` tool:

1. **Guard with `sqlglot`** (`sqlite` dialect): strips comments and a trailing semicolon, accepts a single statement whose root is `SELECT` or a union of `SELECT`s, only tables on the allowed list (the seven read tables, never `events`, `projector_state` or `sqlite_*`), only functions on the allowed list, and wraps the query as `SELECT * FROM (...) LIMIT n`.
2. **Connection `file:...?mode=ro`.** Tested: `INSERT` and `DROP TABLE` fail with `attempt to write a readonly database`.
3. **Time limit** of 2 seconds with `set_progress_handler`. Tested: a recursive CTE was interrupted (`interrupted`).

A prototype of the guard showed four holes that the final version closes, each with a test: the `load_extension` function passed, `SELECT 1; --` was read as two statements, `UNION` had no limit and `sqlite_sequence` exists in the database.

Data that is read (a refund reason, a policy passage) is always data. Scenario S09 plants an instruction to ignore instructions in a reason field, and the test requires that no tool runs because of it.

## Alternatives considered

- **`create_sql_agent` with broad access.** Rejected because of the documentation's own warning.
- **Regular-expression filter.** Easy to get around.
- **A view layer with a low-privilege user.** SQLite has no users.
- **Postgres.** More realistic, but gets in the way of offline reproduction.

## Consequences

- A rejected query is logged with the reason and never executed. The agent receives the error as data and can try again.
- The database stores values in minor units (cents, integers) and rates as text, and the agent is instructed to use the calculator for arithmetic.
- The guard has a function list that needs maintenance when a legitimate query is rejected.
