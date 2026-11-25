"""The verification before the summary: the verifier decides and the summary follows.

What they guarantee, and why: (a) the summary of a run exists only after the verdicts of the verifier, because a
summary without a verdict is a claim that nobody checked; (b) the verifier is deterministic and the studio never
replaces it, because the verifier of the repository is code and a local cross-encoder; (c) a verification that returns
no verdict is refused and no summary is published.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import pytest

from ledgerlens.orchestration.join import JoinOutcome
from ledgerlens.orchestration.verify_stage import VerificationRefused, verify_before_summary
from ledgerlens.schemas import StepResult


def _results() -> list[StepResult]:
    """The results of the steps that were joined."""
    return [
        StepResult(
            step_id="read",
            status="ok",
            evidence_refs=["sql:1"],
            row="TX-1",
            amount=None,
        )
    ]


def _join() -> JoinOutcome:
    """The join of the results."""
    return JoinOutcome(amounts={}, contested=(), results=tuple(_results()))


def test_the_summary_exists_only_after_the_verdicts_of_the_verifier() -> None:
    """The verifier runs first, and the summary is built out of its verdicts."""
    seen: list[str] = []

    def _verifier(claims: list[object]) -> list[str]:
        seen.append("called")
        return ["supported"]

    def _summary(verdicts: list[object], join: JoinOutcome) -> str:
        return f"the summary of {len(verdicts)} verdicts"

    outcome = verify_before_summary(
        _results(),
        join=_join(),
        verifier=_verifier,
        summary_of=_summary,
    )

    assert seen == ["called"]
    assert outcome.verified is True
    assert outcome.summary == "the summary of 1 verdicts"


def test_a_verification_without_a_verdict_is_refused_and_publishes_no_summary() -> None:
    """A summary without a verdict is a claim, and the stage refuses to publish one."""
    with pytest.raises(VerificationRefused, match="no verdict"):
        verify_before_summary(
            _results(),
            join=_join(),
            verifier=lambda claims: [],
            summary_of=lambda verdicts, join: "a summary nobody checked",
        )


def test_the_claims_of_the_verification_come_from_the_results() -> None:
    """The studio does not write claims of its own: they are the claims of its steps."""
    captured: list[object] = []

    def _verifier(claims: list[object]) -> list[str]:
        captured.extend(claims)
        return ["supported"]

    verify_before_summary(
        _results(),
        join=_join(),
        verifier=_verifier,
        summary_of=lambda verdicts, join: "the summary",
    )

    assert captured == [("read", "sql:1", None)]
