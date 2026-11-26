---
type: adr
status: accepted
date: 2026-11-23
---

# ADR-066: The pages of the live mode exist and the README was the one that was wrong

Status: accepted. Date: 2026-11-23.

## Context

[ADR-035](ADR-035-the-facade-of-the-live-mode.md) was accepted on 15 November 2026, and it decided the facade of the
live mode, the vault of the application and the run of the visitor. Two of its sentences say, in the present tense, that
the pages of the live mode do not exist: the pages that consume the mode "are not part of this milestone", because "the
work on `apps/` is paused" (`:384` to `:385` and `:388`).

Those sentences were true when they were written. The milestone they talk about is R3, the release that brings your own
key, and the work on `apps/` was paused at that moment. R3 has since shipped: every task of its specification is
checked, 87 of the 87 tasks of `specs/003-r3-bring-your-own-key/tasks.md`, and the pages of the live mode are on the
disk. The page of the live mode is `apps/web/app/(public)/live/page.tsx`: it exports the page of the mode (`:101`),
opens the session of the visitor (`:124`), reads the catalogue of the models of the server (`:125`) and accepts the
credential that the visitor brings (`:183`). The route `/live` of the site is the one that serves it.

The sentence travelled from the record to the documents. The root README repeated it, and so did the Portuguese
README: both said that the routes exist and the pages that consume them do not. The readiness audit of 2027 then read
that sentence and built on it, and it wrote that the live mode section was missing from the Portuguese README when the
two READMEs were in parity.

An accepted record is not edited: a change of an accepted decision is a new record. The decision of ADR-035 did not
move, and the facade it decided is the facade that shipped. What moved is the world the record was taken in, and the
sentence that described it.

## Decision

**The pages of the live mode were delivered in R3, the README was the artefact that was corrected, and the sentences of
ADR-035 that say that the pages do not exist are superseded by the sentence of this record.**

### The sentences that are superseded

| the record | the sentence | what it becomes |
| --- | --- | --- |
| [ADR-035](ADR-035-the-facade-of-the-live-mode.md) `:384` to `:385` | "The live mode has its own application and its own router, and the pages that consume it are not part of this milestone: the answers of the server are the contracts they will be written against." | The live mode has its own application and its own router, and the pages that consume it were delivered in R3, written against the answers of the server. |
| [ADR-035](ADR-035-the-facade-of-the-live-mode.md) `:388` | "The pages of the live mode are not part of this milestone, because the work on `apps/` is paused." | The pages of the live mode were not part of this milestone when the record was written, and they were delivered in R3. |
| `README.md:169` | "the routes exist and the pages that consume them do not" | the routes and the pages that consume them were delivered in R3 |
| `README.pt-BR.md:171` | the same sentence as the English one, in Portuguese: the routes exist and the pages that consume them did not yet | the routes and the pages that consume them were delivered in R3 |

The two READMEs are not decision records and they are corrected in place. The sentences of the record are not
corrected in place, and the sentences that the world made false are named in the table above.

### What the repository can prove

- **That the pages exist.** The page of the live mode is on the disk, it exports the component of the mode and it
  calls the three things that the mode is: the session, the catalogue of the models and the credential of the visitor
  (`apps/web/app/(public)/live/page.tsx:101`, `:124`, `:125` and `:183`).
- **That the release shipped.** Every task of the specification of R3 is checked, 87 of the 87
  (`specs/003-r3-bring-your-own-key/tasks.md`).
- **That the roadmap agrees.** The rows of R3 of the roadmap carry the state of their release and the specification
  that holds the evidence (`docs/roadmap-v3.md`).

### The cost of this record

A sentence that says in the present tense that a page does not exist is a sentence that a reader of 2027 will quote,
and the whole point of this cycle is that the published documents say what is true. The README is the document that a
stranger reads first, and it was the document that carried the false sentence, so the README is the document that was
corrected.

## Alternatives considered

- **To edit ADR-035 in place.** Refused. An accepted record is not edited, and the decision of ADR-035 is the decision
  that shipped: the live mode has its own application and its own router.
- **To say nothing and to leave the sentence of the record as it is.** Refused. A reader who follows the link of the
  README lands on a record that says the pages do not exist, and the two documents then contradict each other.
- **To rewrite the whole of ADR-035.** Refused. The record describes a milestone, and a milestone that has shipped is
  described by a record that says so, not by a record that has been rewritten to look as if it always knew.
- **To correct the README and to leave the audit of 2027 alone.** Refused. The audit reads the documents, so a
  document that says the opposite of the truth turns the audit into a second source of the false sentence.

## Consequences

- **The two sentences of ADR-035 are superseded** and the tense of the records is honest.
- **The README and the Portuguese README carry the truth** about the pages of the live mode, and the two stay in
  parity.
- **The readiness audit of 2027 reads the pages as they are**, and the gaps it ranks are the gaps that are still open.
- **The number of the live mode does not change.** The pages do not carry a published metric of their own, and the
  contracts of the server are the ones that ADR-035 decided.
- **The debt of this record is the same as the debt of ADR-035.** The pages of the live mode were written against the
  answers of the server, and the trajectory of a real run of a visitor is not published yet.

## Links

- [ADR-035, the facade of the live mode](ADR-035-the-facade-of-the-live-mode.md)
- [ADR-039, the wired application of the demo](ADR-039-the-wired-application-of-the-demo.md)
- [the folder of the site](https://github.com/erikunha/ledgerlens/blob/870b2f9/apps/web/README.md), and the page of the live mode in it,
  `apps/web/app/(public)/live/page.tsx`
- [the specification of R3](../../specs/003-r3-bring-your-own-key/spec.md)
- [the roadmap of the releases](../roadmap-v3.md)
