"""The gap of the rounding mode: the corpus names the mode as a choice of the platform, and the tie exists.

What it guarantees, and why: the rounding paragraphs of `fees-and-pricing.md` and of
`cross-currency-refunds.md` say that the mode of the rounding is the choice of the platform and what the
common commercial practice does with a tie, and the shipped ledger holds one settlement with an exact half
cent tie, so the rule of the rounding is exercised (gap 7 of the audit).

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import sqlite3
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "data" / "ledger.db"
FEES = ROOT / "data" / "policies" / "fees-and-pricing.md"
CROSS = ROOT / "data" / "policies" / "cross-currency-refunds.md"


def test_the_corpus_names_the_mode_as_a_choice_of_the_platform() -> None:
    """The two rounding paragraphs say the mode is the choice of the platform and name the common practice."""
    for policy in (FEES, CROSS):
        text = policy.read_text(encoding="utf-8")
        assert "the choice of the platform" in text, f"{policy.name} does not name the mode as a choice"
        assert "away from zero" in text, f"{policy.name} does not say what the common practice does with a tie"


def test_the_shipped_ledger_holds_a_settlement_with_an_exact_half_cent_tie() -> None:
    """One settlement of the shipped ledger has a processing fee that is an exact half cent tie.

    The fee of the settlement is 2.9 percent of the gross volume rounded half to even: a tie is a gross
    volume whose fee before the rounding ends in half a cent, and the even digit settles it.
    """
    conn = sqlite3.connect(LEDGER)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT id, gross_minor, fees_minor FROM settlements").fetchall()
    finally:
        conn.close()
    ties = []
    for row in rows:
        before = Decimal(row["gross_minor"]) * Decimal("0.029")
        if before % 1 == Decimal("0.5"):
            rounded = int(before.quantize(Decimal("1"), ROUND_HALF_EVEN))
            ties.append((row["id"], str(before), rounded, row["fees_minor"]))
    assert ties, "the shipped ledger holds no settlement with an exact half cent tie"
    for settlement_id, before, rounded, fees in ties:
        assert fees == rounded, (
            f"the settlement {settlement_id} has the fee {fees} and the tie of {before} rounds to {rounded}"
        )
