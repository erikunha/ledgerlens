"""The mapping of the exercises to the taxonomy of the threats: proposed, and never a certification.

What they guarantee, and why: (a) every exercise of the list names its surface, its layer and its reference of
the taxonomy in the mapping of `docs/adversarial-lab.md`, because a mapping that misses one of them is a
mapping a reader cannot check; (b) the page says the mapping is proposed and not a certification, because a
mapping presented as a compliance claim would be a false claim, and the laboratory of the repository exists to
avoid false claims.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import re
from pathlib import Path

from ledgerlens.adversarial.exercises import EXERCISES

PAGE = Path(__file__).resolve().parents[2] / "docs" / "adversarial-lab.md"


def test_every_exercise_names_its_surface_its_layer_and_its_reference() -> None:
    """The mapping names the three things of every exercise, and the source of the taxonomy."""
    text = PAGE.read_text(encoding="utf-8")

    for exercise in EXERCISES:
        assert exercise.exercise_id in text, f"the mapping does not name the exercise {exercise.exercise_id}"
    assert "OWASP" in text
    assert re.search(r"LLM\d{2}", text)


def test_the_mapping_is_proposed_and_not_a_certification() -> None:
    """A mapping presented as a compliance claim would be a false claim."""
    text = PAGE.read_text(encoding="utf-8")

    assert "proposal" in text
    assert "not a certification" in text
    assert "not a compliance claim" in text


def test_the_page_names_the_count_with_the_restriction_it_carries() -> None:
    """The count of the unauthorized actions says nothing about an attack that is not in the list."""
    text = PAGE.read_text(encoding="utf-8")

    assert "zero" in text
    assert "says nothing about an attack that is not in the list" in text
