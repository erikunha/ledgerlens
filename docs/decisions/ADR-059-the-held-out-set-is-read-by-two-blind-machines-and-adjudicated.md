---
type: adr
status: accepted
date: 2026-11-23
---

# ADR-059: The held out set is read by two blind machines and adjudicated

Status: accepted. Date: 2026-11-23.

## Context

[ADR-053](ADR-053-the-held-out-set-and-the-blind-labelling.md) decided that the labels of the held out set of the
verification come from one person, reading the cases one at a time, blind to the recipe of each case, and that the
label of the reader wins over the recipe (`:48-49` and `:80-87`). That record was accepted and it is not rewritten
here: an accepted record is not edited, and a change of an accepted decision is a new record (`AGENTS.md:20`). This
record extends ADR-053 and says in which part the extension goes.

What changed is the reader. The owner of the repository declared that the reading would not happen by his hand. Forty
eight cases at the rate measured on the live set is about two hours and forty five minutes, in three sittings, once
(ADR-053 `:153-158`). That time is not going to be spent, and the constraint is real. So the reading became a machine
reading, and this record decides what a machine reading is allowed to be.

A machine reading has a different risk profile than a human one. A person reading the cases shares nothing with the
model that will be measured by the set: the person did not write the cases and the person was not the model. A machine
reading is a reading by a language model, and the model that will be measured over the set is a language model too.
Both can be blind in the same places, so a reader that is blind to the recipes may still be blind in the same places
as the model, and no count of this repository can rule that out. The risk is not that the reading is dishonest. The
risk is that it is correlated in a way a human reading would not have been, and this record says so out loud, because
a reader who arrives in a year and finds a number over a machine reading must be told what the number is and what it
is not.

The instrument is already the shape this record needs. [scripts/label_heldout.py](../../scripts/label_heldout.py) has
the modes `read`, `report`, `build` and `compare` (`:760-816`), the override that points a reading at its own file of
labels (`:265-273`), the origin line that names the reading (`:89-96`) and the comparison of two readings that never
opens the recipes (`:724-757`). The blind file exists, the labelled file does not exist yet, and the measurement that
will read it is written ([scripts/measure_heldout.py](../../scripts/measure_heldout.py)). The reading is the first
step of the programme of [ADR-058](ADR-058-the-programme-of-readiness-for-2027-and-what-it-does-not-do.md) (`:97-100`
and `:115-119`).

## Decision

**The labels of the held out set come from two independent blind machine readings with an adjudication of the
divergences, and not from one person, because the owner of the repository is not going to read forty eight cases by
hand, and the reading still has to be blind and still has to carry a provenance.**

### 1. Two readers, each one a fresh session with no memory of the other

- Each reader is a fresh session with no memory of the other one. The second reader does not know what the first one
  answered, and the first one does not know that a second one exists while it reads.
- Each reader is blind to the recipes, in the strong sense: it is forbidden to open `data/eval/heldout/recipes.jsonl`,
  `ledgerlens/eval/heldout.py` and `data/eval/heldout/README.md`.
- Each reader is forbidden to open `docs/`, `specs/` and the local research folder of the 2027 audits. The first holds
  the decisions of this repository, the second the specifications of the milestones, and the third the findings of the
  auditors. A reader that reads any of them knows what the repository believes about the shapes of the claims, and a
  reader that knows that is no longer blind.
- Each reader labels the same forty eight cases, one at a time, with the rule of ADR-007 and the rule that ADR-053
  added for the evidence that contradicts itself (`scripts/label_heldout.py:101-126`). The screen shows the rule, the
  claim, the evidence as the model will read it and the three labels, and nothing else (`:475-509`).

The two readings write two files, one each, through the override of the instrument:
`data/eval/heldout/labels_reader_a.jsonl` and `data/eval/heldout/labels_reader_b.jsonl`.

### 2. The instrument stays the same, so the provenance of a label is the instrument

Nothing of the instrument changes: the same script, the same modes and the same screens. The only thing added is the
`--labels` override that sends each reading to its own file. The reason is the provenance: the label of a case is a
label the instrument recorded, and not a label a writer typed into a file.

The mode `compare` is the one mode that never opens the recipes (`scripts/label_heldout.py:724-757`). The reason is in
the sentence of its own docstring: the point of the comparison is to know the noise of the labels with no answer key
anywhere near it. It writes the count of the cases where the two readings diverge.

