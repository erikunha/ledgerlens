---
type: adr
status: accepted
date: 2026-11-14
---

# ADR-031: The catalog of the sandbox grows with the round trip test

Status: accepted. Date: 2026-11-14.

## Context

The catalog of the sandbox holds the kinds of command a visitor may send, and
[ADR-021](ADR-021-typed-mutation-and-atomic-commit.md) says that a kind is enabled only when it has a round trip
test and a coherent domain event. One kind was enabled: the adjustment of the rate of a refund. The published
command schema
([`scenario-mutation.schema.json`](../v3/contracts/schemas/scenario-mutation.schema.json)) declares four more
kinds, and the sandbox refused all of them with the code `UNKNOWN_MUTATION_TYPE`, exactly like a kind that does not
exist.

Two of those four kinds change the rows of the ledger of a branch: `payment.simulate_duplicate` writes a second
charge of a payment, and `chargeback.change_deadline` moves the deadline of a case. The other two, `tool.fx_outage`
and `record.inject_untrusted_note`, change the state of the branch and of the tools and not the rows of the ledger.
Turning one of them on asks a question the hash and the diff of a branch have to answer first, and that question is
not answered yet, so they stay disabled.

Writing the two kinds asked for three things the sandbox did not have.

The vocabulary of the sandbox is its own and the interpreter that applies its events to the projected rows lives in
`ledgerlens/sandbox/projector.py`. It knew one event that moves a row, the adjustment of the rate of a refund, and
the marker of an undo, which moves no row. The two new kinds needed two new events, and the shape of the event
had to be decided: whether the event carries the row the visitor asked for, or the payload of the command and
nothing else.

The duplicate of a payment needed an identifier. The copy of the base is a real database and the published schema
of the ledger checks the shape of the identifier of a transaction with a glob of exactly four digits, so an
identifier cannot be invented freely. The copy also needed to say that it is a simulated row, and which payment it
comes from, so that the visitor can tell the copy from the published row. The marker lives in the projected row and
in the diff of the branch; the ledger view of the branch does not carry it, because the shape of that view is the
published one, and the visitor of that view alone cannot tell the copy from the published row.

The two kinds also needed rules of the domain of their own, and one of those rules was already written and was not
reachable: the invariant `chargeback_deadline_not_before_opening` of `ledgerlens/sandbox/invariants.py` said that
the deadline of a chargeback is not before the day the case was opened, and no kind of the catalog could ever break
it.

## Decision

**The catalog holds three enabled kinds.** `refund.apply_fx_adjustment`, `payment.simulate_duplicate` and
`chargeback.change_deadline` are enabled. `tool.fx_outage` and `record.inject_untrusted_note` stay disabled and are
refused with the code `UNKNOWN_MUTATION_TYPE`, like a kind that does not exist, and the message of the refusal names
the three kinds the sandbox can do. The rule of ADR-021 does not move: a kind is enabled only when it has a round
trip test and a coherent domain event.

**The vocabulary of the sandbox grows two events.** They are `sandbox.payment.duplicated` and
`sandbox.chargeback.deadline_changed`, they carry the origin `sandbox`, and the interpreter of
`ledgerlens/sandbox/projector.py` applies them. The payload of an event is the published payload of the command
that produced it and nothing else, and the interpreter computes the row out of it. So the state of a branch stays a
pure function of the base and of the log (FR-009), the preview and the commit see exactly the same row, and a
branch rebuilt from its events alone is the branch that was committed.

**The duplicate of a payment is a copy of the row of the original.** The copy carries the same merchant, the same
customer, the same amount, the same currency, the same method, the same card brand, the same card fingerprint and
the same status. Three things change.

The identifier of the copy is the next free identifier of the shape `TX-nnnn` inside the branch, and the search
starts at the one right after the original. The space of the identifiers is finite: the published ledger checks the
shape with a glob of four digits, so the identifiers are `TX-0001` to `TX-9999`. The search goes from the one
after the original up to `TX-9999` and then from `TX-0001` up to the original, so the copy never takes an
identifier that is free but out of reach. When every identifier of the space is taken, the branch has no room for
the copy and the command is refused with the code `RESOURCE_LIMIT_EXCEEDED` and the status `429`. The code is reused
because it is the code of the limits of the resources of a branch (FR-025), and the space of the identifiers is one
of those limits.

The moments of the payment move by the elapsed seconds: `created_at` and `captured_at` move by the same amount. A
payment that was authorized has no capture moment, and the copy of it has none either. The elapsed seconds are a
whole number of seconds between one and three hundred, the window of the published schema, and a value outside it
is refused with the code `INVALID_PAYLOAD`.

The row of the copy says that it is a simulated one: its origin is `sandbox` and its `source_ref` is the
identifier of the original transaction, so the projected row of the branch says which payment the duplicate comes
from, and the diff of the branch carries the two fields. The ledger view of the branch does not carry them, because
the shape of that view is the published one.

**The duplicate carries no row of the applied rate.** The duplicate is a second charge of the same payment, and the
conversion of the rate belongs to the payment, which is the same one. The visitor reads the conversion of the rate
in the row of the original, and the branch holds no second row of the rate for the copy.

