"""`query_ledger`: the scripted model writes the SQL, the guard checks it, the database answers.

The database comes from `build_ledger` with the committed sample (the same one the simulator builds), in a
temporary folder, so the test does not depend on `data/ledger.db` existing. No test uses the network.
"""

from __future__ import annotations

import re
import sqlite3
import time
from pathlib import Path

import pytest

from ledgerlens.offline import ScriptedChatModel
from ledgerlens.sim.config import SimConfig
from ledgerlens.sim.pipeline import build_ledger
from ledgerlens.tools.sql import build_query_ledger_tool, open_readonly

EVIDENCE = re.compile(r"^(sql|api|policy|fx|calc|case):.+$")


@pytest.fixture(scope="module")
def ledger_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("ledger") / "ledger.db"
    build_ledger(SimConfig(source="sample"), path).conn.close()
    return path


def tool_with(script: list[str], db: Path, **kwargs):
    model = ScriptedChatModel(script=script)
    return build_query_ledger_tool(model, db_path=db, **kwargs), model


def assert_envelope(result: dict) -> None:
    """Checks the common format of `docs/contracts/tools.md`."""
    assert isinstance(result, dict)
    if result["ok"]:
        assert set(result) == {"ok", "evidence_ids", "data"}
        assert result["evidence_ids"] and all(EVIDENCE.match(e) for e in result["evidence_ids"])
    else:
        assert set(result) == {"ok", "error"}
        assert set(result["error"]) == {"code", "message", "retryable"}


# --- right answer -----------------------------------------------------------------------------


def test_the_status_of_tx_2048(ledger_db: Path) -> None:
    tool, model = tool_with(["SELECT id, status FROM transactions WHERE id = 'TX-2048'"], ledger_db)
    result = tool.invoke({"question": "status of TX-2048"})
    assert_envelope(result)
    assert result["evidence_ids"] == ["sql:1"]
    data = result["data"]
    assert set(data) == {"sql", "columns", "rows", "row_count", "truncated"}
    assert data["columns"] == ["id", "status"]
    assert data["rows"] == [["TX-2048", "refunded"]]
    assert (data["row_count"], data["truncated"]) == (1, False)
    assert data["sql"].startswith("SELECT * FROM (SELECT id, status FROM transactions")
    assert data["sql"].endswith("LIMIT 50")


def test_each_minor_column_comes_with_its_amount_in_major_units(ledger_db: Path) -> None:
    # EC-01: payout_amount_minor 54931 was read as 54,931.00 BRL. The right value is 549.31, and it comes from code.
    sql = "SELECT id, payout_amount_minor, payout_currency FROM refunds WHERE transaction_id = 'TX-2048'"
    tool, _ = tool_with([sql], ledger_db)
    data = tool.invoke({"question": "refund of TX-2048"})["data"]
    assert data["columns"] == ["id", "payout_amount_minor", "payout_amount_major", "payout_currency"]
    assert data["rows"] == [["R-0731", 54931, "549.31", "BRL"]]


def test_major_units_are_exact_for_the_edges(ledger_db: Path) -> None:
    sql = (
        "SELECT 123456789 AS big_minor, 5 AS tiny_minor, 100 AS whole_minor, 0 AS zero_minor, -250 AS delta_minor, "
        "NULL AS gone_minor, 1234.5 AS avg_minor, 'x' AS text_minor"
    )
    tool, _ = tool_with([sql], ledger_db)
    data = tool.invoke({"question": "edge values"})["data"]
    major = dict(zip(data["columns"], data["rows"][0], strict=True))
    assert major["big_major"] == "1234567.89"
    assert major["tiny_major"] == "0.05"
    assert major["whole_major"] == "1.00"
    assert major["zero_major"] == "0.00"
    assert major["delta_major"] == "-2.50"
    assert major["gone_major"] is None
    assert major["avg_major"] == "12.34"  # 12.345 rounds half to even, like calculate
    assert major["text_major"] is None
    assert major["big_minor"] == 123456789  # the original column stays intact


