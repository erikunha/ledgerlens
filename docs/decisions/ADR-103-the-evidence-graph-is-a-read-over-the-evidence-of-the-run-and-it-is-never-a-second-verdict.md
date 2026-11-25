---
type: adr
status: accepted
date: 2026-11-25
---

# ADR-103: The evidence graph is a read over the evidence of the run, and it is never a second verdict

Status: accepted. Date: 2026-11-25.

## Context

The verifier of the repository decides the verdicts of the claims of a run, and the bundle of a run publishes
the claims, the evidence and the verdicts. The design package of the evidence graph
([specs/010](../../specs/010-r8-evidence-graph-and-provenance/spec.md)) asks for the relation between the
claims, the evidence and the sources to be built and published: a graph that a reader can follow from a claim
to the line behind it, served by the API with the scope of the account, and published as an artifact beside the
bundle.

## Decision

**The graph is a read over the evidence of the run and never a second verdict, a citation that resolves to
nothing makes an orphan and never a near match, the scope of an account is applied when the data is read, and
no graph database is added.**

### The graph is a read, never a second verdict

The graph is built from what the run published, and the verdict of a claim of the graph is the verdict of the
run, read and never recomputed. A graph that decided again would be a second verifier, and two verifiers of the
same run would disagree one day. The graph relates the claims, the evidence and the sources, and it marks the
orphans and the conflicts, and it decides nothing.

### A citation that resolves to nothing is an orphan

The citation names one piece of evidence, and a citation that names nothing the run carries is an orphan of the
graph. It is never connected to a near match, because a connection the run did not make is a connection that
proves nothing. A sentence of the model, a claim with no evidence behind it, is held as a hypothesis, and it
supports nothing.

### The scope of an account is applied when the data is read

The route of the graph reads the run and applies the scope of the account before the graph is assembled, and it
publishes the count of the nodes it filtered. A run of another account is refused with a reason that says
nothing about the run, because a refusal that names the run confirms the run exists.

### No graph database is added

The graph is built in memory from the evidence of the run, and the test of the graph reads the modules of the
repository with `ast` and refuses a graph library. The graph of a run is small, and a database would buy the
queries that a read of the run does not need.

## Consequences

- The graph of a run is a value, and two reads of the same run return the same bytes.
- The graph of a published bundle is published as an artifact with the hash of the bundle and the hash of the
  snapshot, and the export refuses a bundle whose digest moved.
- The coverage of the graph is a fraction of counts with `Decimal`, and it names the snapshot it was built
  from.

## Links

- [the specification of the milestone](../../specs/010-r8-evidence-graph-and-provenance/spec.md)
- [ADR-073, the published bundle carries the evidence](ADR-073-the-published-bundle-carries-the-evidence-its-verdict-was-computed-on-and-it-is-reproducible.md)
- [ADR-074, a case ends in a decision](ADR-074-a-case-ends-in-a-decision-and-the-decision-belongs-to-the-code.md)
- [ADR-077, the published bundle is verified](ADR-077-the-published-bundle-is-verified-against-the-answer-the-run-verified.md)
