"""SQL guard: each row of the attack table, the known holes and more.

The guard is the first of three layers (guard, read-only connection, time limit). Only the text is tested
here: what goes in, what comes out rewritten and which rule refused. Nothing runs on the database.
"""

from __future__ import annotations

import pytest

from ledgerlens.tools.sql_guard import ALLOWED_TABLES, SqlRejected, guard_sql

READ_TABLES = {"merchants", "customers", "transactions", "refunds", "chargebacks", "settlements", "fx_applied"}


def rule_of(sql: str, **kwargs: int) -> str:
    with pytest.raises(SqlRejected) as info:
        guard_sql(sql, **kwargs)
    return info.value.rule


# --- what passes ------------------------------------------------------------------------------


def test_the_allowlist_is_exactly_the_seven_read_tables() -> None:
    assert set(ALLOWED_TABLES) == READ_TABLES


def test_a_plain_select_is_accepted_and_wrapped_with_a_limit() -> None:
    out = guard_sql("SELECT id, status FROM transactions WHERE id = 'TX-2048'", max_rows=200)
    assert out.startswith("SELECT * FROM (SELECT id, status FROM transactions WHERE id = 'TX-2048')")
    assert out.endswith("LIMIT 200")


def test_the_default_limit_is_fifty() -> None:
    assert guard_sql("SELECT 1 FROM merchants").endswith("LIMIT 50")


def test_a_larger_limit_inside_the_query_is_clamped_by_the_wrapper() -> None:
    out = guard_sql("SELECT id FROM transactions LIMIT 100000", max_rows=200)
    assert out.endswith(") LIMIT 200")


def test_a_cte_name_is_not_a_table() -> None:
    out = guard_sql("WITH a AS (SELECT * FROM refunds) SELECT * FROM a")
    assert "WITH a AS" in out


def test_a_recursive_cte_is_accepted_the_timeout_stops_it() -> None:
    guard_sql("WITH RECURSIVE a(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM a) SELECT n FROM a")


def test_joins_aggregates_and_the_listed_functions_are_accepted() -> None:
    guard_sql(
        "SELECT m.name, count(*), sum(t.amount_minor), avg(t.amount_minor), min(t.created_at), max(t.created_at), "
        "round(1.234, 2), coalesce(t.card_brand, 'n/a'), abs(-1), lower(m.name), upper(m.name), length(m.name), "
        "substr(t.id, 1, 2), date(t.created_at), datetime(t.created_at), strftime('%Y', t.created_at), "
        "printf('%.2f', t.amount_minor / 100.0), CAST(t.amount_minor AS REAL), "
        "CASE WHEN t.status = 'refunded' THEN 1 ELSE 0 END "
        "FROM transactions t JOIN merchants m ON m.id = t.merchant_id GROUP BY m.name"
    )


def test_set_operations_over_allowed_tables_are_accepted() -> None:
    guard_sql("SELECT id FROM refunds UNION SELECT id FROM chargebacks")
    guard_sql("SELECT id FROM refunds EXCEPT SELECT id FROM chargebacks")


def test_table_names_are_matched_without_regard_to_case_and_quotes() -> None:
    guard_sql('SELECT * FROM "Transactions"')
    guard_sql("SELECT * FROM TRANSACTIONS")


def test_comments_are_stripped_but_text_inside_a_string_is_kept() -> None:
    out = guard_sql("SELECT id /* c1 */ FROM refunds -- c2\nWHERE reason = 'a; -- b /* c */'")
    assert "c1" not in out and "c2" not in out
    assert "'a; -- b /* c */'" in out


def test_one_trailing_semicolon_is_accepted() -> None:
    assert guard_sql("SELECT 1 FROM merchants;").endswith("LIMIT 50")


# --- the four holes of the prototype ---------------------------------------------------------


def test_gap_1_load_extension_is_refused_by_the_function_allowlist() -> None:
    assert rule_of("SELECT load_extension('x')") == "function_not_allowed"


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT \"load_extension\"('x')",
        "SELECT LOAD_EXTENSION ('x')",
        "SELECT main.load_extension('x')",
        "SELECT `load_extension`('x')",
        "SELECT randomblob(8)",
        "SELECT sqlite_version()",
        "SELECT zeroblob(1000000000)",
        "SELECT row_number() OVER (ORDER BY id) FROM transactions",
        "SELECT id FROM transactions WHERE hex(id) = 'x'",
    ],
)
def test_other_functions_outside_the_list_are_refused(sql: str) -> None:
    assert rule_of(sql) == "function_not_allowed"


def test_gap_2_a_trailing_semicolon_and_comment_is_not_a_second_statement() -> None:
    assert guard_sql("SELECT 1; --").endswith("LIMIT 50")
    assert guard_sql("SELECT 1 FROM merchants; -- fim").endswith("LIMIT 50")
    assert guard_sql("SELECT 1 FROM merchants;;").endswith("LIMIT 50")


