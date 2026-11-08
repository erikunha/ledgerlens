"""Portal accounts: who signs in, their statement, and a ledger copy that holds only their records.

What they guarantee, and why: (a) a statement shows the account's payments, refunds, chargebacks and (for a
merchant) payouts, and nothing of another account; (b) the scoped copy keeps only the account's rows, so a query
the agent's model writes cannot read another customer's records; (c) the source ledger is never written.
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from ledgerlens.api.accounts import (  # noqa: E402
    account_kind,
    account_statement,
    load_account_profile,
    load_accounts,
    scoped_ledger,
)
from ledgerlens.offline import ScriptedChatModel  # noqa: E402
from ledgerlens.sim.config import SimConfig  # noqa: E402
from ledgerlens.sim.pipeline import build_ledger  # noqa: E402
from ledgerlens.tools.sql import build_query_ledger_tool  # noqa: E402


@pytest.fixture(scope="module")
def ledger_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("ledger") / "ledger.db"
    build_ledger(SimConfig(source="sample"), path).conn.close()
    return path


def _ids(db: Path, sql: str) -> set[str]:
    with sqlite3.connect(db) as conn:
        return {row[0] for row in conn.execute(sql)}


def test_account_kind_comes_from_the_id() -> None:
    assert account_kind("C-0412") == "customer"
    assert account_kind("M-03") == "merchant"
    with pytest.raises(ValueError):
        account_kind("TX-2048")
    with pytest.raises(ValueError):
        account_kind("C-0412' OR 1=1 --")


def test_accounts_carry_name_and_currency_and_skip_unknown_ids(ledger_db: Path) -> None:
    accounts = load_accounts(ledger_db, ["C-0412", "M-03", "C-9998"])
    assert [(a.id, a.kind, a.name, a.currency) for a in accounts] == [
        ("C-0412", "customer", "Mariana Albuquerque Costa", "BRL"),
        ("M-03", "merchant", "Casa Verde Foods", "BRL"),
    ]
    assert accounts[0].label == "Mariana Albuquerque Costa (customer C-0412)"


def test_a_customer_statement_has_the_payment_and_its_refund_newest_first(ledger_db: Path) -> None:
    lines = account_statement(ledger_db, "C-0412")
    assert [(line["type"], line["id"]) for line in lines] == [("Refund", "R-0731"), ("Payment", "TX-2048")]
    refund, payment = lines
    assert (payment["date"], payment["amount"], payment["currency"], payment["status"]) == (
        "2026-10-15",
        "100.00",
        "EUR",
        "refunded",
    )
    assert payment["counterparty"] == "Lumen Travel GmbH" and refund["counterparty"] == "Lumen Travel GmbH"
    assert payment["record"]["card_brand"] == "visa"
    assert [f["applied_rate"] for f in payment["record"]["fx"]] == ["5.6679"]  # the rate of the charge only
    assert (refund["record"]["payout_amount_minor"], refund["record"]["payout_currency"]) == (54931, "BRL")
    assert [f["applied_rate"] for f in refund["record"]["fx"]] == ["5.4931"]
    assert {"R-0731", "TX-2048", "FX-9002"} <= set(refund["ids"])


def test_a_chargeback_line_carries_its_deadline(ledger_db: Path) -> None:
    lines = {line["id"]: line for line in account_statement(ledger_db, "C-0291")}
    assert lines["CB-0310"]["type"] == "Chargeback"
    assert lines["CB-0310"]["record"]["deadline"] == "2026-11-09"
    assert lines["CB-0310"]["status"] == "evidence_requested"


def test_a_merchant_statement_has_payouts_and_only_its_own_payments(ledger_db: Path) -> None:
    lines = account_statement(ledger_db, "M-03")
    payout = next(line for line in lines if line["id"] == "ST-0044")
    assert (payout["type"], payout["amount"], payout["currency"], payout["status"]) == (
        "Payout",
        "29992.87",
        "BRL",
        "paid",
    )
    assert payout["record"]["expected_payout_date"] == "2026-10-14"
    payments = {line["id"] for line in lines if line["type"] == "Payment"}
    assert payments == _ids(ledger_db, "SELECT id FROM transactions WHERE merchant_id = 'M-03'")
    assert [line["date"] for line in lines] == sorted((line["date"] for line in lines), reverse=True)


def test_the_profile_is_the_account_row(ledger_db: Path) -> None:
    assert load_account_profile(ledger_db, "M-03")["category"] == "food"
    assert load_account_profile(ledger_db, "C-0412")["billing_currency"] == "BRL"
    with pytest.raises(LookupError):
        load_account_profile(ledger_db, "C-9998")


def test_a_customer_copy_holds_only_that_customer(ledger_db: Path, tmp_path: Path) -> None:
    before = hashlib.sha256(ledger_db.read_bytes()).hexdigest()
    db = scoped_ledger(ledger_db, "C-0733", tmp_path / "c.db")
    assert hashlib.sha256(ledger_db.read_bytes()).hexdigest() == before  # the source is untouched
    assert _ids(db, "SELECT DISTINCT customer_id FROM transactions") == {"C-0733"}
    assert _ids(db, "SELECT id FROM customers") == {"C-0733"}
    assert _ids(db, "SELECT id FROM transactions") == {"TX-2051", "TX-2052"}
    assert _ids(db, "SELECT id FROM merchants") == {"M-05"}
    assert _ids(db, "SELECT id FROM settlements") == set()
    kept = _ids(db, "SELECT id FROM transactions")
    for table in ("refunds", "chargebacks", "fx_applied"):
        assert _ids(db, f"SELECT transaction_id FROM {table}") <= kept
    assert _ids(db, "SELECT aggregate_id FROM events") <= kept | {"C-0733", "M-05"}


def test_a_merchant_copy_holds_its_payments_customers_and_payouts(ledger_db: Path, tmp_path: Path) -> None:
    db = scoped_ledger(ledger_db, "M-03", tmp_path / "m.db")
    assert _ids(db, "SELECT DISTINCT merchant_id FROM transactions") == {"M-03"}
    assert _ids(db, "SELECT DISTINCT merchant_id FROM settlements") == {"M-03"}
    assert "ST-0044" in _ids(db, "SELECT id FROM settlements")
    assert _ids(db, "SELECT id FROM customers") == _ids(db, "SELECT customer_id FROM transactions")
    assert {"CB-0311", "CB-0312"} <= _ids(db, "SELECT id FROM chargebacks")


def test_the_copy_keeps_the_events_append_only(ledger_db: Path, tmp_path: Path) -> None:
    db = scoped_ledger(ledger_db, "C-0412", tmp_path / "c.db")
    with sqlite3.connect(db) as conn, pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM events")


def test_a_query_over_the_copy_cannot_read_another_customer(ledger_db: Path, tmp_path: Path) -> None:
    """The model writes SQL with no filter at all, as a careless or manipulated model would: only the account's
    rows come back."""
    db = scoped_ledger(ledger_db, "C-0412", tmp_path / "c.db")
    sql = "SELECT t.id, t.customer_id, c.display_name FROM transactions t JOIN customers c ON c.id = t.customer_id"
    tool = build_query_ledger_tool(ScriptedChatModel(script=[sql]), db_path=db)
    out = tool.invoke({"question": "every transaction of every customer"})
    assert out["ok"], out
    rows = out["data"]["rows"]
    assert rows and {row[1] for row in rows} == {"C-0412"}