### 3. The adjudication of the divergences

A third session, the adjudicator, sees only two things: the two readings and the cases. It never sees the recipes.

- Where the two readings agree, that label is the label of the case. No third reading, no second opinion, no revision:
  agreement is the end of the matter for that case.
- Where the two readings diverge, the adjudicator decides the case and writes the reason. The reason is a sentence
  that names the fact of the claim that decided it, and it travels with the case in the note of the line, so that a
  reader can disagree with the decision and see why it was taken.

The adjudicator writes one file of labels, `data/eval/heldout/labels_adjudicated.jsonl`, with the forty eight labels
of the set: the agreed label where the readings agree and the decided label where they diverge. The file is built by
the mode `report` of the instrument, the mode that compares a reading with the recipes.

### 4. The recipe never overwrites a label

The rule of ADR-053 stands untouched: the label of the reading wins over the recipe, and the recipe is never written
over a label (`scripts/label_heldout.py:686-721`). The recipes are used for one thing only, after the reading is
finished: the count of the cases where the reading and the recipe do not agree is published, exactly as ADR-053
decided (`:86-90` and `:144-146`).

### 5. The origin of every line names the reading

Every line of the labelled set carries an origin, and the origin says who read the cases. The origin of this reading
is the constant `ORIGIN_TWO_READERS` of the instrument (`scripts/label_heldout.py:93-95`):

> `held out: blind reading by two independent machine readers with adjudication, ADR-059`

The origin of ADR-053, `ORIGIN_ONE_READER`, stays in the instrument with its own meaning, and the build takes the
origin as an argument (`--origin`). A label without a reader is a label without a provenance, and the reader is part
of what a number over the set may claim.

### 6. What the published numbers may claim, and what they may not

This is the whole of the risk of a machine reading, so the numbers over the set have to obey these two lists.

**A number over the held out set MAY claim:**

- the agreement between the two readings, a measurement of the noise of the rule of ADR-007 with no answer key
  anywhere near it;
- the agreement of each reading with the recipes of the generator, the distance between a blind reading and the
  expectation of the writer of the case;
- the accuracy of the verifier over the adjudicated set, with its denominator of forty eight;
- the confusion matrix of the reader against the verifier, which the renderer of the measurement already writes
  (`scripts/measure_heldout.py:399-418`);
- the rate of the false `supported`, the costly error of ADR-007 (`:106`).

**A number over the held out set MAY NOT claim:**

- that the labels are the labels a human would have given. The reading was a machine reading, and the sentence that
  says so is part of the number and not a footnote of it;
- that the reading is independent from the model in the sense of being free of a shared blind spot. The reader and the
  model are both language models, a correlated blind spot is possible, and no number here can rule it out;
- that the set is free of contamination with the model that will be measured by it. The cases and the readers are
  texts of language models, and a style they share is a contamination the counts below cannot see.

**What exists as a mitigation, and what it is not.** The mitigation is the divergence of the two readers: two readings
that never saw each other and that disagree on a case show that the rule has a soft edge there. That number is a lower
bound on the noise of a label and not an upper bound, because two machines that share a blind spot agree with each
other. It may never be read as the error rate of the labels.

### 7. The four counts that travel with the number

The number that goes to the README and to [docs/evaluation.md](../evaluation.md) carries four things, and a number
that carries only the accuracy hides the uncertainty it rests on.

| the count | what it is | what it is for |
| --- | --- | --- |
| reader A against reader B | the cases where the two readings diverge | the noise of the rule, with no answer key near it |
| reader A against the recipes | the cases where the first reading and the recipe disagree | the distance between one blind reading and the expectation of the writer |
| reader B against the recipes | the same count over the second reading | the same distance, measured on the other reading |
| the adjudicated accuracy over the set | the cases the verifier got right | the accuracy of the verifier over the set, with its denominator |

### 8. The tasks of `specs/004` that this record changes, and the ones it adds

The task list of the milestone is
[specs/004-r4-verifier-calibration/tasks.md](../../specs/004-r4-verifier-calibration/tasks.md). This record changes
T098, changes the wording of T114, and adds five tasks whose ids continue from T145, the last id of
[ADR-057](ADR-057-the-model-has-a-clock-and-the-repository-pins-it.md) (`:150-164`).

