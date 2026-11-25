---
type: adr
status: accepted
date: 2026-11-24
---

# ADR-079: The records of a result are published whole, because the claims are checked against them

Status: accepted. Date: 2026-11-24.

## Context

The trace of a run cuts what it publishes. A text longer than six hundred characters is cut with a marker that says
what was left out ("…+340 chars"), and a list longer than eight items is cut the same way. ADR-076 kept the answer
of the run whole, because the claims are extracted from it.

The records of a result have the same relation to the claims as the answer has. The verifier checks every value the
answer states against the values of the evidence it cites, and the evidence of a statement of the ledger is the
result it read: the columns of the result and the rows it returned. The cut of the rows was thought to be safe,
because a record that is left out was thought to take no value of the evidence away. That is not true, and the way
the cut was written made it worse: the number of the records left out was written into the list of the rows, as a
marker ("…+5 rows"), and a list that holds a text is not a list of rows any more.

The result is that a published bundle of a real run of the scenario S08 publishes a statement of the ledger that the
verifier cannot read. The bundle shows four claims supported and the code of the repository gives "no evidence" for
the four of them, because the values of the statement (the gross of BRL 30,919.54, the refunds of BRL 0.00, the fees
of BRL 926.67 and the net of BRL 29,992.87) reach the verifier without a column and without a currency, and a value
without a column is a number no reader can put under a column. The artifact of the ledger of that scenario
published the same way: thirteen rows counted, eight rows shown, and the flag of the cut saying that nothing was cut.

None of this was a fault of the run. The run read thirteen rows and the recording published what the trace of the
product publishes.

## Decision

**The contract of a tool is published whole: the records of a result, the identifiers the tool returned and the names
of the columns. Any other list is cut in its number of items, and any other text keeps the cut of six hundred
characters.**

1. **The records of a result are not cut.** The list of the rows of a statement and the list of the results of a
   search are published as they are. The bound is the bound of the tool: `query_ledger` asks the database for at most
   `max_rows` rows (fifty by default, two hundred at most) and says in its own answer how many rows it read
   (`row_count`) and whether it left any out (`truncated`). The trace does not cut a second time what the tool has
   already bounded.
2. **The identifiers the tool returned are not cut.** A list of the identifiers of the evidence is the list that
   links a piece of evidence to its content, and a cut list takes the evidence of a claim away.
3. **A list of records is published whole, whatever the name of the field.** The collections of a record (the
   refunds of a payment, the chargebacks, the rates applied to it) are records, and the cut of a record takes the
   values of a claim away in the same way the cut of the rows did.
4. **The other lists keep the cut, with the marker that says what was left out.** A list of plain values is cut at
   eight items and says "…+4 items".
5. **The budget of the published set does not move.** The size of a scenario is measured by
   `scripts/measure_replay_budget.py` and checked by the gate, so a result that does not fit is caught by the gate
   and not by a silent cut of the evidence.

Why the contract of the tool and not the size of the trace: the trace is the proof a reader checks the verdict of
the run against. A cut of the evidence is a cut of the proof, and the promise of ADR-073 is that the label the
bundle publishes is the label the code gives for the published evidence.

## Alternatives considered

- **To keep the cut of the records and to write the number of the records left out outside the list.** Refused. It
  keeps the shape of the result and loses the values of the records that were left out, and a claim that cites one of
  those values would still publish a label that the code cannot rebuild. The tool already bounds its own answer.
- **To teach the verifier to read a list of rows that holds a marker.** Refused. The published evidence would keep a
  shape that no tool of the product produces, and the repair would be in the code that checks the evidence instead of
  in the code that publishes it.
- **To cut the rows and to declare the catalogue of a real model not re-verifiable.** Refused, for the reason of
  ADR-076: a catalogue whose labels a reader cannot rebuild is a catalogue of claims.
- **To raise the limit of the cut to the number of rows the answer cites.** Refused. The answer is published after
  the tools ran, and the rule of the cut is written once for every span of the trace.

## Consequences

- **The published evidence of a result keeps the shape of the result**: the columns name the values, the values keep
  their currency, and the artifact of the ledger publishes as many rows as the read returned.
- **A bundle of a real run re-verifies with the code of the repository**, which is the promise of ADR-073 and the
  check of `tests/replay/test_published_verdict.py`.
- **The published payload of a scenario grows** by the rows that the old cut left out. The budget of the
  specification (SC-004) measures it and the gate checks it.
- **The trace of the live product shows every row the tool read.** A statement of fifty rows is shown as fifty rows,
  and the flag `truncated` of the tool says when the database had more.

## Links

- [ADR-073, the published bundle carries the evidence its verdict was computed on and it is reproducible](ADR-073-the-published-bundle-carries-the-evidence-its-verdict-was-computed-on-and-it-is-reproducible.md)
- [ADR-076, the answer of the run is published whole, because the claims are extracted from it](ADR-076-the-answer-of-the-run-is-published-whole-because-the-claims-are-extracted-from-it.md)
- [the rule of the cut](../../ledgerlens/observability/trace.py)
- [the claims of the run](../../ledgerlens/verify/checks.py)
- [the artifact of the ledger](../../ledgerlens/replay/ledger_artifact.py)
