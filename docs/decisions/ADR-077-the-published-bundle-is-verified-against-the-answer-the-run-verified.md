---
type: adr
status: accepted
date: 2026-11-24
---

# ADR-077: The published bundle is verified against the answer the run verified

Status: accepted. Date: 2026-11-24.

## Context

ADR-073 asks that the label a published bundle shows is the label the code of the repository gives for the evidence
the bundle publishes. The check of that promise rebuilds the result of the run out of the published events and hands
it to the verifier, and the claims of the run are extracted from the answer again, exactly as the run extracted them.

The rebuild read the answer from the span of the investigation, which is the final answer of the run. It is not
always the answer the run verified. The escalation adds a notice to the answer when the reference source could not
give a rate and the model did not name the missing rate itself: "The reference rate EUR-BRL 2026-10-20 could not be
obtained: the FX source was unavailable. What depends on it was not calculated and the case was sent to human
review." That notice is added after the verification, because the escalation decides what happens to the case and
the verifier decides the claims.

The catalogue of the scripted model never showed the difference, because its answers already name the rate that was
missing. The recording of a real model does not: the model of the scenario S11 answered that the source was
unavailable without naming the rate, the escalation added the notice, and the check found two claims that the run
never had. The bundle published four labels and the code found six.

## Decision

**The check rebuilds the claims of the run from the answer the run verified, which the bundle publishes in the span
of the verifier.**

1. **The answer of the verification is the answer of the run.** The span of the verifier carries the answer the
   verifier received, and the claims of the run were extracted from that text. The rebuild reads it from there.
2. **The final answer is still what the site shows.** The span of the investigation keeps the answer with the
   notice of the escalation, and the reader of the site reads that one. The bundle publishes both texts, and the
   difference between them is the notice, which the escalation span explains.
3. **A bundle without a span of the verifier falls back to the final answer.** A recording that has no verification
   has no claims to rebuild, and the check says so instead of inventing an answer.

Why the notice stays in the answer and the notice does not become a claim: the notice tells the reader which rate is
missing, and a sentence of the product that nobody verified is not a claim of the run. The escalation names it as
missing information, and that is where a reader looks for it.

## Alternatives considered

- **To add the notice before the verification, so that the final answer is the verified answer.** Refused. The
  notice says that the case was sent to human review, and at the time the answer is assembled the escalation has
  not decided that yet: the sentence would claim something that had not happened.
- **To drop the notice from the answer.** Refused. The answer of a case whose rate is missing has to say which rate
  is missing, and that was the decision of ADR-072.
- **To compare only the claims that the run published and to ignore the ones the code finds.** Refused. A check
  that ignores the claims it does not expect hides the differences it is meant to catch, and the extra claims of
  this case were the symptom of a text that was not the text of the run.
- **To publish the answer the run verified as the answer of the investigation.** Refused. The answer the visitor
  reads is the final one, and it is the one that carries the notice.

## Consequences

- **The check of ADR-073 covers the catalogue of a real model**, because the claims it rebuilds are the claims of
  the run and the evidence is the evidence the bundle publishes.
- **The bundle publishes two texts of the answer** when the escalation added its notice: the answer of the run and
  the final answer. Both are in the trace, and the difference between them is the notice of the escalation.
- **The catalogue of the scripted model does not change**: its answers name the missing rate, so the notice was
  never added to them, and the answer of the verification is the answer of the investigation.

## Links

- [ADR-072, a currency the reference source does not publish is missing data and the case goes to a person](ADR-072-a-currency-the-reference-source-does-not-publish-is-missing-data-and-the-case-goes-to-a-person.md)
- [ADR-073, the published bundle carries the evidence its verdict was computed on and it is reproducible](ADR-073-the-published-bundle-carries-the-evidence-its-verdict-was-computed-on-and-it-is-reproducible.md)
- [ADR-075, the site publishes two catalogs and each bundle declares the one it belongs to](ADR-075-the-site-publishes-two-catalogs-and-each-bundle-declares-the-one-it-belongs-to.md)
- [ADR-076, the answer of the run is published whole because the claims are extracted from it](ADR-076-the-answer-of-the-run-is-published-whole-because-the-claims-are-extracted-from-it.md)
- [the rebuild of the published result](../../ledgerlens/replay/verdict.py)
- [the notice of the escalation](../../ledgerlens/verify/escalation.py)
