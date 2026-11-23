---
type: adr
status: accepted
date: 2026-11-14
---

# ADR-018: The branch layer sits behind a store interface and the base of a branch is a canonical hash

Status: accepted. Date: 2026-11-14.

## Context

The phase R2 gives every visitor a private working copy of a published case. The feature specification
(`specs/002-r2-visitor-sandbox/spec.md`) and the design package (`docs/v3/specs/LL-R2-02-isolated-sandbox.md`)
ask for four things that shape the code:

- the branch store sits behind an interface, so that one implementation can replace the other without any change
  in the domain logic, and the two behave identically under the same test suite (FR-040, SC-015);
- the canonical hash is computed with one implementation for the published base and for every branch, so that the
  two hashes are comparable (FR-010);
- every branch belongs to exactly one owner session, and a session that asks for a branch it does not own gets a
  generic answer that does not disclose that the branch exists (FR-004, FR-005, FR-027);
- the published snapshot is never written, and every visitor of a scenario starts from the same bytes (FR-001,
  FR-002).

The repository already holds the pieces that make this possible: the event log and the projector of the simulator,
the canonical hash of `ledgerlens/sim/projector.py`, the account scoping of `ledgerlens/api/accounts.py` and the
canonical session identifier of ADR-015.

## Decision

**The branch layer lives in `ledgerlens/sandbox/`, and the domain logic never writes SQL.** The fork, the owner
check, the reuse rule and the status live in `branch.py`. The persistence lives behind the `BranchStore` protocol
in `store.py`, which has one method per operation and no knowledge of the domain.

**The owner of a branch is the canonical session identifier.** The canonical form of ADR-015 is what is stored,
because a filesystem may ignore the case of a name and two visitors must never share a folder. The identifier of
the branch is opaque: `sb_` followed by twenty four hexadecimal characters drawn from `secrets`, carrying no
session, no scenario and no path.

**Every operation of the store takes the owner session and refuses a branch that belongs to someone else.** The
refusal raises the same error as a branch that does not exist, so nothing about the existence of a branch leaks.
The isolation is therefore proven in the data and not only in the path of the domain layer: a store that is asked
for the branch of another visitor returns nothing, whatever the caller does next.

**The base of a branch is the account scoped projection of the published snapshot, and its identity is the
canonical hash.** The hash is the one of `ledgerlens/sim/projector.py`, used for the base and for the branch, so
that a branch rebuilt from its events alone produces the hash the commit reported (SC-003). The byte hash of the
SQLite file is not the identity of a branch: it moves with the layout of the file and with the vacuum, so two
branches of the same base could never be compared with it.

**The first implementation is the file backed store.** A branch is a folder of files inside a private folder named
after the canonical session identifier, under the runtime folder of the repository, which is never a global cache.
The Postgres implementation arrives next, behind the same protocol, and the contract test suite is written once
and runs against both.

**The published snapshot is read only.** A fork writes neither `data/ledger.db` nor `data/scenarios.json`, and a
test compares the hash of both before and after the whole fork suite (SC-004). At revision zero the state of a
branch is the base itself; the private projection of a branch arrives with the milestone that applies a mutation.

## Alternatives considered

- **The identifier of the branch derived from the session.** It would disclose the owner of the branch in every
  answer and it would collide when a session opens two branches.
- **The byte hash of the scoped file as the base hash.** It moves with the layout of SQLite and with the vacuum,
  so it cannot be compared with a branch rebuilt from its events.
- **The events of the branch in the event log of the published snapshot.** The log of the snapshot is published
  and read only, and writing there would break FR-001.
- **The name of the folder of the branch derived from its identifier.** It would tie the identifier to a
  filesystem layout and would make the isolation depend on the path.
- **A store that knows the owner rule.** It would put a domain rule in the persistence layer and the two
  implementations could drift apart.

## Consequences

- The domain logic is testable without a database, and the Postgres implementation can arrive without touching it.
- The contract test suite is written once and runs against every implementation of the protocol.
- The canonical hash is the identity of a branch; the bytes of a file are not.
- The base snapshot has to be built deterministically before the first fork, which costs one simulation, and the
  result is cached for the life of the process.
- The branch of a session that asks for the branch of another one is refused at the storage layer, so a mistake
  in the domain layer cannot leak the data of a visitor.
