"""The audit test of the corpus against the simulator: a rule of the world the simulator contradicts.

What it guarantees, and why: a policy that states a rule of the money agrees with the simulator that produces
the money, and the first case is the rule of the negative net: the corpus of the generation said that a
negative net gets no payout, and the simulator paid two such settlements (ADR-061, gap 3).

This test is written to FAIL before the correction of the rule, because a test that passes before the
correction would prove nothing.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "data" / "ledger.db"
POLICY = ROOT / "data" / "policies" / "settlement-schedule.md"


def _negative_net_settlements() -> list[dict]:
    """The settlements of the shipped ledger whose net is negative, with the status of each one."""
    conn = sqlite3.connect(LEDGER)
    conn.row_factory = sqlite3.Row
    try:
        return [
            dict(row)
            for row in conn.execute(
                "SELECT id, merchant_id, net_minor, status FROM settlements WHERE net_minor < 0"
            ).fetchall()
        ]
    finally:
        conn.close()


def _the_corpus_rule() -> str:
    """The paragraph of the corpus about the negative net, read from the policy."""
    text = POLICY.read_text(encoding="utf-8")
    match = re.search(r"## Negative balance \{#negative-net\}\n\n(.+?)\n\n", text, re.S)
    assert match, "the policy has no paragraph about the negative net"
    return match.group(1)


def test_a_negative_net_settlement_agrees_with_the_rule_of_the_corpus() -> None:
    """A negative net either has no payout or is carried, and the corpus states the same rule.

    The rule of the corpus: a negative net has no payout and the balance is carried into the next
    settlement of the merchant. The test reads the settlements of the shipped ledger and expects every
    negative net to have no payout and to be carried, and it reads the corpus and expects the same rule.
    """
    rule = _the_corpus_rule()
    settlements = _negative_net_settlements()

    assert settlements, "the shipped ledger has no negative net settlement: the case of the audit is gone"
    assert "no payout is made" in rule, "the corpus does not state the rule of the negative net"
    assert "carried" in rule, "the corpus does not state the carry of the balance"
    paid = [row["id"] for row in settlements if row["status"] == "paid"]
    assert not paid, (
        f"the corpus says a negative net gets no payout and the simulator paid {paid}: "
        "the corpus and the simulator disagree (gap 3 of the audit)"
    )
    conn = sqlite3.connect(LEDGER)
    conn.row_factory = sqlite3.Row
    try:
        for row in settlements:
            following = conn.execute(
                "SELECT id, gross_minor, refunds_minor, fees_minor, net_minor FROM settlements WHERE "
                "merchant_id = ? AND period_start > (SELECT period_end FROM settlements WHERE id = ?) "
                "ORDER BY period_start LIMIT 1",
                (row["merchant_id"], row["id"]),
            ).fetchone()
            assert following is not None, (
                f"the negative net of {row['id']} was not carried: the merchant has no next settlement"
            )
            expected = (
                following["gross_minor"] - following["refunds_minor"] - following["fees_minor"]
                + row["net_minor"]
            )
            assert following["net_minor"] == expected, (
                f"the negative net of {row['id']} was not carried into {following['id']}: "
                f"the net is {following['net_minor']} and the carry of {row['net_minor']} gives {expected}"
            )
    finally:
        conn.close()
