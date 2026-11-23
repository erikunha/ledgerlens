---
type: adr
status: accepted
date: 2026-11-14
---

# ADR-027: The refresh of the deadline moves only the deadline

Status: accepted. Date: 2026-11-14.

## Context

Reading the status of a branch is an activity: the idle deadline of the branch moves and the absolute deadline never
does. The deadline is part of the row of the branch, so the store has to write the row again, and the layer did that
with the method that writes a whole row: it read the row, replaced the two fields of the deadline and handed the row
it had read back to the store.

That write carries the whole row, and the whole row is a snapshot of the moment of the read. When a mutation landed
between the read and the write, the write rolled the row back over it: the revision went back to the old one and the
current canonical hash went back to the hash of the base, while the log of the branch kept the event of the mutation.

The verification of the undo milestone on 2026-11-14 reproduced it. The sequence is a read of the status, a mutation
and the refresh of the read:

```
the status: 0
the revision of the row the read had: 0
the revision after the mutation: 1
the revision of the row after the refresh: 0
the number of events of the branch: 1
the branch is refused with HASH_MISMATCH
```

The branch is lost. The row says that the branch holds no event and the log says that it holds one, so the branch
cannot prove its own state, and the rule of ADR-021 refuses it on every route. The visitor loses the mutation and
loses the branch with it.

The defect is not the race of the read and the mutation: that race is the reason the expected revision exists. The
defect is that the refresh wrote a field it had no business writing.

## Decision

**The store gains a method that moves the deadline and nothing else.** `touch_branch` takes the identifier of the
branch, its owner, the new moment of the last activity and the new expiry, and it writes those two fields of the
row and no other. In the database it is one `UPDATE` of two columns. In the file backed store it reads the row that
is on the disk under the lock of the instance, replaces the two fields and writes the row back, so the revision, the
hash and the generation of the branch are the ones the branch holds and not the ones a reader held a moment ago.

**The layer refreshes the deadline with that method.** The read of the status and the move of the deadline are one
operation of the domain, and the operation moves the deadline and nothing else.

**The method that writes a whole row stays in the protocol, and it is not on the path of the product.** It is the
tool the tests use to put a branch in a state the product never creates, like a row whose recorded base hash is
wrong, so that the refusal of that state can be proven. The rule of ADR-022 about the two implementations of the
protocol carrying the same public surface still holds: both stores have both methods.

**A write that changes nothing else cannot lose a write that landed in between.** That is the whole promise of the
decision, and it is a promise about the shape of the write, not about the timing of the read.

## Alternatives considered

- **Compare and set on the whole row.** The store would refuse to write a row that moved, and the layer would read
  the branch again and try once more. It keeps the clobbering write in the protocol and adds a retry loop to a read.
- **Keep the deadline outside the row.** The row would hold a moment of the last activity and the store would
  compute the expiry from it, so a read would write nothing. It changes the shape of the row and the schema of the
  database for a promise that one method already keeps.
- **Do not move the deadline on a read.** The idle deadline would then only move on a write, and a visitor that
  reads the branch for a long time would lose it while doing nothing, which is the opposite of what the deadline is
  for.

## Consequences

- A read of the status can no longer lose a mutation, and a read of the status can no longer lose the branch.
- The protocol of the store grows by one method, and the two implementations carry it in their own way.
- The row of the branch keeps the shape it had, and the schema of the database does not change.
- The tests that write a whole row to forge a state keep the tool they use, and the product never calls it.
