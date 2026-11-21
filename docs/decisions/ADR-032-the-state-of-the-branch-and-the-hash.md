---
type: adr
status: accepted
date: 2026-11-14
---

# ADR-032: The state of the branch and the hash

Status: accepted. Date: 2026-11-14.

## Context

The catalog of the sandbox holds the kinds of command a visitor may send, and
[ADR-021](ADR-021-typed-mutation-and-atomic-commit.md) says that a kind is enabled only when it has a round trip
test and a coherent domain event. [ADR-031](ADR-031-the-catalog-grows-with-the-round-trip-test.md) enabled the
three kinds that change the rows of the ledger and left the last two kinds of the published command schema
disabled, because they change the state of the branch and of the tools and not the rows of the ledger, and because
the hash and the diff of a branch had to answer that case first.

The two kinds are `tool.fx_outage`, whose data says that the FX tool of the branch is unavailable or is available
again, and `record.inject_untrusted_note`, whose data attaches a note of an untrusted source to a record of the
case. The published command schema
([`scenario-mutation.schema.json`](../v3/contracts/schemas/scenario-mutation.schema.json)) declares both, and the
sandbox refused them with the code `UNKNOWN_MUTATION_TYPE`, exactly like a kind that does not exist.

The refusal was honest but it left the catalog short of the contract. The two kinds are the ones the scenarios of
the published case are about: the scenario S11 is the case of the FX source that is down, and the scenario S09 is
the case of a text that tries to give instructions from inside the data.

Enabling them asks a question the sandbox had never been asked before. The state of a branch was the rows of the
ledger, and the hash of a branch was the canonical hash of the projector of the simulator over those rows. The
state of the branch is now more than its rows: it is the rows, the state of the tools of the branch and the notes
of its records. A hash that covers only the rows would say that a branch whose tool is down is the branch that was
forked, and the visitor would be shown a state the branch cannot prove.

The rule of the hash therefore had to be decided, and it had to live in one place. The branch layer compares the
hash of the projection with the hash the row of the branch declares, on every read of the branch, and a branch
whose row and whose events disagree is refused with the code `HASH_MISMATCH` and is never served as valid
(ADR-021). The interpreter writes the state of the branch. Two copies of the rule of the hash would drift apart,
and a branch would be refused for a hash it does have.

## Decision

**The catalog holds five enabled kinds.** `refund.apply_fx_adjustment`, `payment.simulate_duplicate`,
`chargeback.change_deadline`, `tool.fx_outage` and `record.inject_untrusted_note` are enabled. The rule of ADR-021
does not move: a kind is enabled only when it has a round trip test and a coherent domain event, and the two new
kinds have both.

**The vocabulary of the sandbox grows two events.** They are `sandbox.tool.fx_outage` and
`sandbox.record.note_injected`, they carry the origin `sandbox`, and the interpreter of
`ledgerlens/sandbox/projector.py` applies them. The payload of an event is the published payload of the command
that produced it and nothing else, and the interpreter computes the state out of it. So the preview and the commit
see exactly the same state, and a branch rebuilt from its events alone is the branch that was committed (ADR-031).

**The projection of a branch carries a derived state.** Beside the rows of the ledger, the projection holds the
state of the tools of the branch and the notes of its records. The derived state is a pure function of the base
and of the log, exactly like the rows (FR-009), and the interpreter derives it while it applies the events, in the
order of the log. Two projections of the same log always have the same derived state, and the state of a branch
that was undone is the state of the branch before the undone mutation, because the derived state is derived and
never stored.

**The canonical hash of a branch covers the derived state, and the rule lives in one function.** The rule is in
`branch_hash` of the projector, so the branch layer and the interpreter cannot disagree about it.

A branch that holds no derived state has the canonical hash of its rows. The rows of a branch that forked and
never changed are the rows of the published base, so the hash of a forked branch is exactly the canonical hash of
the published base, and the two hashes stay comparable (FR-010, ADR-021). The base snapshot keeps the canonical
hash of the simulator of the ledger, and the hash of a branch at revision zero is that same value. This amends
ADR-018 for a branch that holds a derived state: the hash of such a branch is no longer the hash of the simulator
of the ledger alone.

