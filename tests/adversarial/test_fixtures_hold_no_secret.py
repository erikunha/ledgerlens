"""The fixtures of the exercises hold no secret: no key, no address of a real service and no personal data.

What they guarantee, and why: every fixture of the laboratory is synthetic, and a test reads every fixture and
expects no value of a key, no address of a real service and no personal data, because a payload that carries
one of the three is a payload that leaks something real into an attack that is meant to be a toy (the risk the
plan of the milestone names).

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[2] / "data" / "adversarial" / "fixtures"

# The shapes of a key, of an address of a real service and of personal data. The fixtures are synthetic, so
# none of the three has a reason to be in one.
_KEY_SHAPE = re.compile(r"sk-[A-Za-z0-9_-]{8,}|api[_-]?key|secret|password|bearer\s+[A-Za-z0-9._-]+", re.IGNORECASE)
_ADDRESS_SHAPE = re.compile(r"https?://|www\.|\b[\w-]+\.(com|net|org|io|dev|app)\b", re.IGNORECASE)
_PERSONAL_SHAPE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+|\b\d{3}[ .-]?\d{3}[ .-]?\d{3}\b")


def _fixtures() -> list[Path]:
    """Every fixture of the laboratory, and none of the record of the hashes."""
    return sorted(path for path in FIXTURES.glob("*.json") if path.name != "hashes.json")


def test_every_exercise_of_the_list_has_a_fixture() -> None:
    """The list of the exercises names a fixture per exercise, and the fixture is on the disk."""
    from ledgerlens.adversarial.exercises import EXERCISES

    on_disk = {path.name for path in _fixtures()}
    for exercise in EXERCISES:
        assert exercise.fixture in on_disk, f"the fixture of {exercise.exercise_id} is not on the disk"


def test_no_fixture_holds_a_key_an_address_or_personal_data() -> None:
    """A payload that carries one of the three is a payload that leaks something real."""
    for path in _fixtures():
        text = path.read_text(encoding="utf-8")
        assert not _KEY_SHAPE.search(text), f"the fixture {path.name} holds something that looks like a key"
        assert not _ADDRESS_SHAPE.search(text), f"the fixture {path.name} holds an address of a real service"
        assert not _PERSONAL_SHAPE.search(text), f"the fixture {path.name} holds personal data"


def test_every_fixture_names_the_exercise_and_the_surface_it_attacks() -> None:
    """A fixture says which exercise it is and which surface it attacks, so a reader can audit it."""
    for path in _fixtures():
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["exercise_id"], f"the fixture {path.name} names no exercise"
        assert data["surface"], f"the fixture {path.name} names no surface"
        assert data["payload"], f"the fixture {path.name} holds no payload"
