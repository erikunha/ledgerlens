"""The gap of the reason codes: FRD, NRC, NAD, DUP and OTH are internal codes of Acme.

What it guarantees, and why: the paragraph of the reason codes of `chargeback-handling.md` says that the
five codes are internal codes of Acme and that no card network uses them, and the mapping to the codes of
the networks lives in `docs/policies-of-acme.md` with the source and the date it was read (gap 2 of the
audit).

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "data" / "policies" / "chargeback-handling.md"
DOC = ROOT / "docs" / "policies-of-acme.md"


def test_the_paragraph_says_the_five_codes_are_internal_codes_of_acme() -> None:
    """The paragraph of the reason codes says the codes are internal to Acme and no network uses them."""
    text = POLICY.read_text(encoding="utf-8")
    paragraph = re.search(r"## Reason codes \{#reason-codes\}\n\n(.+?)\n\n", text, re.S)
    assert paragraph, "the policy has no paragraph of the reason codes"

    body = paragraph.group(1)
    assert "internal codes of Acme" in body
    assert "no card network uses them" in body


def test_the_mapping_to_the_codes_of_the_networks_is_in_the_document_with_the_source() -> None:
    """The mapping to the codes of the networks lives in the document, with the source and the date."""
    doc = DOC.read_text(encoding="utf-8")

    assert "13.1" in doc
    assert "13.3" in doc
    assert "12.6" in doc
    assert "Visa Core Rules" in doc
    assert "2026-11-25" in doc
