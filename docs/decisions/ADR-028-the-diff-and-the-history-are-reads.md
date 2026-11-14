---
type: adr
status: accepted
date: 2026-11-14
---

# ADR-028: The diff and the history are reads of the branch as it is now

Status: accepted. Date: 2026-11-14.

## Context

ADR-023 declared three routes of the facade that the contract of the design package does not declare, because the
package cannot be edited. The undo has landed. The other two are the read of the diff and the read of the history.

The specification of the feature asks for the diff of the branch as a read of its own, so that the interface can show
the before and after of a revision (FR-034), and for the history of the branch, so that the visitor can read the
events of the branch and see which one was undone. The design package asks for the same thing in its own words and
does not declare the shape of either answer, so the shape is ours to decide.

Three shapes of diff exist in the sandbox today and they are not the same thing:

* the diff of a mutation, which is the answer of the commit and the answer of the preview: the difference between
  the state before that mutation and the state after it;
* the diff of the branch, which the route has to answer: the difference between the published base and the state the
  branch holds now;
* the diff of the undo, which is the reverse of the diff of the mutation it undid.

The route is a read of the branch, so the diff it answers is the second one. The first one is already in the answer of
the commit, and the third one is in the answer of the undo.

The history has two things to carry: the events of the log, which are append only and grow with every undo, and the
answers the branch remembers, which are marked stale after a reset (ADR-022) and marked undone after an undo
(ADR-024).

## Decision

**The route of the diff answers the difference between the base and the state the branch holds now.** The answer
carries the revision of the branch, the canonical hash of the base, the canonical hash of the branch, the entries of
the difference, the invariants of the current state and the verdict of the case over it:

```json
{
  "revision": 1,
  "base_canonical_hash": "...",
  "canonical_hash": "...",
  "diff": [{"record": "fx_applied", "record_id": "FX-9002", "field": "applied_rate",
            "before": "5.4931", "after": "5.4125", "value_kind": "non_monetary", "currency": null},
           {"record": "refunds", "record_id": "R-0731", "field": "payout_amount_minor",
            "before": "549.31", "after": "541.25", "value_kind": "monetary", "currency": "BRL"}],
  "invariants": [],
  "verdict": {"label": "within_expected_range", "measure": "...", "value": "...", "low": "...",
              "high": "...", "detail": "..."}
}
```

The entries are the ones of the projector, and one adjustment of the rate of a refund names two of them: the rate that
was applied and the payout that it produced. The values are text, so the interface never reads a number and never
calculates one. A branch that was mutated and undone answers the diff of the base, because the state of the branch
after the undo IS the state of the base, row for row. That is the cost ADR-024 already accepted, and the route shows
it honestly instead of hiding it.

**The route of the history answers the events of the log and the answers the branch remembers.** The events come in
the order of the log, and each one carries the mark that says it was undone:

```json
{
  "revision": 1,
  "canonical_hash": "...",
  "events": [{"event_uid": "...", "event_type": "refund.fx_adjusted", "aggregate_id": "R-0731",
              "occurred_at": "...", "payload": {}, "undone": false}],
  "answers": [{"branch_id": "...", "idempotency_key": "...", "revision": 1, "stale": false,
               "undone": false, "undone_event_uid": null, "...": "..."}]
}
```

The payload of an event is carried, because it is what tells the visitor what the event changed, and the payload of
the marker of an undo names the event it undid. The answers carry the two marks of ADR-022 and ADR-024, and they
carry the same fields they carry everywhere else, so the interface reads one vocabulary.

**Both routes are reads of the branch, and they read it the way every other read reads it.** They verify the branch
before they answer it: a branch whose log does not agree with its row is refused with `HASH_MISMATCH`, a branch of
another visitor is refused with the generic `404`, and an expired branch is refused with `410`. The history reads the
log once and uses that same log for the verification and for the marks, so the marks of the history are the marks of
the log that was verified.

**The guard of the facade widens with the two routes.** ADR-023 was amended: the guard names the paths of the
decision that have landed, and it names these two from now on. The guard test stays what it is, a route that nobody
decided still cannot appear in the facade.

**The `diff` of the branch and the `diff` of a mutation are two things with the same name.** The answer of the commit
and the answer of the undo carry the difference that the request made, and the answer of the diff of the branch carries
the difference between the base and the state of the branch. The route says which one it answers, and the answer
stored with a request carries it under the name `response_diff`, so the stored answer is never confused with the
answer of the route of the diff.

## Alternatives considered

- **Answer the diff of the last mutation.** The route would answer the diff of the commit, and the interface would
  have to ask for the diff of every commit to know what the branch holds now.
- **Answer the diff of the branch as a list of the diffs of its mutations.** It would name the changes and the order
  of the changes, but the entries would be nested and the interface would have to fold them.
- **Leave the payload of the events out of the history.** The history would be shorter, and the visitor would see
  that an event happened without seeing what it did.
- **Leave the answers out of the history.** The history would be the log of the events, and the answers of the
  branch, which are marked stale after a reset, would have no place to be read.

## Consequences

- The interface has the before and after of the branch and the log of the branch, in two reads, with the vocabulary
  of the commit and of the undo.
- The diff of the branch and the answer of the commit are two different things and they say so.
- A branch that was mutated and undone shows the diff of the base, and only the history tells that something
  happened.
- The protocol of the store does not grow: both answers are computed from the events and from the answers the store
  already keeps.
