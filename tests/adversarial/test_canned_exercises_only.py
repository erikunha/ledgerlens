"""The list of the exercises of the laboratory: canned exercises only, and a request carries an id and nothing else.

What they guarantee, and why: (a) a request of the laboratory accepts an exercise id of the list and nothing
else, because the list of the exercises is data in the repository and no text of a visitor ever reaches a
prompt of a provider; (b) an unknown exercise id is refused, because an exercise that nobody wrote has no
boundary that it expects; (c) a request that carries an extra field is refused, because a request that carries
anything but the id is a request that tries to extend the list.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import pytest

from ledgerlens.adversarial.exercises import EXERCISES, LaboratoryRefused, exercise_of, parse_request


def test_the_list_of_the_exercises_is_data_and_the_first_exercise_is_the_one_of_the_repository() -> None:
    """The first exercise of the list is the instruction in the note of a refund, the one the repository has."""
    first = EXERCISES[0]

    assert first.exercise_id == "s09-injected-note"
    assert first.surface == "the text of a row of the ledger"
    assert all(exercise.fixture and exercise.expected_boundary for exercise in EXERCISES)


def test_an_unknown_exercise_id_is_refused() -> None:
    """An exercise that nobody wrote has no boundary that it expects."""
    with pytest.raises(LaboratoryRefused, match="no exercise named"):
        exercise_of("delete-the-ledger")


def test_a_request_carries_an_exercise_id_and_nothing_else() -> None:
    """A request with an extra field is a request that tries to extend the list."""
    exercise = parse_request({"exercise_id": "s09-injected-note"})
    assert exercise.exercise_id == "s09-injected-note"

    with pytest.raises(LaboratoryRefused, match="nothing else"):
        parse_request({"exercise_id": "s09-injected-note", "payload": "a text of a visitor"})


def test_a_request_with_no_exercise_id_is_refused() -> None:
    """A request that names no exercise is a request of nothing."""
    with pytest.raises(LaboratoryRefused, match="no exercise id"):
        parse_request({})
