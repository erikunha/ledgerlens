---
type: adr
status: accepted
date: 2026-11-14
---

# ADR-025: A write that fails leaves the branch exactly where it was, in the two stores alike

Status: accepted. Date: 2026-11-14.

## Context

FR-040 of `specs/002-r2-visitor-sandbox/spec.md` asks for the two implementations of the protocol of the store to
behave the same way, and the contract suite of `tests/sandbox/test_store_contract.py` is written once and run
against both, so that is how the promise is kept.

The database store keeps that promise by itself: it appends the events, moves the row of the branch and remembers
the answer of the request in ONE transaction, and a failure rolls the transaction back, so the branch keeps its
events, its revision, its hash and its answers.

The file backed store cannot do that in one step, because a branch is three files: the file of the events, the file
of the answers and the file of the row. It writes them one after the other, and the order matters: the row is
written LAST, so a reader that finds a row that is older than the events refuses the branch instead of serving it
half applied.

Two decisions already said that a failed write has to leave the branch where it was. ADR-022 made it for the reset:
the file of the events is emptied before the row is written and the content is put back when the write of the row
fails. ADR-024 made it for the undo: the marker, the move of the row and the answer of the request happen together.

The verification of the undo milestone on 2026-11-14 found that the promise was kept only in part. The restore of
the undo wrapped the write of the row and left the write of the answers outside of it, so a failure in the middle
left the marker of the undo in the log of the branch and the row of the branch where it was. The commit of a
mutation had no restore at all.

The consequence is the same in both cases and it is not small: the projection of a branch whose log carries a marker
skips the event the marker names, so the projection no longer agrees with the row, and the branch is refused with
the code `HASH_MISMATCH` (409) FOREVER. The visitor loses the branch over a write that failed, and the branch
cannot be recovered, because the reset drops the log of the branch and the undo needs a branch that proves its own
state.

## Decision

**Every write of the file backed store that touches more than one file restores what it wrote when any of the
writes fails.** The store keeps the content of the files it is about to write, and when a write fails it puts the
content back, or removes the file when there was none, and lets the failure travel to the caller. A commit, an undo
and a reset that did not happen leave the branch exactly where it was, with the same events, the same answers, the
same revision and the same hash, and the branch still proves its own state.

**The two stores lose the same thing when a write fails: nothing.** The database store loses nothing because the
transaction rolls back. The file backed store loses nothing because the content of the files goes back. FR-040 is
kept by the two implementations, and the contract suite proves it by running the same assertions against both.

**The order of the writes does not change.** The events first, the answers second and the row last, in every write
path of the file backed store. The row is last because a reader that finds a row that is older than the events
refuses the branch instead of serving it half applied (ADR-021). The order is part of the promise of the store, and
the contract suite records it.

**Every file of the store is written with a temporary file and a rename.** The fork of a branch and the save of a row
write one file each, and they write it the same way the other paths write theirs. The reason is the same: a reader
that finds a row that is half written cannot read the branch at all, and the row is the one file a reader always
needs. The write of the row of the fork and of the row of the save is therefore atomic like the others, and the
store does not keep one path that writes its file differently from the rest.

**A failure the store cannot observe is not covered by this decision.** A process that is killed between two writes
leaves a branch that is torn, because the content cannot be put back by a process that no longer runs. Such a
branch is refused with `HASH_MISMATCH` by the verification of the read, and the visitor forks the scenario again.
The store does not try to repair a branch that it did not tear, because a repair would have to guess which of the
files is the truth.

## Alternatives considered

- **Leave the torn branch and let the visitor fork again.** It is the behaviour of the code before this decision,
  and it loses the branch of the visitor over an error the visitor can do nothing about.
- **Keep a journal file of the writes and repair the branch when it is read.** It would also cover the kill of the
  process, at the price of a third file that has to agree with the two others, and the repair would have to guess
  which of the writes the process had finished.
- **Keep the whole branch in one file.** It would make the file backed store atomic by construction, and it is a
  rewrite of the store, of the layout it keeps and of the tests that read that layout, for a store that the
  production path does not use yet.

## Consequences

- The two implementations of the protocol of the store lose the same thing when a write fails, which is nothing
  (FR-040).
- The file backed store keeps the content of two files in memory for the duration of a write, and it puts them back
  when the write fails.
- The contract suite proves the promise for the two stores, and it proves it by making a write fail, not by reading
  the code of the store.
- The row of the fork and the row of the save are written with a temporary file and a rename, so a reader never finds
  a branch that is half written.
- A branch torn by the kill of a process is still refused with `HASH_MISMATCH`, and the visitor forks again. The
  promise of this decision covers the failures the store can observe.