def test_gap_3_a_union_gets_a_limit_through_the_wrapper() -> None:
    out = guard_sql("SELECT id FROM refunds UNION SELECT id FROM chargebacks", max_rows=7)
    assert out.startswith("SELECT * FROM (SELECT id FROM refunds UNION SELECT id FROM chargebacks)")
    assert out.endswith("LIMIT 7")


def test_gap_4_sqlite_sequence_and_every_sqlite_table_are_refused() -> None:
    assert rule_of("SELECT * FROM sqlite_sequence") == "table_not_allowed"
    assert rule_of("SELECT * FROM sqlite_master") == "table_not_allowed"
    assert rule_of("SELECT * FROM sqlite_schema") == "table_not_allowed"
    assert rule_of("SELECT * FROM sqlite_stat1") == "table_not_allowed"


# --- internal tables and ways to hide them ---------------------------------------------------


@pytest.mark.parametrize("table", ["events", "projector_state"])
def test_internal_tables_are_refused(table: str) -> None:
    assert rule_of(f"SELECT * FROM {table}") == "table_not_allowed"
    assert rule_of(f'SELECT * FROM "{table.upper()}"') == "table_not_allowed"
    assert rule_of(f"SELECT * FROM [{table}]") == "table_not_allowed"


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT id FROM refunds UNION SELECT payload FROM events",
        "SELECT * FROM (SELECT * FROM events) x",
        "SELECT (SELECT count(*) FROM events)",
        "SELECT 1 WHERE EXISTS (SELECT 1 FROM events)",
        "SELECT * FROM transactions WHERE id IN (SELECT aggregate_id FROM events)",
        "WITH x AS (SELECT * FROM events) SELECT * FROM x",
        "SELECT * FROM transactions JOIN events ON events.aggregate_id = transactions.id",
    ],
)
def test_a_forbidden_table_is_found_in_every_position(sql: str) -> None:
    assert rule_of(sql) == "table_not_allowed"


def test_a_schema_qualified_table_is_refused() -> None:
    assert rule_of("SELECT * FROM main.transactions") == "table_not_allowed"
    assert rule_of("SELECT * FROM temp.sqlite_master") == "table_not_allowed"


@pytest.mark.parametrize("sql", ["SELECT * FROM pragma_table_info('transactions')", "SELECT * FROM json_each('[1]')"])
def test_a_table_valued_function_is_refused(sql: str) -> None:
    assert rule_of(sql) == "table_not_allowed"


# --- what is not a SELECT ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE transactions SET status = 'x'",
        "DELETE FROM refunds",
        "INSERT INTO merchants (id) VALUES ('M-99')",
        "REPLACE INTO merchants (id) VALUES ('M-99')",
        "PRAGMA table_info(transactions)",
        "ATTACH DATABASE 'x.db' AS x",
        "VACUUM",
        "EXPLAIN SELECT 1",
        "EXPLAIN QUERY PLAN SELECT 1",
        "DROP TABLE transactions",
        "CREATE TABLE x (a)",
        "VALUES (1)",
        "WITH x AS (DELETE FROM refunds RETURNING *) SELECT * FROM x",
    ],
)
def test_a_statement_that_is_not_a_select_is_refused(sql: str) -> None:
    assert rule_of(sql) == "not_select"


def test_a_second_statement_is_refused() -> None:
    assert rule_of("select id from transactions; drop table transactions") == "multiple_statements"
    assert rule_of("SELECT 1; SELECT 2") == "multiple_statements"


def test_a_destructive_statement_hidden_by_a_comment_is_still_refused() -> None:
    assert rule_of("DROP/**/TABLE transactions") == "not_select"
    assert rule_of("SELECT 1 FROM merchants; /* x */ DELETE FROM merchants") == "multiple_statements"


@pytest.mark.parametrize("sql", ["", "   ", ";", "-- just a comment", "/* nothing */"])
def test_an_empty_statement_is_refused(sql: str) -> None:
    assert rule_of(sql) == "empty"


def test_text_that_does_not_parse_is_refused_with_a_syntax_rule() -> None:
    assert rule_of("SELECT FROM WHERE") == "syntax"


def test_a_bad_row_limit_is_a_programming_error_not_a_rejection() -> None:
    with pytest.raises(ValueError):
        guard_sql("SELECT 1", max_rows=0)


def test_the_message_names_the_rule_and_the_offender() -> None:
    with pytest.raises(SqlRejected) as info:
        guard_sql("SELECT * FROM events")
    assert "events" in str(info.value) and info.value.rule == "table_not_allowed"
    with pytest.raises(SqlRejected) as info:
        guard_sql("SELECT load_extension('x')")
    assert "load_extension" in str(info.value)


def test_exists_and_case_are_syntax_not_functions() -> None:
    guard_sql("SELECT id FROM transactions t WHERE EXISTS (SELECT 1 FROM refunds r WHERE r.transaction_id = t.id)")
    guard_sql("SELECT CASE status WHEN 'paid' THEN 1 ELSE 0 END FROM refunds")
