---
type: adr
status: accepted
date: 2026-11-14
---

# ADR-021: A mutation is a typed command, the sandbox owns its own domain, and the commit is atomic

Status: accepted. Date: 2026-11-14.

## Context

The R2 feature specification asks for a loop of three steps: the visitor previews a typed mutation and sees what it
would do, then commits it, and then reads the diff and the verdict of the case. Around that loop it asks for a set
of rules that are easy to state and hard to keep: the preview writes nothing (FR-016, SC-008), the commit moves the
revision exactly once (FR-036), a stale expected revision is refused without moving anything (FR-014), the same
request with the same idempotency key returns the same answer and appends nothing (FR-012), the same key with another
payload is a conflict (FR-013), the append and the projection move together (FR-033), and every amount is computed
with `Decimal` and never with a float (FR-017).

The design package says that a new event of the sandbox must satisfy the whitelist of the simulator or be
interpreted by an explicit versioned sandbox domain interpreter
(`docs/v3/specs/LL-R2-02-isolated-sandbox.md`). The whitelist of the simulator has no event that adjusts the payout
of a refund, so the sandbox needs its own vocabulary.

## Decision

**The sandbox owns its own domain, versioned and namespaced.** The events of a branch are `sandbox.*` events with
the origin label `sandbox`, and the interpreter that applies them to the projected rows is versioned with the code.
The events of the simulator stay the events of the published ledger, and the two never mix.

**The catalog of the mutations holds only the kinds that have a round trip test.** The first enabled kind is
`refund.apply_fx_adjustment`, the example of the specification and the case of the scenario S01. The other four
kinds of the published command schema are known but not enabled, and a kind that is not enabled is refused with the
code `UNKNOWN_MUTATION_TYPE`, exactly like a kind that does not exist, because the catalog is the promise of what the
sandbox can do. The design package suggests starting with the two fault overlays, which do not touch a financial
projection; the feature specification of this repository works the refund adjustment of S01 from the first day, and
the specification of the feature is the one that binds here.

**The command is validated before anything is written.** The payload is validated against the published command
schema and against the rules of the domain: an unknown kind, a read only field, a wrong precision, a currency that
does not match the record and an effective date outside the window are each refused with their own code, in plain
English that names the rule that failed.

**The preview computes in memory and writes nothing.** It projects the branch state with the event that the
command would produce, over a copy of the state, and answers with the values before and after as decimal strings
with the currency, the affected records and the invariants. The revision, the canonical hash and the count of the
events of the branch are the same before and after.

**The commit is atomic.** The store gains one method that appends the events and moves the row of the branch
together. In the database the two happen in one transaction. In the file backed store the two files are written
with a temporary file and a rename, the row last, and the branch is verified after every read: a branch whose row
does not agree with the projection of its events is refused with the code `HASH_MISMATCH` and is never served as
valid. A crash between the append and the row therefore leaves a branch that is detected and refused, never one
that is served half applied.

**The store also remembers the answer of a request.** The idempotency key of a request, the digest of its payload,
the revision, the canonical hash, the diff, the verdict and the invariants of the answer are stored with the branch,
so a repeated request returns the identical answer and appends nothing, and the same key with another payload is a
conflict.

**The idempotency key is answered before the expected revision.** Three rules, in this order: a key that was seen
with the same payload returns the stored answer, whatever the expected revision says, because a client that lost
the answer of its first request cannot learn whether that request was applied; a key that was seen with another
payload is a conflict; a key that was never seen has to carry the expected revision of the branch, and a stale one
is a conflict. The replay therefore returns the answer of the request and not a hybrid of two states.

**The verdict of the case is a small, declared set of labels.** The sandbox compares the projected state with the
truth of the scenario and answers one of `within_expected_range`, `below_expected_range`, `above_expected_range`
or `not_available`. The labels are declared in the code and in the documentation of the sandbox, so the interface
can render them without guessing.

## Alternatives considered

- **Reuse an event of the simulator for the adjustment.** The whitelist has no event that moves the payout of a
  refund, and inventing one inside the simulator would change the contract of the published ledger to serve the
  sandbox.
- **Let the store of the branch hold the events of the simulator.** The events of the published snapshot and the
  events of a branch would then share a vocabulary, and a reader of the log could not tell them apart.
- **Enable the five kinds of the published schema at once.** The assumption of the specification says that a kind is
  added only when it has a round trip test and a coherent domain event. Declaring a kind that is not implemented
  would be a promise the sandbox cannot keep.
- **Write the events and the row without atomicity and rely on the reader.** A reader that trusts the row would
  serve a branch whose events say something else. The verification after the read is the honest alternative: the
  branch is refused and the visitor forks again.

## Consequences

- The preview is safe by construction: it works on a copy and never touches the branch.
- The commit moves the revision exactly once, and a crash cannot serve a branch in a half applied state.
- The catalog is the promise of the sandbox, and it grows only with a test behind each kind.
- The verdict is one of four labels, and the interface does not have to interpret a sentence.
- The protocol of the store grows by the two methods that carry the atomicity and the idempotency, and the two
  implementations have to honour them in their own way.
