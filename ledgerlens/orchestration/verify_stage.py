"""The verification before the summary: the verifier of the repository decides the claims of the joined steps.

Why the verifier runs before the summary: a summary that nobody verified is a claim, and the repository publishes the
claims with the verdicts of the verifier next to them (FR-009 of the spec of the studio).

Why it stays deterministic: the verifier is code and a local cross-encoder, and a verifier that a model could change
is not a verifier. The studio never replaces it.

Why the verifier is an argument and not an import: the caller decides which verifier runs, and the test runs one that
it controls. A module that called the verifier itself would make every test of the studio depend on the model.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from ledgerlens.orchestration.join import JoinOutcome
from ledgerlens.schemas import StepResult

__all__ = ["VerificationOutcome", "VerificationRefused", "verify_before_summary"]

# The verifier of the repository: it receives the claims and the evidence and returns the verdicts. The signature is
# the one of `ledgerlens/verify/checks.py`, so the real verifier fits without a wrapper.
Verifier = Callable[[Sequence[Any]], Sequence[Any]]


class VerificationRefused(Exception):
    """The verification is refused, and the message says why."""


@dataclass(frozen=True)
class VerificationOutcome:
    """The verdicts of the verifier and the summary that they carry.

    Why the summary exists only when the verdicts do: a summary without the verdicts is a claim, and the stage
    refuses to publish one.
    """

    verdicts: tuple[Any, ...]
    summary: str | None

    @property
    def verified(self) -> bool:
        """Whether the summary exists, which it does only after the verdicts."""
        return self.summary is not None


def verify_before_summary(
    results: Sequence[StepResult],
    *,
    join: JoinOutcome,
    verifier: Verifier,
    summary_of: Callable[[Sequence[Any], JoinOutcome], str],
) -> VerificationOutcome:
    """The verdicts of the verifier over the claims of the joined steps, and the summary that follows them.

    Why the summary is built after the verdicts and not before: the summary of a run that was not verified is a
    sentence that nobody checked.
    """
    claims = _claims_of(results, join)
    verdicts = tuple(verifier(claims))
    if not verdicts:
        raise VerificationRefused(
            "the verifier returned no verdict, so the run has no summary: a summary without a verdict is a claim"
        )
    return VerificationOutcome(verdicts=verdicts, summary=summary_of(verdicts, join))


def _claims_of(results: Sequence[StepResult], join: JoinOutcome) -> list[Any]:
    """The claims of the joined steps, in the order of the steps.

    Why the claims come from the results and not from the model: the claims of a run are the claims of its steps,
    and the studio does not write claims of its own.
    """
    claims: list[Any] = []
    for result in results:
        for reference in result.evidence_refs:
            claims.append((result.step_id, reference, join.amounts.get(result.row or reference)))
    return claims
