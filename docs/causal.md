# Causal counterfactual interventions

The causal engine of the repository answers one question: if one field of the synthetic world had been
different, what else would be different. The answer is computed, never learned: the dependencies of the
synthetic world are declared in a registry written by hand over the code of the repository, and the engine
recomputes the descendants of an intervention along the edges of the registry. The decision is recorded in
[ADR-095](decisions/ADR-095-the-registry-of-the-structural-functions-is-the-only-source-of-a-dependency.md).

A result of the engine is a statement about a simulation and never a prediction for a real merchant, a real
bank or a real policy of the world. Every sentence of cause of a report names the simulation, and no sentence
of a report says what a merchant outside the simulation received.

## The registry

The registry lives in `ledgerlens/causal/registry.py` and covers the four families of the code of the
repository. Every edge names the two nodes it connects, the function that implements it and the reason of the
edge, because an edge that exists because a function reads a value is different from an edge that exists
because a policy says so.

### Exchange rate

| Node | Meaning |
|---|---|
| `fx.reference_rate` | the reference rate of a day |
| `fx.applied_rate` | the applied rate of a transaction |
| `fx.markup` | the markup of a merchant |

| Edge | Function | Reason |
|---|---|---|
| `fx.reference_rate` -> `fx.applied_rate` | `ledgerlens.sim.fx.FxTable.rate` | the applied rate of a transaction is read from the reference rate of the day of the transaction |
| `fx.applied_rate` -> `fx.markup` | `ledgerlens.tools.calculator._implied_markup_pct` | the markup of a merchant is computed from the applied rate and the reference rate |

### Policy

| Node | Meaning |
|---|---|
| `policy.rule` | the rule of a policy of the corpus |
| `policy.deadline_window` | the window of a deadline of a policy |
| `policy.markup_ceiling` | the ceiling of a markup of a policy |

| Edge | Function | Reason |
|---|---|---|
| `policy.markup_ceiling` -> `fx.markup` | `ledgerlens.tools.calculator._fx_markup_check` | the ceiling of a markup of a policy bounds the markup of a merchant, because the policy says so |
| `policy.rule` -> `policy.deadline_window` | `ledgerlens.retrieval.load_policy_documents` | the window of a deadline is read from the rule of the policy of the corpus |

### Settlement

| Node | Meaning |
|---|---|
| `settlement.fee` | the fee of a settlement |
| `settlement.net` | the net of a settlement |
| `settlement.date` | the date of a settlement |

| Edge | Function | Reason |
|---|---|---|
| `settlement.fee` -> `settlement.net` | `ledgerlens.tools.calculator._net_settlement` | the net of a settlement is the gross minus the refunds minus the fees, and the function reads the fee |
| `settlement.date` -> `settlement.net` | `ledgerlens.sim.calendars.payout_date` | the date of a settlement is computed from the period of it, and the net is read with the date |

### Review

| Node | Meaning |
|---|---|
| `review.dispute_deadline` | the deadline of a dispute |
| `review.escalation` | the escalation of a case |
| `review.decision` | the decision of the verifier |

| Edge | Function | Reason |
|---|---|---|
| `review.dispute_deadline` -> `review.escalation` | `ledgerlens.verify.escalation.escalation_reasons` | the escalation of a case reads the deadline of the dispute, because the policy of the escalation says so |
| `review.escalation` -> `review.decision` | `ledgerlens.verify.checks.verify_result` | the decision of the verifier reads the escalation of the case |

The test of the registry checks that every function named by an edge exists in the code, because the registry
is a declaration of the code and not a picture of it: an edge whose function was renamed is a broken edge.

## The intervention

An intervention (`ledgerlens/causal/intervention.py`) is a typed record: the target node, the do value, the
day when the node is dated, and the assumptions of the run. Three interventions are refused before anything is
written, each with a readable reason that names the field that is wrong: an intervention on an unknown node,
an intervention with an invalid value, and an intervention on a date outside the horizon. A compound
intervention names both of its targets, and its result is not the sum of the results of the two single
interventions, because the descendants of one target can read the value of the other.

## The engine

The engine (`ledgerlens/causal/engine.py`) validates the intervention, recomputes the world and classifies
every node of the registry:

- **Changed and explained**: the node is a descendant of the target in the registry, and the change follows a
  declared edge.
- **Unknown**: the node changed and no declared edge reaches it from the target. The status is `unknown`, the
  missing edge is named, and the claim is listed as an unsupported causal claim. A change without a declared
  edge is never a cause.
- **Unchanged**: the node kept the value it had, and the report names it.

Two rules protect the world. The history is not rewritten: the applied rate of a transaction is the rate that
was applied on the day of the transaction, and the reference rate of a later day does not reach into the past.
And an intervention that breaks a money invariant of `ledgerlens/sandbox/invariants.py` is refused, and the
state of the world is the one before the intervention.

Two runs over the same base carry the same digest of the exogenous stream of the twin, because two runs over
two streams are two worlds and not a comparison.

## The report

The report (`ledgerlens/causal/report.py`) carries every amount as a `Decimal` with the value before, the
value after and the difference, and every difference recomputes exactly. The result carries its assumptions,
and the sensitivity of a result to an assumption is the movement of the nodes between two runs that differ
only in the assumption: a measurement of the assumption, not an interval of confidence.

## What the engine never says

- Nothing is learned from an observation: a node that is not in the registry is never a descendant of
  anything.
- No result is a prediction for a real merchant: every value is a value of the simulation.
- No unknown is a cause: an unsupported causal claim is listed with the missing edge named, and the registry
  stays the only source of a dependency.
