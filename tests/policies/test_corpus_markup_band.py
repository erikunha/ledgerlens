"""The audit test of the band of the markup: the implied markup of a refund against the ceiling of the policy.

What it guarantees, and why: the implied markup of a refund of a merchant of the markup plan is inside the
band that `data/policies/fx-reference-rates.md` defines, because the ceiling of the policy is read with the
rounding band of the same policy, and a merchant whose contractual markup is exactly three percent is not
escalated for the rounding of the rate (ADR-061, gap 5).

This test is written to FAIL before the correction of the ceiling, because a test that passes before the
correction would prove nothing.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import date
from decimal import Decimal
from pathlib import Path

from ledgerlens.sim.fx import FxTable

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "data" / "ledger.db"
POLICY = ROOT / "data" / "policies" / "fx-reference-rates.md"


def _ceiling_and_band() -> tuple[Decimal, Decimal]:
    """The ceiling of the markup of the paragraph of the comparison, and the band when the paragraph names it.

    The ceiling is the percentage of the paragraph of the comparison. The band of the rounding tolerance of
    the policy counts only when the paragraph of the comparison reads the ceiling with it: a ceiling that is
    stated flat escalates the merchant whose contractual markup is exactly the ceiling, and the correction of
    the gap is the paragraph that reads the ceiling with the band.
    """
    text = POLICY.read_text(encoding="utf-8")
    comparison = re.search(
        r"## How to compare with the applied rate \{#comparing-with-applied\}\n\n(.+?)\n\n", text, re.S
    )
    assert comparison, "the policy has no paragraph of the comparison"
    paragraph = comparison.group(1)
    ceiling = re.search(r"up to (\d+\.\d+)%", paragraph)
    assert ceiling, "the paragraph of the comparison names no ceiling"
    band = Decimal("0")
    if "rounding" in paragraph.lower() or "band" in paragraph.lower():
        tolerance = re.search(r"## Rounding tolerance \{#rounding-tolerance\}\n\n(.+?)\n\n", text, re.S)
        assert tolerance, "the policy has no paragraph of the rounding tolerance"
        named = re.search(r"plus or minus (\w+) hundredths of a percentage point", tolerance.group(1))
        assert named, "the paragraph of the rounding tolerance names no band"
        hundredths = {"five": Decimal("0.05"), "ten": Decimal("0.10")}
        assert named.group(1) in hundredths, f"the band of the policy is not a number the test reads: {named.group(1)}"
        band = hundredths[named.group(1)]
    return Decimal(ceiling.group(1)), band


def _implied_markups() -> list[tuple[str, Decimal]]:
    """The implied markup of every refund of a merchant of the markup plan of the shipped ledger.

    The refunds of the planted scenarios of a markup above the limit are excluded: those are the violations
    the demo plants to be escalated, and they are outside the band by design (the scenario S13 is one of
    them, with the implied markup of 4.5 percent).
    """
    import json

    planted: set[str] = set()
    manifest = json.loads((ROOT / "data" / "scenarios.json").read_text(encoding="utf-8"))
    for scenario in manifest["scenarios"]:
        truth = scenario.get("truth", {})
        if "implied_markup_pct" in truth and Decimal(str(truth["implied_markup_pct"])) > Decimal("3.0"):
            planted.update(truth.get("refund_ids", []))
            planted.update(scenario.get("ids", {}).get("refund_ids", []))
    conn = sqlite3.connect(LEDGER)
    conn.row_factory = sqlite3.Row
    fx = FxTable.from_file()
    try:
        rows = conn.execute(
            "SELECT r.id, f.applied_rate, f.applied_at, f.from_currency, f.to_currency "
            "FROM refunds r "
            "JOIN fx_applied f ON f.id = r.fx_applied_id "
            "JOIN transactions t ON t.id = r.transaction_id "
            "JOIN merchants m ON m.id = t.merchant_id "
            "WHERE m.fx_plan = 'markup'"
        ).fetchall()
    finally:
        conn.close()
    markups = []
    for row in rows:
        if row["id"] in planted:
            continue
        day = date.fromisoformat(str(row["applied_at"])[:10])
        reference = fx.rate(day, row["from_currency"], row["to_currency"]).rate
        applied = Decimal(str(row["applied_rate"]))
        markups.append((row["id"], (1 - applied / reference) * 100))
    return markups


def test_the_implied_markup_of_every_refund_of_a_markup_merchant_is_inside_the_band_of_the_policy() -> None:
    """The ceiling of the policy is read with the band, and every refund of a markup merchant is inside it."""
    ceiling, band = _ceiling_and_band()
    limit = ceiling + band
    outside = [
        (refund_id, str(implied.quantize(Decimal("0.0001"))))
        for refund_id, implied in _implied_markups()
        if implied > limit
    ]
    assert not outside, (
        f"the implied markup of {len(outside)} refund(s) of a markup merchant is above the ceiling of "
        f"{ceiling}% plus the band of {band} points: {outside[:5]}"
    )