A branch that holds a derived state has a hash that combines the canonical hash of its rows with the derived
state. A branch whose log was tampered with therefore holds a state that its rows do not prove, and it cannot
prove its own state: it is refused with the code `HASH_MISMATCH`, like every other branch that cannot prove itself
(ADR-021). The undo of a note or of an outage takes the derived state back and the hash with it.

**A log that cannot be projected is refused like a log that does not hash the same.** The interpreter reads the
payload of every event it applies, and a payload that lost a field it reads is a payload it refuses to apply. The
rule covers every kind of the catalog and not only the two new ones, because a `KeyError` would leave the refusal
unhandled and the facade would answer an error of the server instead of the 409 of the contract. The refusal is a
`ProjectionError`, so the branch layer turns it into the code `HASH_MISMATCH` and the facade answers 409 and never
an error of the server. A branch that cannot prove its own state is refused the same way whether its log hashes
differently or cannot be projected at all (ADR-021, ADR-032).

**The cost of the rule is the price of the promise.** The hash of a branch is no longer only the hash of its rows.
A reader that wants to know whether two branches hold the same rows can no longer compare the hashes of the
branches: it has to compare the hashes of the rows. And a branch that ends with no derived state has the hash of
its rows again, so a branch that had an outage and ended it has the hash of the base, although its log is longer.
That is the price of the promise of FR-010: the hash of a forked branch and the hash of the published base stay
comparable, and a branch that holds no derived state is a branch that holds no state of its own.

**The state of the FX tool.** The event carries the flag `enabled` and the error code. The flag is the state of
the outage and not the state of the tool: `enabled` true means that the outage is on, that is, that the tool of the
branch is down with the error code of the event, and `enabled` false means that the outage is over and that the tool
of the branch is available. So a branch holds an outage when the flag is true and holds no outage when the flag is
false. The last event of the log wins, because the events are applied in the order of the log.

**The verdict of the case with the FX tool down is `not_available`.** The measure of the case is the markup of the
refund, and the markup needs the rate of the reference source. With the source down the measure cannot be
computed, so the verdict is `not_available` and the detail of the answer names the outage and its error code
(ADR-021). With the tool back, the verdict is the one of the state of the rows, exactly as before.

**The untrusted notes.** The note is attached to a record of the case, that is, to a transaction, a refund, a
chargeback or a settlement of the branch. A record that is not in the branch is refused with the code
`UNKNOWN_RECORD`. A note is text from an untrusted source: it is not evidence, it does not move the verdict of the
case, and it does not move the invariants of the domain. The state of a record holds the last note that was
injected on it, and the log holds the history of every note.

**The length of a note is a rule of the payload, not a quota of the branch.** The note of a record and the reason of a
command are refused with the status `422` and the code of the rule that failed: `INVALID_PAYLOAD` when the text of the
note is longer than the limit of the published schema, and `NOTE_TOO_LONG` when the reason of the command is longer than
the limit. The status `429` belongs to the quota of the branch, that is, to the number of its mutations and of its
events, and the status `413` belongs to a payload that is too big. The published contract says the same: the `429` of
the contract is the quota of the visitor. So the note kind does not open a new status and does not change the meaning
of an old one (FR-025, ADR-031).

**A command that changes nothing is refused.** The hash of a branch only moves when its state moves, and a commit
that moved the revision without moving the hash would break that promise for the visitor. So an outage that is
already on, an outage that is ended when there is none, and a note whose text is the text the record already
carries, are all refused with the code `INVALID_STATE` and the status `422`, and the message of the refusal says
which of the rules failed (ADR-031).

**The diff of the branch carries the derived state.** The state of the tool is the record `tools`, the record id
`fx` and the field `outage`: the value before is empty when the tool was available and the value after is the error
code, and the reverse when the tool comes back. An empty value means the tool is available, and this ADR says so.
The notes are the record of the table of the record the note is attached to, the record id of that record and the
field `untrusted_note`: the value before is the note the record carried, empty when it carried none, and the value
after is the note. The kind of the value is not monetary. The entries of the derived state come after the entries of
the rows, so the reader of the diff reads the rows first.

**The round trip test of each kind is what "enabled" means.** For each of the two kinds the test proves that the
preview writes nothing, that the revision, the canonical hash and the count of the events do not move; that the
preview and the commit see exactly the same state, the same projected canonical hash and the same diff; that the
commit moves the revision by exactly one, appends exactly one event, and the hash moves; that the branch rebuilt
from the events alone has the same canonical hash as the branch; and that the undo takes the change back, the
revision goes back and the hash returns to the value it had before the commit.

