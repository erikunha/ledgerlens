---
type: adr
status: accepted
date: 2026-11-23
---

# ADR-064: The sentences that assert the blindness of the reading as a fact are superseded

Status: accepted. Date: 2026-11-23.

## Context

Three accepted records of this repository say, in the present tense, that the readers of the held out set did not
open the answer key of the generator. The reading happened on 2026-11-23, between 07:31 and 08:22, and the answer key
was on the disk of the owner at that moment: the generator writes it next to the cases and the owner ran the generator
before the readings. The file was not in the published tree, and it was never in the public branch, but it was in the
working tree of the machine that ran the three sessions.

So the sentences are of two kinds. Some of them describe the instruction, which is a fact about what the sessions were
told, and they are true. The others describe what the sessions did, which the repository cannot prove: the transcripts
of the sessions are part of the local notes of the owner, and the local notes stay out of git.

An accepted record is not edited: a change of an accepted decision is a new record. The decisions themselves did
not move. What moved is the world they were taken in, and what the repository can prove about it.

## Decision

**The sentences that assert the blindness of the reading as a fact are superseded by the sentence of this record: the
readings were instructed to be blind to the key, the repository cannot prove that they were, and what the labels show
is that the readings are not a copy of the key.**

### The sentences that are superseded

| the record | the sentence | what it becomes |
| --- | --- | --- |
| [ADR-053](ADR-053-the-held-out-set-and-the-blind-labelling.md) `:84` | "The recipes live in a file the reader never opens, and the case id never encodes the template, so the reading is blind." | The recipes live in a file the reader was forbidden to open, and the case id never encodes the template, so the reading was blind in the only sense that a procedure can be blind. |
| [ADR-053](ADR-053-the-held-out-set-and-the-blind-labelling.md) `:101` | "The reader never opens this file" | The reader was forbidden to open this file |
| [ADR-059](ADR-059-the-held-out-set-is-read-by-two-blind-machines-and-adjudicated.md) `:51` | "Each reader is blind to the recipes, in the strong sense: it is forbidden to open ..." | Each reader is instructed to be blind to the recipes: it is forbidden to open ... |
| [ADR-059](ADR-059-the-held-out-set-is-read-by-two-blind-machines-and-adjudicated.md) `:76` | "It never sees the recipes." | It is forbidden to see the recipes. |
| [ADR-059](ADR-059-the-held-out-set-is-read-by-two-blind-machines-and-adjudicated.md) `:195` | "The set is blind, it has a provenance, and the instrument that produced it is reproducible." | The set was read blind by procedure, it has a provenance, and the instrument that produced it is reproducible. |
| [ADR-061](ADR-061-the-corpus-of-the-policies-is-the-contract-of-a-fictional-company.md) `:115` | "The recipes of the generator were not in the public tree while the reading happened, so the reading was blind in the only sense that a procedure can be blind." | The recipes of the generator were not in the public tree while the reading happened, and the reading was instructed to be blind to them, so the reading was blind in the only sense that a procedure can be blind. |

The decisions of the three records stand. The reading is the instrument of the labels, the label of the reading wins
over the recipe, the set freezes the corpus of its generation and the corpus of the policies is the contract of a
company that does not exist. What this record changes is the tense of six sentences.

### What the repository can prove about the blindness

- **The instruction.** Each session was forbidden to open the answer key, the module of the generator, the README of
  the folder, `docs/`, `specs/` and the research folder of the audits. The instruction is in the transcript of the
  coordinator and it is the shape of the three readings.
- **That the readings are not a copy of the key.** Each of the two readings disagrees with the key in two of the
  forty eight cases, and the adjudicated reading disagrees with it in two as well. A reading that had the key open
  would have agreed with it everywhere.
- **That the key was never published.** No commit of the published history carries it, the manifest does not declare
  it and the object of the key was pruned from the repository before the push.

### What the repository cannot prove

- **That the three sessions obeyed the instruction.** The transcripts are out of git, and the answer key was on the
  disk of the owner while they read. The repository cannot tell a reader that the sessions did not open it.

### The cost of this record

The claim of the blindness is now a claim about a procedure and about the agreement of the labels with the key, and
not a claim about the absence of the file. A reader who wants the guarantee of the blindness has to read the
provenance of the reading, in [`data/eval/heldout/provenance.md`](../../data/eval/heldout/provenance.md), where the
digests of the files and the limit of what they prove are written down.

## Alternatives considered

- **To edit the three records in place.** Refused. An accepted record is not edited, and the sentences are part of a
  decision that did not move.
- **To say nothing and to leave the six sentences as they are.** Refused. A sentence that says in the present tense
  that the readers never opened a file that was on their disk is a sentence that a reader in 2027 will quote, and the
  whole point of this cycle is that the published documents say what is true.
- **To publish the transcripts of the sessions.** Refused. The transcripts are the local notes of the owner and the
  local notes stay out of git. A transcript that is published would also publish the content of the sessions, which
  is the content of the cases, and the cases are published already.
- **To run the reading again, now that the key is out of the tree.** Refused for this cycle and left as the decision
  of ADR-053: a reading that is blind in the strong sense is a reading of a person, and the person is the owner. The
  next reading of a set of this repository has to be a human one, and this record says so.

## Consequences

- **The six sentences are superseded** and the tense of the records is honest.
- **The number over the held out set does not change.** It stays 24 of 48 (0,500) against the adjudicated labels, and
  the agreement of the reading with the key stays 46 of 48 (95,8 %).
- **The next reading has to be a human one**, and the debt of ADR-059 stays open until it is.

## Links

- [ADR-053](ADR-053-the-held-out-set-and-the-blind-labelling.md)
- [ADR-059](ADR-059-the-held-out-set-is-read-by-two-blind-machines-and-adjudicated.md)
- [ADR-061](ADR-061-the-corpus-of-the-policies-is-the-contract-of-a-fictional-company.md)
- [ADR-062](ADR-062-the-role-held-out-exists-and-the-sentence-of-adr-052-is-superseded.md)
- [the provenance of the reading](../../data/eval/heldout/provenance.md)
