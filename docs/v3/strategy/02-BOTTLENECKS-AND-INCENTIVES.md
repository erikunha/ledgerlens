# Bottlenecks, Review Economics, and Incentive Alignment

## End-to-end workflow map

`input → identity/scope → triage → tool selection → retrieval → computation → synthesis → verification → review/abstain → answer`

A wall-clock trace is not sufficient for queue economics. For each step capture (when available): service time, wait time, rework, failure/retry, amount of human labor, capacity, fan-out and uncertainty. Present latency critical path alongside total compute spent; parallel tasks can reduce elapsed time while increasing total cost.

## Review-queue experiment

Visitor changes a scenario's case arrivals per hour, fraction requiring review, reviewer handling minutes, number of reviewers and review policy. Queue utilization = `arrival_rate * review_fraction * mean_review_time_hours / reviewers` for a simple stable approximation. If ≥ 1, show overload, not an invented finite waiting time. Little's Law `L = λW` applies to a stable system with compatible rates and steady-state averages; do not treat it as a waiting-time predictor without additional assumptions. Provide simple deterministic discrete-event simulation as the educational default and optional queue theory compare.

### A revealing counterfactual

Changing verification thresholds might improve overall automated 'throughput' while creating more dangerous false negatives. Reducing review rate is not automatically better; compare **risk-adjusted utility** and reviewer minutes alongside decision quality. Show calibrated confidence and failure slices.

## Incentive-conflict experiments

- Support lead optimizes `resolved_cases / staffed_hour`.
- Customer optimizes correctness and response experience, including justified abstention.
- Compliance minimizes unsupported claims and unsafe actions.
- Finance seeks correct reconciliation and audit trail.
- Platform engineer minimizes cost and incidents at target accuracy.
- Researcher optimizes learning from failure cases and uncertainty.

Allow a *stakeholder view* of the same case that changes the displayed objectives and metrics, not the evidence or correctness labels. No persona can change the actual ledger truth.

## Feature admission policy

Each feature must document `beneficiary`, `incentive_conflict`, `bottleneck_changed`, `first_order_effect`, `second_order_risk`, `success_metric`, `failure_metric`, `reversibility`, `measurement_plan`. If the feature creates no economic or learning value but provides a compelling research demonstration, put it under research horizon instead of deleting it.

## Applied engineering exercise

Question: S10 uses a currency for which the reference FX service has no data. What is the better action: a guessed rate, escalation, or a source expansion? Distinguish immediate response quality, tool integration cost, trust impact, and operational backlog. Record the decision and demonstrate it with trace evidence, not preference alone.
