"""The studio of the orchestration: the plan of a case, the specialists, the dispatcher and the scheduler.

Why it exists: the design package proposes a dispatcher that sends work to specialists and a graph that is
checkpointed and resumed, and the repository ships a single agent with a deterministic verifier. This package is the
proposal, ported, and it is experimental: it is behind a flag that is off in the shipped configuration and it only
opens for an experiment that is registered before it runs (ADR-P007).

Why it never replaces the verifier: the verifier decides the claims of a run and it stays deterministic. A specialist
prepares the evidence of a part of the question and never decides what the answer is.

Why the package never widens a scope: the permissions of a specialist are the intersection of the permissions of its
parent with the permissions of its own spec, and a specialist that widens the scope of a run turns a research question
into a data leak.

Why the money is a `Decimal` everywhere: the spend of a step is money, and an unknown price leaves the money
unmeasured instead of zero.
"""

from __future__ import annotations

__all__ = [
    "SPECIALISTS",
    "DispatchRefused",
    "JoinOutcome",
    "JoinRefused",
    "Journal",
    "JournalEntry",
    "JournalRefused",
    "Permissions",
    "PlanRefused",
    "ResumePlan",
    "ResumeRefused",
    "RunOutcome",
    "SpecialistSpec",
    "StepResult",
    "StudioRefused",
    "VerificationOutcome",
    "VerificationRefused",
    "digest_of",
    "digest_of_inputs",
    "dispatch",
    "inputs_of",
    "join_results",
    "open_studio",
    "permissions_of",
    "plan_resume",
    "run_plan",
    "spec_of",
    "steps_in_order",
    "studio_manifest",
    "validate_plan",
    "verify_before_summary",
]
