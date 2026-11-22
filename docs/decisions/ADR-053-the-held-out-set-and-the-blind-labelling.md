---
type: adr
status: accepted
date: 2026-11-22
---

# ADR-053: The held out set and the blind labelling

Status: accepted. Date: 2026-11-22.

## Context

The manifest of ADR-052 says what the five datasets of `data/eval/` are and what may be done with each one, and it
says that no dataset of this repository carries the role `held_out` today. R4 asks for the opposite: a set that no
decision of the repository was taken against, and a calibration that names the bytes it was measured over.

The calibration of `ledgerlens/verify/thresholds.json` is now pinned (ADR-052 and the pin of milestone 20), and the
guard of `ledgerlens/eval/manifest.py` refuses a tuning script that reads a set which is not of the role `tuning`.
What is missing is the set itself: 48 verification cases that differ from the sets of the tuning in template, in
text and in source structure, and whose labels nobody in this repository chose to make the verifier look good.

### The label is the product of this milestone

Milestone 20 publishes the set and its provenance. The number over it arrives in milestone 21. So the question this
record has to answer is not "how good is the verifier over unseen data" but "where does the label of a case come
from, and can the label be wrong in a way that nobody can see".

Three positions were debated by a board of specialists and decided by a judge, with the repository as the only
evidence. The judge scored them on integrity, power, cost and reproducibility:

| position | integrity | power | cost | reproducibility |
| --- | --- | --- | --- | --- |
| P1 the hand | 3 | 4 | 4 | 3 |
| P2 the construction | 2 | 3 | 3 | 5 |
| P3 the second reader | 1 | 1 | 3 | 1 |

