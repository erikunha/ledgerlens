# The held out set

This folder holds the held out verification cases of the repository: 48 cases that nobody tuned anything against,
whose labels come from two independent blind readings of the cases and from an adjudication of the two cases where
the readings diverged. The two readers were instructed to be blind to the recipe of a case, and the labels show that
the readings are not a copy of it: each of the two readings disagrees with the recipe in two of the forty eight
cases, and a reading that had the recipe open would have agreed with it everywhere. The file that holds the recipes
is not published either: it is not in the public tree and the manifest of the datasets does not declare it. The
provenance of the reading, with the digests of its files and the limit of what they prove, is in
[`provenance.md`](provenance.md).

The reading is what produces the labels, and its own files are the record that it happened:
`labels_reader_a.jsonl` and `labels_reader_b.jsonl` hold what each reader answered, one line per label, and
`labels_adjudicated.jsonl` holds the label of each case of the set, with the reason of every decision of the
adjudication. The label of the adjudication is the label of the set. The label the generator expected is never
written over it.

The files of this folder and the key never meet:

- `cases.jsonl` is the file the readers read. Every line is one case with its id, its claim and its evidence. It
  holds **no label, no template name, no recipe and no id that says which template the case belongs to**. The ids run
  from `ho-001` to `ho-048` in an order that does not group the templates together.
- `recipes.jsonl` is the file the readers were forbidden to open, and it is **not published**: it is not in the public tree, it is
  not in the index of git and no entry of the manifest of the datasets declares it. Every line is the recipe of one
  case of the other file: the label the generator expects (`label`), the template of the case (`template`), the pair
  it belongs to (`pair_id`), the fact the pair changes (`fact_key`, `fact_value` and `differing_fact`) and, for the
  three controls, what makes the case a control (`control`).
- the three files of the labels hold what the readers answered and what the adjudication decided, and they hold no
  recipe and no template.

The recipe is read by the instrument of the reading, `scripts/label_heldout.py`, which compares the labels with the
recipe and writes every disagreement into the note of the case. The mode `compare` compares two readings with each
other and never opens the recipe at all, so the divergence between the two readers is measured with no answer key
anywhere near it.

The generator is `ledgerlens/eval/heldout.py`. The cases come from the synthetic ledger of the seed 7301, which the
simulator of the repository builds and the module reads. The module writes both files:

```bash
uv run python -m ledgerlens.eval.heldout
```

## What the set holds

Six templates, eight instances each:

| Template | The shape of the claim |
| --- | --- |
| `hedge_shape` | A claim with a hedge. |
| `compound_shape` | A claim with two facts joined by "and", where the premise carries only one of them. |
| `negation_shape` | A claim with a negation inside the sentence. |
| `relative_period_shape` | A claim with a relative clause about a period. |
| `range_shape` | A claim with a number written as a range. |
| `two_source_shape` | A claim whose premise is the concatenation of two tools at once. |

The set carries the three negative controls the reconciliation asked for, and the machine finds each of them by
reading the data and not by reading a flag:

- a claim that cites **no evidence at all**, in the hedge template;
- a claim whose **evidence contradicts itself**, in the two source template: the settlement row says a payout was made
  for a period whose net amount is negative and the excerpt of the policy says a period with a negative net amount
  gets no payout;
- a **benign claim the evidence does not support**, in the compound template: the premise says the refund was issued
  and the claim says the customer received the money.

The labels the recipes expect are the labels of the verifier: `supported`, `contradicted` and `not_enough_evidence`.
The generator expects 18 supported, 24 contradicted and 6 without enough evidence. The reading is allowed to disagree
with any of them, and **the disagreement is the measure of the set**: the recipe and the label are allowed to
disagree, and each disagreement is recorded in the note of the case.

## What the reading found

The adjudicated reading answers 19 supported, 23 contradicted and 6 without enough evidence. It disagrees with the
recipe of the generator in 2 of the 48 cases, and the two readings disagreed with each other in 2 of the 48 as well:

| Count | What it is |
|---|---|
| 2 of 48 | the cases where the two readings diverge from each other, `ho-013` and `ho-035` |
| 2 of 48 | the cases where the first reading and the recipe disagree, `ho-002` and `ho-013` |
| 2 of 48 | the cases where the second reading and the recipe disagree, `ho-002` and `ho-035` |

Put the other way round, the adjudicated reading agrees with the recipe of the generator in **46 of the 48 cases,
95.8 % of the set**, and the two exceptions are the same two cases the table names.

**What that agreement means.** The blind reading is a second opinion that lands in the same place as the writer of
the cases, so it is not independent evidence of the quality of the labels: a reader who asks whether the labels are
right cannot use this number to find out. What the number does say is that the set is not ambiguous on those points,
that 46 of the 48 cases carry a label that a careful reader of the same evidence reaches as well, and that the
generator and the reading are not two things that disagree about the set.

The two cases where the readings diverged are the pair whose evidence contradicts itself. The adjudication applied
the rule that is in the header of every screen of the reading, that evidence which contradicts itself says two
things and so says nothing, and the label of both cases is `not_enough_evidence`.

The number over the set, and what it may claim, are in
[`data/eval/report_heldout.md`](../report_heldout.md) and in
[`docs/verification_sets.md`](../../docs/verification_sets.md).

## What the set does not hold

No case is a numeric case and none is a coherence case: every case is one claim, and no claim carries an amount, so
no label of the set is computed by the code that judges it.

No case names a record of the tuning material. The exclusion is read, not written: the module reads the ids of the
tuning datasets and of the manifest of the scenarios when it builds the set, because the synthetic ledger reuses the
id space of the sample ledger and the collision would not be automatic.

The shape of the set differs from the shape of both tuning sets, and no claim of the set is closer to a claim of the
tuning material than the token overlap ceiling of the module. Both properties are proved by the test of the
generator, `tests/eval/test_heldout_generator.py`.

## The blindness is a procedure and not a secret

The recipes are not in this folder any more and they are not in the public tree: the file was removed from the index
of git and no entry of the manifest of the datasets, `data/eval/datasets.json`, declares it, so the guard of the
tuning refuses a path that no entry declares. The generator that writes them is public and deterministic, so anybody
can rebuild the key at any time:

```bash
uv run python -m ledgerlens.eval.heldout
```

What the procedure guarantees is narrower and it is what matters: the readings happened while the key was still out of
the public tree, and the readers were forbidden from opening it. The protection of the role of the set is the
procedure, the guard and the review of this repository, and not a secret.

## The folder and the manifest of the datasets

The folder sits outside the scan of `data/eval/*.jsonl`, so the files of it are not datasets of the scan. One of
them is declared anyway, in `data/eval/datasets.json`, with the role `held_out`: the labelled set of the reading,
`data/eval/verification_heldout.jsonl`. The key of the generator is not declared, because it is not published: no
entry of the manifest names it, and the guard of the tuning refuses a path that no entry declares, so a tuning script
cannot read it.
