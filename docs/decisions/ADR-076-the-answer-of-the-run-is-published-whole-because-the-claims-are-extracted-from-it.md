---
type: adr
status: accepted
date: 2026-11-24
---

# ADR-076: The answer of the run is published whole, because the claims are extracted from it

Status: accepted. Date: 2026-11-24.

## Context

The published trace cuts a text at six hundred characters and says what it left out ("…+340 chars"). The cut was
made for the texts of the conversation: the messages of the model, the excerpts of a policy, the answer of a tool.
A text of that kind is reference material, and the reader of the recording has the evidence of the claims in the
events of the tools.

The answer of the run is not a text of that kind. It is the text the claims are extracted from: the verifier reads
the answer, splits it in sentences, and links every sentence that carries a citation to the evidence it cites. The
bundle then publishes the label of every claim of the run and the evidence of every claim, and ADR-073 asks that the
label the bundle publishes is the label the code of the repository gives for the published evidence.

That promise held for the catalogue of the scripted model, because the answers of that catalogue were written to
fit: the longest of them has five hundred and seventy seven characters. It does not hold for a recording of a real
model, because nobody writes the answer of a real model to fit. The first recording of a real run of the scenario
S01 answers in one thousand one hundred and seventeen characters, the trace publishes the first six hundred of them
with the marker of what was left out, and the check of ADR-073 finds three differences: two claims of the run are
gone from the published answer and the label of a third one changes, because the sentence that carried it is cut in
the middle.

The recording was not wrong. The recording published what the trace of the product publishes. The promise was the
thing that could not hold, because the answer the recording publishes was not the answer the run gave.

## Decision

**The answer of the run is published whole, up to a limit no model of the product reaches, and every other text
keeps the cut of six hundred characters.**

1. **The answer is a field of its own in the rule of the cut.** The compaction of the trace already knows the name
   of the field it is cutting, and the field `answer` gets a limit of sixteen thousand characters. The limit is a
   limit and not an absence of one: the output of a model is bounded, and a text that passes it is cut with the
   marker, so a bundle always says what it left out.
2. **The cut of the other texts does not move.** The messages of the model, the excerpts of a policy and the answer
   of a tool keep the six hundred characters, because they are reference material and the payload of the site stays
   inside the budget of the specification.
3. **The catalogue of the scripted model does not change.** Its longest answer has five hundred and seventy seven
   characters, which the old rule already published whole, and no other published text of the catalogue carries the
   name `answer`. The nine bundles and the export of the sandbox catalogue are the same bytes after this change,
   and the capture that made them makes them again.

Why the answer and not the conversation: the claims are extracted from the answer and from nothing else. A cut
conversation takes no claim away, because the evidence of a claim is published in the events of the tools, and a cut
answer takes the claims away, because the answer is where they are written.

## Alternatives considered

- **To cut the answer and declare that the catalogue of a real model is not re-verifiable.** Refused. A catalogue
  whose labels a reader cannot rebuild is a catalogue of claims, and the whole point of publishing a recording of a
  real run is to let a reader check it.
- **To raise the cut of every text.** Refused. The texts of the conversation are reference material and the payload
  of the site is bounded by the specification; raising the cut for them would change the published catalogue of the
  scripted model for no reason.
- **To write the answer of the catalogue of a real model by hand, short enough to fit.** Refused. A hand-written
  answer is the recording of the scripted model, and the catalogue of a real model exists to be a recording of a real
  run.
- **To publish the answer outside the trace, in a field of the manifest.** Refused. The manifest is the description
  of the package and the answer is the content of the run; a field of the manifest is read by nobody and breaks the
  contract of the manifest.

## Consequences

- **The trace publishes the answer of the run whole**, in the live mode of the product and in the recording alike.
- **The check of ADR-073 covers the catalogue of a real model**, because the answer the bundle publishes is the
  answer the run gave, and the claims and their labels can be rebuilt from it.
- **The payload of a scenario grows by the size of the answer**, which the budget of the specification (SC-004)
  measures and the gate checks.
- **A model that answers with more than sixteen thousand characters has its answer cut**, with the marker that says
  so, and the labels of the claims of that sentence cannot be rebuilt. The limit is far above the answer of a real
  run of the product.

## Links

- [ADR-071, the wall and the ceiling of the loop are in every path and the cut is named to the visitor](ADR-071-the-wall-and-the-ceiling-of-the-loop-are-in-every-path-and-the-cut-is-named-to-the-visitor.md)
- [ADR-073, the published bundle carries the evidence its verdict was computed on and it is reproducible](ADR-073-the-published-bundle-carries-the-evidence-its-verdict-was-computed-on-and-it-is-reproducible.md)
- [ADR-075, the site publishes two catalogs and each bundle declares the one it belongs to](ADR-075-the-site-publishes-two-catalogs-and-each-bundle-declares-the-one-it-belongs-to.md)
- [the rule of the cut](../../ledgerlens/observability/trace.py)
- [the claims of the run](../../ledgerlens/verify/checks.py)
