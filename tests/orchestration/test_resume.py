"""The resume of a suspended run: what it reuses, what it runs again and what it refuses.

What they guarantee, and why: (a) the output of a step that completed is reused and not computed again, because the
step was paid for; (b) a step that is not read-only is never run again, because an effect that happens twice corrupts
the branch of the visitor; (c) a step whose snapshot or whose configuration version changed is refused, because its
answer is an answer about something else; (d) a step whose inputs changed runs again, because the answer of the
journal is an answer about other arguments; (e) a resume never rehydrates a credential of a visitor.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import pytest

from ledgerlens.orchestration.journal import Journal, digest_of
from ledgerlens.orchestration.resume import ResumeRefused, inputs_of, plan_resume
from ledgerlens.schemas import OrchestrationPlan, OrchestrationStep

SNAPSHOT = "a" * 64
OTHER_SNAPSHOT = "b" * 64


def _journal(
    step: OrchestrationStep,
    *,
    snapshot: str = SNAPSHOT,
    config_version: str = "v1",
    inputs: dict[str, object] | None = None,
) -> Journal:
    """A journal with one step that completed.

    Why the journal records the canonical inputs of the step: the resume reuses an output only when the inputs of the
    step are the same as they were, and the digest of the inputs is what says so.
    """
    journal = Journal()
    output = {"rate": "5.41"}
    journal.record(
        step_id=step.id,
        inputs=inputs_of(step) if inputs is None else inputs,
        output=output,
        output_digest=digest_of(output),
        status="ok",
        snapshot=snapshot,
        config_version=config_version,
    )
    return journal


def _plan(*steps: OrchestrationStep) -> OrchestrationPlan:
    """The plan of the steps that the test hands over."""
    return OrchestrationPlan(steps=list(steps), snapshot=SNAPSHOT)


def test_a_resume_reuses_the_output_of_a_step_that_completed() -> None:
    """The step was paid for, and a run that repeats it spends again for the same answer."""
    step = OrchestrationStep(id="read", goal="read the rate", tool="get_reference_fx")
    plan = _plan(step)

    resume = plan_resume(plan, journal=_journal(step), snapshot=SNAPSHOT, config_version="v1")

    assert resume.reused == ("read",)
    assert resume.to_run == ()
    assert resume.outputs["read"] == {"rate": "5.41"}


def test_a_resume_runs_again_the_step_that_never_completed() -> None:
    """A step that did not answer has to run again."""
    step = OrchestrationStep(id="read", goal="read the rate", tool="get_reference_fx")
    plan = _plan(step)

    resume = plan_resume(plan, journal=Journal(), snapshot=SNAPSHOT, config_version="v1")

    assert resume.to_run == ("read",)
    assert resume.reused == ()


def test_a_resume_runs_again_the_step_whose_inputs_changed() -> None:
    """The answer of the journal is an answer about other arguments, and a step that only reads is safe to repeat."""
    previous = OrchestrationStep(
        id="read", goal="read the rate", tool="get_reference_fx", arguments={"currency": "BRL"}
    )
    current = OrchestrationStep(
        id="read", goal="read the rate", tool="get_reference_fx", arguments={"currency": "USD"}
    )
    plan = _plan(current)

    resume = plan_resume(plan, journal=_journal(previous), snapshot=SNAPSHOT, config_version="v1")

    assert resume.reused == ()
    assert resume.to_run == ("read",)


def test_a_resume_never_runs_again_a_step_that_writes() -> None:
    """An effect that happens twice corrupts the branch of the visitor."""
    step = OrchestrationStep(id="commit", goal="commit the change", tool="calculate")
    plan = _plan(step)

    resume = plan_resume(plan, journal=_journal(step), snapshot=SNAPSHOT, config_version="v1")

    assert resume.reused == ()
    assert resume.refused_steps == ("commit",)
    assert "not read-only" in dict(resume.refused)["commit"]


def test_a_resume_refuses_a_step_whose_snapshot_changed() -> None:
    """The step was computed over another snapshot, and its answer is an answer about something else."""
    step = OrchestrationStep(id="read", goal="read the rate", tool="get_reference_fx")
    plan = _plan(step)

    resume = plan_resume(plan, journal=_journal(step), snapshot=OTHER_SNAPSHOT, config_version="v1")

    assert resume.refused_steps == ("read",)
    assert "snapshot" in dict(resume.refused)["read"]


def test_a_resume_refuses_a_step_whose_configuration_version_changed() -> None:
    """The step ran with another version of the code."""
    step = OrchestrationStep(id="read", goal="read the rate", tool="get_reference_fx")
    plan = _plan(step)

    resume = plan_resume(plan, journal=_journal(step), snapshot=SNAPSHOT, config_version="v2")

    assert resume.refused_steps == ("read",)
    assert "configuration" in dict(resume.refused)["read"]


def test_a_resume_never_rehydrates_a_credential() -> None:
    """The key of a visitor lives in its session and never travels to a machine that does not have it."""
    step = OrchestrationStep(
        id="read",
        goal="read the rate",
        tool="get_reference_fx",
        arguments={"api_key": "sk-visitor-key-not-real"},
    )
    plan = _plan(step)

    with pytest.raises(ResumeRefused, match="never rehydrates a credential"):
        plan_resume(plan, journal=_journal(step), snapshot=SNAPSHOT, config_version="v1")
