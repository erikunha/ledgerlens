# LL-V3-R19-02 - Causal counterfactual interventions

**Status:** design proposed; not yet implemented. **Strategic lens:** Second-Order and Probabilistic Thinking. **Audience:** Researcher and finance engineer. **Dependencies:** R17 digital twin, R8 graph, R9 economic math.

## User outcome

Distinguish a rate-change intervention from a correlated observation by replaying controlled changes to the synthetic world.

## Ownership and compatibility

Build explicit structural function registry over FX, policy, settlement and review rules. No learned causality from observational correlations unless assumptions identified.

## Typed interfaces and persisted state

`Intervention {branch_id,target,do_value,assumptions,dependent_nodes}`; result includes before/after source/derived facts, invariants and unsupported causal claims.

## Algorithm and execution contract

Fix base seed and all independent exogenous events, change one intervened field, recompute descendants according to documented DAG, compare exact money/verification/review changes; label extrapolations and confounders.

## Security, invalid states and recovery

Do not state the intervention would cause real merchant payment outcomes. Require declared model of dependencies and valid dates.

## Acceptance scenarios (Given / When / Then)

- Intervening on reference FX alone does not rewrite historical applied FX.
- Intervening on merchant policy changes only eligible periods.
- Unmodeled causal link shown as unknown.
- Double change uses explicit compound intervention.

## Metrics, evidence and regression gates

Synthetic causal oracle accuracy, coverage, sensitivity to assumptions and correctness of affected edges.

## Definition of done and rollback

Toy structural tests, visual caveats and study guide; rollback to pure scenario diff.

No claim of implementation is made by this spec. Shipped status requires passing exact executable tests, a source revision, a sanitized replay/trace, and known limitations in release notes.
