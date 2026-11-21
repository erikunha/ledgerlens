---
type: adr
status: accepted
date: 2026-11-14
---

# ADR-026: The store serialises the writes of a branch, and the lock is the one of the row

Status: accepted. Date: 2026-11-14.

## Context

ADR-024 promised that the undo of a branch is refused when the branch moved between the read and the write: the
store compares the revision of the row under a lock, and the loser of two undos that cross is refused with
`BranchRevisionConflict` and writes nothing.

The verification of the undo milestone on 2026-11-14 reproduced the opposite. Two requests of undo that cross on the
same branch were both answered 200 in three runs of six, and the log of the branch held TWO markers of an undo that
named the SAME event: the second request was answered with a success although there was nothing left to undo. FR-012
and FR-038 were both broken by the race, and the promise of ADR-024 was false in the configuration that ships.

The cause is not the SQL. The store of the database locks the row of the branch with `SELECT ... FOR UPDATE` inside
the transaction of the undo, and with two connections the race never happens: one request wins and the other is
refused with `REVISION_CONFLICT`. The cause is that the store holds ONE connection for the whole life of the
instance, and every request of the facade uses that instance. Two threads therefore share one connection, they share
one transaction, and the lock of the row protects nothing: the second thread reads what the first thread wrote
because they are the same session of the database.

The file backed store has the same shape for the same reason. It has no lock at all, so two writes that cross read the
row, both see the revision they expect, and both write. The verifier saw the two markers of the undo collapse into
one and one of the two answers disappear, because the second write was built from a stale read of the files: a
request answered 200 left no trace in the log of the branch.

## Decision

**The store holds one connection per thread, and the row of the branch is the lock.** The database store opens a
connection for the thread that asks for it and keeps it for that thread, so two requests of two threads are two
sessions of the database and the `FOR UPDATE` of the row of the branch really serialises them. The connection of a
thread is opened when the thread first needs it and is closed with the store.

**The file backed store holds one lock, and the write paths of a branch take it.** The check of the revision and the
write of the row happen inside the lock, so two writes that cross cannot both pass the check. The lock belongs to the
instance of the store, because the instance is the thing that owns the files.

**The loser of two writes that cross is refused with `REVISION_CONFLICT`, and it writes nothing.** That is the
promise of ADR-024, and it is now true in the two implementations alike. The loser of a race is not a second winner
with half a write: it is a refusal, and the branch keeps the state the winner left.

**The lock belongs to the store and not to the domain layer.** The reason is the one ADR-022 already gave for the
generation: the store is the only place where the row of the branch is locked, so the store is the only place where a
check and a write can be one step. The layer prepares the row it wants and the store decides whether the branch is
still where the layer found it.

**A request that arrives with a revision that is not the current one is refused before the store is asked.** The
layer compares the expected revision of the request with the revision it read, so the common case of a stale client
never reaches the store. The lock of the store is for the requests that cross in the narrow window between the read
and the write, and it is the last line of the defence, not the first one.

## Alternatives considered

- **One lock in the domain layer.** The layer would serialise the writes of every branch of the server, and the layer
  is not the place where the row of the branch is locked.
- **A pool of connections.** It would keep the connections open and would be the right answer for a server with a
  real load, but it brings a dependency and a configuration, and the number of threads of this server is small.
- **A lock that covers the whole store in the database one too.** It would be simple, and it would serialise every
  branch of the server on one lock, which the row of the branch does not need to do.
- **Accept the race and document it.** The undo is the action where the race does the most harm: the visitor sees two
  successes and the log holds one of them.

## Consequences

- Two requests that cross on the same branch leave one winner and one refusal, and the branch keeps the state of the
  winner.
- The database store holds one connection per thread, so the number of connections follows the number of the threads
  of the server and not the number of the branches.
- The file backed store serialises its writes with a lock of the instance, so two branches of the same visitor do not
  block each other and two writes of the same branch do.
- The tests that prove it are in the contract suite of the store, and they prove it with two real threads and not
  with a mock of the lock.
