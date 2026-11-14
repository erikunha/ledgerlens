---
type: adr
status: accepted
date: 2026-11-14
---

# ADR-020: The branch data lives in Postgres and the file backed store is the fallback

Status: accepted. Date: 2026-11-14.

## Context

ADR-018 decided that the branch layer sits behind the `BranchStore` protocol, with one implementation delivered and
the database one to come. The feature specification asks for the two to behave identically under the same test
suite (FR-040, SC-015), and its assumptions say that the branch data is held in Postgres for the deployment and
that the same store is reachable through a local container for development and for the continuous integration.

The machine of the author has Docker with the image `postgres:17-alpine` already present, so the database half can
be built and proven here and not only on paper.

## Decision

**The branch data lives in Postgres, and the file backed store is the fallback.** One database holds the branches
of every visitor, and the owner session is a column of the row: the isolation is enforced by a condition of the
query and not by a folder. The file backed store stays the one the fast unit tests use, and it is the one that runs
when no database is configured.

**The container is declared in `docker-compose.yml`.** The image is pinned, the credentials come from the
environment, the port is published on the loopback only, and the service carries a healthcheck that the gate waits
for, so the tests never run against a database that is still starting.

**The schema of the store is versioned in the repository.** `ledgerlens/sandbox/schema.sql` holds the tables of
the branches, of the events and of the commands, and `scripts/apply_sandbox_schema.py` applies it, safe to run
twice. Three constraints carry the promises of the specification: the unique index on `(branch_id, event_uid)` is
what makes the append idempotent in the database (FR-011), the unique index on `(branch_id, idempotency_key)` is
what makes a repeated request idempotent (FR-012), and the index on the expiry is what the cleanup job reads
(FR-024).

**The contract suite of the store is written once and parametrized over the implementations.** The Postgres case
is skipped with an explicit reason when the driver or the container is not there. A skip is never silent, because a
suite that quietly stops testing half of the protocol is a suite that lies.

**The continuous integration starts the container before the tests.** The suite of the store then runs against the
same image as the local run, and the image is the same in both.

## Alternatives considered

- **A database per visitor.** It is the strictest isolation, but it costs one container or one schema per visitor
  and it does not fit a public site with many anonymous visitors. The owner column with a condition of the query
  gives the same guarantee for the reader.
- **The file backed store only.** It is enough for the unit tests and it would let the feature ship, but the
  specification asks for the database implementation and the deployment assumption says the branch data is held in
  Postgres.
- **Reading the state of the repository to decide which store to use.** The decision belongs to the configuration,
  not to a command that touches the disk in a working tree.

## Consequences

- The two implementations of the protocol are compared by one suite, and the comparison is visible in the report of
  the suite, with an explicit skip when the database is not there.
- The schema of the store is versioned with the code, so the database of a deployment can be brought to the shape
  of the code with one command that is safe to run twice.
- The continuous integration needs the container, and the machine that runs it needs Docker.
- A machine without Docker runs the file backed store and the record of the run says that the Postgres half was
  skipped, instead of pretending that both were tested.
