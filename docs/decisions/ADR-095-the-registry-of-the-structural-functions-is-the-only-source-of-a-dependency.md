---
type: adr
status: accepted
date: 2026-11-24
---

# ADR-095: The registry of the structural functions is the only source of a dependency

Status: accepted. Date: 2026-11-24.

## Context

The design package
[LL-V3-R19-02, causal counterfactual interventions](../v3/advanced-specs/R19-02-causal-counterfactual-interventions.md)
proposes a registry of the structural functions of the synthetic world, a typed intervention over that registry,
and a report that separates a difference that the registry explains, a difference that the registry does not
explain, and a statement of cause that nobody can check. The repository can change one field of a branch and
read the difference between two states, but it cannot say what caused the difference, and it cannot say what
would have happened if a rule had been different.

The milestone of [specs/020](../../specs/020-r19-causal-counterfactual-interventions/spec.md) adds the engine,
and the rule that decides everything is that the registry is the only source of a dependency. The largest risk
of the milestone is a silent cause: a tool that says "because" when it cannot is worse than a tool that says
nothing.

## Decision

**The registry is written by hand over the code of the repository, a node that is not in the registry is never
a descendant, a change without a declared edge is reported as `unknown` with the missing edge named, no cause
is learned from an observation, and every statement of the report is a statement about the simulation.**

1. **The registry is written by hand over the code of the repository.** It declares the dependencies of the
   synthetic world over the code that already exists: the exchange rate, the settlement, the rules of the
   policies, the calculator and the escalation. Every edge names the two nodes it connects, the function that
   implements it and the reason of the edge, so a reader can open the edge and find the code.
2. **A node that is not in the registry is never a descendant of anything.** Nothing is learned from an
   observation: only a declared edge makes a descendant, and the evidence graph of the repository keeps its
   meaning of a link, which is a citation and not a cause.
3. **A change without a declared edge is reported as `unknown` with the missing edge named.** The engine
   recomputes the descendants of the target along the edges of the registry, and a node that changes without a
   declared edge is reported as `unknown` and listed as an unsupported causal claim. That is the whole point of
   the milestone.
4. **An intervention on the reference rate of a day does not rewrite the applied rate of the history.** The
   applied rate of a transaction is the rate that was applied on the day of the transaction, and the reference
   rate of a later day does not reach into the past.
5. **Every statement of the report is a statement about the simulation.** The result of an intervention is a
   statement about the synthetic world of the repository, and no sentence of the report says what a real
   merchant would have received. The report is checked by a test that reads it.
6. **The difference and the cause are separate outputs.** Every amount of a result is a `Decimal`, the result
   says the value before, the value after and the difference, and the difference recomputed with `Decimal` is
   the published difference. A result that says "the cost went up" without the two values is not a result.

## Alternatives considered

- **To learn the dependencies from the observations of the world.** Refused. A dependency that is learned from
  an observation is a dependency that the data suggests and not a dependency that the code implements, and the
  registry is the only source of a dependency.
- **To report a change without a declared edge as a cause.** Refused. A change without a declared edge is
  `unknown` with the missing edge named, because a tool that says "because" when it cannot is worse than a tool
  that says nothing.
- **To let an intervention rewrite the applied rates of the history.** Refused. The applied rate of a
  transaction is the rate that was applied on the day of the transaction, and the reference rate of a later day
  does not reach into the past.
- **To present a result as a prediction for a real merchant.** Refused. The result of an intervention is a
  statement about the synthetic world of the repository, and the package is explicit that an intervention must
  not be presented as a prediction of what would have happened to a real merchant.

## Consequences

- **The repository has the causal engine**, in `ledgerlens/causal/`: the registry (`registry.py`), the
  intervention (`intervention.py`), the engine (`engine.py`) and the report (`report.py`), with the tests in
  `tests/causal/`.
- **The page of the causal engine is [the page of the causal engine](../causal.md)**, with the four families of
  the registry, the meaning of `unknown`, the meaning of an unsupported causal claim and the statement that a
  result is a statement about a simulation.
- **The engine reads the world through the simulator and the projector**, and it never rewrites the simulator,
  the projector or the sandbox.
- **The result of an intervention is never a bundle of the agent**, and a run of the engine writes nothing
  under the two published catalogs.

## Links

- [ADR-013, the public trace is a versioned contract](ADR-013-public-trace-as-a-versioned-contract.md)
- [ADR-032, the state of the branch and the hash](ADR-032-the-state-of-the-branch-and-the-hash.md)
- [ADR-074, a case ends in a decision and the decision belongs to the code](ADR-074-a-case-ends-in-a-decision-and-the-decision-belongs-to-the-code.md)
- [the page of the causal engine](../causal.md)
- [the specification of the milestone](../../specs/020-r19-causal-counterfactual-interventions/spec.md)
- [the design package](../v3/advanced-specs/R19-02-causal-counterfactual-interventions.md)
