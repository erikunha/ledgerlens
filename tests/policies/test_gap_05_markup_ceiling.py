"""The gap of the ceiling of the markup: the ceiling is read with the band, and no merchant at the ceiling is escalated.

What it guarantees, and why: the paragraph of the comparison of `fx-reference-rates.md` reads the ceiling of
3.0% with the rounding band of the same policy, and the implied markup of every refund of a merchant of the
markup plan is inside the ceiling read with the band, because a merchant whose contractual markup is exactly
three percent is not escalated for the rounding of the rate (gap 5 of the audit).

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

from tests.policies.test_corpus_markup_band import _implied_markups

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "data" / "policies" / "fx-reference-rates.md"


def test_the_paragraph_of_the_comparison_reads_the_ceiling_with_the_band() -> None:
    """The paragraph of the comparison names the rounding band next to the ceiling."""
    text = POLICY.read_text(encoding="utf-8")
    comparison = re.search(
        r"## How to compare with the applied rate \{#comparing-with-applied\}\n\n(.+?)\n\n", text, re.S
    )
    assert comparison, "the policy has no paragraph of the comparison"

    paragraph = comparison.group(1)
    assert "3.0%" in paragraph
    assert "band" in paragraph.lower(), "the paragraph of the comparison does not read the ceiling with the band"


def test_every_refund_of_a_markup_merchant_is_inside_the_ceiling_read_with_the_band() -> None:
    """The ceiling read with the band is 3.0% plus 0.05 points, and every refund of a markup merchant is inside it."""
    limit = Decimal("3.0") + Decimal("0.05")
    outside = [
        (refund_id, str(implied.quantize(Decimal("0.0001"))))
        for refund_id, implied in _implied_markups()
        if implied > limit
    ]
    assert not outside, f"refunds of markup merchants above the ceiling read with the band: {outside[:5]}"