def test_the_model_sees_the_question_and_the_real_columns(ledger_db: Path) -> None:
    tool, model = tool_with(["SELECT 1 FROM merchants"], ledger_db)
    tool.invoke({"question": "refunds for TX-2048"})
    prompt = "\n".join(str(m.content) for m in model.calls[0])
    assert "refunds for TX-2048" in prompt
    for column in ("amount_minor", "applied_rate", "expected_payout_date", "refund_window_days"):
        assert column in prompt, column
    assert "events" not in prompt and "projector_state" not in prompt


def test_a_fenced_answer_is_accepted(ledger_db: Path) -> None:
    tool, _ = tool_with(["Here it is:\n```sql\nSELECT id FROM merchants LIMIT 2;\n```"], ledger_db)
    result = tool.invoke({"question": "two merchants"})
    assert result["ok"] and result["data"]["row_count"] == 2


def test_an_unknown_id_is_a_success_with_no_rows(ledger_db: Path) -> None:
    tool, _ = tool_with(["SELECT id FROM transactions WHERE id = 'TX-9999'"], ledger_db)
    result = tool.invoke({"question": "status of TX-9999"})
    assert_envelope(result)
    assert result["ok"] is True
    assert result["data"]["rows"] == [] and result["data"]["row_count"] == 0 and result["data"]["truncated"] is False


def test_rows_past_max_rows_are_cut_and_flagged(ledger_db: Path) -> None:
    tool, _ = tool_with(["SELECT id FROM transactions ORDER BY id"], ledger_db)
    result = tool.invoke({"question": "all transactions", "max_rows": 3})
    data = result["data"]
    assert data["row_count"] == 3 and len(data["rows"]) == 3 and data["truncated"] is True
    assert data["sql"].endswith("LIMIT 3")
    assert [row[0] for row in data["rows"]] == sorted(row[0] for row in data["rows"])  # the query order is kept


def test_exactly_max_rows_is_not_truncated(ledger_db: Path) -> None:
    tool, _ = tool_with(["SELECT id FROM merchants WHERE id = 'M-17'"], ledger_db)
    assert tool.invoke({"question": "merchant M-17", "max_rows": 1})["data"]["truncated"] is False


def test_text_in_a_row_comes_back_as_data_only(ledger_db: Path) -> None:
    tool, model = tool_with(["SELECT reason FROM refunds WHERE reason LIKE '%IGNORE ALL%'"], ledger_db)
    result = tool.invoke({"question": "refund reasons that look odd"})
    assert result["ok"] and "IGNORE ALL PREVIOUS INSTRUCTIONS" in result["data"]["rows"][0][0]
    assert model.remaining == 0  # nothing more was asked of the model because of the text


def test_evidence_ids_count_successful_calls(ledger_db: Path) -> None:
    tool, _ = tool_with(["SELECT 1 FROM merchants", "DELETE FROM refunds", "SELECT 2 FROM merchants"], ledger_db)
    assert tool.invoke({"question": "first"})["evidence_ids"] == ["sql:1"]
    assert tool.invoke({"question": "second"})["ok"] is False
    assert tool.invoke({"question": "third"})["evidence_ids"] == ["sql:2"]


# --- refusals and failures --------------------------------------------------------------------


def test_an_update_is_rejected_and_nothing_changes(ledger_db: Path) -> None:
    tool, _ = tool_with(["UPDATE transactions SET status = 'captured' WHERE id = 'TX-2048'"], ledger_db)
    result = tool.invoke({"question": "mark TX-2048 as captured"})
    assert_envelope(result)
    assert result["error"]["code"] == "SQL_REJECTED" and result["error"]["retryable"] is True
    assert "not_select" in result["error"]["message"]
    with sqlite3.connect(ledger_db) as conn:
        assert conn.execute("SELECT status FROM transactions WHERE id = 'TX-2048'").fetchone() == ("refunded",)


@pytest.mark.parametrize(
    ("sql", "rule"),
    [
        ("SELECT * FROM events", "table_not_allowed"),
        ("SELECT load_extension('x')", "function_not_allowed"),
        ("SELECT 1; DROP TABLE refunds", "multiple_statements"),
    ],
)
def test_the_guard_reasons_reach_the_model(ledger_db: Path, sql: str, rule: str) -> None:
    tool, _ = tool_with([sql], ledger_db)
    error = tool.invoke({"question": "something risky"})["error"]
    assert error["code"] == "SQL_REJECTED" and rule in error["message"]


