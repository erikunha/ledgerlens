"""The hash of a fixture: what makes an exercise reproducible, recorded and checked.

What they guarantee, and why: (a) the hash of every fixture of the list is recorded, because an exercise whose
fixture is not hashed is an exercise that is not reproducible; (b) the hash of a fixture changes when the
fixture changes, because a fixture that changed under the same exercise id is a different attack wearing the
name of the first one; (c) the record of the hashes and the bytes of the fixtures agree, because a record that
does not match the bytes is a record of another exercise.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from ledgerlens.adversarial.exercises import EXERCISES
from ledgerlens.adversarial.hashes import check_hashes, compute_hashes, fixture_hash, recorded_hashes

FIXTURES = Path(__file__).resolve().parents[2] / "data" / "adversarial" / "fixtures"


def test_the_hash_of_every_fixture_of_the_list_is_recorded() -> None:
    """Every fixture the list names has its hash in the record."""
    recorded = recorded_hashes(FIXTURES)
    for exercise in EXERCISES:
        assert exercise.fixture in recorded, f"the fixture of {exercise.exercise_id} has no recorded hash"


def test_the_record_of_the_hashes_and_the_bytes_of_the_fixtures_agree() -> None:
    """A record that does not match the bytes is a record of another exercise."""
    assert check_hashes(FIXTURES) == []


def test_the_hash_of_a_fixture_changes_when_the_fixture_changes(tmp_path) -> None:
    """A fixture that changed under the same exercise id is a different attack."""
    copy = tmp_path / "fixtures"
    shutil.copytree(FIXTURES, copy)
    before = compute_hashes(copy)

    target = copy / "invented_citation.json"
    target.write_text(target.read_text(encoding="utf-8").replace("approved", "denied"), encoding="utf-8")
    after = compute_hashes(copy)

    assert before["invented_citation.json"] != after["invented_citation.json"]
    assert fixture_hash(target) == after["invented_citation.json"]
    assert check_hashes(copy), "the record of the hashes did not move with the fixture"
