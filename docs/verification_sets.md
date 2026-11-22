# The sets of the verifier and what each number means

The LedgerLens verifier works with three different sets, and the number 30 appears in two of them with different
meanings. A wrong citation here becomes a wrong number in the README, in the report and in the post. This document is
the canonical place: when a number appears anywhere else, its meaning comes from here.

Every number below names the dataset it was measured over and the restriction that applies to that dataset. A number
without its dataset is a claim about nothing in particular, and a number without its restriction is a claim about more
than the measurement supports.

## The numbers

| Number | What it is | Where it lives | Split role | Decided by |
|---|---|---|---|---|
| 43 | Total of the verification set of the verifier | `data/eval/verification_set.jsonl` | tuning | 30 text, 7 numeric, 6 coherence |
| 30 | The part of the verification set that goes through the NLI, the text cases | `data/eval/verification_set.jsonl`, filter `type == "text"` | tuning | the model |
| 40 | Live labelled sentences, read from the evidence | `data/eval/verification_live.jsonl` | tuning | the model |
| 70 | Denominator of the NLI calibration | 30 text plus 40 live, both tuning | tuning | the model |
| 30 | Cases of the online evaluation, the `EC-xx` ones | `data/eval/eval_cases.jsonl` | tuning | the whole agent, with a real model and real tools |

The two 30s are different sets and they do not add up. The first is a part of the verification set; the second is the
set of the online evaluation.

The split role of every dataset is written down in the manifest, [`data/eval/datasets.json`](../data/eval/datasets.json),
and the decision that says what a role means is
[ADR-052](decisions/ADR-052-the-manifest-of-the-eval-datasets.md). The table above repeats the roles so that a
reader of this document does not have to open a JSON file to know what a number is allowed to claim.

## What the calibration measures

The calibration chooses the NLI thresholds with the rule of the [ADR-007](decisions/ADR-007-nli-verification.md): no
false `supported` and no false `contradicted` on both sets, then the highest accuracy, and on a tie the middle of the
plateau. Both sets of the rule are the same sets the thresholds were chosen against, so both of them are `tuning`.

| Set | Dataset | Cases | Accuracy | Reading |
|---|---|---|---|---|
| Verification, text cases | `data/eval/verification_set.jsonl` | 30 | 1.000 | the NLI gets all of them right, because they are short sentences and the NLI returns 0.0 or 1.0 |
| Live | `data/eval/verification_live.jsonl` | 40 | 0.625 | sentences of the real agent, on a set of 19 supported, 12 contradicted and 9 without enough evidence: 25 of the 40 land on the right label |
| Combined | the 70 NLI cases of the two sets above | 70 | 0.786 | (30 x 1.000 + 40 x 0.625) / 70 |

**The 1.000 is measured over the 30 text cases of `data/eval/verification_set.jsonl`, which are the tuning set of
the sweep of ADR-007: the sweep chose `entailment_min` 0.81 and `contradiction_min` 0.91 over these 30 cases
together with the 40 live sentences of the live set, so an accuracy over the tuning set is a measure of the fit of the
thresholds and not a measure of generalization.**

**The 0.625 is measured over the 40 sentences of `data/eval/verification_live.jsonl`, which were part of the same
sweep of ADR-007: the rule that chose the thresholds was "no false `supported` and no false `contradicted` on both
sets", so the live set was read against while the thresholds were chosen, and this number is a tuning number too.**

**The 0.786 is measured over a denominator of 70 NLI cases, the 30 text cases of the verification set plus the 40
live sentences. The 43 records of `data/eval/verification_set.jsonl` include 7 numeric cases and 6 coherence cases
that the NLI never sees, because the code decides them, so they enter none of the accuracies above.**

What the calibration **does not** measure: the 7 numeric cases and the 6 coherence cases of the verification set. Those
are decided by code, the NLI does not see them, and they enter none of the accuracies above.

## The rule of citation

1. The NLI accuracy is over 70 NLI cases. Never over the 43.
2. "25 of 40" is the NLI accuracy on the live set, `data/eval/verification_live.jsonl`. The live set is text only:
   the numeric and the coherence checks do not apply to it, so it is one term of the combined 0.786 over the 70 NLI
   cases, and not a separate measurement of the whole verifier.
3. The 43 are the test set of the verifier, `data/eval/verification_set.jsonl`. Citing "43 cases" without saying that
   the accuracy has another denominator is a citation error.
4. The 30 cases of the online evaluation, `data/eval/eval_cases.jsonl`, are another set, the one that compares the
   three variants of the agent. Thirty cases show a tendency, not a significance.
5. The NLI threshold does not fix the limitation of the model: of the supported live sentences, many stay without a
   verdict at any threshold, because the error is the model with a long premise, not the cut.
6. Every accuracy named above is a number over a `tuning` dataset, so none of them is a generalization to unseen
   data. A number that claims to generalize names the dataset it was measured over and the restriction that applies
   to it, or it does not go out.

## Where the truth lives now

The three places that hold the truth about the datasets are these, and they are the ones a reader has to check:

- **[`data/eval/datasets.json`](../data/eval/datasets.json)**, the manifest: for each dataset its sha256, its record
  count, its source, its labeling version, its split role, its scenario seed and its contamination policy. It is the
  single source of what the datasets of the repository are.
- **[`scripts/check_eval_datasets.py`](../scripts/check_eval_datasets.py)**, the check: it reads the disk, recomputes
  the fingerprints and refuses with a readable reason when a dataset moved without the manifest moving with it, when a
  declared dataset is missing, or when a dataset of the folder is not declared. It writes nothing when it verifies.
- **[ADR-052](decisions/ADR-052-the-manifest-of-the-eval-datasets.md)**, the decision: what a role means, that the
  role of a dataset is decided by evidence with the conservative role winning when the evidence is not clean, and
  that no dataset of the repository carries the role `held_out` today.

**The check is a step of the gate.** It runs in `scripts/gate.sh`, after the tests and before the export check, and it
is in the first job of the continuous integration. A dataset that moves without the manifest moving breaks the build,
and the fix is a `--write` that updates the two fingerprints, followed by a review of the diff of the manifest.

## How this is checked

- `ledgerlens/verify/thresholds.json` keeps the calibration metadata with the explicit denominators: the total, the
  part that goes to the NLI, the breakdown by type, the live total and the combined denominator.
- `tests/verify/test_verification_sets.py` ties that metadata to the data files, with no model and no network, so the
  divergence does not come back without anyone noticing.
- `tests/verify/test_verification_live.py::test_the_chosen_thresholds_follow_the_calibration_rule_on_both_sets` redoes
  the full sweep with the real model. It is a slow test, switched off in the normal gate.
- `tests/eval/test_dataset_manifest.py` ties the manifest to the disk: every entry of the manifest matches the file it
  names, and no dataset of the folder is left out.

## The divergence this slice reconciled

The metadata said `calibration.sets.verification_set: 30`, and the verification set has 43 records. The name said
"verification set" and the number was the one of the subset that goes through the NLI. It was not a calculation error:
it was a naming error. From now on the metadata says each number with what it counts, and the test checks it.

The second half of the same problem is now closed by the manifest: the numbers name the dataset they were measured
over, and the manifest says which bytes that dataset was, so a number can be checked against the file it came from.
