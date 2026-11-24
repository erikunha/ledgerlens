"""The plan of a case of the studio: the steps of the case and the order they may run in.

Why the plan is validated before any step runs: a plan with a cycle has no order, and a dispatcher that starts a step
of a cycle waits for an answer that never comes. The validation costs nothing and it happens before the first tool
call, so a plan that cannot run never spends anything (FR-005).

Why the validation lives here and not in the dispatcher: the dispatcher runs the steps, and the rule that decides
whether a plan may run at all belongs to the plan.

Why a step that depends on a step that does not exist is refused: a plan that names a step nobody wrote is a plan
that cannot run, and running half of it is running a plan that nobody wrote.
"""

from __future__ import annotations

from ledgerlens.schemas import OrchestrationPlan, OrchestrationStep

__all__ = ["PlanRefused", "steps_in_order", "validate_plan"]


class PlanRefused(Exception):
    """The plan cannot run, and the message says why.

    Why the refusal is a class and not a string: the scheduler catches it and stops the run before any step ran,
    and a caller that wants to know whether a plan may run asks the question and catches the class.
    """


def validate_plan(plan: OrchestrationPlan) -> OrchestrationPlan:
    """The plan when it may run, and a refusal that names the reason when it may not.

    Why the plan comes back and not None: the caller hands the plan it wrote to the validation and gets the same
    plan back, so the validation is a gate and not a transformation.
    """
    ids = [step.id for step in plan.steps]
    duplicates = sorted({identifier for identifier in ids if ids.count(identifier) > 1})
    if duplicates:
        raise PlanRefused(f"the plan has two steps with the same id: {duplicates}")

    known = set(ids)
    for step in plan.steps:
        for dependency in step.depends_on:
            if dependency == step.id:
                raise PlanRefused(f"the step {step.id} depends on itself")
            if dependency not in known:
                raise PlanRefused(f"the step {step.id} depends on {dependency} and the plan has no such step")

    cycle = _cycle_of(plan)
    if cycle:
        raise PlanRefused(f"the plan has a cycle: {' -> '.join(cycle)}")
    return plan


def _cycle_of(plan: OrchestrationPlan) -> list[str]:
    """The steps of a cycle of the plan, or an empty list when the plan has none.

    Why the cycle is named and not only reported: a plan that cannot run and a plan that does not exist are two
    different problems, and the reader of the refusal needs to know which one it is.
    """
    depends: dict[str, list[str]] = {step.id: list(step.depends_on) for step in plan.steps}
    visiting: list[str] = []
    seen: set[str] = set()

    def _walk(step_id: str) -> list[str]:
        if step_id in visiting:
            return visiting[visiting.index(step_id) :]
        if step_id in seen:
            return []
        visiting.append(step_id)
        for dependency in depends.get(step_id, []):
            found = _walk(dependency)
            if found:
                return found
        visiting.pop()
        seen.add(step_id)
        return []

    for step in plan.steps:
        found = _walk(step.id)
        if found:
            return found
    return []


def steps_in_order(plan: OrchestrationPlan) -> list[OrchestrationStep]:
    """The steps of the plan in the order they may run: the dependencies of a step come before it.

    Why the order is computed and not taken from the plan: the plan is a graph and the order of the list that a
    model wrote is not an order, and a scheduler that trusts it runs a step before the step it waits for.
    """
    validate_plan(plan)
    ordered: list[OrchestrationStep] = []
    placed: set[str] = set()
    remaining = list(plan.steps)
    while remaining:
        ready = [step for step in remaining if all(dependency in placed for dependency in step.depends_on)]
        if not ready:
            # The plan was validated, so this cannot happen. The refusal names it anyway, because a scheduler that
            # loops for ever is worse than a scheduler that stops with a sentence.
            raise PlanRefused(f"the plan has no step that may run: {[step.id for step in remaining]}")
        for step in ready:
            ordered.append(step)
            placed.add(step.id)
        remaining = [step for step in remaining if step.id not in placed]
    return ordered