P2 was rejected as the position of record: a label that is a function of the writer is a tautology, and
`specs/004-r4-verifier-calibration/spec.md` forbids it in as many words ("An agent that writes a case and labels it
produces a tautology, so the writing and the labeling are two different acts by two different readers"). P3 was
rejected because it breaks FR-006 word for word, because the repository already ruled on that shape in the wrong
direction (ADR-052: the answer key of EC-19 to EC-24 was moved after the agent ran over the set, and that is one
reason `eval_cases` is a tuning set), and because a labeler that performs the same judgment as the model under test
reproduces the blind spot of that model: the 15 cases that are still wrong at the chosen thresholds are all
`not_enough_evidence` predictions (ADR-007).

## Decision

**The generator writes the cases. One person reads the labels, blind to the recipe of each case. The recipe and the
label are allowed to disagree, and the disagreement counts.**

The cases are written by machine and every property of them is checkable:

1. **A new seed.** The cases come from a synthetic ledger built with the seed 7301, not the seed 42 that
   `SimConfig` uses by default (`ledgerlens/sim/config.py`). A different seed gives a different world, and the
   `scenario_seed` field of the manifest records it.
2. **A declared template inventory, written down before the reading.** Six named templates, eight instances each,
   forty eight cases. The templates carry a hedge, a compound, a negation inside the sentence, a relative clause
   about a period, a number written as a range, and a premise that is the concatenation of two tools at once. The
   range of the fifth template is a range of dates and not a range of money: a range of amounts would be judged by the
   numeric rule and not by the NLI model, and this set is the set of the NLI path. The
   set also carries the three negative controls that R4 asks for: a claim with no evidence at all, a claim whose
   evidence contradicts itself, and a benign claim that the evidence does not support.
3. **Pairs certified by code.** The cases come in pairs of the same template over the same record, with one fact
   changed between them, and the test proves the difference from the recipes rather than from a reading.
4. **The ids of the tuning material are excluded by code.** The synthetic world reuses the id space of the tuning
   world, so an exclusion has to be proved: at build time the module reads every id named by the five tuning datasets
   and by the manifest of the scenarios, the claims and the evidence alike, and a case that names one of them is
   refused. The exclusion is the strict superset of the forty ids the judge listed, sixty one ids in all, because an id
   that appears in the evidence of a tuning case is still a record of the tuning material. The cost of that strictness
   is measured and published: thirteen of the twenty four merchants of the synthetic ledger become unusable, so the
   pool of settlements falls from two hundred and sixty to one hundred and twenty six and the pool of chargebacks
   from seven to four.
5. **A novelty check against the two tuning sets.** The shape inventory of the held out set differs from the shape
   inventory of the two tuning sets, and no claim of the held out set exceeds the token overlap ceiling with any
   claim of a tuning set. The 30 text cases of `data/eval/verification_set.jsonl` carry prose evidence and the 40
   cases of `data/eval/verification_live.jsonl` carry rendered envelopes, so "a different source structure" means
   different from both.
6. **A re-derivation test of the case texts**, not of the labels.

The labels come from one person, and the split is explicit:

- The reader is given one case at a time, with the claim, the evidence rendered the way the model will read it, the
  rule of ADR-007 in the header of every screen and three empty boxes.
- The recipes live in a file the reader never opens, and the case id never encodes the template, so the reading is
  blind.
- The label of the reader wins over the recipe. Every disagreement with the recipe is written in the note of the
  case, and the count of the disagreements goes into this record.

That count is the measurement this repository has never had. It is the number that says how noisy a label can be,
read by somebody who did not write the case.

### Where the pieces live

The milestone has six pieces and the role of each of them is named here, so that nobody has to guess which file is
the blind one and which one is the truth:

| Piece | Path | What it is |
| --- | --- | --- |
| the generator | `ledgerlens/eval/heldout.py` | writes the two files below from the synthetic ledger of the seed 7301 |
| the blind file | `data/eval/heldout/cases.jsonl` | the forty eight cases as the reader sees them: an id, a claim, the ids of the evidence and the content of the evidence. No label, no template, no recipe |
| the recipes | `data/eval/heldout/recipes.jsonl` | the expectation of the generator for each case: the label, the template, the pair, the fact that differs and, for the three controls, what makes the case a control. The reader never opens this file |
| the reading instrument | `scripts/label_heldout.py` | shows one case at a time, saves every label as it is given, compares the labels with the recipes afterwards and builds the labelled set |
| the reader of the labelled set | `ledgerlens/eval/heldout_reader.py` | reads the labelled file for the sweep. It has a module of its own because the readers of the existing datasets do not understand this format, and because the case without evidence has to reach the verifier instead of being dropped |
| the tests | `tests/eval/test_heldout_generator.py`, `tests/eval/test_heldout_reader.py`, `tests/eval/test_label_heldout.py` | the properties above, proved |

The blind file carries no label, so the reader of the sweep refuses it as it stands. That is not a defect of the
reader: the labelled file does not exist yet, and it is the instrument of the blind reading that builds it, from the
labels the reader gave and the cases of the blind file. The manifest is declared over the labelled file and never over
the blind one.

### The rule that ADR-007 does not have

ADR-007 says what `supported`, `contradicted` and `not_enough_evidence` mean, and it admits that the reading is
subjective in the judgment cases. It says nothing about an evidence that contradicts itself. This record adds the
sentence:

> Evidence that contradicts itself says two things and so says nothing, therefore the label is `not_enough_evidence`.

The set carries one case of that shape, and the reader applies the sentence to it.

### What a tuning script is allowed to read

Only the datasets with the role `tuning`. The guard of `ledgerlens/eval/manifest.py` refuses the door with a
sentence that names the dataset, the role it has and the role that is allowed, and `scripts/sweep_nli_thresholds.py`
refuses to run when the manifest of the disk is not the one the calibration names. The recipes of the held out set
are not a dataset of the manifest: they live outside the scan of `data/eval/*.jsonl` and they are never read by a
tuning script.

### The numbers to update in the same milestone

`docs/verification_sets.md` (rule 6 and the table), `README.md` and `README.pt-BR.md` (the line that names the
43 case number), the sentence of ADR-052 that says no dataset carries the role `held_out` (it becomes false the
moment the role is declared), and `data/eval/datasets.json` (the new entry with the role `held_out`, the new
`scenario_seed`, the labelling version and a note that says what the set does not measure). Then the calibration is
re-pinned with `scripts/pin_calibration.py`, because the manifest moved.

## What the set measures, and what it does not measure

What it measures is the NLI path over six templates of claims against rendered envelopes of a new seed. What it does
not measure is the sentences the agent writes at run time, the human review rate, the numeric and the coherence
paths, or any generalization to traffic outside the sample ledger. A number over it guides and does not measure a
rate.

The repository does not publish an accuracy over this set in this milestone. The set and its provenance are the
product of milestone 20; the number over it is a decision of milestone 21, and it can only be published with the
denominator, the template table and the count of the disagreements that the reader had with the recipes.

## Consequences

- The set is reproducible: same seed, same bytes, and a test that proves it.
- The label can be wrong, and every instance of that is on the record: the note of the case and the count in this
  record.
- The cost is the reading. Forty eight cases at the rate measured on the live set is about two hours and ten
  minutes of reading, plus about twenty minutes for the disagreement pass and about fifteen minutes for the labels
  and the notes: about two hours and forty five minutes, in three sittings, once. If that time is not available,
  the fallback is the construction with the labels written by the rule and audited by a person on twelve cases, and
  then this record says "synthetic labels by construction, audited on 12 cases" and the milestone publishes the set
  and its provenance and no number at all.
- The role `held_out` is declared only over the complete labelled file. A file whose cases carry no label still has
  a count and a sha256, and a manifest entry is what gives a file a role, so a manifest that declares a role over an
  unread file is a manifest that lies.

## The debt of this record

The debt of ADR-052 was the held out set, and this record pays it. The debt of this record is the held out set of
the RETRIEVAL.

The retrieval of this repository is measured with a recall at 3 over the 12 questions of
`data/eval/policy_questions.jsonl`, and those 12 questions are a tuning set: ADR-006 chose the embedding
`BAAI/bge-small-en-v1.5` and the query transform with the recall over them, so the number 0.67 is a number over the
data the retrieval was tuned on. When the roadmap asks for a dense against a hybrid comparison over the same
relevance labels (`LL-V3-R12-03`), the labels have to come from a set that no decision of the retrieval was taken
against, and such a set does not exist today.

The three properties this record gives the held out set of the verification are the three the retrieval set needs
as well: the cases written by a generator over a new seed, the labels read by one person blind to the recipe, and the
guard that refuses a tuning script that reads them. The tool of the blind reading that milestone 20 writes serves
both, because the evidence of a retrieval question is a passage and the evidence of a verification case is an
envelope, and the reader judges the same three labels in both.

Until that set exists, the retrieval of this repository reports a fit and not a generalization, in the same words
that ADR-052 used for the verifier.