**The promises of the hash and of the diff are proved by the suite.** The order of the entries of the diff is proved
by a branch that changed a row and that changed its state at the same time: the entries of the rows come first and
the entries of the derived state come last. The text of the notes is proved by a log whose text was tampered with:
the branch is refused with `HASH_MISMATCH`. The rows of a branch that holds a derived state are proved by two
branches of the same base that hold the same derived state and different rows: their hashes are different, because a
hash that covered the derived state alone would say that the two branches are one branch.

## Alternatives considered

- **Keep the hash of the rows and put the derived state outside of it.** A branch whose tool was down and whose log
  was tampered with would hold the same hash as the branch that was forked, and the branch would prove a state it
  does not have. The promise of ADR-021 is that a branch that cannot prove its own state is refused, and this
  would break it.
- **Hash the derived state alone when the branch holds one.** The hash of a branch would no longer say anything
  about its rows, and a visitor who compared the hash of a branch with the hash of the base would learn nothing.
- **Give every branch a hash that always covers the derived state, even an empty one.** The hash of a forked
  branch would no longer be the hash of the published base, and the two hashes would stop being comparable
  (FR-010, ADR-021).
- **Write the state of the tools and the notes as rows of the ledger.** The rows of the ledger are the published
  ones, and the schema of the published ledger decides which columns exist. A note is not a column of a
  transaction, and an outage is not a column of anything.
- **Keep the state of the tools and the notes in the row of the branch of the store.** The state of a branch is a
  pure function of the base and of the log (FR-009). A stored state would be a second truth that could drift away
  from the log, and the undo would have to repair it.
- **Let the visitor choose the table of the record of a note.** The published schema declares the identifier of the
  record and not its table, and the table is a property of the state of the branch. The interpreter therefore looks
  for the record in the tables of the case, in the order of `NOTE_TABLES`, and the domain asks the same resolver,
  `table_of_the_record` of the projector, so the two always attach the note to the same table. The resolver takes
  the identifier of the record and a lookup that answers whether a table holds it: the domain builds the lookup
  from the rows of the projection and the interpreter from the rows of the connection. So the order of the tables
  lives in one place, and the lookup of the table of a note asks for no statement of SQL of its own.
- **Accept a command that changes nothing.** The revision of the branch would move and the hash would not, and the
  visitor would be told that the state of the branch moved when it did not. The refusal with `INVALID_STATE` keeps
  the two together.
- **Let a note move the verdict of the case.** A note is text from an untrusted source. The point of the scenario
  S09 is exactly that such a text is data and never an instruction, and a verdict that moves with it would let an
  untrusted text decide the case.

## Consequences

- The catalog of the sandbox holds five enabled kinds, and every kind of the published command schema is enabled.
- The vocabulary of the sandbox holds six events, and the interpreter of `ledgerlens/sandbox/projector.py` knows
  each one of them.
- The projection of a branch carries the derived state beside its rows, and the derived state is derived from the
  log, never stored.
- The hash of a branch covers the derived state. The rule lives in `branch_hash` of the projector, and the branch
  layer and the interpreter ask the same function.
- The hash of a branch that holds no derived state is the hash of its rows, so the hash of a forked branch and the
  hash of the published base stay comparable, and the hash of a branch that ended its outage is the hash of the
  base again.
- The diff of a branch carries the entries of the derived state after the entries of the rows: the state of the
  tool as the record `tools` and the field `outage`, and the notes of the records as the field `untrusted_note`.
- The code `INVALID_STATE` refuses the three commands that change nothing, with the status `422`.
- The verdict of a case whose FX tool is down is `not_available`, and its detail names the outage and its error
  code.
- The invariants of the domain do not change: a note and an outage move no rule of the domain.
- The table of the record of a note is decided by one resolver, `table_of_the_record` of the projector, and the
  order of `NOTE_TABLES` lives in it.
- A log that cannot be projected is refused with `HASH_MISMATCH` like every other branch that cannot prove its own
  state, and the facade answers 409 and never 500. The rule covers every kind of the catalog and not only the two
  kinds that came last.
- The length of a note and of the reason of a command is refused with the status `422` and the code of the rule that
  failed. The status `429` stays the quota of the branch and the status `413` stays the size of the payload.
