"""The gap of the response deadline: the window of ten to fourteen days is the deadline of Acme.

What it guarantees, and why: the paragraph of the response deadline of `chargeback-handling.md` says that
the window of ten to fourteen days is the deadline of Acme for the response of the merchant, and not the
deadline of the card network, and the window of the network lives in `docs/policies-of-acme.md` with the
source and the date it was read (gap 1 of the audit).

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "data" / "policies" / "chargeback-handling.md"
DOC = ROOT / "docs" / "policies-of-acme.md"


def test_the_paragraph_says_the_window_is_the_deadline_of_acme_and_not_of_the_network() -> None:
    """The paragraph of the response deadline names Acme as the owner of the window of ten to fourteen days."""
    text = POLICY.read_text(encoding="utf-8")
    paragraph = re.search(r"## Response deadline \{#response-deadline\}\n\n(.+?)\n\n", text, re.S)
    assert paragraph, "the policy has no paragraph of the response deadline"

    body = paragraph.group(1)
    assert "ten to fourteen days" in body
    assert "deadline of Acme" in body
    assert "not the deadline of the card network" in body


def test_the_window_of_the_network_is_in_the_document_with_the_source_and_the_date() -> None:
    """The window of the network lives in the document of the policies of Acme, with the source and the date."""
    doc = DOC.read_text(encoding="utf-8")

    assert "thirty calendar days" in doc
    assert "Mastercard" in doc
    assert "Visa Core Rules" in doc
    assert "2026-11-25" in doc
