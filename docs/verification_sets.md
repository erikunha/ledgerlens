# The sets of the verifier and what each number means

The LedgerLens verifier works with four different sets, and the number 30 appears in two of them with different
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
| 48 | Total of the held out set of the verifier | `data/eval/verification_heldout.jsonl` | held_out | 47 through the NLI, 1 by the code |
| 47 | The part of the held out set that goes through the NLI | `data/eval/verification_heldout.jsonl`, the 47 cases with evidence | held_out | the model |
| 24 | Cases of the held out set the verifier decided as the blind reading decided | `data/eval/verification_heldout.jsonl` | held_out | the model and the code |
| 25 | Cases of the held out set the verifier decided as the recipes of the generator expected | `data/eval/verification_heldout.jsonl`, scored against the recipes of the generator, which are not published | held_out | the model and the code |
| 46 | Cases of the held out set where the adjudicated reading and the recipe of the generator agree | the labels of the reading against the recipes of the generator, which are not published | held_out | the two blind readings and the adjudication |

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

## The held out set, and the first number over data nobody decided on

The held out set of the verification is the set of forty eight cases that no decision of this repository was taken
against. It was written by a generator over a synthetic ledger of a seed the rest of the repository does not use, in
six templates that the tuning sets do not have, and it carries the three negative controls: a claim with no evidence
at all, a claim whose evidence contradicts itself, and a benign claim that the evidence does not support.

Its labels come from **two independent blind machine readings with an adjudication of the divergences**
([ADR-059](decisions/ADR-059-the-held-out-set-is-read-by-two-blind-machines-and-adjudicated.md)). The recipe of the
generator was written in a file that the two readers were forbidden to open, that file is not published now, the id of
a case does not encode its template, and the templates are not grouped in the file. The labels show that the readings
are not a copy of the key: each of the two readings disagrees with it in two of the forty eight cases. The generator
that writes the recipes is public and deterministic, so anybody can rebuild the key: the blindness of the reading is a
procedure and not a secret. The provenance of the reading, with the digests of its files and the limit of what they
prove, is in [data/eval/heldout/provenance.md](../data/eval/heldout/provenance.md). The label of the adjudication
wins over the label of the generator, and every disagreement is on the record, with the count of them. The decision
that supersedes the sentence of ADR-052 about the role is
[ADR-062](decisions/ADR-062-the-role-held-out-exists-and-the-sentence-of-adr-052-is-superseded.md).

| Set | Dataset | Cases | Accuracy | Reading |
|---|---|---|---|---|
| Held out | `data/eval/verification_heldout.jsonl` | 48 | 0.500 | 24 of the 48 cases, with the denominator of the set |
| Held out, the cases the model judged | the same file, the 47 cases with evidence | 47 | 0.489 | 23 of the 47, and one case decided by the code |

**The same verifier scores 25 of the 48 cases when it is scored against the recipes of the generator instead of the
adjudicated labels.** The one case of the difference is `ho-002`: the verifier answers `not_enough_evidence` for it,
the recipe expects `not_enough_evidence` and the adjudicated reading answers `supported`. That one case is the whole
distance between reproducing the generator and generalising, so the published number is 24 of the 48 cases, 0.500,
the one measured against the adjudicated labels. The recipes themselves are not published, and the number of 25 of
48 is published here because a reader who decides whether to trust 0.500 needs to see how close the two numbers are.

The confusion matrix, with the reader in the rows and the verifier in the columns:

| the reader \ the verifier | supported | contradicted | not_enough_evidence | total |
|---|---|---|---|---|
| supported | 10 | 0 | 9 | 19 |
| contradicted | 2 | 10 | 11 | 23 |
| not_enough_evidence | 2 | 0 | 4 | 6 |
| total | 14 | 10 | 24 | 48 |

**The false `supported` is 4 and the false `contradicted` is 0.** The verifier says `not_enough_evidence` for half
of the set, 24 cases of the 48, and the blind reading said `not_enough_evidence` for six. The error of the verifier
over unseen data is not that it is wrong in one direction: it is that it refuses to decide, and it refuses most of
the time.

