---
type: adr
status: accepted
date: 2026-11-14
---

# ADR-024: The undo is an event of the vocabulary, and the revision of the branch goes back

Status: accepted. Date: 2026-11-14.

## Context

The seventh story of the R2 feature specification asks for an undo of the last mutation of a branch: the visitor
applies a mutation, sees that it was a mistake, and asks for the branch to go back to the state it had before it. The
specification is explicit about three things (US7, FR-037, FR-038):

* the canonical hash after the undo is the hash the branch had at the previous revision, and the revision of the branch
  is back at the previous value;
* the history of the branch keeps the undone event and records the undo as a new event, because the history is append
  only and the event is never removed;
* an undo on a branch that has nothing to undo is refused with `409` and the code `NOTHING_TO_UNDO`, and the branch
  stays untouched.

The feature specification of the repository and the design package do not disagree here: the package asks for the same
thing in its own words. What the specification does not say is how the undo is built, and the mechanism decides several
things that the rest of the sandbox depends on.

## Decision

**The undo is a new event of the vocabulary of the sandbox, and it names the event it undoes.** The vocabulary grows one
event, `sandbox.branch.undone`, whose payload carries the uid of the undone event and the command id of the request
that produced it. The events of the branch stay append only: nothing is ever deleted and nothing is ever updated in
place.

**The projection of the branch resolves the undo markers.** When the projector replays the log of a branch, it reads
the undo markers first, collects the events they undo, and applies only the events that are still live. The marker
itself changes no row. So the state of a branch is still a pure function of the base and of the log (FR-009), the hash
of a branch after an undo is the hash of the state before the undone mutation, and the hash can be recomputed from the
log alone at any time.

**The revision of the branch goes back, because the specification asks for it.** The revision of a branch is the number
of the mutations that are still live, so an undo takes it back to the previous value. The event log keeps everything,
the marker included, and the log is therefore longer than the revision counts.

**The undo is a request with a key and with an expected revision, exactly like a mutation.** The route takes the
`Idempotency-Key` header and the `If-Match` header, and the answer of the request is remembered with the branch, the
way the answer of a mutation is. The reason is concrete: an undo that is delivered twice would undo two different
mutations, because the second delivery would find another mutation to undo. With a key, the second delivery is
answered with the answer that was stored and appends nothing (FR-012). The expected revision refuses a request that
was prepared against a state that is not the current one (FR-014).

**The store commits the undo in one operation.** The store gains one method for it: it appends the marker, moves the
row of the branch and remembers the answer of the request, in one transaction in the database and with the same
atomicity of the file backed store that the reset has. The store refuses the request with `BranchRevisionConflict`
when the branch moved between the read and the write, and nothing is written.

**The answer of an undone mutation is marked as undone.** The branch remembers the answers of its requests, and the
answer of the request that was undone is not the current result of the branch any more. The mark of the staleness of
ADR-022 answers a different question: it says that a reset closed the generation the answer was produced in. The mark of
the undo says that the mutation the answer describes was undone. The two marks are separate fields and the history
route carries both.

The mark of the undo is two fields with two different meanings, and they never overlap:

* `undone` says that the mutation this answer describes was undone afterwards. It is true for the answer of the
  mutation that was undone and false for the answer of the undo itself, because an undo can never be undone: the undo
  only takes back a mutation, and a marker of the log is not a mutation.
* `undone_event_uid` says which event the request that this answer describes undid. It is filled only for the answer of
  an undo, and it is empty for every other answer.

The two fields are separate because a single field cannot carry both facts without confusing the reader: the answer of
the undone mutation and the answer of the undo both name the same event, and a reader that saw one field would read the
answer of the undo as "this mutation was undone", which is false.

**The key of a request that was undone stays bound to that request.** The answers survive an undo, exactly as they
survive a reset, and the branch keeps the first answer it was given for a key. So a request that arrives again with the
key of an undone mutation is answered with the answer that was stored, marked as undone, and it never commits a second
time. The visitor that wants to apply the same change again sends a new key. The alternative, dropping the answers of
the past, would break the requirement that they be marked.

**The known cost of a revision that goes back.** A revision that can go back is not a monotonic number, so two
different states of a branch can carry the same revision: a branch that was mutated and undone is at the revision zero
with the hash of the base, exactly like a branch that was never mutated. The hash does not tell those two apart either,
because the state of the branch after the undo is the state of the base, row for row: the two branches hold the same
rows and the same hash. What tells them apart is the log of the branch, and the interface that needs to tell them apart
reads the history.

The cost that matters is on the server: the expected revision of a request cannot detect a stale write, because the
revision the client remembers can become current again. A tab that was left open before an undo can send a mutation
with an expected revision that matches the branch again, and the mutation lands on a state that the tab never saw. The
branch belongs to one anonymous session, the change is the visitor's own, and the diff and the verdict of the answer
show the truth of what happened, so the cost is accepted. The alternative, an `If-Match` header that carries the hash of
the branch and not only its revision, would change the shape of the contract of the design package, and it is written
down here as the decision to take if the sandbox ever serves more than one tab of the same visitor.

Two other consequences follow from the same decision and are accepted here: the limit of twenty live mutations is
freed by an undo, so the number of mutations a branch ever commits is bounded by the limit of two hundred events
instead; and a client that asks for an undo with an expected revision that is not the current one is refused, which is
the same rule as a mutation.

## Alternatives considered

- **Delete the events of the undone mutation.** The state of the branch would be right and the log would be short, but
  the history would stop being append only, and the specification asks for the undone event to stay in the log and to
  be marked as undone.
- **Keep the revision monotonic and report the previous revision in the answer.** The revision would stay a monotonic
  name of a state and the concurrency would stay simple, but the specification asks for the revision of the branch to
  go back to the previous value, and the revision is what the visitor reads in the status of the branch.
- **Make the undo a kind of the mutation catalog.** The undo does not change a record of the case, it changes the log
  of the branch, and the catalog holds the kinds that change a record (ADR-021).
- **Let the undo work without an idempotency key.** A second delivery of the request would undo another mutation, and
  the visitor would lose work without being told.

## Consequences

- The state of a branch is still a pure function of the base and of the log, and the hash can be recomputed from the
  log alone (FR-009, FR-010).
- The history of a branch grows with every undo, and the branch shows which event was undone and when.
- A request of the visitor can be undone only once, because the key of the request is remembered with its answer.
- The revision of a branch is not a unique name of a state, and a stale write cannot be detected by the expected
  revision alone.
- The protocol of the store grows by the method of the undo, and the two implementations of the protocol have to honour
  it in their own way.
- A malformed log, one that cannot be projected at all, is a branch that cannot prove its own state, and it is refused
  with `HASH_MISMATCH` like any other branch that cannot prove it. A marker that names an event that does not exist
  changes no row, so it changes no hash, and it is harmless: the branch is served, because the state it holds is the
  state it proves.
