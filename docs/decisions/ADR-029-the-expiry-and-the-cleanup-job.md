---
type: adr
status: accepted
date: 2026-11-14
---

# ADR-029: The expiry has one home, and the cleanup is a job of the process

Status: accepted. Date: 2026-11-14.

## Context

The sixth story of the R2 feature specification asks for a branch with a hard time to live: every access after the
expiry answers `410` with the code `BRANCH_EXPIRED`, and the stored rows and the stored events of the expired branch
are deleted automatically, with a delay of at most sixty seconds between the expiry and the deletion (US6, FR-023,
FR-024, SC-011).

Two thirds of that is already in the branch layer. The layer knows the two deadlines, computes the expiry of a
branch and refuses an expired branch with `410` on every route. The store knows how to list the branches whose
expiry has passed and how to delete one with its owner.

What is missing is the job. Nothing deletes an expired branch today, so the rows and the events of every branch
that ever expired are still there, and the promise of FR-023 and FR-024 is not kept.

The rule of the expiry is also in the wrong place. It lives in the branch layer, mixed with the rules of the fork and
of the mutation, while the job that applies it has to live somewhere else, and the two would drift apart.

## Decision

**The rule of the expiry lives in one module, and the layer uses it.** `ledgerlens/sandbox/ttl.py` holds the two
deadlines, the idle one of sixty minutes and the absolute one of four hours, the computation of the expiry of a
branch, the check of the expiry and the cleanup job. The branch layer asks that module instead of computing the
expiry itself, so there is one rule of the time to live and not two.

**The cleanup job deletes the expired branches with their owner.** It lists the branches whose expiry has passed,
whatever their owner, and deletes each one naming its owner, so the deletion is an operation of the store like every
other one and the isolation of the owner is never bypassed. The deletion drops the row of the branch, its events and
its answers: the database does it with the cascade of the schema and the file backed store with the folder of the
branch.

**The job runs in the process of the facade, in a daemon thread of the lifespan of the app, every thirty seconds.**
Thirty seconds is half of the sixty seconds of FR-024, so the delay between the expiry of a branch and the deletion
of its rows is inside the bound even when a sweep begins just before the expiry. The thread stops when the app stops,
and it is a daemon, so a process that is killed does not wait for it.

**The job also runs from the command line.** `scripts/cleanup_sandbox.py` opens the store of the configuration and
runs one sweep, so a deployment that runs the facade with many workers, or that restarts it often, can schedule the
cleanup from the outside as well. The two ways are the same function, so they cannot disagree.

**The clock of the job is the clock of the server.** The job never takes a moment from the visitor and never asks
the database for its clock, and it uses the same clock the layer uses, so the branch that the job deletes and the
branch that the layer refuses are the same branch at the same moment (FR-031).

## Alternatives considered

- **Leave the cleanup to the deployment only.** The command is enough for a deployment that schedules it, but the
  repository would not keep the promise of FR-024 by itself, and a deployment that forgets the schedule keeps every
  expired branch forever.
- **A thread that starts with the module instead of with the lifespan.** The thread would run in every test that
  builds the app, and a test that moves the clock would race with the sweep.
- **Delete the expired branches when a visitor touches them.** The job would run only for the visitors that come
  back, and a branch that nobody touches again would stay forever.
- **A separate process for the cleanup.** It is the shape of a big deployment, and it is a second thing to run and
  to watch.

## Consequences

- The rule of the time to live has one home, and the layer and the job cannot drift apart.
- The facade keeps a thread that wakes up every thirty seconds, and the thread does nothing when there is no expired
  branch.
- The repository ships the command of the cleanup, so the deployment can schedule it with the same code the process
  runs.
- The protocol of the store does not grow: the job uses the listing of the expired branches and the deletion that
  are already there.
