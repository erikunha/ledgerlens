"""The gap of the negative net: the corpus and the simulator state the same rule.

What it guarantees, and why: the corpus of `settlement-schedule.md` states that a negative net is paid and
the balance is carried into the next settlement, and the settlements of the shipped ledger follow the same
rule: every negative net is paid and the balance is carried into the net of the next settlement of the
merchant (gap 3 of the audit).

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "data" / "ledger.db"
POLICY = ROOT / "data" / "policies" / "settlement-schedule.md"


def test_the_corpus_states_that_a_negative_net_has_no_payout_and_is_carried() -> None:
    """The paragraph of the negative net says the payout is withheld and the balance is carried."""
    text = POLICY.read_text(encoding="utf-8")
    paragraph = re.search(r"## Negative balance \{#negative-net\}\n\n(.+?)\n\n", text, re.S)
    assert paragraph, "the policy has no paragraph of the negative net"

    body = paragraph.group(1)
    assert "no payout is made" in body
    assert "carried into the next settlement" in body


def test_every_negative_net_of_the_shipped_ledger_has_no_payout_and_is_carried() -> None:
    """Every negative net of the shipped ledger has no payout, and the balance is in the net of the next."""
    conn = sqlite3.connect(LEDGER)
    conn.row_factory = sqlite3.Row
    try:
        negatives = conn.execute(
            "SELECT id, merchant_id, net_minor, status FROM settlements WHERE net_minor < 0"
        ).fetchall()
        assert negatives, "the shipped ledger has no negative net settlement: the case of the audit is gone"
        for row in negatives:
            assert row["status"] == "scheduled", f"the negative net of {row['id']} was paid and it must not be"
            following = conn.execute(
                "SELECT id, gross_minor, refunds_minor, fees_minor, net_minor FROM settlements WHERE "
                "merchant_id = ? AND period_start > (SELECT period_end FROM settlements WHERE id = ?) "
                "ORDER BY period_start LIMIT 1",
                (row["merchant_id"], row["id"]),
            ).fetchone()
            assert following is not None, f"the negative net of {row['id']} has no next settlement to carry it"
            expected = (
                following["gross_minor"] - following["refunds_minor"] - following["fees_minor"] + row["net_minor"]
            )
            assert following["net_minor"] == expected, (
                f"the balance of {row['id']} was not carried into {following['id']}: "
                f"the net is {following['net_minor']} and the carry gives {expected}"
            )
    finally:
        conn.close()
