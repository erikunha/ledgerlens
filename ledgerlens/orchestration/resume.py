"""The resume of a suspended run: it continues from what the run already did.

Why a resume reuses the output of a step that completed: the step was paid for, and a run that repeats it spends
again for the same answer (FR-008).

Why a resume runs again only a step that is idempotent and read-only: a step that writes is an effect, and an effect
that happens twice corrupts the branch of the visitor, which the sandbox protects with an idempotent commit (ADR-021).

Why a resume refuses a step whose snapshot or whose configuration version changed: the step was computed over another
snapshot or with another version of the code, and its answer is an answer about something else.

Why a resume runs again a step whose inputs changed: the answer of the journal is an answer about other arguments,
and a step that only reads is safe to repeat.

Why a resume never rehydrates a credential: the key of a visitor lives in its session, and a resume that carried it
across the restart would break the vault of the live mode (ADR-037).

Why the plan of the resume is a value and not a run: the caller has to see which steps are reused, which ones run
again and which ones are refused before anything runs.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ledgerlens.orchestration.journal import Journal, digest_of
from ledgerlens.schemas import OrchestrationPlan, OrchestrationStep

__all__ = ["ResumePlan", "ResumeRefused", "digest_of_inputs", "inputs_of", "plan_resume"]

# The keys of the arguments of a step that would carry a credential. A resume never rehydrates one of them.
CREDENTIAL_KEYS = ("api_key", "apikey", "authorization", "cookie", "set-cookie", "x-api-key")


class ResumeRefused(Exception):
    """The resume is refused, and the message says why."""


@dataclass(frozen=True)
class ResumePlan:
    """What a resume does: the steps it reuses, the steps it runs again and the steps it refuses."""

    reused: tuple[str, ...]
    to_run: tuple[str, ...]
    refused: tuple[tuple[str, str], ...]
    outputs: Mapping[str, Mapping[str, Any]]

    @property
    def refused_steps(self) -> tuple[str, ...]:
        """The names of the steps that the resume refused."""
        return tuple(step_id for step_id, _ in self.refused)


def plan_resume(
    plan: OrchestrationPlan,
    *,
    journal: Journal,
    snapshot: str,
    config_version: str,
) -> ResumePlan:
    """The plan of the resume of a suspended run.

    Why the snapshot and the configuration version are arguments and not read from the journal: they are the state of
    the world now, and the journal is what the world was then.

    Why a step whose inputs changed runs again instead of being refused: a step that only reads is safe to repeat, and
    the answer of the journal is an answer about other arguments, so reusing it would answer a question that nobody
    asked. A step that writes never reaches this branch: it is refused before.
    """
    reused: list[str] = []
    to_run: list[str] = []
    refused: list[tuple[str, str]] = []
    outputs: dict[str, Mapping[str, Any]] = {}

    for step in plan.steps:
        _refuse_the_credentials(step)
        entry = journal.completed(step.id)
        if entry is None:
            to_run.append(step.id)
            continue
        if entry.snapshot != snapshot:
            refused.append((step.id, f"the step read the snapshot {entry.snapshot} and the run reads {snapshot}"))
            continue
        if entry.config_version != config_version:
            refused.append(
                (
                    step.id,
                    f"the step ran with the configuration {entry.config_version} and the run runs "
                    f"{config_version}",
                )
            )
            continue
        if not _is_read_only(step):
            refused.append((step.id, "the step is not read-only, so it may not run again"))
            continue
        if entry.inputs_digest != digest_of_inputs(step):
            to_run.append(step.id)
            continue
        reused.append(step.id)
        outputs[step.id] = entry.output

    return ResumePlan(reused=tuple(reused), to_run=tuple(to_run), refused=tuple(refused), outputs=outputs)


def _refuse_the_credentials(step: OrchestrationStep) -> None:
    """Refuses a step whose arguments carry a credential.

    Why the refusal is here and not in the dispatcher: the dispatcher runs a step of a run that is alive, and a resume
    is the path where a secret of the session of a visitor could travel to a machine that does not have it.
    """
    for key in step.arguments:
        if str(key).lower() in CREDENTIAL_KEYS:
            raise ResumeRefused(
                f"the step {step.id} carries the credential {key!r} and a resume never rehydrates a credential"
            )


def _is_read_only(step: OrchestrationStep) -> bool:
    """Whether the step only reads.

    Why the list is in the code and not in the configuration: a step that may write and that nobody marked as such is
    a step that writes twice, and the list is a rule of safety.
    """
    return step.tool in {"query_ledger", "get_ledger_record", "search_policies", "get_reference_fx", "recall_cases"}


def inputs_of(step: OrchestrationStep) -> dict[str, Any]:
    """The canonical inputs of a step: its arguments, its tool and its account.

    Why the canonical form exists: the journal stores the digest of the inputs of a step, and a digest of a form that
    changes with the order of the keys of a dictionary is a digest that never matches.
    """
    return {"arguments": dict(step.arguments), "tool": step.tool, "account": step.account}


def digest_of_inputs(step: OrchestrationStep) -> str:
    """The digest of the inputs of a step, for the comparison with the entry of the journal."""
    return digest_of(inputs_of(step))