def test_a_rejected_statement_is_logged_with_its_reason(ledger_db: Path, caplog: pytest.LogCaptureFixture) -> None:
    tool, _ = tool_with(["SELECT * FROM events"], ledger_db)
    with caplog.at_level("WARNING"):
        tool.invoke({"question": "internal events"})
    assert "table_not_allowed" in caplog.text


def test_the_connection_is_read_only(ledger_db: Path) -> None:
    conn = open_readonly(ledger_db)
    try:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            conn.execute("INSERT INTO merchants (id) VALUES ('M-99')")
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            conn.execute("DROP TABLE refunds")
    finally:
        conn.close()


def test_a_slow_query_hits_the_time_limit(ledger_db: Path) -> None:
    slow = "WITH RECURSIVE a(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM a) SELECT max(n) FROM a"
    tool, _ = tool_with([slow], ledger_db, timeout_s=0.2)
    start = time.monotonic()
    result = tool.invoke({"question": "count forever"})
    assert time.monotonic() - start < 3
    assert result["error"]["code"] == "SQL_TIMEOUT" and result["error"]["retryable"] is False


def test_a_missing_database_is_unavailable(tmp_path: Path) -> None:
    tool, _ = tool_with(["SELECT 1 FROM merchants"], tmp_path / "no-such.db")
    error = tool.invoke({"question": "any merchant"})["error"]
    assert error["code"] == "DB_UNAVAILABLE" and error["retryable"] is False
    assert not (tmp_path / "no-such.db").exists()  # opening for reading does not create the file


# --- generation and repair --------------------------------------------------------------------


def test_text_without_sql_gets_one_repair(ledger_db: Path) -> None:
    tool, model = tool_with(["I do not know how to query that.", "SELECT id FROM merchants LIMIT 1"], ledger_db)
    result = tool.invoke({"question": "one merchant"})
    assert result["ok"] is True
    assert len(model.calls) == 2
    assert "SELECT" in "\n".join(str(m.content) for m in model.calls[1])  # the repair request asks for SQL only


def test_a_database_error_is_repaired_once_with_its_message(ledger_db: Path) -> None:
    tool, model = tool_with(["SELECT nope FROM merchants", "SELECT id FROM merchants LIMIT 1"], ledger_db)
    assert tool.invoke({"question": "one merchant"})["ok"] is True
    assert "no such column" in "\n".join(str(m.content) for m in model.calls[1])


def test_two_failed_generations_end_as_generation_failed(ledger_db: Path) -> None:
    tool, model = tool_with(["blah", "SELECT FROM WHERE"], ledger_db)
    error = tool.invoke({"question": "one merchant"})["error"]
    assert error["code"] == "SQL_GENERATION_FAILED" and error["retryable"] is True
    assert len(model.calls) == 2  # one repair, never two


def test_a_rejection_is_not_repaired(ledger_db: Path) -> None:
    tool, model = tool_with(["DELETE FROM refunds", "SELECT 1 FROM merchants"], ledger_db)
    assert tool.invoke({"question": "wipe it"})["error"]["code"] == "SQL_REJECTED"
    assert len(model.calls) == 1


# --- input and description --------------------------------------------------------------------


@pytest.mark.parametrize(
    "arguments",
    [
        {"question": "ab"},
        {"question": "x" * 501},
        {"question": "ok ok", "max_rows": 0},
        {"question": "ok ok", "max_rows": 201},
    ],
)
def test_invalid_input_never_reaches_the_model(ledger_db: Path, arguments: dict) -> None:
    tool, model = tool_with(["SELECT 1 FROM merchants"], ledger_db)
    result = tool.invoke(arguments)
    assert not model.calls
    assert "INVALID_INPUT" in str(result)


def test_the_tool_is_described_for_the_model(ledger_db: Path) -> None:
    tool, _ = tool_with([], ledger_db)
    assert tool.name == "query_ledger"
    assert "read-only SQL" in tool.description and "minor units" in tool.description
    assert set(tool.args) == {"question", "max_rows"}
    assert tool.args["max_rows"]["default"] == 50
