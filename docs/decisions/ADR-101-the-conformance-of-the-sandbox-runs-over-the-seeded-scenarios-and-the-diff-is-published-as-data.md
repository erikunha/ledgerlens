---
type: adr
status: accepted
date: 2026-11-25
---

# ADR-101: The conformance of the sandbox runs over the seeded scenarios, the generator of the sequences is seeded, and the diff of a branch is published as data

Status: accepted. Date: 2026-11-25.

## Context

The branch layer of the sandbox was built and tested one rule at a time, spread over the tests of the folder.
The design package of the sandbox
([R2-03](../../docs/design/advanced-specs/R2-03-isolated-sandbox-mutations.md)) asks for three things the folder did
not have: the six acceptance scenarios gathered in one conformance suite over the seeded scenarios S01, S02 and
S03, the property tests of the invariants of the branch over sequences of commands nobody wrote by hand, and the
diff of a branch published as data. The milestone of
[specs/008](../../specs/008-r2-isolated-sandbox-mutations/spec.md) is those three things.

## Decision

**The conformance suite of the acceptance scenarios runs over the three seeded scenarios, the generator of the
sequences of commands is a seeded generator inside `tests/sandbox/` and not a property testing library, and the
diff of a branch is published as data with a hash and with the command that reproduces the mutation, and never
as a picture.**

### The conformance suite runs over the three seeded scenarios

`tests/sandbox/test_acceptance_conformance.py` gathers the six sentences of the package: the isolation of two
sessions, the retry with the same idempotency key, the wrong precision and the wrong currency, the reset that
returns the base hash, the read only field that is denied, and the mutated rate that marks the published answer
stale. Every case runs over S01, S02 and S03, every case names the scenario it ran, and the suite runs over the
two implementations of the store, because a conformance that holds over one store and not over the other is a
conformance of the store and not of the branch.

### The generator of the sequences is seeded, and no library is added

The repository carries no property testing library, and the choice of the milestone is a seeded generator inside
`tests/sandbox/sequences.py` and not a new dependency of the suite. The reason: the sequences of the branch are
short, the commands of the catalog are five, and the invariants are checked after every command, so the thing a
library would buy is the shrinking of a failing sequence, and a sequence of twelve commands that names its seed
is already replayable by hand. The generator is deterministic, the same seed produces the same sequence, and the
seed of every case is in the message of a failure. The generator never touches `data/runtime/sandbox-bases/`,
because the bases of the runtime are the bases of the visitors of the demo.

### The diff of a branch is published as data

`ledgerlens/sandbox/diff_artifact.py` reads the diff of the branch and builds the artifact: the diff, the hash
of the branch, the hash of the base, the invariants, the verdict and the commands of the log that reproduce the
mutation. The artifact is a value, so the export moves neither the revision nor the hash of the branch, and the
render is canonical, so two exports of the same branch are byte identical. The export is
`scripts/export_sandbox_diff.py`, and the domain never imports the facade: the reader works over the branch
layer, and the facade of the HTTP is a caller of the layer.

## Consequences

- The six sentences of the package are one suite, and a rule that breaks under a sequence and not under a command
  is caught by the property tests.
- A failure of a property test names the seed that replays it.
- The diff of a branch is a publication that can be hashed, and the package of the sandbox has its data and not
  its picture.
- The suite of the repository gains no dependency.

## Links

- [the specification of the milestone](../../specs/008-r2-isolated-sandbox-mutations/spec.md)
- [ADR-028, the diff and the history are reads](ADR-028-the-diff-and-the-history-are-reads.md)
- [ADR-021, the typed mutation and the atomic commit](ADR-021-typed-mutation-and-atomic-commit.md)
- [ADR-022, the reset and the staleness](ADR-022-reset-and-staleness.md)