**This number is the first one of this repository that is not a fit.** Every other accuracy of this document was
measured over a `tuning` set, over the very sentences the thresholds were chosen against. This one was measured over
a set that no decision of this repository was taken against, so it is a measure of the behaviour on unseen data, with
its denominator and with the restriction of the role.

### The counts of the reading, and what they may claim

| Count | What it is | What it is for |
|---|---|---|
| 2 of 48 | the cases where the two readings diverge (`ho-013` and `ho-035`) | the noise of the rule, with no answer key anywhere near it |
| 2 of 48 | the cases where the first reading and the recipe disagree (`ho-002` and `ho-013`) | the distance between one blind reading and the expectation of the writer |
| 2 of 48 | the cases where the second reading and the recipe disagree (`ho-002` and `ho-035`) | the same distance, measured on the other reading |
| 46 of 48 | the cases where the adjudicated reading and the recipe agree, 95.8 % of the set | the agreement of the second opinion with the key, which is a measurement of the set and not of the reader |
| 25 of 48 | the accuracy of the verifier scored against the recipes of the generator | the distance between reproducing the generator and generalising, which is the one case that separates it from the 24 of 48 |
| 24 of 48 | the adjudicated accuracy over the set | the accuracy of the verifier over the set, with its denominator |

Both divergences between the two readings are the same two cases, the pair whose evidence contradicts itself: the
row of the settlement says the payout was made and the excerpt of the schedule says a period with a negative net
gets no payout, so the cited evidence gives two opposite answers and says nothing. The adjudication applied the rule
that is in the header of every screen of the reading, that evidence which contradicts itself says two things and so
says nothing, and the label is `not_enough_evidence` in both cases.

**What these counts may not claim.** The reading is a machine reading, so it may share a blind spot with the model
that the set measures, and the number cannot rule that out. The agreement of the adjudicated reading with the key,
46 of the 48 cases, is a measurement of the set and not of the independence of the reader: the reading landed where
the writer of the cases landed, so it is not independent evidence of the quality of the labels. The divergence
between the two readers is a lower bound on the noise of a label, and not an upper bound. The labels are not the
labels a human would have given.

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
6. Every accuracy named above, except the one over the held out set, is a number over a `tuning` dataset, so none of
   them is a generalization to unseen data. The accuracy over the held out set, 24 of 48, is the only one that may be
   presented as a measure over data nobody decided on, and it may be presented only with its denominator and with the
   restriction of the role. The 25 of 48 the same verifier scores against the recipes of the generator is not the
   accuracy of the set: the labels of the set are the adjudicated ones and the recipes are not published, so that
   number may be cited only as the distance between reproducing the generator and generalising, and never as the
   accuracy of the verifier over the held out set. A number that claims to generalize names the dataset it was
   measured over and the restriction that applies to it, or it does not go out.

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
  that the role `held_out` was empty when the record was written.
- **[ADR-053](decisions/ADR-053-the-held-out-set-and-the-blind-labelling.md)** and
  **[ADR-059](decisions/ADR-059-the-held-out-set-is-read-by-two-blind-machines-and-adjudicated.md)**, the decisions
  that hold the set and its blind reading: the set that no decision was taken against, and the two readings with an
  adjudication that labelled it.

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
- `scripts/measure_heldout.py` writes the number over the held out set, and `tests/verify/test_measure_heldout.py`
  holds the shape of that report with the scripted model, so the denominators cannot move without a test noticing.
  The report itself is [`data/eval/report_heldout.md`](../data/eval/report_heldout.md).

## The divergence this slice reconciled

The metadata said `calibration.sets.verification_set: 30`, and the verification set has 43 records. The name said
"verification set" and the number was the one of the subset that goes through the NLI. It was not a calculation error:
it was a naming error. From now on the metadata says each number with what it counts, and the test checks it.

The second half of the same problem is now closed by the manifest: the numbers name the dataset they were measured
over, and the manifest says which bytes that dataset was, so a number can be checked against the file it came from.
