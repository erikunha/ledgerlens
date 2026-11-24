---
type: adr
status: accepted
date: 2026-11-24
---

# ADR-092: The journal of a run reuses the idempotence of the branch, and a step that is not idempotent is not run again

Status: accepted. Date: 2026-11-24.

## Context

The design package
[LL-V3-R16-02, idempotent durable operations and forensic traces](../v3/advanced-specs/R16-02-idempotent-durable-operations-and-forensic-traces.md)
proposes a run that restarts without losing evidence and without doing the same work twice, and a trace that a
reader can read as a forensic record. The repository already held half of this: the branch of a visitor is
durable (the idempotent commit of [ADR-021](ADR-021-typed-mutation-and-atomic-commit.md), the atomic write of
[ADR-025](ADR-025-a-failed-write-loses-nothing.md), the pure projection of
[ADR-032](ADR-032-the-state-of-the-branch-and-the-hash.md)). The other half did not exist: a run of the agent
wrote nothing durable, died with its steps half done and could not be resumed.

The milestone of [specs/017](../../specs/017-r16-durable-operations-and-forensic-traces/spec.md) adds the
second half: the journal of a run, the restart of a run that died, the unknown status of a call whose answer
never arrived, the barrier of a cancellation and the forensic export of a run.

## Decision

**The durable side of the sandbox was not rebuilt, the journal of a run reuses the rule of idempotence of the
branch, a step that is not idempotent is not run again after a restart, the trace keeps the shape of its own
span, and the store of a deployment is a later decision.**

1. **The durable side of the sandbox was not rebuilt.** The branch of a visitor is durable, it is proven by
   its own tests, and this milestone adds a second durable thing next to it. The tests of the sandbox keep
   passing, and the first tests of the milestone pin the durability of the sandbox so that a change of it in a
   later task fails there.
2. **The journal of a run reuses the rule of idempotence of the branch.** The intent of a step is written
   before the step runs, and the result after it ran, and the numbers of the journal grow by one under a lock,
   so the order of a run is readable after the fact. A run that dies between the two writes is a run whose
   restart knows where it stopped.
3. **A step that is not idempotent is not run again after a restart.** A step that writes without an
   idempotency key may have written before the process died, and the repository cannot know, so it is never
   run again. A step whose effect is idempotent (a read, or a write the store makes idempotent, like the
   commit of the branch) is run again with the same idempotency key, and the effect does not happen twice. A
   step whose snapshot changed needs a new run, because a number that was read from another branch is not the
   number of this case.
4. **A call of the provider whose answer never arrived is marked with the unknown status.** The cost of the
   call is unknown and never zero, and the run neither repeats the call nor claims a success it cannot prove.
5. **A cancelled run starts no tool after the barrier of the cancellation.** The run closes its spans and
   marks the claims that were not verified as incomplete, because a tool that starts after the cancellation
   spends the money of a visitor who already said stop.
6. **The forensic export keeps the shape of the span of the repository.** The export carries the spans, the
   parent of every span, the order of the events and the spend of every step, it redacts what looks like a key
   and says what it redacted, and it does not export the raw content of a prompt by default (ADR-013). The
   trace is a published contract, and a contract that is replaced by a standard is a contract that breaks.
7. **The store of a deployment is a later decision.** The journal of a run lives in the folder of the session
   that owns the run, beside the folder of the branch, and the durable store of a deployment is a decision
   that this milestone does not take.
8. **The recovery of a run is exercised on every run of the continuous integration.** The fixture of the kill
   points names the points at which the continuous integration kills a run, and every kill recovers with the
   same answer of the case and no duplicated event of the branch.

## Alternatives considered

- **To rebuild the durable side of the sandbox.** Refused. The branch of a visitor is durable and proven, and
  a rebuild would be a second rule of the same thing, and two rules drift.
- **To run again every step that did not complete.** Refused. A step that writes without an idempotency key
  may have written before the process died, and the repository cannot know, so running it again could
  duplicate an effect.
- **To mark a call whose answer never arrived as failed with a cost of zero.** Refused. The call may have
  spent the money of the visitor without the repository knowing, and a cost of zero would say the call was
  free. The status is unknown and the cost is unknown.
- **To export the raw content of the prompts by default.** Refused. The trace of the repository stays in the
  session of the person who asked (ADR-013), and a published export is read by strangers.
- **To replace the span of the repository with the conventions of OpenTelemetry.** Refused. The trace is a
  published contract (ADR-013), and the conventions are used where they apply, and the shape of the span of
  the repository stays.

## Consequences

- **The repository has the durability of a run**, in `ledgerlens/durability/`: the journal (`journal.py` and
  `store.py`), the restart (`restart.py`), the unknown status (`unknown.py`), the cancellation
  (`cancellation.py`), the retry of a rate limited call (`retry.py`) and the forensic export (`export.py`),
  with the tests in `tests/durability/`.
- **The journal of a run lives in the folder of the session**, beside the folder of the branch, and the
  numbers of the journal grow by one under a lock.
- **The runbook of the durability is [the runbook of the durability](../runbook/durability.md)**, with the
  states of a run, the restart, the unknown status and the rollback of the journal of a run.
- **The fault injection runs in the continuous integration**, with the fixture of the kill points, and every
  kill recovers.
- **The store of a deployment is a later decision**, and this record is the one that says the journal of a
  run lives in the folder of the session until that decision is taken.

## Links

- [ADR-013, the public trace is a versioned contract](ADR-013-public-trace-as-a-versioned-contract.md)
- [ADR-021, the typed mutation and the atomic commit](ADR-021-typed-mutation-and-atomic-commit.md)
- [ADR-025, a failed write loses nothing](ADR-025-a-failed-write-loses-nothing.md)
- [ADR-032, the state of the branch and the hash](ADR-032-the-state-of-the-branch-and-the-hash.md)
- [the runbook of the durability](../runbook/durability.md)
- [the specification of the milestone](../../specs/017-r16-durable-operations-and-forensic-traces/spec.md)
- [the design package](../v3/advanced-specs/R16-02-idempotent-durable-operations-and-forensic-traces.md)
