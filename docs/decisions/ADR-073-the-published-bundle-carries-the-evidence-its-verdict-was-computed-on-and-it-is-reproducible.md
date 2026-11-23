---
type: adr
status: accepted
date: 2026-11-24
---

# ADR-073: The published bundle carries the evidence its verdict was computed on, and it is reproducible

Status: accepted. Date: 2026-11-24.

## Context

ADR-068 published the catalogue of the replay and claimed that a reader of it "can check the depth of the case and
not only the depth of the answer". The review of this branch read the published bundles and found three things that
made that claim false or unverifiable.

The first is the cut of the trace. The published bundle of the scenario S11 carries the verdict of its first claim,
`supported`, with the note "Every stated value is a value of the cited ledger evidence", and it does not carry the
evidence that verdict was computed on. The trace compacts what it records, and the compaction cut the list of the
columns of the query and the values of its row, leaving a marker of what was left out. The two columns it cut were
exactly the two the answer cites, `applied_rate` and `applied_at`, so the rate of 5.4931 and the day of 2026-10-20
that the answer states were not in the bundle. The reviewer recomputed the claim with the published evidence and got
`not_enough_evidence`, where the run itself got `supported`: the bundle published a verdict that its own contents
contradict. The scenario S11 is the flagship of the catalogue, the one where a number would have been easy to make
up, and it was published with a number that the package did not sustain.

The second is the identifier of the case. The scenario S07 is the only one that writes a case in the memory of the
long term, and the identifier it published, `CASE-0280`, came from a counter over a store that lives outside the
repository and is ignored by the git. Two captures of the same commit wrote `CASE-0282` and `CASE-0284`, so the
bundle published was not the bundle a reader could rebuild, and the identifier it names points at a record that
nobody can find.

The third is the digest of the dataset. Every bundle carries the digest of `data/scenarios.json`, and the record
says that a change of that file would invalidate the provenance of every bundle. Nothing compared the digest of the
bundle with the digest of the file, so the file could change and the provenance of the nine bundles would go on
describing a dataset that is not there anymore.

## Decision

**The published bundle carries the evidence its verdict was computed on, the reader can redo the verdict with the
published contents, and the bundle is reproducible from the commit it names.**

### The cut of the trace follows the contract of the tools

The tools of the ledger answer with a contract: the names of the columns and the records. The cut of the trace may
take records out of a result, because a record that is left out takes no value of the evidence away, but it never
takes the fields of a record and never the names of the columns, because those are what the answer cites. The
marker says what was cut: the records of a result, the items of a list, the characters of a text.

### The verdict of a published bundle is re-verified by the code of the repository

A module reads the published events of a bundle, rebuilds the result of the run out of them, and hands it to the
verifier of the repository. The label the bundle publishes and the label the code gives for the published evidence
have to be the same, for every scenario of the catalogue. The evidence is rebuilt the way the integrator writes it,
read from the integrator for that reason, and the claims are extracted from the published answer and the published
evidence exactly as the run did, because the bundle does not publish the text of a claim.

What this proves and what it does not: it proves that the published label is the label the code gives for the
published evidence. It does not prove that the evidence is the truth of the ledger. That is the digest of the
snapshot, which the manifest of the bundle carries and the artifact of the ledger repeats.

### The identifier of the case comes from the scenario

The capture writes its memory in the folder of the capture and names the case after the scenario. A counter over a
store of the machine is a number of one afternoon of one machine, and a number of that kind cannot be looked up; the
scenario is in the bundle, and the case that names it can be.

### The gate compares the digest of the dataset

The digest of `data/scenarios.json` that every bundle carries is compared with the digest of the file, so a change
of the dataset stops the gate instead of leaving the provenance of the nine bundles describing a dataset that is not
there anymore.

## Alternatives considered

- **To publish the evidence of the verdict in a file of its own, next to the events.** Refused. The trace is the
  record of the run, and a second file with the same content in another shape is a second thing to keep in step
  with the first. The cut was the defect, and the fix belongs to the cut.
- **To keep the cut and to mark the bundle as a summary that cannot be re-verified.** Refused. The catalogue
  publishes verdicts, and a verdict that cannot be re-verified is a claim that nobody can check, which is what this
  repository does not publish.
- **To keep the counter of the cases and to publish the store with it.** Refused. The store of the machine holds the
  cases of every run of every machine, and publishing it publishes the memory of runs that have nothing to do with
  the catalogue.
- **To take the cases out of the recordings.** Refused. The recording of a case that the agent solved is part of what
  the product does, and the identifier of that case has to be there.

## Consequences

- **A reader of the catalogue can redo every published verdict** with the code of the repository and the published
  contents of the bundle, and the test that says so runs over the nine scenarios.
- **The values the answer cites are in the bundle**, and the marker of the cut says what it left out.
- **Two captures of the same commit give the same bundle**, because the memory of the capture is its own and the
  identifier of the case comes from the scenario.
- **A change of `data/scenarios.json` stops the gate**, instead of leaving nine provenances to describe a dataset
  that is not there anymore.
- **The nine bundles are recaptured** with the code of this branch, so their digest of the commit names the commit
  that carries these decisions.
- **The trace grows where the evidence is wide**, and the budget of the catalogue, four hundred kibibytes per
  scenario, is what holds it: the gate measures every bundle and fails when one is over.

## Links

- [ADR-068, the published catalogue holds the failures and not only the cases the agent resolves](ADR-068-the-published-catalogue-holds-the-failures-and-not-only-the-cases-the-agent-resolves.md)
- [ADR-013, the public trace is a versioned contract](ADR-013-public-trace-as-a-versioned-contract.md)
- [the trace](../../ledgerlens/observability/trace.py)
- [the re-verification of a published bundle](../../ledgerlens/replay/verdict.py)
- [the capture](../../scripts/capture_replay.py)
