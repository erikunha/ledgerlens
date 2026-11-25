"""The gap of the refund floor: the time to pay states the floor of fourteen days with the source of the law.

What it guarantees, and why: the paragraph of the time to pay of `refund-policy.md` states the floor of
fourteen days with the source of the law, and says that the window of the policy is a house rule that cannot
be narrower than the right of withdrawal (gap 8 of the audit). The held out set keeps the excerpt of its
generation, so the correction of the paragraph does not change the cases.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "data" / "policies" / "refund-policy.md"


def test_the_paragraph_states_the_floor_of_fourteen_days_with_the_source() -> None:
    """The paragraph of the time to pay names the floor, the source of the law and the date of the reading."""
    text = POLICY.read_text(encoding="utf-8")
    paragraph = re.search(r"## Time to pay \{#processing-time\}\n\n(.+?)(?:\n\n## |\Z)", text, re.S)
    assert paragraph, "the policy has no paragraph of the time to pay"

    body = paragraph.group(1)
    assert "fourteen days" in body
    assert "Directive 2011/83/EU" in body
    assert "2026-11-25" in body


def test_the_paragraph_says_the_window_is_a_house_rule_that_cannot_be_narrower_than_the_right() -> None:
    """The window of the policy is a house rule, and the floor of the right of withdrawal bounds it."""
    text = POLICY.read_text(encoding="utf-8")
    paragraph = re.search(r"## Time to pay \{#processing-time\}\n\n(.+?)(?:\n\n## |\Z)", text, re.S)
    assert paragraph, "the policy has no paragraph of the time to pay"

    body = paragraph.group(1)
    assert "house rule" in body
    assert "cannot be narrower than the right of withdrawal" in body
