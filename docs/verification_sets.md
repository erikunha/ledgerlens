# The sets of the verifier and what each number means

The LedgerLens verifier works with three different sets, and the number 30 appears in two of them with different
meanings. A wrong citation here becomes a wrong number in the README, in the report and in the post. This document is
the canonical place: when a number appears anywhere else, its meaning comes from here.

## The numbers

| Number | What it is | Where it lives | Decided by |
|---|---|---|---|
| 43 | Total of the verification set of the verifier | `data/eval/verification_set.jsonl` | 30 text, 7 numeric, 6 coherence |
| 30 | The part of the verification set that goes through the NLI, the text cases | `data/eval/verification_set.jsonl`, filter `type == "text"` | the model |
| 40 | Live labelled sentences, read from the evidence | `data/eval/verification_live.jsonl` | the model |
| 70 | Denominator of the NLI calibration | 30 text plus 40 live | the model |
| 30 | Cases of the online evaluation, the `EC-xx` ones | `data/eval/report_online.json` | the whole agent, with a real model and real tools |

The two 30s are different sets and they do not add up. The first is a part of the verification set; the second is the
set of the online evaluation.

## What the calibration measures

The calibration chooses the NLI thresholds with the rule of the [ADR-007](decisions/ADR-007-nli-verification.md): no
false `supported` and no false `contradicted` on both sets, then the highest accuracy, and on a tie the middle of the
plateau.

| Set | Cases | Accuracy | Reading |
|---|---|---|---|
| Verification, text cases | 30 | 1.000 | the NLI gets all of them right, because they are short sentences and the NLI returns 0.0 or 1.0 |
| Live | 40 | 0.625 | sentences of the real agent, on a set of 19 supported, 12 contradicted and 9 without enough evidence: 25 of the 40 land on the right label |
| Combined | 70 | 0.786 | (30 x 1.000 + 40 x 0.625) / 70 |

What the calibration **does not** measure: the 7 numeric cases and the 6 coherence cases of the verification set. Those
are decided by code, the NLI does not see them, and they enter none of the accuracies above.

## The rule of citation

1. The NLI accuracy is over 70 NLI cases. Never over the 43.
2. "25 of 40" is the NLI accuracy on the live set. The live set is text only: the numeric and the coherence checks do
   not apply to it, so it is one term of the combined 0.786 over the 70 NLI cases, and not a separate measurement of the
   whole verifier.
3. The 43 are the test set of the verifier. Citing "43 cases" without saying that the accuracy has another denominator
   is a citation error.
4. The 30 cases of the online evaluation are another set, the one that compares the three variants of the agent. Thirty
   cases show a tendency, not a significance.
5. The NLI threshold does not fix the limitation of the model: of the supported live sentences, many stay without a
   verdict at any threshold, because the error is the model with a long premise, not the cut.

## How this is checked

- `ledgerlens/verify/thresholds.json` keeps the calibration metadata with the explicit denominators: the total, the
  part that goes to the NLI, the breakdown by type, the live total and the combined denominator.
- `tests/verify/test_verification_sets.py` ties that metadata to the data files, with no model and no network, so the
  divergence does not come back without anyone noticing.
- `tests/verify/test_verification_live.py::test_the_chosen_thresholds_follow_the_calibration_rule_on_both_sets` redoes
  the full sweep with the real model. It is a slow test, switched off in the normal gate.

## The divergence this slice reconciled

The metadata said `calibration.sets.verification_set: 30`, and the verification set has 43 records. The name said
"verification set" and the number was the one of the subset that goes through the NLI. It was not a calculation error:
it was a naming error. From now on the metadata says each number with what it counts, and the test checks it.
