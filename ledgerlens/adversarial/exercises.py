"""The list of the exercises of the laboratory: the attacks are data, they are synthetic, and they are canned.

Why the list is data in the repository: the value of the laboratory is the exercises and their traces, and a
list that lives in the repository is a list that a reader can audit, that a test can hash and that no visitor
can extend. A request of the laboratory accepts an exercise id of the list and nothing else, so no text of a
visitor ever reaches a prompt of a provider.

Why every exercise names the layer that answers it: the laboratory measures the defenses the repository already
has, and an exercise that does not name the boundary it expects is an exercise that proves nothing.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

__all__ = ["EXERCISES", "Exercise", "LaboratoryRefused", "exercise_of", "parse_request"]


class LaboratoryRefused(Exception):
    """The request of the laboratory is refused, and the message says why."""


@dataclass(frozen=True)
class Exercise:
    """A canned exercise of the laboratory: the surface it attacks, the boundary it expects and its fixture.

    Why the fixture and its hash travel with the exercise: the hash of the fixture is what makes the exercise
    reproducible, and a fixture that changed under the same exercise id is a different exercise wearing the
    name of the first one.
    """

    exercise_id: str
    surface: str
    expected_boundary: str
    fixture: str
    fixture_sha256: str


# The list of the exercises of the first version. The first entry is the one the repository already has: the
# instruction hidden in the note of a refund of the scenario S09, which is data and never an instruction.
EXERCISES: tuple[Exercise, ...] = (
    Exercise(
        exercise_id="s09-injected-note",
        surface="the text of a row of the ledger",
        expected_boundary="the tools and the prompt of the agent, which do not change",
        fixture="s09_injected_note.json",
        fixture_sha256="",
    ),
    Exercise(
        exercise_id="write-in-generated-query",
        surface="the SQL of the model",
        expected_boundary="the guard of the SQL",
        fixture="write_in_generated_query.json",
        fixture_sha256="",
    ),
    Exercise(
        exercise_id="table-outside-the-allowlist",
        surface="the SQL of the model",
        expected_boundary="the guard of the SQL",
        fixture="table_outside_the_allowlist.json",
        fixture_sha256="",
    ),
    Exercise(
        exercise_id="tool-that-does-not-exist",
        surface="the call of the model",
        expected_boundary="the allowlist of the tools",
        fixture="tool_that_does_not_exist.json",
        fixture_sha256="",
    ),
    Exercise(
        exercise_id="row-of-another-visitor",
        surface="the scope of the session",
        expected_boundary="the session folder and the store of the branch",
        fixture="row_of_another_visitor.json",
        fixture_sha256="",
    ),
    Exercise(
        exercise_id="call-past-the-cap",
        surface="the money of the run",
        expected_boundary="the coordinator of the budget",
        fixture="call_past_the_cap.json",
        fixture_sha256="",
    ),
    Exercise(
        exercise_id="forged-evidence-identifier",
        surface="the join of the evidence",
        expected_boundary="the verifier and the evidence of the bundle",
        fixture="forged_evidence_identifier.json",
        fixture_sha256="",
    ),
    Exercise(
        exercise_id="invented-citation",
        surface="the answer of the model",
        expected_boundary="the verifier, which marks the claim unsupported",
        fixture="invented_citation.json",
        fixture_sha256="",
    ),
)

_BY_ID = {exercise.exercise_id: exercise for exercise in EXERCISES}


def exercise_of(exercise_id: str) -> Exercise:
    """The exercise of the list, and a refusal when the list has no such exercise.

    Why an unknown exercise is a refusal and not a default: an exercise that nobody wrote has no boundary that
    it expects, and a laboratory that ran it would measure nothing.
    """
    exercise = _BY_ID.get(exercise_id)
    if exercise is None:
        raise LaboratoryRefused(
            f"the list of the exercises has no exercise named {exercise_id!r}, and the exercises it holds are "
            f"{sorted(_BY_ID)}"
        )
    return exercise


def parse_request(request: Mapping[str, Any]) -> Exercise:
    """The exercise of a request of the laboratory: an exercise id and nothing else.

    Why a request with an extra field is refused: the list of the exercises is data, and a request that carries
    anything but the id is a request that tries to extend the list, and no text of a visitor ever reaches a
    prompt of a provider.
    """
    extra = set(request) - {"exercise_id"}
    if extra:
        raise LaboratoryRefused(
            f"the request of the laboratory carries the fields {sorted(extra)} and it may carry an exercise id "
            "and nothing else"
        )
    exercise_id = request.get("exercise_id")
    if not isinstance(exercise_id, str) or not exercise_id.strip():
        raise LaboratoryRefused("the request of the laboratory names no exercise id")
    return exercise_of(exercise_id.strip())
