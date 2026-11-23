---
type: adr
status: accepted
date: 2026-11-23
---

# ADR-062: The role held out exists, and the sentence of ADR-052 is superseded

Status: accepted. Date: 2026-11-23.

## Context

[ADR-052](ADR-052-the-manifest-of-the-eval-datasets.md) decided, on 2026-11-22, that `data/eval/datasets.json` is the
single source of what the datasets of the repository are, and that a dataset carries one of three roles: `tuning`,
`validation` and `held_out`. The third role was declared over nothing, and the record said so in two places:

> Not one of the five datasets carries the role `held_out`.

(`:81`), and

> No dataset of this repository carries the role `held_out` today, so no result of this repository may be presented as
> a generalization to unseen data.

(`:170-176`)

Both sentences were true on the day of that record. They became false the moment the role was declared, and ADR-053
said that this would happen: the sentence of ADR-052 "becomes false the moment the role is declared" (`:131-132`). The
manifest now declares the role `held_out` over `data/eval/verification_heldout.jsonl`, the labelled set of the blind
reading of [ADR-059](ADR-059-the-held-out-set-is-read-by-two-blind-machines-and-adjudicated.md), and the number over
that set is published.

ADR-052 is an accepted record, and an accepted record is not rewritten: a change of an accepted decision is a new
record (`AGENTS.md:20`). So the two sentences stay where they are, and this record says what is true in the present
tense.

### The decision of ADR-052 stands, and what changed is the state of the world

Nothing of the decision of ADR-052 moved. The manifest is still the single source of what the datasets are, their
digest, their count, their origin and their role, and the role is still decided by evidence with the conservative role
winning when the evidence is not clean. What changed is the world the decision was taken in: the milestone that ADR-052
named as the next one built the set, read it blind and declared the role.

The manifest is therefore the truth about the roles from now on. A reader who wants to know which datasets carry the
role `held_out` reads `data/eval/datasets.json`, and not this record and not ADR-052: the manifest is a file that the
gate checks, and a record is a sentence that the gate does not.

The contamination policy that ADR-052 wrote as one sentence in every entry of the manifest (`:156-164`) has been
rewritten in the manifest, because the sentence it carried said that no dataset of the repository carries the role
`held_out`. The manifest is the file that holds the policy, and the file moved with the role. ADR-052 is not rewritten
by that: the decision it took, that the policy is one sentence and the same in every entry, stands, and the sentence
inside it changed with the world.

### The answer key is not published, and the guard refuses it by path

The answer key of the generator that wrote the set is `data/eval/heldout/recipes.jsonl`. It is not published and it
is not declared by the manifest.

The two readings were instructed to be blind to it, and the repository cannot prove that they were: the key was on
the disk of the owner during the reading, because it had been committed to the local branch on 2026-11-22 at 20:23
and the readings ran on 2026-11-23 at 07:31. What the labels themselves show is that the readings are not a copy of
the key, because each of the two readings disagrees with it in two of the forty eight cases, and a reading that had
the key open would have agreed with it everywhere. The provenance of the reading, with the digests of its files and
the limit of what they prove, is in [`data/eval/heldout/provenance.md`](../../data/eval/heldout/provenance.md).

The guard that refuses it is the one of ADR-052: `require_tuning_path` in `ledgerlens/eval/manifest.py` refuses a path
that no entry of the manifest declares, with a `TuningRefusal` that names the path and says that only the datasets with
the role `tuning` may be tuned against. The recipes are refused for the same reason that any undeclared file is
refused: the manifest is what says which file is which, and a file that no entry names is a file that nobody may tune
on. It is refused by its path and not by a role, because the answer key has no role: it is not a dataset of the
repository.

### The blindness of the reading was a procedure and not a secret

The generator of the set, `ledgerlens/eval/heldout.py`, is public, and it is deterministic: the same seed, the same
ledger and the same bytes, which `tests/eval/test_heldout_generator.py` proves. Anybody can rebuild the key of the set
from the public tree, with the seed 7301 that the manifest declares.

So the blindness of the reading was a procedure and not a secret. The two readers were told not to open the key, and
the repository cannot prove that they did not, because the key was on the disk of the owner while they read. What the
labels show is that the readings are not a copy of the key: each of the two readings disagrees with it in two of the
forty eight cases, and a reading that had the key open would have agreed with it everywhere. This is the honest shape
of the claim, and it is the shape ADR-059 already gave it: the reading was blind in the only sense that a procedure can
be blind.

### The sentence of ADR-059 that the reading made false

ADR-059 says at `:36` that the blind file exists and that the labelled file does not exist yet. The reading happened on
2026-11-23 and the labelled set exists, so that sentence became false when the reading was executed. It was a statement
of the state of the world on the day of that record, and this record supersedes it for the present tense: the labelled
set exists, the manifest declares it, and the number over it is published.

## Decision

