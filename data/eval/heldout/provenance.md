# The provenance of the blind reading

Why this file exists: ADR-059 decides that the labels of the held out set come from two independent blind machine
readings with an adjudication of the divergences. A document that says only "two machines read it" is the word of
the owner and nothing else. This file records what a reader of the repository can check for himself, and it names
the limit of what he can check, because a record that hides its limit is worth less than no record.

## What happened

| the fact | the value |
| --- | --- |
| the date of the reading | 2026-11-23, between 07:31 and 08:22, the time of the machine of the owner (-03:00) |
| the sessions | three: the first reading, the second reading and the adjudication |
| the nature of each session | a fresh session of the runtime of the owner, with no memory of the other ones |
| the instrument | `scripts/label_heldout.py`, the mode `read` writes the label and the mode `report` writes the label of the case and its origin |
| the cases read | `data/eval/heldout/cases.jsonl`, the file that holds no label, no template and no recipe |

The first reading did not know that a second reading existed. The second reading did not know what the first one
answered. The adjudicator saw the two readings and the cases and nothing else.

The instruction that each session received allowed it to open the file of the cases and the screen of the
instrument, and forbade it to open `data/eval/heldout/recipes.jsonl`, `ledgerlens/eval/heldout.py`, the README of
this folder, `docs/`, `specs/` and the research folder of the audits of 2027.

## What a reader can check

The files of the reading are published with the digest of their bytes, and the history of the repository shows the
commit that first carried each one, so a reader can check that the labels did not change after the reading.

| the file | its sha256 | the commit that first carried it |
| --- | --- | --- |
| `data/eval/heldout/cases.jsonl` | `790425b3988984b9e6f00d1af3e7c06bcdc56de9c29973a22bbb6fc1ec89f844` | `50956b1` |
| `data/eval/heldout/labels_reader_a.jsonl` | `222d8411fa596ddf139e33d897b899c86d8692002e1f18e80a6173c9854a19ba` | `56bff5c` |
| `data/eval/heldout/labels_reader_b.jsonl` | `3153de3ffad5af26c0ff6fb0d6d4bf6f3b04de13f31947133b272aac34da1149` | `56bff5c` |
| `data/eval/heldout/labels_adjudicated.jsonl` | `09113557a540a153357cf405f68b5846e87c94cca28b8beadb9057bbc73764e2` | `56bff5c` |
| `data/eval/verification_heldout.jsonl` | `e8dbcdfbc3f75eafbd3cd3c6d88da5641175cec93b4a48109073c80438924212` | `56bff5c` |

A reader recomputes a digest with `shasum -a 256 data/eval/heldout/labels_reader_a.jsonl` and compares it.

## What a reader can check about the blindness itself

The answer key of the generator was on the disk of the owner during the reading: it had been committed to the
local branch on 2026-11-22 at 20:23, eleven hours before the first session started. It was never in the published
tree, because the public branch never carried it, and it is not published now.

So the blindness of the reading is a procedure and not an absence, and the repository cannot prove that the three
sessions obeyed the instruction they received. The transcripts of the sessions are part of the local notes of the
owner, and the local notes stay out of git.

What the labels themselves show is that the readings are not a copy of the key: each one of the two readings
disagrees with the key of the generator in two cases of the forty eight, and a reading that had the key open would
have agreed with it everywhere. The divergence is the evidence that the readings were made from the cases.

## What a number over the set may not claim

- That the reading was blind to the key in the sense of not being able to see it. It could see it.
- That the reading is independent from the model that the set measures. The reader and the model are both language
  models, and a correlated blind spot is possible.
- That the agreement of the reading with the key measures the quality of the labels. It measures how close a
  second opinion landed to the expectation of the writer of the cases, and the number is published in
  [`docs/verification_sets.md`](../../docs/verification_sets.md) and in
  [`docs/evaluation.md`](../../docs/evaluation.md).

ADR-059 holds the same three sentences in its section 6. This file does not weaken the record; it is the record
that says what the numbers rest on.
