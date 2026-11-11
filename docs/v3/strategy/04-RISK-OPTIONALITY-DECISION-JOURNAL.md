# Asymmetric Bets, Opportunity Cost, Reversibility and Decision Quality

A technically impressive feature can have low portfolio ROI. The strategic intent is **unlimited documented exploration, selective resource allocation**. Nothing is excluded from the future capability atlas because it is difficult; nothing is automatically implemented because it is novel.

## Decision record schema

Each record uses: `decision_id`, `hypothesis`, `options`, `reference_class`, `cost_estimate`, `failure_risks`, `worst_plausible_loss`, `potential_gain`, `reversal_cost`, `measurement_window`, `confidence`, `new_information`, `owner`, `status`, `observed_outcome`, `postmortem`.

## Prioritization sequence (not a single score)

1. Safety/security hard stop. 2. Verified public-demo user path. 3. Engineering or empirical uncertainty: prioritize small experiment reducing it. 4. Independent hiring signal. 5. Maintenance and cloud-cost budget. 6. Additive research depth. If resources are constrained, use options: mock data, replay, off-by-default feature, optional local mode or external integration adapter.

## Example experiment decisions (hypotheses only)

| Bet | Test | Downside | Leading signal | What would change the decision |
|---|---|---|---|---|
| Build Next.js guided demo | 5 people complete replay | 1-2 weeks of UI work | Median time-to-comprehension | Visitors cannot understand trace |
| Scenario mutation engine | 3 adversarial mutations on same case | Complexity in event projector | User notices predictable before/after | Data invariants repeatedly break |
| Multi-agent analysis | C-vs-D paired eval | More cost and failure modes | Superior utility under pre-registered threshold | No quality gain net of cost |
| Live BYOK | One sandbox run with no leaked keys | Security/infra overhead | Stable success on tested providers | Cost abuse or secret leakage risk |
| Specialized fine-tuning | Offline eval with holdout | Compute, data licensing | Significant improvement vs prompt/retrieval baseline | Dataset leakage or no improvement |
| Human review simulator | Validate simulated queue against toy oracle | Misleading economic insights | Correct utilization and safe decisions | No defensible assumptions |

## Prevention of false certainty

Retain 'unknown' state. Record estimates separately from measurements. A model proving 'case solved' in a synthetic environment does not prove financial benefits for a real company. If a claim cannot be reproduced, it stays out of the landing metrics and case study.
