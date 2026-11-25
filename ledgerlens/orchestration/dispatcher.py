"""The dispatcher: the policy of the run, the registry of the tools and the refusal of what is out of scope.

Why the permissions of a specialist are the intersection and never the union: the parent gives the run its scope and
the specialist narrows it. A union would let a specialist widen the scope of the run, and a specialist that widens
the scope turns a research question into a data leak (FR-004).

Why the dispatcher calls no tool when it refuses: the refusal is the answer, and a tool that was called anyway would
have read what it was not allowed to read.

Why the cap of the money is not checked here: the spend of a step is only known after the tool answered, and a check
that happens after the money was spent is a check that cannot undo the spend. The scheduler holds the money the run
spent and stops the run at the cap, naming it.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from ledgerlens.orchestration.specialists import SpecialistSpec
from ledgerlens.schemas import OrchestrationStep, StepResult

__all__ = ["DispatchRefused", "Permissions", "dispatch", "permissions_of"]

# What a tool of the studio returns: the identifiers of the evidence it produced, the amount it computed and what it
# spent. Every field is optional, because a tool that read something and computed nothing is a normal answer.
ToolAnswer = Mapping[str, Any]


class DispatchRefused(Exception):
    """The dispatcher refused the step, and the message says why.

    Why the class exists even though the refusal is also a result: the scheduler catches the class to stop the run,
    and a caller that wants the reason of a refusal reads it from the result of the step.
    """


@dataclass(frozen=True)
class Permissions:
    """What a run may do: the tools it may call, the accounts it may read and the most it may spend.

    Why the accounts are a set and not a scope of the branch: the run may read the accounts of its own case, and a
    specialist of the run may not read an account that the run may not read (FR-004).
    """

    tools: frozenset[str]
    accounts: frozenset[str]
    max_spend_usd: Decimal | None = None


def permissions_of(parent: Permissions, spec: SpecialistSpec) -> Permissions:
    """The permissions of a specialist: the intersection of the permissions of the parent with its own spec.

    Why the intersection of the accounts is the accounts of the parent when the parent names none: a run that names
    no account may read every account of the case, and a specialist that names accounts narrows that.
    """
    tools = parent.tools & frozenset(spec.tools)
    if parent.accounts:
        accounts = parent.accounts & frozenset(spec.accounts)
    else:
        accounts = frozenset(spec.accounts)
    spend = spec.max_spend_usd
    if parent.max_spend_usd is not None:
        spend = spend if spend is not None else parent.max_spend_usd
        spend = min(spend, parent.max_spend_usd)
    return Permissions(tools=tools, accounts=accounts, max_spend_usd=spend)


def dispatch(
    step: OrchestrationStep,
    *,
    permissions: Permissions,
    tools: Mapping[str, Callable[[Mapping[str, Any]], ToolAnswer]],
    spend: Decimal = Decimal("0"),
) -> StepResult:
    """The result of the step, and no tool call at all when the step is refused.

    Why the step is refused and not failed: a refusal is a decision of the code about what the run may do, and a
    failure is an error of a tool that ran. The two tell the reader different things about the run.

    Why the money the run spent so far is an argument: the spend of a step is the sum of the spends of the steps
    before it, and the scheduler is the one that holds it.
    """
    if step.tool is not None and step.tool not in permissions.tools:
        return StepResult(
            step_id=step.id,
            status="refused",
            error=f"the tool {step.tool} is not in the allowlist of the run",
            specialist=step.specialist,
        )
    if step.account is not None and step.account not in permissions.accounts:
        return StepResult(
            step_id=step.id,
            status="refused",
            error=f"the account {step.account} is outside the scope of the run",
            specialist=step.specialist,
        )
    if step.tool is None:
        # A step without a tool prepares nothing and decides nothing. It is an answer with no evidence, and it is
        # published as such instead of as a failure.
        return StepResult(step_id=step.id, status="ok", specialist=step.specialist)

    tool = tools.get(step.tool)
    if tool is None:
        return StepResult(
            step_id=step.id,
            status="refused",
            error=f"the registry of the tools has no tool named {step.tool}",
            specialist=step.specialist,
        )

    answer = tool(step.arguments)
    spent = answer.get("spend_usd")
    if spent is None:
        spent = Decimal("0")
    if not isinstance(spent, Decimal):
        return StepResult(
            step_id=step.id,
            status="failed",
            error=f"the spend of the step is a Decimal and not {type(spent).__name__}",
            specialist=step.specialist,
        )

    amount = answer.get("amount")
    evidence = answer.get("evidence_refs", [])
    return StepResult(
        step_id=step.id,
        status="ok",
        evidence_refs=[str(reference) for reference in evidence],
        spend_usd=spent,
        row=None if answer.get("row") is None else str(answer["row"]),
        amount=amount,
        specialist=step.specialist,
    )
