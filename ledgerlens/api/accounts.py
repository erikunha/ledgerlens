"""Accounts of the payments portal: who is signed in, their statement, and a ledger that holds only their records.

Why it exists: the demo page reads like a portal. A person signs in as one customer (`C-nnnn`) or one merchant
(`M-nn`), sees their own statement and asks the agent about a line of it. Three reads serve that page:

- `load_accounts`: name, kind and currency of each account id.
- `account_statement`: the account's payments, refunds, chargebacks and (for a merchant) payouts, as one list of
  statement lines, newest first.
- `scoped_ledger`: a copy of the ledger that keeps only the account's records. The agent's tools and the verifier
  read that copy, so a query cannot return another customer's rows, whatever SQL the model writes.

Protections: the source ledger opens read-only (`open_ledger`, `mode=ro`) and every query uses parameters. The
scoped copy is a new file; the source is never written. A customer's copy keeps their transactions with the
refunds, chargebacks and applied FX of those transactions, the merchants they paid and no settlement. A merchant's
copy keeps the merchant's transactions, the customers who paid it, and its own settlements.
"""

from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from ledgerlens.api.ledger_service import open_ledger
from ledgerlens.tools.sql import major_amount

CUSTOMER_ID = re.compile(r"^C-[0-9]{4}$")
MERCHANT_ID = re.compile(r"^M-[0-9]{2}$")
STATEMENT_TYPES = ("Payment", "Refund", "Chargeback", "Payout")


@dataclass(frozen=True)
class Account:
    id: str
    kind: Literal["customer", "merchant"]
    name: str
    country: str
    currency: str

    @property
    def label(self) -> str:
        return f"{self.name} ({self.kind} {self.id})"


def account_kind(account_id: str) -> Literal["customer", "merchant"]:
    """The kind of an account id. Anything that is not a customer or merchant id is refused."""
    if CUSTOMER_ID.match(account_id):
        return "customer"
    if MERCHANT_ID.match(account_id):
        return "merchant"
    raise ValueError(f"not an account id: {account_id!r} (use C-nnnn or M-nn)")


def _rows(conn: sqlite3.Connection, sql: str, *params: Any) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def load_accounts(db_path: Path | str, account_ids: list[str]) -> list[Account]:
    """The accounts with these ids, in the given order. Ids missing from the ledger are left out."""
    accounts = []
    with closing(open_ledger(db_path)) as conn:
        for account_id in account_ids:
            if account_kind(account_id) == "customer":
                found = _rows(
                    conn,
                    "SELECT display_name AS name, country, billing_currency AS currency FROM customers WHERE id = ?",
                    account_id,
                )
            else:
                found = _rows(
                    conn,
                    "SELECT name, country, settlement_currency AS currency FROM merchants WHERE id = ?",
                    account_id,
                )
            if found:
                accounts.append(Account(account_id, account_kind(account_id), **found[0]))
    return accounts


