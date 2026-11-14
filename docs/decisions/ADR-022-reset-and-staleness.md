---
type: adr
status: accepted
date: 2026-11-14
---

# ADR-022: The reset returns the base, and a generation marks the answers that went stale

Status: accepted. Date: 2026-11-14.

## Context

The fourth story of the R2 feature specification asks for the escape hatch of the sandbox: a visitor changes their mind
or wants to compare two variations from the same starting point, so the reset drops every event of the branch and
returns the branch to the published base, with the canonical hash the branch had at fork time and the revision back at
zero (US4, FR-021, SC-002).

Around that action the specification asks for two things that are easy to state and easy to get wrong:

* the answers, the traces and the replays produced before the reset have to be marked stale against the original
  snapshot, and none of them may be presented as the current result of the branch (FR-022, SC-014);
* a canonical hash that does not match the recomputed value after a reset has to be detected, and the branch has to be
  refused with the code `HASH_MISMATCH` instead of being served (FR-032).

The route of the reset is already declared by the versioned contract of the design package,
`docs/v3/contracts/openapi.yaml`, with the resource `Sandbox` as the body of the answer, so the reset needs no route
that the contract does not declare.

## Decision

**The reset is a move of the row, and it is not an event.** It drops the events of the branch, sets the revision back to
zero, sets the current canonical hash back to the hash of the base, and returns the branch. The count of the events of
the branch after the reset is zero, and the ledger of the branch is the ledger of the base, row for row. The reset
itself is not recorded as an event, because an event would survive the drop it performs, and the specification asks for
a branch with no events after the reset.

**The branch row carries a generation, and the generation is what marks the staleness.** Every reset moves the
generation of the branch forward by one. Every stored answer of the branch carries the generation it was produced in.
An answer whose generation is behind the generation of the branch is stale, and the staleness is derived from those two
numbers instead of being a flag that can drift away from the truth. A stale answer is answered with `stale: true` and
with the base canonical hash of the branch in `stale_against`, which is the hash of the original snapshot, so the
answer points at the base it was computed against and is never presented as the current result of the branch.

**The store moves the generation, and it moves it under its own lock.** The domain layer computes the rest of the row,
but the number of the generation is written by the store, which reads the generation it finds in the row and writes one
more. The reason is a race: when the layer computed the number and handed it over, the lock of the store serialised the
writes but not the arithmetic, so two resets that crossed wrote the same generation twice and an answer of the past was
served as the current result. The store is the only place where the row of the branch is locked, so the store is the
only place where the generation can move safely.

**The key of a request of the past cannot be used again on that branch.** The answers survive the reset, and the store
keeps the first answer it was given for a key, so a request that arrives again with the key of a request of the past is
answered with that answer and the mark of the staleness, and it never commits a second time. A visitor that wants to try
the same change again after a reset sends a new key. The alternative, dropping the answers of the past, would break the
requirement that they be marked stale.

**Where the mark is observed.** The mark reaches the interface through the replay of a request, which carries `stale`
and `stale_against`. The layer also lists every answer the branch remembers with its mark, and the route of the history
that ADR-023 declares will expose that list; until that route exists, the replay is the only way the staleness is
observed from outside.

**The file backed store empties the file of the events and does not remove it.** A branch with an empty file of the
events and a branch with no file of the events hold the same thing, and the store always finds the file where it
expects it.

**The stored answers survive the reset.** The specification asks for the answers of the past to be marked stale, and an
answer that was deleted cannot be marked. The reset therefore drops the events and keeps the answers, with the
generation they were produced in, and a request that arrives again with the key of an answer of the past returns that
answer with the mark of the staleness.

The task list of the feature asks the reset to delete the answers of the branch together with the events. That line is
superseded here, because the requirement it serves cannot be served that way: a requirement that asks for an answer to be
marked stale needs the answer to still exist. The requirement of the specification wins over the task list, as it has
won everywhere else in this feature.

What the mark covers today: the answers the branch remembers are the artifacts of the branch, and they are the ones the
reset marks. The trace and the replay of a branch are artifacts of the execution path, which the sandbox does not produce
yet; when they arrive, they inherit the same generation and the same mark.

**The reset verifies the branch before it moves anything.** The projection of the events of the branch has to agree with
the row, and the base hash recorded at fork time has to agree with the base the resolver hands over. A base that moved
under the branch, or a row that does not agree with its events, is refused with the code `HASH_MISMATCH` and the branch
is not served (FR-032, ADR-021). The comparison of the base hash is not a rule of the reset alone: it is part of the
verification of the branch, so every read of a branch refuses a branch whose recorded base hash does not match the base
it names. A branch that cannot prove its own state is refused wherever it is asked for, not only where it is repaired.

**The reset is atomic in the store.** The store gains one method that drops the events of the branch and moves the row
together. In the database the two happen in one transaction. In the file backed store the file of the events is emptied
before the row is written, and if the write of the row fails the content of the events is put back, so a reset that did
not happen leaves the branch exactly where it was. The two implementations therefore lose the same thing when the reset
fails: nothing. The order of the two writes still matters, because a crash between them leaves a branch whose row does
not agree with its events, and such a branch is detected and refused by the verification of the read instead of being
served (ADR-021).

## Alternatives considered

- **Delete the answers of the branch together with the events.** The reset would leave nothing behind, but the
  specification asks for the answers of the past to be marked stale, and a deleted answer cannot be marked nor read.
- **Record the reset as an event of the vocabulary.** The history of the branch would show the reset, but the event
  would be one of the events the reset drops, and the specification asks for a count of zero after the reset.
- **Keep a boolean column of staleness on every answer.** The mark would be explicit, but it is a second truth that can
  disagree with the generation, and the disagreement would be invisible until a visitor reads a wrong answer.
- **Move the revision of the branch back to zero without a generation.** The revision is the name of the optimistic
  concurrency of the branch, and two different histories would then carry the same name.

## Consequences

- The branch after a reset is indistinguishable from a branch that was just forked, and the hash it reports is the hash
  recorded at fork time (SC-002).
- The staleness of an answer is a number that cannot drift, and the answer says which base it belongs to (FR-022).
- The protocol of the store grows by the reset and by the listing of the answers, and the two implementations of the
  protocol have to honour them in their own way.
- The generation is part of the row of the branch, so the schema of the database gains a column and the file backed
  store gains a field, and both are read back with the row.
- The scaffolding of the tests of the database lives in the tests and not in the product module. The rule of the
  repository is that the domain layer never writes SQL, and the helpers that only a test uses, like the shape of the
  tables before the generation existed, belong to the tests. The two stores therefore do not carry a public method that
  only one of them has.
