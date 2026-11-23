# The evaluation of this repository, and what each number is allowed to claim

This page answers one question, for a reader who did not read the code: **is any number published by this repository
a generalization, or is it a fit?** The short answer is written down in the manifest of the datasets and it is checked
by the gate, but the answer is easy to miss when it lives in a JSON file, and this repository would rather say it
twice than have a reader infer it.

The long answer is here.

## The one rule

> Every number names the dataset it was measured over, and the restriction that applies to that dataset.

A number without its dataset is a claim about nothing in particular. A number without its restriction is a claim
about more than the measurement supports. The canonical place where every number of this repository is written with
its dataset and its restriction is [the sets of the verifier](verification_sets.md). This page is the map that says
where the truth lives and why it lives there.

## Three roles, and what each one allows

The datasets of `data/eval/` do not all have the same status. The manifest gives each one a **split role**, and the
role decides what may be done with it. The decision that defines the roles is
[ADR-052](decisions/ADR-052-the-manifest-of-the-eval-datasets.md).

| Role | What it is | What may be done with it | What may NOT be done with it |
|---|---|---|---|
| `tuning` | A set a decision of this repository was taken against | It may be read, and a threshold, a prompt or a hyperparameter may be chosen against it | Its number may not be published as a generalization to unseen data |
| `validation` | A set that may be scored but never tuned against | It may be scored | It may not be used to choose anything |
| `held_out` | A set that no decision of this repository was taken against | It may be read by the final scoring step, and only by it | A tuning script that reads it has to fail, and it does |

The guard that enforces the third row is code, not a convention. `ledgerlens/eval/manifest.py` refuses a dataset
whose role is not `tuning` to a tuning script, and it refuses with a sentence that names the dataset, the role it
has and the role that is allowed. `scripts/sweep_nli_thresholds.py` refuses to run when the manifest of the disk is
not the manifest the calibration was measured over, and it refuses to read a held out dataset. The refusal has a
non zero exit code, so a script that tries cannot pass by accident.

```mermaid
flowchart LR
    A["A dataset of data/eval/"] --> B{"the role in the manifest"}
    B -->|tuning| C["may be tuned against"]
    B -->|validation| D["may be scored only"]
    B -->|held_out| E["may be read by the final scoring only"]
    C --> F["a number over it is a fit, never a generalization"]
    D --> F
    E --> G["a number over it may be a generalization, with its denominator"]
```

## The manifest, and what it pins

[`data/eval/datasets.json`](../data/eval/datasets.json) is the single source of what the datasets of this repository
are. Every entry pins:

- the **sha256** of the bytes of the file, so that a number can be checked against the file it came from;
- the **record count**, so that a number with a denominator has a denominator that is written down;
- the **source**, the story of how the cases were made, in words;
- the **labeling version**, the pass of labelling the set went through;
- the **split role**, and therefore what the numbers over it may claim;
- the **scenario seed**, when the cases come from a generated world;
- the **contamination policy**, the sentence that says what is forbidden.

The check is `scripts/check_eval_datasets.py`, and it is a step of `scripts/gate.sh` and of the first job of the
continuous integration. It reads the disk, recomputes the fingerprints, and refuses with a readable reason when a
dataset moved without the manifest moving with it, when a declared dataset is missing, or when a dataset of the
folder is not declared. A dataset that moves breaks the build, and the fix is a write of the two fingerprints
followed by a review of the diff.

The notes of each entry carry the evidence for the role, and they are written against the interest of the number.
The entry of the online evaluation says that the answer key of six of its cases was changed after a run, that the
trajectory equivalence that lets one tool count as another was added so that the tool the agent chose would count,
and that three of its questions are the few shot examples of the system prompt of the agent. The entry of the live
sentences says that the sweep of ADR-007 used those very sentences to choose the thresholds, so the 0.625 over them
is a tuning number. A reader who wants to know whether a number is a generalization can read those notes and find
out without trusting the headline.

## The calibration, and the pin that holds it

The NLI thresholds live in `ledgerlens/verify/thresholds.json`. They were chosen by the rule of
[ADR-007](decisions/ADR-007-nli-verification.md) over the seventy NLI cases of the two tuning sets, so they are a
fit to those cases and not a generalization.

The calibration now names the bytes it was measured over. The pin holds the sha256 of the manifest it was measured
against, the datasets that took part in the sweep, the version of the NLI model and the log of the sweep. When the
manifest moves, the pin stops agreeing with it, and `scripts/pin_calibration.py` is the script that re-pins it. The
pin is what stops a quiet change of a dataset from turning the numbers of the past into numbers about something
else.

## The held out set, and the number over it

The held out set of the verification is the set of forty eight cases that no decision of this repository was taken
against. It was written by a generator over a synthetic ledger of a seed that the rest of the repository does not
use, in six templates that the two tuning sets do not have, and it carries the three negative controls the roadmap
asks for: a claim with no evidence at all, a claim whose evidence contradicts itself, and a benign claim that the
evidence does not support.

Its labels come from **two independent blind machine readings with an adjudication of the divergences**. The recipe of
the generator lives in a file neither reader opened, the id of a case does not encode its template, and the templates
are not grouped in the file. The label of the adjudication wins over the label of the generator, and every
disagreement between the two is on the record, with the count of them. The decisions are
[ADR-053](decisions/ADR-053-the-held-out-set-and-the-blind-labelling.md) and
[ADR-059](decisions/ADR-059-the-held-out-set-is-read-by-two-blind-machines-and-adjudicated.md).

