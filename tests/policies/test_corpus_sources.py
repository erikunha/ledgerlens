"""The audit test of the sources: a paragraph that names an external body names the source and the date.

What it guarantees, and why: a paragraph of a policy that names the card network, the central bank or the law
names the source of the rule and the date it was read in the same paragraph, because a rule of the world
without a source is a rule of the fiction enforced as if it were a rule of the world (ADR-061).

This test is written to FAIL before the corrections of the corpus, because a test that passes before the
correction would prove nothing.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLICIES = ROOT / "data" / "policies"

# The external bodies a policy may name: the card network, the central bank and the law. A paragraph that
# names one of them is a paragraph about the world, and a paragraph about the world names its source.
EXTERNAL_BODY = re.compile(
    r"card network|central bank|European Central Bank|\bECB\b|\bVisa\b|\bMastercard\b|the law\b|statutory",
    re.IGNORECASE,
)

# The shape of a source with a date: a date of the reading, in the same paragraph. The word source alone is
# not enough, because it appears in the prose of the policies with no date next to it.
SOURCE_AND_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _paragraphs(text: str) -> list[str]:
    """The paragraphs of a policy, split on the blank lines, with the headings kept out."""
    return [paragraph.strip() for paragraph in re.split(r"\n\s*\n", text) if paragraph.strip()]


def test_a_paragraph_that_names_an_external_body_names_the_source_and_the_date() -> None:
    """The corpus never states what the world requires without the source and the date of the reading."""
    offenders: list[str] = []
    for policy in sorted(POLICIES.glob("*.md")):
        for paragraph in _paragraphs(policy.read_text(encoding="utf-8")):
            if paragraph.startswith("#"):
                continue
            if EXTERNAL_BODY.search(paragraph) and not SOURCE_AND_DATE.search(paragraph):
                first = paragraph.splitlines()[0][:80]
                offenders.append(f"{policy.name}: {first}")
    assert not offenders, "paragraphs that name an external body without the source and the date:\n" + "\n".join(
        offenders
    )
