---
type: adr
status: accepted
date: 2026-11-24
---

# ADR-080: The rule of the dashes governs the writing of the repository, and the recording of a real model is published as it is

Status: accepted. Date: 2026-11-24.

## Context

The repository has a zero tolerance rule: no em dash (U+2014) and no en dash (U+2013) in any text of the repository.
The guard that enforces it (`tests/test_public_clean.py`) reads every tracked file, line by line.

The rule was written for the writing of the repository: the documentation, the code, the comments, the prompts, the
policy data and the interface are ours, and a dash in them is a style that the repository does not carry. The rule of
the language of the repository says the same thing about the words: it scans the surfaces this repository writes
(ADR-016), and the data of the repository is outside that scan because the data is not the writing of this repository.

The recordings of a real model are data of the repository, and they are the writing of the model. The first recording
of the real catalogue that carried a dash shows it: the answer of the scenario S11 says "the payment and the refund
were processed in different currencies, EUR for the payment and BRL for the refund", with an em dash between the
words. The model wrote it, the run verified it, and the bundle publishes the answer the run gave (ADR-076).

Three ways were open to the repository, and one of them was refused for a reason that belongs to no style rule:

- **To edit the answer of the recording.** Refused. ADR-076 asks the bundle to publish the answer the run gave, so
  that the claims of the run can be extracted from it and the label of every claim can be rebuilt. A bundle that
  publishes an answer nobody wrote is the failure ADR-076 was written for.
- **To refuse the recording and to record the scenario again.** Refused. It makes the publication of the catalogue a
  coin flip: the answer of a model is not written to a rule, so a recording is refused and the operator records it
  again, and the same happens on every refresh of the catalogue. A rule of typography decides what the catalogue
  holds, and the catalogue is the product.
- **To keep the recordings of the real catalogue outside the rule of the dashes.** Accepted.

## Decision

**The rule of the dashes governs the writing of this repository. The recordings of a real model are published as the
model wrote them, and they are outside the rule. The recordings of the scripted model are our writing and stay
inside it.**

1. **The exemption is narrow and it is named.** The guard spares the files of the two folders that hold the
   recordings of a real model: `data/eval/replay-real/` (the canonical bundles) and `site/replay-real/` (the
   published copies). Nothing else is spared: the documentation, the code, the tests, the policy data, the
   interface and the recordings of the scripted model are all inside the rule.
2. **The exemption is proved to be narrow.** The guard has a test of its own: a file of the recordings of a real
   model may carry a dash, a file of the recordings of the scripted model may not, and a file of the documentation may
   not.
3. **The rule keeps its shape for everything else.** A dash in a file of the repository still fails the gate, and the
   gate still fails the publication.

Why the recordings of the scripted model stay inside the rule: their answer is written by this repository, in
`ledgerlens/demo.py`, and it is the same answer in every recording. It is our writing and it obeys our rules.

Why the recording of a real model is the writing of the model: the model wrote the answer, the run verified it and
the bundle publishes it. The bundle is the evidence of the run and the evidence is not edited.

## Alternatives considered

- **To normalise the dashes of the answer into hyphens, the way the import of the v3 package does (ADR-012).**
  Refused, and the refusal is the whole of this decision: ADR-012 normalises the typography of a package that the
  repository versions as documentation. The recording is versioned as evidence, and a published answer that is not
  the answer the run gave is the failure of ADR-076. A dash in a data file is cheaper than a broken promise.
- **To put the recordings of a real model outside the repository.** Refused. The recording is the published proof of
  the product, and ADR-073 asks the bundle to be in the repository, with the digests that a reader checks.
- **To let the guard spare the dashes of any data file.** Refused. The rule is about the writing, and the data of
  this repository that is ours (the policy data, the datasets of the evaluation, the index) stays inside it.

## Consequences

- **The repository carries a dash in the recordings of the real catalogue**, and the guard says so in the place
  where the rule lives, with the reason.
- **The catalogue of a real model can be recorded again without a coin flip**, and the answer of every recording is
  the answer the run gave.
- **The recordings of the scripted catalogue are inside the rule**, and a dash in one of them still fails the gate.
- **A reader of the rule knows what it governs**: the writing of the repository, and not the text a model wrote in a
  run that the repository publishes.

## Links

- [ADR-012, the v3 package versioned in `docs/design/`](ADR-012-v3-package-versioned-in-docs-v3.md)
- [ADR-016, the Brazilian Portuguese translation layer](ADR-016-brazilian-portuguese-translation-layer.md)
- [ADR-073, the published bundle carries the evidence its verdict was computed on and it is reproducible](ADR-073-the-published-bundle-carries-the-evidence-its-verdict-was-computed-on-and-it-is-reproducible.md)
- [ADR-076, the answer of the run is published whole, because the claims are extracted from it](ADR-076-the-answer-of-the-run-is-published-whole-because-the-claims-are-extracted-from-it.md)
- [the guard of the public repository](../../tests/test_public_clean.py)