T098 becomes, in the format the tasks of the repository use:

```
- [ ] T098 Read the labels of the held out cases in two independent blind machine readings with an adjudication of the divergences, with the rule of ADR-007, and record the labeling version in the manifest - the agent that writes a case does not label it, and the agent that reads it does not see the recipe
```

T114 gains the counts of the section 7 beside the count of the disagreements with the recipes that it already asks
for. The other tasks are not touched: T099 still declares the role `held_out` before any threshold is chosen against
it, and T113 still asks for the held out set of the retrieval, whose labels this record decides are read blind to the
recipe by two readings and an adjudication when the reading is a machine one.

The tasks this record adds:

```
- [ ] T146 Test in tests/eval/test_label_heldout.py that the mode compare never opens the recipes, that the build writes the origin of ADR-059 in every line, and that an incomplete reading is refused
- [ ] T147 Run the first reading: a fresh session, blind to the recipes, over the forty eight cases of data/eval/heldout/cases.jsonl, writing data/eval/heldout/labels_reader_a.jsonl
- [ ] T148 Run the second reading: another fresh session, blind to the recipes and blind to the first reading, over the same cases, writing data/eval/heldout/labels_reader_b.jsonl
- [ ] T149 Compare the two readings with the mode compare and adjudicate every case where they diverge into data/eval/heldout/labels_adjudicated.jsonl, with the reason of every decision
- [ ] T150 Build the labelled set with the origin of ADR-059, declare the role held_out in data/eval/datasets.json, and publish the four counts of the section 7 in the two READMEs and in docs/evaluation.md
```

## Alternatives considered

- **Labelling the set with the recipes themselves.** Refused. The generator is the answer key, so the set would
  measure the generator against itself and nothing else, and the number would be high by construction. This is the
  position P2 of ADR-053, rejected as the position of record (`:37-39`).
- **The synthetic fallback, where the label comes from the construction of the case.** Refused for the same reason,
  and ADR-053 already refused it: the fallback publishes the set and its provenance and no number at all (`:155-158`).
- **One machine reader only.** Refused. A single reading has no noise measurement that does not depend on the recipes:
  the only comparison available is the reading against the answer key of the generator, which measures the distance
  from the writer and not the softness of the rule.
- **The owner reading the forty eight cases by hand.** Refused by the owner himself, and this record says so without
  blame: the constraint was real, the time was not going to be spent, and the cost of the constraint is paid in the
  claim that the number is allowed to make and not in a quiet gap in the documentation.
- **Dropping the blind reading and publishing the recipes as the labels.** Refused. It is the first alternative with
  the blind part removed, and it is the failure the held out set exists to prevent: a manifest that declares a role
  over a file whose labels came from the generator is a manifest that lies (`:159-161`).

## Consequences

- **The set exists.** Without a decision of this kind the labelled file would never exist, and the first number of
  this repository measured over data no decision was taken against would never be produced. The set is blind, it has a
  provenance, and the instrument that produced it is reproducible.
- **The reading is not a human reading.** Every number over the set carries that sentence, and the number may not be
  presented as a human labelling of the cases.
- **The cost of the reading is two sessions.** There are two readings and an adjudication instead of one reading by a
  person, and the time of the machine is not free either.
- **The divergence between two machines may understate the divergence between two humans.** Two machines that share a
  blind spot agree, so the count of the divergences is a floor under the noise and not a ceiling over it. The number
  is worth publishing and it is not the error rate of the labels.
- **The specification of the milestone has to be read with this record.** FR-006 of
  [specs/004-r4-verifier-calibration/spec.md](../../specs/004-r4-verifier-calibration/spec.md) says that the labels of
  the held out set come from a person reading the evidence (`:123-124`). This record changes the reader and keeps the
  blindness, so that sentence is read with this record and not against it.

## The debt of this record

The debt of this record is the contamination of the set by the style of the generator. Both the cases and the readers
are texts of language models, and a style they share is a contamination that the four counts of the section 7 cannot
see.

The way out of this debt is a human reading, and the human reading is still the decision of ADR-053. This record does
not revoke it: if a future version of the set is read by a person, ADR-053 is extended and that extension is a new
record, with the same shape as this one. The debt is named here so that the person who reads the number in 2027 knows
that the labels of the set are machine labels.