**The deadline of a chargeback is written by the interpreter, and nothing else of the row moves.** The event carries
the identifier of the chargeback and the new deadline, and the interpreter writes the deadline of the row. The
amount, the currency, the reason, the stage, the day the case was opened and the day it was resolved do not move.

**The two kinds have their own rules of the domain, and each one has its own code.**

The record the command names has to be in the branch, and a command that names a record the branch does not hold is
refused with the code `UNKNOWN_RECORD`.

The currency the visitor asserts about the record, when it does not match the currency of the record, is refused with
the code `CURRENCY_MISMATCH`, the same code the adjustment of the rate already has (ADR-021). The assertion is
optional and the published schema does not declare it, and the rule holds for the three kinds of the catalog.

A payment that failed is not charged twice, and a chargeback that was won or lost is a closed case whose deadline
may not move. Both are refused with the code `INVALID_STATE` and the status `422`. The reason for the new code is
the shape of the refusal: the record exists and the payload has the shape of the published schema, so what does not
hold is the state of the record and not the shape of the payload. The status is the default one of the rules of the
payload, so the map of the statuses of the codes does not have to name it.

A deadline that is not a day of the calendar is refused with the code `INVALID_PAYLOAD`. The published schema
declares the format of the day and the checker of the schema does not read the format, so the check is written in
the domain of the kind.

A deadline that is before the day the chargeback was opened is refused by the invariant
`chargeback_deadline_not_before_opening`, with the code `INVARIANT_VIOLATION`. The rule was already written and is
now reachable, and the commit that would break it is refused and writes nothing.

**The diff of the branch shows the change.** The duplicate adds a row, and the diff carries one entry per column of
that row with the value before empty and the value after the one the interpreter wrote. The deadline carries one
entry, with the value before and the value after.

**The verdict of the case does not move.** The measure of the case is the markup of the refund, and neither kind
touches the refund, so the verdict stays one of the four declared labels of ADR-021.

**The undo takes each kind back.** The row of the duplicate disappears, the deadline goes back to the value of the
base, the revision of the branch goes back and the canonical hash returns to the value it had before the commit
(ADR-024).

**The round trip test of a kind is what "enabled" means.** For each of the two kinds the test proves that the
preview writes nothing, that the revision, the canonical hash and the count of the events of the branch do not
move; that the commit moves the revision by exactly one, appends one event and moves the hash; that the preview
answers the same projected hash and the same diff as the commit that follows it; that the diff names the row of the
duplicate or the deadline of the chargeback, with the value before and the value after; that the branch rebuilt from
the events alone has the same canonical hash; and that the undo takes the change back, the revision goes back and
the hash returns to the value it had before the commit.

## Alternatives considered

- **Enable the five kinds of the published schema at once.** The two kinds that change the state of the tools and
  not the rows of the ledger ask a question about the hash and the diff that this milestone does not answer, and a
  kind that is enabled without a rule is a promise the sandbox cannot keep (ADR-021).
- **Carry the row of the copy in the event.** The event would carry the amount, the identifier and the moments of
  the copy, and the interpreter would write them. The row would then be decided when the command was prepared and
  not when it is applied, and a branch rebuilt from its events alone could hold a row that the branch never had.
- **Let the visitor choose the identifier of the copy.** The identifier of a transaction is checked by the published
  ledger, and the copy of the base is a real database, so an identifier the visitor invents either breaks the
  schema of the row or collides with a row the branch already holds.
- **Number the copy after the last identifier of the branch.** The number of the copy would then depend on the
  order of the mutations and not on the payment it copies, and two branches that copied the same payment would hold
  two different rows.
- **Refuse the duplicate of a payment that was already refunded or disputed.** The rule of ADR-031 refuses only the
  payment that failed, because a payment that failed is not charged twice. A payment that was refunded or disputed
  is a payment the merchant may have charged twice by mistake, and that is the case the sandbox has to be able to
  show.
- **Give the duplicate a row of the applied rate of its own.** The rate belongs to the payment and the payment is
  the same one, so a second row of the rate would say that the merchant applied the rate twice, which is not what
  happened.
- **Write the deadline of the chargeback from the mutation path instead of the interpreter.** The mutation path
  does not write rows, and a row written there and a row written by the interpreter could drift apart. The event
  carries the payload of the command and the interpreter writes the row, so the preview and the commit see the same
  one.
- **Use the code `INVALID_PAYLOAD` for the state of a record.** The payload of the command has the shape of the
  published schema in that case, and the code of a rule of the shape would say that the payload was wrong when the
  state of the record was wrong.

## Consequences

- The catalog of the sandbox holds three enabled kinds, and the message of the refusal of an unknown kind names
  them.
- The vocabulary of the sandbox holds four events, and the interpreter of `ledgerlens/sandbox/projector.py` knows
  each one of them.
- The rule of the identifier of the copy lives in one place, in `next_transaction_id` of the projector, and the
  domain and the interpreter ask the same function, so they cannot drift apart.
- The code `INVALID_STATE` exists, with the status `422`, and the message of its refusal says which of the two rules
  of the state of a record failed, in plain English. It carries no identifier of the rule the way the refusals of the
  invariants do.
- The invariant `chargeback_deadline_not_before_opening` is reachable, and a test proves it.
- A branch of a visitor can hold one more transaction than the published case holds for every duplicate it
  commits, and the row of the copy says that it is a simulated one.
