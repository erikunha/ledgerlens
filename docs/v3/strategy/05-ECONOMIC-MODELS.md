# Operations Economics Lab - Exact Calculation Specification

**Purpose:** let visitors compare agent strategies on economic outcomes within a documented **hypothetical** operations model. This is not a real loss, earnings or recovery calculator. Economic parameters are user assumptions unless grounded in authorized measurement.

## Mathematical definitions

For case `i`, define:
- `m_i`: metered LLM spend (USD), with provider and price snapshot or unknown.
- `k_i`: measured other compute/infrastructure cost, or estimated with methodology.
- `h_i`: human review minutes actually observed or simulated.
- `w`: loaded human hourly cost in USD/hour (assumed by visitor; do not present as average industry wage).
- `f_i`: case-specific fixed processing expense in USD.
- `e_i`: loss cost attributable to wrong decision, with **event probability and assumed impact shown separately**.
- `c_i = m_i + k_i + (h_i / 60)*w + f_i + e_i`.
- `correct_i ∈ {true,false,unknown}` only determined against a declared ground truth/eval evaluation criteria.

`total_cost = Σ c_i`. `cost_per_correct = Σ c_i / Σ 1[correct_i=true]` when denominator positive; if no correctly resolved cases, show undefined and reason. `automation_rate = automated_without_human / eligible_cases`, where eligibility criteria are versioned. `risk_coverage_curve(threshold)` shows errors and review load versus model confidence; **do not equate self-reported confidence to calibrated probability**.

Expected error loss may be simulated as `P(error_j | cohort) * impact_j` per mutually exclusive error class `j`; avoid double counting overlapping events. Present interval/sensitivity bands instead of single numbers if inputs are uncertain.

Savings comparisons: `incremental_savings = baseline_cost - treatment_cost` only for paired, comparable case sets with matching scope and full cost model; do not infer actual operational savings from offline code runs alone.

## Worked example: explicitly fictional

A manual investigation takes 12 minutes. A proposed assistant produces an answer with 2 minutes of review and a model cost of `$0.08`, other costs assumed zero. At *hypothetical* loaded hourly cost `$45/hour`, manual labor cost is `$9.00`; proposed review labor is `$1.50`, plus `$0.08`, resulting in `$7.42` per-case **modeled** cost difference. This is not measured productivity or a real savings claim. Include changes in error rate, rework and escalations before interpreting benefits.

## Experiments

**ECO-01 Cost/quality frontier:** compare A/B/C/D on same batch; quality, total cost, cost/correct, p50/p95, correct escalation, confidence interval and failure slices.

**ECO-02 Human review thresholds:** change abstention threshold, recompute review burden and expected harm. Require disaggregation into false accept and false reject.

**ECO-03 Routing economics:** simple-vs-complex case router, measured quality by class, cascading fallback and worst-case tool budgets.

**ECO-04 Bottleneck shift:** lower model latency while fixed review capacity remains; show when the queue dominates throughput.

**ECO-05 Fault economics:** simulate FX outage, timed-out SQL, stale policy and memory contamination; measure expected cost of recovery vs failure with assumptions visible.

**ECO-06 Risk of 'free' retrieval:** embeddings, indexing, per-request RAG and human review included in TCO. No 'zero-cost local' claim without actual hardware/runtime measurement.

## Required validation

- Use Python `Decimal` or integer minor units; never JS floating point for financial truth.
- Publish currency, rate source date, timezone and rounding convention for every monetary quantity.
- Prevent divide-by-zero, negative review minutes, negative token counts and non-finite numbers.
- Every chart has `observed/simulated/assumed/replayed/unknown`, sample size and comparison method.
- Sensitivity test ±20% review time and ±25% hourly cost without interpreting as confidence intervals.
- Deterministic ground truth is evaluated before LLM-generated narrative.
- Optional visitors can export a methods JSON with exact assumptions; sharing excludes BYOK/identifying data.
