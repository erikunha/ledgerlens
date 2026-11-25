"""The gap of the markup wording: the merchant applies the markup below the reference rate.

What it guarantees, and why: the paragraph of the merchant markup of `cross-currency-refunds.md` says the
markup is applied below the reference rate, with one direction word, and the worked example of the corpus
recomputes through the calculator of the repository (gap 6 of the audit).

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

from ledgerlens.tools.calculator import compute

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "data" / "policies" / "cross-currency-refunds.md"


def test_the_paragraph_says_the_markup_is_applied_below_the_reference_rate() -> None:
    """The paragraph of the merchant markup has one direction word, and it is below."""
    text = POLICY.read_text(encoding="utf-8")
    paragraph = re.search(r"## Merchant markup \{#merchant-fx-markup\}\n\n(.+?)\n\n", text, re.S)
    assert paragraph, "the policy has no paragraph of the merchant markup"

    body = paragraph.group(1)
    assert "below the reference rate" in body
    assert "over the reference rate" not in body
    assert "multiplied by one minus the markup" in body


def test_the_worked_example_of_the_corpus_recomputes_through_the_calculator() -> None:
    """The worked example of the corpus recomputes through the calculator of the repository."""
    text = POLICY.read_text(encoding="utf-8")
    example = re.search(r"## Worked example \{#worked-example\}\n\n(.+?)\n\n", text, re.S)
    assert example, "the policy has no worked example"

    body = example.group(1)
    reference = re.search(r"reference rate is (\d+\.\d+)", body)
    applied = re.search(r"applied rate is (\d+\.\d+)", body)
    markup = re.search(r"applies a (\d+\.\d+)% markup", body)
    assert reference and applied and markup, "the worked example does not name the three numbers"
    result, _formula = compute(
        "implied_markup_pct",
        {"applied_rate": applied.group(1), "reference_rate": reference.group(1)},
    )
    assert Decimal(str(result)) == Decimal(markup.group(1))
