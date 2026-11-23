---
type: adr
status: accepted
date: 2026-11-24
---

# ADR-069: The reservation follows the content of the case, and the key of the set is not published

Status: accepted. Date: 2026-11-24.

## Context

The review of this branch found two things about the reservation of the held out set.

The first is a hole in the guard. The guard of ADR-065 has four doors: the path of the file, the digest of its bytes,
the digest of its records and the digest of each case, in the projection that the sweep reads. The projection was
the five keys that a case of the sweep carries: the claim, the evidence, the ids of the evidence, the id of the case
and the label. The id of the case is the key of the join that rebuilds the set and the label of the line in the
sweep. It is not the content that the tuning optimizes. A rebuild that renames the cases carries the same claims,
the same evidence and the same labels, so it tunes over the same truth with the same effect on the number, and the
guard accepted it: the sweep over that rebuild measured 0.617 where the set measures 0.489. A reservation that a
one line change defeats is not a reservation.

The second is the key of the generator. ADR-067 says that the expected label of a case "is not published and will not
be published, in any form, including a hash". Two of the artefacts that this branch published said otherwise. The
published labelled set, `data/eval/verification_heldout.jsonl`, and the published Markdown report,
`data/eval/report_heldout.md`, carried the note of the two cases where the blind reading disagreed with the recipes,
and that note named the expected label of the case and the fact that differs. The label of the reading is published
for the forty eight cases and the generator agrees with the reading in forty six of them, so a reader who had the
two labels of the diverging cases had the key of all forty eight. The promise of ADR-067 was false in the artefacts
that carry the promise.

Two more sentences of the accepted records do not survive the same review. ADR-065 says that "a copy of the labelled
set under another name passes those doors", and no copy ever did: the file of the set is reserved by its path and by
its digest, and what the doors of the case were for is the join that rebuilds the set from its own sources. ADR-067
says that "a reader of the public repository cannot run the measurement at all", because the file of the recipes is
not published. The generator is public and deterministic, and `uv run python -m ledgerlens.eval.heldout` rebuilds the
key of the set byte for byte, so the reader can do what the record says it cannot.

And the leak is older than this branch. The commit `619617e` of the branch, "feat(eval): the held out set, read by
two blind machines and measured", carries the two notes with the expected label and the fact that differs, and that
commit is in `origin/feature/v3`. Redacting the files of the tree does not take the key out of the history of a
public branch.

## Decision

**The reservation of the held out set follows the content of a case and not the identifier of the case, and the key of
the set is not published, in the artefacts of the tree or in the notes of a divergence.**

### The projection of a case has four keys

The projection is the claim, the evidence, the ids of the evidence and the label. The id of the case is not part of
it, because the id is the key of the join and the label of the line in the sweep, and a rebuild that renames the
cases tunes over the same truth. The fifty digests of the cases are the digests of that projection, and a rebuild
with the ids renamed is refused like the join itself.

### A note of a divergence names the reading and nothing else

The note of a case where the reading disagreed with the recipes says which label the reader gave and that the recipe
expected a different label. It does not name the expected label and it does not name the fact that differs, because
the fact that differs narrows the expected label to a candidate or two and a determined reader turns that into the
label. The view of the operator, the mode `report` of `scripts/label_heldout.py`, keeps the detail: the tool is local,
it runs on the machine of the person who has the recipes and its output is never published. What leaves the machine
does not carry the key.

### The sentences of ADR-065 and ADR-067 that said otherwise are superseded by this record

The copy of the labelled set under another name never passed the doors of the case, because the doors of the case are
for the join. The reader of the public repository can rebuild the key of the set, because the generator is public and
deterministic, and the published reports therefore never claim that the measurement cannot be run.

## Alternatives considered

- **To keep the id of the case in the projection and to close the hole some other way.** Refused. Every other way
  keeps a reservation that a rename defeats: the sweep that tunes over the renamed rebuild measures the same truth
  with a better number, and the number published over the set stops being a measurement of the generalization.
- **To publish the expected label of the two diverging cases and to amend ADR-067.** Refused. The label of the
  reading is the truth of forty six of the forty eight cases, and the two labels of the diverging cases would
  complete the key. A published key ends the property that ADR-052, ADR-062 and ADR-065 defend.
- **To publish the fact that differs and to withhold only the expected label.** Refused. The fact that differs, with
  the claim and with the evidence, narrows the expected label of the case to a candidate or two, and a determined
  reader picks the right one.
- **To rewrite the history of the branch to take the key out.** Refused, and not only because it is destructive. A
  branch that is rewritten after every leak is a branch that no reader can check, and the records of this repository
  are worth more than the secrecy of two labels. The key is disclosed instead, in this record and in the readiness
  audit, and the set is treated as spent.
- **To leave the two notes as they are and to write that the key is public.** Refused. A key in the tree is a key in
  every copy of the tree, and the notes are cheap to redact.

## Consequences

- **A rebuild of the set with the identifiers renamed is refused**, with the same door that refuses the join, and the
  sweep over it can no longer raise the number.
- **The published artefacts no longer carry the key**: the labelled set, the Markdown report and the JSON report name
  the label of the reading, the label that the model predicted and the identifiers of the two diverging cases, and
  nothing that names the label the generator expected.
- **The number of the set does not change**: it stays 24 of 48, 0.500, and it is reproducible with the real model of
  the commit that the calibration recorded.
- **The set is spent as a reserve, and this record says so.** The key of the forty eight cases is in the history of
  the branch at the commit `619617e`, so a future change can be tuned against those cases by anybody who reads the
  history. The guard of ADR-065 still refuses the set as a tuning target, and the guard is what protects the files;
  what is spent is the claim that the number measures the generalization. The readiness audit of 2027 carries the debt
  that this record opens: a new held out set has to be read blind before any number of this repository is presented
  again as a measurement of unseen data.
- **The reading is still a procedure and not a secret**, which is what ADR-059 and ADR-062 already said. What changes
  is that the repository now says which sentences were false and when.

## Links

- [ADR-052, the manifest of the eval datasets](ADR-052-the-manifest-of-the-eval-datasets.md)
- [ADR-059, the held out set is read by two blind machines and adjudicated](ADR-059-the-held-out-set-is-read-by-two-blind-machines-and-adjudicated.md)
- [ADR-062, the role held out exists](ADR-062-the-role-held-out-exists-and-the-sentence-of-adr-052-is-superseded.md)
- [ADR-065, the reservation of the held out set follows the case and not only the file](ADR-065-the-reservation-of-the-held-out-set-follows-the-case-and-not-only-the-file.md)
- [ADR-067, the measurement of the held out set is published without its answer key](ADR-067-the-measurement-of-the-held-out-set-is-published-without-its-answer-key.md)
- [the guard of the tuning](../../ledgerlens/eval/manifest.py)
- [the tool of the reading](../../scripts/label_heldout.py)
- [the published report](../../data/eval/report_heldout.md)