**The decision of ADR-052 stands, the manifest is the truth about the roles, and the sentence of ADR-052 about the role
`held_out` is superseded by this record for the present tense.**

The sentence that replaces the two sentences of ADR-052 is this one, and it is the sentence the documents of the
repository quote from now on:

> The manifest of the datasets declares the role `held_out` over the labelled set of the blind reading, and no number
> over any other dataset of this repository may be presented as a generalization to unseen data.

What a published number over the held out set may claim, and what it may not, is the second half of this record.

**A number over the held out set MAY claim:**

- the accuracy of the verifier over the forty eight cases of the adjudicated set, with its denominator: 24 of the 48,
  0.500, with 23 of the 47 cases that go through the NLI model and one that the code decides;
- that it is the first number of this repository that is not a fit. The set is the one that no decision of the
  repository was taken against, and every other accuracy was measured over the sentences the thresholds were chosen
  against;
- the rate of the false `supported` and of the false `contradicted`, the costly error of ADR-007: 4 and 0 over the set;
- the three counts of the reading: the 2 of the 48 cases where the two readings diverge from each other, the 2 where
  the first reading and the recipe of the generator disagree, and the 2 where the second one and the recipe disagree;
- that the labels came from two independent blind machine readings with an adjudication of the divergences, and the
  reader of the number is told so.

**A number over the held out set MAY NOT claim:**

- that it measures a rate of the product. It measures the NLI path over six templates of claims against rendered
  evidence of one generated world, and it guides a decision;
- that the labels are the labels a human would have given. The reading was a machine reading, and the sentence that
  says so is part of the number and not a footnote of it;
- that the reading is free of a shared blind spot with the model that the set measures. The readers and the model are
  language models, two of them may be wrong in the same place, and no number here can rule that out;
- that the set is free of contamination with the model that will be measured by it;
- that the divergence between the two readings is the error rate of the labels. It is a lower bound on the noise of a
  label and not an upper bound;
- that any accuracy over a tuning set is a generalization. The 1.0 over the 30 text cases of the verification set, the
  0.625 over the 40 live sentences and the 0.786 over the 70 NLI cases remain measurements of the fit over the sets
  the decisions were taken against, and this record does not move them.

## Alternatives considered

- **Rewriting the two sentences of ADR-052.** Refused. ADR-052 is an accepted record, and the rule of the repository is
  that a change of an accepted decision is a new record (`AGENTS.md:20`). A record that was edited in place cannot tell
  a reader what was decided and when.
- **Adding a note to ADR-052 that points at this record.** Refused for the same reason: a note is an edit of an
  accepted record. The index of the decision records lists both records, and the link between them is the navigation.
- **Deleting the two sentences of ADR-052.** Refused. A record that loses a sentence is a record that says it never
  thought what it thought, and the sentence of a record is the history of the decision.
- **Saying nothing and letting the manifest answer.** Refused. The sentence of ADR-052 is quoted by other documents, and
  a quoted sentence that is false stays false in the mouth of whoever quotes it. The supersession has to be a record,
  with the sentence that replaces it.
- **Publishing the answer key of the generator, so that anybody could check the number against it.** Refused. A key
  that is public is not a key, and the reading that produced the labels would have been a reading with the key next to
  it. The counts of the divergence are published instead, and they are the distance between a blind reading and the
  expectation of the writer of the case.
- **Calling the blindness a secret.** Refused, and this record says why. The generator is public and deterministic, so
  anybody can rebuild the key: the blindness was a procedure, and a procedure that nobody is told about is not a blind
  reading but a hidden one.

## Consequences

- The decision of ADR-052 stands, and so does its sentence about the state of the world on the day it was written. A
  reader of ADR-052 learns what was true then, and a reader of this record learns what is true now.
- The roles live in one file and in one place. The manifest says which datasets carry the role `held_out`, the gate
  refuses when it drifts from the disk, and no document of the repository has to repeat the list to be right.
- The number over the held out set is 0.500 over 48 cases, and it is the only accuracy of the repository that is not a
  measurement of the fit. It is also the smallest one, and that is what an unseen set says.
- The answer key of the generator is not published, and the guard refuses it by its path. The reading stays blind
  because the procedure makes it blind, and the procedure is public.
- The debt of ADR-052 is paid and the debt of ADR-059 is not. The held out set of the retrieval does not exist, so the
  0.67 of the recall at 3 is still a number over the twelve questions the embedding model was chosen against.

## Links

- [ADR-052, the manifest of the eval datasets](ADR-052-the-manifest-of-the-eval-datasets.md)
- [ADR-053, the held out set and the blind labelling](ADR-053-the-held-out-set-and-the-blind-labelling.md)
- [ADR-059, the held out set is read by two blind machines and adjudicated](ADR-059-the-held-out-set-is-read-by-two-blind-machines-and-adjudicated.md)
- [the manifest of the datasets](../../data/eval/datasets.json)
- [the evaluation of the verifier](../evaluation.md)