def account_statement(db_path: Path | str, account_id: str) -> list[dict[str, Any]]:
    """The account's statement lines, newest first.

    Each line has `date` (YYYY-MM-DD), `at` (the full timestamp), `type` (Payment, Refund, Chargeback or Payout),
    `id`, `amount` (major units, text), `currency`, `status` (as stored), `counterparty`, `ids` (every ledger id on
    the line, for matching) and `record`: the row itself, plus `fx` (the rates applied to it) where there are any.
    """
    kind = account_kind(account_id)
    column = "t.customer_id" if kind == "customer" else "t.merchant_id"
    lines: list[dict[str, Any]] = []
    with closing(open_ledger(db_path)) as conn:
        fx_rows = _rows(
            conn,
            "SELECT f.* FROM fx_applied f JOIN transactions t ON t.id = f.transaction_id "
            f"WHERE {column} = ? ORDER BY f.applied_at",
            account_id,
        )
        payments = _rows(
            conn,
            "SELECT t.*, m.name AS merchant_name, c.display_name AS customer_name "
            "FROM transactions t JOIN merchants m ON m.id = t.merchant_id "
            f"JOIN customers c ON c.id = t.customer_id WHERE {column} = ?",
            account_id,
        )
        for p in payments:
            counterparty = p["merchant_name"] if kind == "customer" else p["customer_name"]
            fx = [f for f in fx_rows if f["transaction_id"] == p["id"] and f["kind"] == "charge"]
            lines.append(
                {
                    "date": p["created_at"][:10],
                    "at": p["created_at"],
                    "type": "Payment",
                    "id": p["id"],
                    "amount": major_amount(p["amount_minor"]),
                    "currency": p["currency"],
                    "status": p["status"],
                    "counterparty": counterparty,
                    "ids": [p["id"], p["merchant_id"], p["customer_id"]],
                    "record": {**p, "fx": fx},
                }
            )
        payment_by_id = {p["id"]: p for p in payments}
        refunds = _rows(
            conn,
            f"SELECT r.* FROM refunds r JOIN transactions t ON t.id = r.transaction_id WHERE {column} = ?",
            account_id,
        )
        for r in refunds:
            fx = [f for f in fx_rows if f["id"] == r["fx_applied_id"]]
            payment = payment_by_id.get(r["transaction_id"], {})
            lines.append(
                {
                    "date": r["created_at"][:10],
                    "at": r["created_at"],
                    "type": "Refund",
                    "id": r["id"],
                    "amount": major_amount(r["requested_amount_minor"]),
                    "currency": r["requested_currency"],
                    "status": r["status"],
                    "counterparty": payment.get("merchant_name" if kind == "customer" else "customer_name", ""),
                    "ids": [i for i in (r["id"], r["transaction_id"], r["fx_applied_id"]) if i],
                    "record": {**r, "fx": fx},
                }
            )
        chargebacks = _rows(
            conn,
            f"SELECT cb.* FROM chargebacks cb JOIN transactions t ON t.id = cb.transaction_id WHERE {column} = ?",
            account_id,
        )
        for cb in chargebacks:
            payment = payment_by_id.get(cb["transaction_id"], {})
            lines.append(
                {
                    "date": cb["opened_at"][:10],
                    "at": cb["opened_at"],
                    "type": "Chargeback",
                    "id": cb["id"],
                    "amount": major_amount(cb["amount_minor"]),
                    "currency": cb["currency"],
                    "status": cb["stage"],
                    "counterparty": payment.get("merchant_name" if kind == "customer" else "customer_name", ""),
                    "ids": [cb["id"], cb["transaction_id"]],
                    "record": cb,
                }
            )
        if kind == "merchant":
            for st in _rows(conn, "SELECT * FROM settlements WHERE merchant_id = ?", account_id):
                lines.append(
                    {
                        "date": st["period_end"],
                        "at": st["paid_at"] or st["expected_payout_date"],
                        "type": "Payout",
                        "id": st["id"],
                        "amount": major_amount(st["net_minor"]),
                        "currency": st["currency"],
                        "status": st["status"],
                        "counterparty": "",
                        "ids": [st["id"], st["merchant_id"]],
                        "record": st,
                    }
                )
    order = {name: n for n, name in enumerate(STATEMENT_TYPES)}
    lines.sort(key=lambda line: (line["date"], -order[line["type"]], line["id"]), reverse=True)
    return lines


def load_account_profile(db_path: Path | str, account_id: str) -> dict[str, Any]:
    """The account row: the customer, or the merchant with its category, FX plan and refund window."""
    table = "customers" if account_kind(account_id) == "customer" else "merchants"
    with closing(open_ledger(db_path)) as conn:
        found = _rows(conn, f"SELECT * FROM {table} WHERE id = ?", account_id)
    if not found:
        raise LookupError(f"no account {account_id}")
    return found[0]


def scoped_ledger(db_path: Path | str, account_id: str, out_path: Path | str) -> Path:
    """Writes to `out_path` a copy of the ledger with only the account's records, and returns the path.

    The source opens read-only and is copied with SQLite's backup; rows are then removed from the copy only.
    """
    kind = account_kind(account_id)
    out = Path(out_path)
    if out.exists():
        out.unlink()
    target = sqlite3.connect(out)
    with closing(open_ledger(db_path)) as source:
        source.backup(target)
    with closing(target):
        # The events table is append-only by trigger; the copy drops the triggers, filters, then restores them.
        triggers = target.execute("SELECT name, sql FROM sqlite_master WHERE type = 'trigger'").fetchall()
        for name, _ in triggers:
            target.execute(f'DROP TRIGGER "{name}"')
        owner = "customer_id" if kind == "customer" else "merchant_id"
        tx = "SELECT id FROM transactions"
        target.execute(f"DELETE FROM transactions WHERE {owner} <> ?", (account_id,))
        for table in ("refunds", "chargebacks", "fx_applied"):
            target.execute(f"DELETE FROM {table} WHERE transaction_id NOT IN ({tx})")
        if kind == "customer":
            target.execute("DELETE FROM settlements")
            target.execute("DELETE FROM customers WHERE id <> ?", (account_id,))
            target.execute("DELETE FROM merchants WHERE id NOT IN (SELECT merchant_id FROM transactions)")
        else:
            target.execute("DELETE FROM settlements WHERE merchant_id <> ?", (account_id,))
            target.execute("DELETE FROM customers WHERE id NOT IN (SELECT customer_id FROM transactions)")
            target.execute("DELETE FROM merchants WHERE id <> ?", (account_id,))
        target.execute(
            "DELETE FROM events WHERE aggregate_id NOT IN ("
            "SELECT id FROM transactions UNION SELECT id FROM refunds UNION SELECT id FROM chargebacks "
            "UNION SELECT id FROM settlements UNION SELECT id FROM merchants UNION SELECT id FROM customers)"
        )
        for _, sql in triggers:
            target.execute(sql)
        target.commit()
        target.execute("VACUUM")
    return out
