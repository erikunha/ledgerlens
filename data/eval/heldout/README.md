# The held out set

This folder holds the held out verification cases of the repository: 48 cases that nobody tuned anything against and
that one person labelled by reading them.

Two files live here and they never meet:

- `cases.jsonl` is the file the person reads. Every line is one case with its id, its claim and its evidence. It
  holds **no label, no template name, no recipe and no id that says which template the case belongs to**. The ids run
  from `ho-001` to `ho-048` in an order that does not group the templates together.
- `recipes.jsonl` is the file the person never sees. Every line is the recipe of one case of the other file: the
  label the generator expects (`label`), the template of the case (`template`), the pair it belongs to (`pair_id`), the
  fact the pair changes (`fact_key`, `fact_value` and `differing_fact`) and, for the three controls, what makes the
  case a control (`control`).

The recipe is read by the blind reading session, `scripts/label_heldout.py`, which compares the label the reader
gives with the label the recipe expects and writes every disagreement into the note of the case.

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
The generator expects 18 supported, 24 contradicted and 6 without enough evidence. **The person who reads the set may
disagree with any of them, and the disagreement is the measure of the set**: the recipe and the label are allowed to
disagree, and each disagreement is recorded.

## What the set does not hold

No case is a numeric case and none is a coherence case: every case is one claim, and no claim carries an amount, so
no label of the set is computed by the code that judges it.

No case names a record of the tuning material. The exclusion is read, not written: the module reads the ids of the
tuning datasets and of the manifest of the scenarios when it builds the set, because the synthetic ledger reuses the
id space of the sample ledger and the collision would not be automatic.

The shape of the set differs from the shape of both tuning sets, and no claim of the set is closer to a claim of the
tuning material than the token overlap ceiling of the module. Both properties are proved by the test of the
generator, `tests/eval/test_heldout_generator.py`.

## The folder and the manifest of the datasets

The folder sits outside the scan of `data/eval/*.jsonl`, so neither file of it is a dataset of
`data/eval/datasets.json` and the manifest does not know them. The labelled set that the sweep reads is declared by
the coordinator, not by this folder.
