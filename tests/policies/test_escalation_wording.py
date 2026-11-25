"""The sentence of the wrong policy: a contradiction with a policy may mean that the policy is wrong.

What it guarantees, and why: the paragraph of the contradicted claims of `escalation-and-review.md` says
that a contradiction with a policy may mean that the policy is wrong, next to the sentence that the system
does not resolve contradictions by picking a side (the task T169 of the milestone).

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "data" / "policies" / "escalation-and-review.md"


def test_the_paragraph_says_a_contradiction_with_a_policy_may_mean_the_policy_is_wrong() -> None:
    """The paragraph of the contradicted claims carries the sentence of the wrong policy."""
    text = POLICY.read_text(encoding="utf-8")
    paragraph = re.search(r"## Contradicted claims \{#contradicted-claims\}\n\n(.+?)\n\n", text, re.S)
    assert paragraph, "the policy has no paragraph of the contradicted claims"

    body = paragraph.group(1)
    assert "may mean that the policy is wrong" in body
    assert "does not resolve contradictions by picking a side" in body
