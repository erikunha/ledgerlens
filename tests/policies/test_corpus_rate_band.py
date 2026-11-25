"""The audit test of the band of the rate: the applied rate against the reference of the same day.

What it guarantees, and why: an applied rate of the shipped ledger is inside the rounding band of four
decimals of the reference of the same day, and the calculator of the repository accepts every pair the ledger
contains, because the applied rate is rounded to four decimals and the rounding can put it a hair above the
reference (ADR-061, gap 4).

This test is written to FAIL before the correction of the guard of the calculator, because a test that passes
before the correction would prove nothing.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from decimal import Decimal
from pathlib import Path

from ledgerlens.sim.fx import FxTable
from ledgerlens.tools.calculator import CalcError

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "data" / "ledger.db"

# The rounding band of four decimals: the applied rate is rounded to four decimals, so the rounding can move
# it by half of the last place, and the band of the audit is one whole place of the fourth decimal.
BAND = Decimal("0.00005")


def _conversions() -> list[dict]:
    """Every conversion of the shipped ledger, with the applied rate and the reference of the same day."""
    conn = sqlite3.connect(LEDGER)
    conn.row_factory = sqlite3.Row
    fx = FxTable.from_file()
    try:
        rows = conn.execute(
            "SELECT id, kind, from_currency, to_currency, applied_rate, applied_at FROM fx_applied"
        ).fetchall()
    finally:
        conn.close()
    conversions = []
    for row in rows:
        day = date.fromisoformat(str(row["applied_at"])[:10])
        reference = fx.rate(day, row["from_currency"], row["to_currency"]).rate
        conversions.append(
            {
                "id": row["id"],
                "kind": row["kind"],
                "applied": Decimal(str(row["applied_rate"])),
                "reference": reference,
            }
        )
    return conversions


def test_every_applied_rate_of_the_ledger_is_inside_the_rounding_band_of_the_reference() -> None:
    """An applied rate above the reference of the same day is inside the rounding band of four decimals."""
    outside = [
        (row["id"], str(row["applied"]), str(row["reference"]))
        for row in _conversions()
        if row["applied"] > row["reference"] + BAND
    ]
    assert not outside, f"applied rates above the reference of the day outside the rounding band: {outside[:5]}"


def test_the_calculator_accepts_every_pair_the_ledger_contains() -> None:
    """The guard of the calculator accepts every conversion of the ledger, and an applied rate a hair above
    the reference is a rounding effect and not a swapped pair."""
    from ledgerlens.tools.calculator import guard_inputs

    refused: list[str] = []
    for row in _conversions():
        try:
            guard_inputs(
                "fx_markup_check",
                {
                    "units": "100.00",
                    "charge_rate": str(row["reference"]),
                    "refund_reference_rate": str(row["reference"]),
                    "refund_applied_rate": str(row["applied"]),
                },
            )
        except CalcError as exc:
            refused.append(f"{row['id']}: {exc}")
    assert not refused, f"the calculator refused conversions of the ledger: {refused[:5]}"