**The role is declared and the number is published.** The manifest declares the file with the role `held_out`, and
the accuracy over it is 24 of the 48 cases, 0.500, with 23 of the 47 cases that go through the NLI model and one case
that the code decides because the claim cites no evidence at all. The false `supported` is 4 and the false
`contradicted` is 0. The report is [`data/eval/report_heldout.md`](../data/eval/report_heldout.md) and the canonical
reading of every number is in [the sets of the verifier](verification_sets.md).

This is the first number of this repository that is not a fit. Every other accuracy was measured over the very
sentences the thresholds were chosen against. This one was measured over cases that no decision of this repository
was taken against, so it says what the verifier does with data it has never seen, which is a harder and less
flattering answer than the tuning sets gave.

### The three counts of the reading

| Count | What it is |
|---|---|
| 2 of 48 | the cases where the two readings diverge from each other |
| 2 of 48 | the cases where the first reading and the recipe of the generator disagree |
| 2 of 48 | the cases where the second reading and the recipe of the generator disagree |

The divergence between the two readers is a measurement of the noise of the rule, and it is the only one of the three
that was made with no answer key anywhere near it. The divergence of each reader against the recipe measures the
distance between a blind reading and the expectation of the writer of the generator.

**What these counts may not claim.** The readers are language models, so a reading may share a blind spot with the
model the set measures, and the number cannot rule that out. The divergence between the two readers is a lower bound
on the noise of a label, and not an upper bound. The labels are not the labels a human would have given, and no
sentence of this repository may say that they are.

## What the held out set does not measure

It measures the NLI path over six templates of claims against rendered evidence of one generated world. It does not
measure the sentences the agent writes at run time, the rate of the human review, the numeric path, the coherence
path, or any generalization to traffic outside the sample ledger. A number over it guides a decision and does not
measure a rate.

It does not measure the blind spot of the reader either: the labels came from two language models reading the same
evidence, so the number over the set says what the verifier does with the labels of two careful machine readers, and
not what it would do with the labels of a person.

## The debt: the held out set of the retrieval does not exist

The retrieval of this repository is measured with a recall at 3 over the twelve questions of
`data/eval/policy_questions.jsonl`, and those twelve questions are a tuning set: ADR-006 chose the embedding and
the query transform with the recall over them. So the retrieval number of this repository is a fit and not a
generalization, in the same words that ADR-052 used for the verifier. When the roadmap asks for a dense against a
hybrid comparison over the same relevance labels, the labels have to come from a set that no decision of the
retrieval was taken against, and such a set does not exist yet.

The three properties of the held out set of the verification are the three the retrieval set needs as well: the
cases written by a generator, the labels read blind to the recipe, and the guard that refuses a tuning script that
reads them. The instrument of the blind reading serves both, because the evidence of a retrieval question is a
passage and the evidence of a verification case is an envelope, and the reader judges the same three labels in both.
The reading is a machine reading with two readings and an adjudication, as ADR-059 decided, and the cost of that
decision is paid here too: the labels of the retrieval set will carry the same blind spot that the labels of the
verification set carry.

## Where the truth lives

| What you want to know | Where it is |
|---|---|
| What every published number means, with its dataset and its restriction | [the sets of the verifier](verification_sets.md) |
| What the datasets are, with their sha256, their count, their role and their story | [`data/eval/datasets.json`](../data/eval/datasets.json) |
| What a role means, and what the repository decided about contamination | [ADR-052](decisions/ADR-052-the-manifest-of-the-eval-datasets.md) |
| How the held out set is written and how it is labelled, and why the reading is blind | [ADR-053](decisions/ADR-053-the-held-out-set-and-the-blind-labelling.md) and [ADR-059](decisions/ADR-059-the-held-out-set-is-read-by-two-blind-machines-and-adjudicated.md) |
| The number over the held out set, with its denominator and its confusion matrix | [`data/eval/report_heldout.md`](../data/eval/report_heldout.md) |
| What the thresholds are and what they were measured over | [`ledgerlens/verify/thresholds.json`](../ledgerlens/verify/thresholds.json) and [ADR-007](decisions/ADR-007-nli-verification.md) |
| What the verifier decides and what each label means | [ADR-007](decisions/ADR-007-nli-verification.md) |
| Whether the disk still matches the manifest | `scripts/check_eval_datasets.py`, a step of the gate |

## The tests that hold all of this

- `tests/eval/test_dataset_manifest.py` ties the manifest to the disk: every entry matches the file it names, and no
  dataset of the folder is left out.
- `tests/eval/test_dataset_documentation.py` reads the two READMEs and the canonical document, and fails when a
  public number stops naming its dataset, its role and the decision that says what the role means.
- `tests/eval/test_tuning_guard.py` proves that the guard refuses to tune against a set that was not meant for it.
- `tests/verify/test_calibration_pin.py` proves that the pin and the manifest agree.
- `tests/verify/test_verification_sets.py` ties the calibration metadata to the data files, with no model and no
  network.
- `tests/eval/test_heldout_generator.py` proves the properties of the held out set: the six templates, the eight
  instances of each, the exclusion of the ids of the tuning material, the novelty against the two tuning sets and
  the reproducibility of the bytes.
- `tests/eval/test_heldout_reader.py` proves that the case with no evidence reaches the verifier instead of being
  dropped, and that the reader counts the split between the cases that go to the model and the ones that do not.
- `tests/eval/test_label_heldout.py` proves the instrument of the reading: that the mode `compare` never opens the
  recipes, that the build writes the origin of the reading in every line, and that an incomplete reading is refused.
- `tests/verify/test_measure_heldout.py` proves the shape of the report of the measurement, with the denominators and
  the confusion matrix, with the scripted model and no network.

A number of this repository that is not held by a test is a number that is not published.
