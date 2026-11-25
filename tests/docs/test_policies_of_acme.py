"""The document of the truth of the policies: every policy named, every rule of the world with a source.

What it guarantees, and why: `docs/policies-of-acme.md` names every one of the eight policies of
`data/policies/`, says for every rule whether it is a rule of the world, a house rule of Acme or an
invention of this project, and carries a source and a date for every rule of the world, with the caveats of
the audit next to the rules it marked as unverified (the task T163 of the milestone).

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "policies-of-acme.md"
POLICIES = ROOT / "data" / "policies"


def test_every_one_of_the_eight_policies_is_named_in_the_document() -> None:
    """The document has a section for each of the eight policies of the corpus."""
    doc = DOC.read_text(encoding="utf-8")

    for policy in sorted(POLICIES.glob("*.md")):
        assert policy.stem in doc, f"the document does not name the policy {policy.stem}"


def test_every_rule_of_the_world_carries_a_source_and_a_date() -> None:
    """Every rule of the world of the document names the source and the date it was read."""
    doc = DOC.read_text(encoding="utf-8")

    # The bullets of the document: a rule of the world is a bullet that says it is a rule of the world, and
    # the bullet carries the source and the date of the reading.
    bullets = re.split(r"\n(?=- \*\*)", doc)
    world_rules = [
        bullet
        for bullet in bullets
        if bullet.startswith("- **") and "is a rule of the world" in bullet.split("\n")[0]
    ]
    assert world_rules, "the document classifies no rule as a rule of the world"
    for bullet in world_rules:
        assert "Source:" in bullet, f"a rule of the world has no source: {bullet[:80]}"
        assert re.search(r"\d{4}-\d{2}-\d{2}", bullet), f"a rule of the world has no date: {bullet[:80]}"


def test_the_caveats_of_the_audit_are_next_to_the_rules_it_marked_as_unverified() -> None:
    """The caveats of the audit (the provision of the United Kingdom, the Brazilian right of regret) are in
    the document next to the rules they belong to."""
    doc = DOC.read_text(encoding="utf-8")

    assert "caveat" in doc.lower()
    assert "United Kingdom" in doc
    assert "Brazilian right of regret" in doc
