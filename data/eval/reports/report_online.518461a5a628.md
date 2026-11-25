# Evaluation of the three variants (online)

> Real run: the configured model (temperature 0), the real tools and one LangSmith experiment per variant. The verifier is the real one and the NLI is the `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli` model running on the CPU, with the thresholds calibrated in `ledgerlens/verify/thresholds.json`. Correctness is code: it counts the expected facts that appear in the answer, with values, dates and ids normalized. The explanation is an LLM judge's score. 3 runs per case and per variant, each in its own experiment: thirty cases give a trend, not statistical significance.

30 cases: 12 from the planted scenarios and 18 natural ones from the generated database.

Model: `gpt-4.1-mini`, temperature 0.

## Scores per variant: mean [min, max] of 3 runs

| Variant | correctness | groundedness | trajectory_strict_match | trajectory_unordered_match | trajectory_subset_match | trajectory_superset_match | trajectory_equivalent_strict_match | trajectory_equivalent_unordered_match | explanation | human review |
|---|---|---|---|---|---|---|---|---|---|---|
| A: chain with no tools | 0.17 [0.17, 0.17] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 1.00 [1.00, 1.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.70 [0.69, 0.72] | 30.0 [30, 30] |
| B: ReAct agent (legacy_react) | 0.55 [0.51, 0.58] | 0.00 [0.00, 0.00] | 0.44 [0.37, 0.50] | 0.48 [0.40, 0.53] | 0.54 [0.47, 0.60] | 0.62 [0.57, 0.67] | 0.64 [0.57, 0.70] | 0.68 [0.60, 0.73] | 0.83 [0.80, 0.87] | 29.0 [28, 30] |
| C: full agent (integrator with verifier) | 0.82 [0.79, 0.85] | 0.74 [0.71, 0.76] | 0.53 [0.53, 0.53] | 0.53 [0.53, 0.53] | 0.63 [0.60, 0.67] | 0.63 [0.60, 0.67] | 0.73 [0.73, 0.73] | 0.73 [0.73, 0.73] | 0.79 [0.77, 0.81] | 9.3 [8, 10] |

Experiments of each run:

- A: `not stored`, `not stored`, `not stored`
- B: `not stored`, `not stored`, `not stored`
- C: `not stored`, `not stored`, `not stored`

## Storage in LangSmith

These runs were not stored in LangSmith: the service refused to accept traces (`HTTP 429: Too many requests: tenant exceeded usage limits: Monthly unique traces usage limit exceeded`). The model, FX and NLI were the real ones, with tracing turned off.

Experiments stored earlier, from the last full run: A `ledgerlens-A-f5fda939`, B `ledgerlens-B-1da5bbf2`, C `ledgerlens-C-0d3f2d05`; verification `ledgerlens-verification-4063d413`.

## Quality goal

- C beats A in correctness: yes.
- C trajectory (`unordered` mode): 0.53, does not meet the 0.80 minimum.
- C trajectory with equivalent tools (`unordered`): 0.73, does not meet the 0.80 minimum. The equivalence only swaps `get_ledger_record` for `query_ledger` when looking up a record by id.

## Answer key changes

- EC-19, EC-20, EC-21, EC-22, EC-23, EC-24: expected `query_ledger`, `calculate`, now expects `query_ledger`. The question is the payout's net amount, and the settlements table already keeps it in net_minor; in the six payouts net_minor equals gross_minor - refunds_minor - fees_minor, which is what calculate would redo with the same three columns, and the settlement_net coherence rule checks that equality by itself. Calculate is still expected where the question is how the payout was calculated (EC-08, scenario S08).

## Verifier on the verification set

43 cases from `verification_set.jsonl` (16 planted contradictions, 18 supported claims), NLI: `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`.

| verdict accuracy | contradiction recall | false positives | misses |
|---|---|---|---|
| 1.00 | 1.00 | 0.00 | none |

## Tokens and cost

| Variant | input | output | total | cost (US$) |
|---|---|---|---|---|
| A | 34896 | 16918 | 51814 | 0.0410 |
| B | 388774 | 39466 | 428240 | 0.2187 |
| C | 690504 | 33866 | 724370 | 0.3304 |
| total | 1114174 | 90250 | 1204424 | 0.5901 |

The cost uses the model's list price, with no cache discount, so it is a ceiling.

## Cases that did not get the top score in at least one run

**A**
- `correctness`: 30 cases (EC-01, EC-02, EC-03, EC-04, EC-05, EC-06, EC-07, EC-08, EC-09, EC-10, EC-11, EC-12, EC-13, EC-14, EC-15, EC-16, EC-17, EC-18, EC-19, EC-20, EC-21, EC-22, EC-23, EC-24, EC-25, EC-26, EC-27, EC-28, EC-29, EC-30)
- `groundedness`: 30 cases (EC-01, EC-02, EC-03, EC-04, EC-05, EC-06, EC-07, EC-08, EC-09, EC-10, EC-11, EC-12, EC-13, EC-14, EC-15, EC-16, EC-17, EC-18, EC-19, EC-20, EC-21, EC-22, EC-23, EC-24, EC-25, EC-26, EC-27, EC-28, EC-29, EC-30)
- `trajectory_strict_match`: 30 cases (EC-01, EC-02, EC-03, EC-04, EC-05, EC-06, EC-07, EC-08, EC-09, EC-10, EC-11, EC-12, EC-13, EC-14, EC-15, EC-16, EC-17, EC-18, EC-19, EC-20, EC-21, EC-22, EC-23, EC-24, EC-25, EC-26, EC-27, EC-28, EC-29, EC-30)
- `trajectory_unordered_match`: 30 cases (EC-01, EC-02, EC-03, EC-04, EC-05, EC-06, EC-07, EC-08, EC-09, EC-10, EC-11, EC-12, EC-13, EC-14, EC-15, EC-16, EC-17, EC-18, EC-19, EC-20, EC-21, EC-22, EC-23, EC-24, EC-25, EC-26, EC-27, EC-28, EC-29, EC-30)
- `trajectory_superset_match`: 30 cases (EC-01, EC-02, EC-03, EC-04, EC-05, EC-06, EC-07, EC-08, EC-09, EC-10, EC-11, EC-12, EC-13, EC-14, EC-15, EC-16, EC-17, EC-18, EC-19, EC-20, EC-21, EC-22, EC-23, EC-24, EC-25, EC-26, EC-27, EC-28, EC-29, EC-30)
- `trajectory_equivalent_strict_match`: 30 cases (EC-01, EC-02, EC-03, EC-04, EC-05, EC-06, EC-07, EC-08, EC-09, EC-10, EC-11, EC-12, EC-13, EC-14, EC-15, EC-16, EC-17, EC-18, EC-19, EC-20, EC-21, EC-22, EC-23, EC-24, EC-25, EC-26, EC-27, EC-28, EC-29, EC-30)
- `trajectory_equivalent_unordered_match`: 30 cases (EC-01, EC-02, EC-03, EC-04, EC-05, EC-06, EC-07, EC-08, EC-09, EC-10, EC-11, EC-12, EC-13, EC-14, EC-15, EC-16, EC-17, EC-18, EC-19, EC-20, EC-21, EC-22, EC-23, EC-24, EC-25, EC-26, EC-27, EC-28, EC-29, EC-30)
- `explanation`: 24 cases (EC-01, EC-02, EC-03, EC-05, EC-07, EC-08, EC-10, EC-11, EC-12, EC-13, EC-14, EC-15, EC-16, EC-17, EC-18, EC-19, EC-20, EC-21, EC-22, EC-23, EC-24, EC-26, EC-29, EC-30)

**B**
- `correctness`: 17 cases (EC-01, EC-02, EC-03, EC-04, EC-05, EC-06, EC-07, EC-10, EC-11, EC-12, EC-20, EC-25, EC-26, EC-27, EC-28, EC-29, EC-30)
- `groundedness`: 30 cases (EC-01, EC-02, EC-03, EC-04, EC-05, EC-06, EC-07, EC-08, EC-09, EC-10, EC-11, EC-12, EC-13, EC-14, EC-15, EC-16, EC-17, EC-18, EC-19, EC-20, EC-21, EC-22, EC-23, EC-24, EC-25, EC-26, EC-27, EC-28, EC-29, EC-30)
- `trajectory_strict_match`: 20 cases (EC-01, EC-03, EC-05, EC-06, EC-07, EC-08, EC-10, EC-11, EC-12, EC-13, EC-14, EC-15, EC-16, EC-17, EC-18, EC-20, EC-22, EC-23, EC-25, EC-26)
- `trajectory_unordered_match`: 19 cases (EC-01, EC-05, EC-06, EC-07, EC-08, EC-10, EC-11, EC-12, EC-13, EC-14, EC-15, EC-16, EC-17, EC-18, EC-20, EC-22, EC-23, EC-25, EC-26)
- `trajectory_subset_match`: 17 cases (EC-01, EC-05, EC-06, EC-10, EC-11, EC-12, EC-13, EC-14, EC-15, EC-16, EC-17, EC-18, EC-20, EC-22, EC-23, EC-25, EC-26)
- `trajectory_superset_match`: 13 cases (EC-01, EC-07, EC-08, EC-10, EC-12, EC-13, EC-14, EC-15, EC-16, EC-17, EC-18, EC-20, EC-26)
- `trajectory_equivalent_strict_match`: 14 cases (EC-01, EC-03, EC-05, EC-06, EC-07, EC-08, EC-10, EC-11, EC-12, EC-20, EC-22, EC-23, EC-25, EC-26)
- `trajectory_equivalent_unordered_match`: 13 cases (EC-01, EC-05, EC-06, EC-07, EC-08, EC-10, EC-11, EC-12, EC-20, EC-22, EC-23, EC-25, EC-26)
- `explanation`: 12 cases (EC-01, EC-02, EC-03, EC-05, EC-07, EC-10, EC-11, EC-12, EC-19, EC-20, EC-23, EC-26)

**C**
- `correctness`: 10 cases (EC-01, EC-04, EC-05, EC-06, EC-07, EC-10, EC-11, EC-12, EC-28, EC-30)
- `groundedness`: 14 cases (EC-01, EC-02, EC-03, EC-04, EC-05, EC-06, EC-07, EC-08, EC-09, EC-10, EC-11, EC-12, EC-26, EC-28)
- `trajectory_strict_match`: 14 cases (EC-01, EC-02, EC-06, EC-07, EC-08, EC-10, EC-11, EC-13, EC-14, EC-15, EC-16, EC-17, EC-18, EC-28)
- `trajectory_unordered_match`: 14 cases (EC-01, EC-02, EC-06, EC-07, EC-08, EC-10, EC-11, EC-13, EC-14, EC-15, EC-16, EC-17, EC-18, EC-28)
- `trajectory_subset_match`: 12 cases (EC-01, EC-02, EC-06, EC-07, EC-10, EC-11, EC-13, EC-14, EC-15, EC-16, EC-17, EC-18)
- `trajectory_superset_match`: 12 cases (EC-01, EC-02, EC-07, EC-08, EC-10, EC-13, EC-14, EC-15, EC-16, EC-17, EC-18, EC-28)
- `trajectory_equivalent_strict_match`: 8 cases (EC-01, EC-02, EC-06, EC-07, EC-08, EC-10, EC-11, EC-28)
- `trajectory_equivalent_unordered_match`: 8 cases (EC-01, EC-02, EC-06, EC-07, EC-08, EC-10, EC-11, EC-28)
- `explanation`: 11 cases (EC-01, EC-05, EC-07, EC-10, EC-11, EC-12, EC-19, EC-20, EC-21, EC-23, EC-28)

## Runs with errors

- B: EC-20, EC-26

## What the numbers show and what they do not

- They show what each layer brings with a real model: A answers from what the model knows, B has the four tools and C has the six plus the verifier.
- Groundedness comes from the inference model `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`: each text claim is a verdict between the cited evidence and the sentence, and numbers go through code, not the model.
- The human review column uses the thresholds calibrated with that model; a smaller model or a different threshold changes how many cases go to review.
- Correctness counts the expected facts in the text; a right answer written another way loses points.
- One run per case at temperature 0 still varies a little between runs; thirty cases give a trend, not statistical significance.
