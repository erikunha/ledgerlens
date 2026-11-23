# Implementation Plan: Runtime latency and cost per case

**Branch**: `feature/v3` | **Date**: 2026-11-22 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/005-r4-runtime-latency-and-cost-per-case/spec.md`

## Summary

The release makes the runtime of a turn a number the repository can show. It starts with the ceiling: every path
that reaches a provider carries the same `RunBudget` and the same `BudgetCoordinator`, a turn that a cap stopped
comes back as a result and not as an exception, and the numbers of the turn travel on the result. It continues with
the freshness of the index: the meta carries the digest of the corpus, a stale index refuses before it loads, and
the gate refuses a repository whose committed index does not match its policies. It then corrects the promise about
the vector library, with one protocol in `ledgerlens/vectorstore.py` and a test that refuses any other site. It ends
with the measurement: the p50 and the p95 of the latency, the cost of an investigation and the cost of a correctly
resolved case, with the hardware, the denominator and the role of the set in the report.

The technical approach keeps the Python core as the authority. The ceiling is the object ADR-034 already made, the
digest is a function of the bytes of the corpus, the protocol is a module of three operations, and the measurement
is a script that writes a document and a module that computes money with `Decimal`. The money of a human review is
an assumption of the run and never a constant of the code, and a number that nobody measured says so.

## Technical Context

**Language/Version**: Python 3.12 for the core
**Primary Dependencies**: the existing `ledgerlens` core, `langchain-core` for the agents, `langchain-community` for
the vector store, `fastembed` for the embedding of the policies
**Architecture**: the ceiling is enforced in one place, the digest is computed in the module that reads the corpus, the
vector library is imported by one module, and the measurement writes documents that name what they were measured over
**Storage**: the committed index of the policies under `data/index/policies_fastembed/`, the reports under `data/eval/`
**Testing**: pytest offline with `LEDGERLENS_OFFLINE=1`, and the scripted model for the agent
**Constraints**: no key and no network in the gate, money as `Decimal`, no change in `docs/v3/`

## The milestones of the release

| Milestone | What it delivers | State |
|---|---|---|
| M23 | The ceiling of the agent loop in every path that ships, the verdict of a cap and the usage on the result | Next |
| M24 | The digest of the corpus in the meta, the refusal of a stale index and the check in the gate | Later |
| M25 | One protocol for the vector sites, the third site declared and the promise as a test | Later |
| M26 | The p50 and the p95 of the latency, the cost of an investigation, the cost of a correctly resolved case and the wall clock of the cap | Later |

## The order, and why it is that order

The ceiling comes before the latency measurement, because a measurement over a loop that can run for ever is not a
measurement of anything: the p95 of an unbounded loop is the p95 of the loop and not of the agent. The digest of
the corpus comes before the protocol of the vectors, because a protocol without the digest would hide a stale index
behind a clean interface: the protocol answers the question of how the store is used, and the digest answers the
question of what is inside it. The measurement comes last, because the numbers it publishes describe the runtime
that the three milestones above built, and a number measured over a runtime that is about to change is a number
about a different system.

## The rules that apply to every milestone of this release

1. The ceiling is declared in `RunBudget` and enforced in `BudgetCoordinator`, and no path adds a counter of its own.
2. A cap that was hit is a result with a verdict, never an exception.
3. The money is a `Decimal` or nothing at all, and an unknown price is unknown and not zero.
4. Every number of the latency and of the cost names the set it was measured over, the denominator and the hardware.
5. A set whose role is `tuning` produces a tendency and not a generalization, and the report says so.
6. A promise about the shape of the repository becomes a test.
7. Every decision that restricts the future becomes an ADR in `docs/decisions/`.

## The risks

- **A number that is true and not usable**. The guard is the provenance, the denominator and the hardware beside it.
- **A cap that cuts an honest turn**. The guard is the measurement that comes back to ADR-054 and moves the cap.
- **A cost that counts the same money twice**. The guard is the categories that do not overlap and the double count flag.
- **A policy edited and an index not rebuilt**. The guard is the digest, the refusal before the load and the gate step.
- **A protocol that grows into a framework**. The guard is the review of the protocol the day a fourth operation appears.

## The strategy for the validation

Each milestone ships its test before its code, and the gate of the Python side is the one that runs everywhere,
including in the continuous integration. The measurement is a script that runs by hand, because it needs a provider
and a machine, and the guard that its numbers are honest runs in the gate in milliseconds.

## The questions the coordinator answered

- **The count of the fields of the meta.** The record names the field it adds and not the number of the fields of
  the file: the meta of the disk has seven fields today (`data/index/policies_fastembed/index_meta.json`) and the
  digest makes eight. ADR-055 was corrected to say eight.
- **Where the tests of the retrieval live.** The folder `tests/retrieval/` is created. The retrieval is a domain area
  of this repository, the two records already name that folder, and the guard that refuses a FAISS import outside the
  protocol belongs next to the protocol it protects. The tests of the index that exist today stay where they are.
- **The price of the model in the shipped paths.** The report publishes an unknown, and says that it is unknown. A
  number that is unknown is not zero, and the report never prints a zero where it does not have a price. The
  measurement of the latency does not wait for a price: the latency is measured with the denominator, the set and the
  hardware beside it, and the cost waits for a price with a provenance.
- **Where the economics live.** In `ledgerlens/economics/`, because the v3 package already decides it: R9-03 asks for
  a module `ledgerlens/economics` with `Decimal`, and R10-03 asks for `ledgerlens/economics/queue.py`. The reports
  live in `data/eval/` next to `report_online.md` and `report_offline.md`, with the names `report_latency.md` and
  `report_cost.md`.
