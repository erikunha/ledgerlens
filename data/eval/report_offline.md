# Evaluation of the three variants (offline)

> The offline numbers measure the plumbing (the trace conversion, the evaluators and the report) with scripted answers, not the quality of a model. Each variant replays each case's script: the differences between them come from the tools the variant has, not from the model reasoning better or worse. To measure quality, run with `--online` and a LangSmith key.

31 cases: 12 from the planted scenarios and 18 natural ones from the generated database.

## Mean scores per variant

| Variant | correctness | groundedness | trajectory_strict_match | trajectory_unordered_match | trajectory_subset_match | trajectory_superset_match | trajectory_equivalent_strict_match | trajectory_equivalent_unordered_match | human review |
|---|---|---|---|---|---|---|---|---|---|
| A: chain with no tools | 0.00 | 0.00 | 0.00 | 0.00 | 1.00 | 0.00 | 0.00 | 0.00 | 31 |
| B: ReAct agent (legacy_react) | 0.77 | 0.63 | 0.77 | 0.77 | 1.00 | 0.77 | 0.77 | 0.77 | 16 |
| C: full agent (integrator with verifier) | 1.00 | 0.86 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 10 |

## Latency of the full agent

The latency of the cases of eval_cases over the full agent, by the nearest_rank method, over a denominator of 31 cases that produced a measurement.

| stage | p50 (ms) | p95 (ms) |
|---|---|---|
| end to end | 16.0 | 36.0 |
| triage | 1.0 | 2.0 |
| agent | 14.0 | 33.0 |
| verify | 1.0 | 3.0 |

## Cost of a turn

The total of the run is not published: the price of the model of the run is unknown, and an unknown price is unknown and never zero: the total of the run is not published.
No case of the run was cut by a cap.

## Quality goal

- C beats A in correctness: yes.
- C trajectory (`unordered` mode): 1.00, meets the 0.80 minimum.
- C trajectory with equivalent tools (`unordered`): 1.00, meets the 0.80 minimum. The equivalence only swaps `get_ledger_record` for `query_ledger` when looking up a record by id.

## Answer key changes

- EC-19, EC-20, EC-21, EC-22, EC-23, EC-24: expected `query_ledger`, `calculate`, now expects `query_ledger`. The question is the payout's net amount, and the settlements table already keeps it in net_minor; in the six payouts net_minor equals gross_minor - refunds_minor - fees_minor, which is what calculate would redo with the same three columns, and the settlement_net coherence rule checks that equality by itself. Calculate is still expected where the question is how the payout was calculated (EC-08, scenario S08).

## Verifier on the verification set

43 cases from `verification_set.jsonl` (16 planted contradictions, 18 supported claims), NLI: `stub`.

| verdict accuracy | contradiction recall | false positives | misses |
|---|---|---|---|
| 1.00 | 1.00 | 0.00 | none |

## Cases that did not get the top score

**A**
- `correctness`: 31 cases (EC-01, EC-02, EC-03, EC-04, EC-05, EC-06, EC-07, EC-08, EC-09, EC-10, EC-11, EC-12, EC-13, EC-14, EC-15, EC-16, EC-17, EC-18, EC-19, EC-20, EC-21, EC-22, EC-23, EC-24, EC-25, EC-26, EC-27, EC-28, EC-29, EC-30, EC-31)
- `groundedness`: 31 cases (EC-01, EC-02, EC-03, EC-04, EC-05, EC-06, EC-07, EC-08, EC-09, EC-10, EC-11, EC-12, EC-13, EC-14, EC-15, EC-16, EC-17, EC-18, EC-19, EC-20, EC-21, EC-22, EC-23, EC-24, EC-25, EC-26, EC-27, EC-28, EC-29, EC-30, EC-31)
- `trajectory_strict_match`: 31 cases (EC-01, EC-02, EC-03, EC-04, EC-05, EC-06, EC-07, EC-08, EC-09, EC-10, EC-11, EC-12, EC-13, EC-14, EC-15, EC-16, EC-17, EC-18, EC-19, EC-20, EC-21, EC-22, EC-23, EC-24, EC-25, EC-26, EC-27, EC-28, EC-29, EC-30, EC-31)
- `trajectory_unordered_match`: 31 cases (EC-01, EC-02, EC-03, EC-04, EC-05, EC-06, EC-07, EC-08, EC-09, EC-10, EC-11, EC-12, EC-13, EC-14, EC-15, EC-16, EC-17, EC-18, EC-19, EC-20, EC-21, EC-22, EC-23, EC-24, EC-25, EC-26, EC-27, EC-28, EC-29, EC-30, EC-31)
- `trajectory_superset_match`: 31 cases (EC-01, EC-02, EC-03, EC-04, EC-05, EC-06, EC-07, EC-08, EC-09, EC-10, EC-11, EC-12, EC-13, EC-14, EC-15, EC-16, EC-17, EC-18, EC-19, EC-20, EC-21, EC-22, EC-23, EC-24, EC-25, EC-26, EC-27, EC-28, EC-29, EC-30, EC-31)
- `trajectory_equivalent_strict_match`: 31 cases (EC-01, EC-02, EC-03, EC-04, EC-05, EC-06, EC-07, EC-08, EC-09, EC-10, EC-11, EC-12, EC-13, EC-14, EC-15, EC-16, EC-17, EC-18, EC-19, EC-20, EC-21, EC-22, EC-23, EC-24, EC-25, EC-26, EC-27, EC-28, EC-29, EC-30, EC-31)
- `trajectory_equivalent_unordered_match`: 31 cases (EC-01, EC-02, EC-03, EC-04, EC-05, EC-06, EC-07, EC-08, EC-09, EC-10, EC-11, EC-12, EC-13, EC-14, EC-15, EC-16, EC-17, EC-18, EC-19, EC-20, EC-21, EC-22, EC-23, EC-24, EC-25, EC-26, EC-27, EC-28, EC-29, EC-30, EC-31)

**B**
- `correctness`: 7 cases (EC-12, EC-13, EC-14, EC-15, EC-16, EC-17, EC-18)
- `groundedness`: 14 cases (EC-01, EC-02, EC-06, EC-11, EC-12, EC-13, EC-14, EC-15, EC-16, EC-17, EC-18, EC-26, EC-30, EC-31)
- `trajectory_strict_match`: 7 cases (EC-12, EC-13, EC-14, EC-15, EC-16, EC-17, EC-18)
- `trajectory_unordered_match`: 7 cases (EC-12, EC-13, EC-14, EC-15, EC-16, EC-17, EC-18)
- `trajectory_superset_match`: 7 cases (EC-12, EC-13, EC-14, EC-15, EC-16, EC-17, EC-18)
- `trajectory_equivalent_strict_match`: 7 cases (EC-12, EC-13, EC-14, EC-15, EC-16, EC-17, EC-18)
- `trajectory_equivalent_unordered_match`: 7 cases (EC-12, EC-13, EC-14, EC-15, EC-16, EC-17, EC-18)

**C**
- `groundedness`: 7 cases (EC-01, EC-02, EC-06, EC-11, EC-26, EC-30, EC-31)

## What the numbers show and what they do not

- They show that the trace conversion, the six evaluators and the report work end to end.
- They show the effect of having a tool or not: A looks up nothing, and B has neither `get_ledger_record` nor `recall_cases`, so it loses the cases that depend on them.
- They do not show model quality: the answers are scripted and C replays the expected trajectory by construction.
- Thirty cases give a trend, not statistical significance.
