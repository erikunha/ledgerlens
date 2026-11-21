# Implementation Plan: Isolated visitor sandbox branches

**Branch**: `feature/v3` | **Date**: 2026-11-11 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-r2-visitor-sandbox/spec.md`

## Summary

The feature gives every anonymous visitor a private, short lived branch of a published scenario. The
visitor forks the immutable base snapshot, previews a typed mutation without writing anything,
commits it as an append only event, reads a deterministic before and after diff with the verdict of
the case, and can reset the branch back to the original canonical hash. No visitor ever sees the
work of another visitor, and nothing in the sandbox reaches a real payment path.

The technical approach keeps the Python core as the authority. The existing simulator modules
(`ledgerlens/sim/events.py`, `ledgerlens/sim/projector.py`, `ledgerlens/sim/scenarios.py`) already
provide the event store, the deterministic projector and the canonical hash. This feature adds a
`ledgerlens/sandbox/` package that owns the branch, the typed mutation catalog, the invariant
checks, the store interface and the time to live rules. The branch metadata and the branch event
log live in Postgres, one row set per visitor branch, with a hard expiry column that a cleanup job
enforces. A thin FastAPI facade in `ledgerlens/api/sandbox.py` exposes the branch status, the
account scoped ledger, the preview, the commit, the diff, the reset and the undo, and publishes the
branch lifecycle over server sent events. The Next.js application under `apps/web` consumes the
versioned schemas and never computes money.

## Technical Context

**Language/Version**: Python 3.12 for the core and the facade, TypeScript for the web application

**Primary Dependencies**: the existing `ledgerlens` core (`langchain`, `langchain-core`, `pydantic`),
`fastapi` and `uvicorn` from the existing `api` extra, `psycopg` (version 3) as the Postgres driver,
`pytest`, `ruff` and `jsonschema` from the existing `dev` extra

**Storage**: Postgres 16 for the per visitor branch metadata and the branch event log, with the
`expires_at` column carrying the hard time to live and a unique index on `(branch_id, event_uid)`
making the append idempotent. The published base snapshot stays in the repository as an immutable
artifact and is only ever read. The branch store sits behind the `BranchStore` interface in
`ledgerlens/sandbox/store.py`, so a file backed implementation (`FileBranchStore`) can replace the
Postgres one (`PostgresBranchStore`) with no change in the domain logic.

**Testing**: `pytest` offline with `LEDGERLENS_OFFLINE=1`, `ruff` for linting, `jsonschema` to
validate the payloads against `docs/v3/contracts/schemas/scenario-mutation.schema.json`

**Target Platform**: Linux server for the facade, a container image for the local run and for the
continuous integration run

**Project Type**: web service (FastAPI facade over a Python domain core) with a Next.js frontend

**Performance Goals**: preview of a mutation under 300 ms at the 95th percentile, commit under
800 ms at the 95th percentile, on the reference machine of the continuous integration run

**Constraints**: no provider key is needed and no network call is allowed in the sandbox path, no
write to any published artifact, one transaction per commit, a hard branch time to live of 60
minutes of idleness and 4 hours in absolute terms, at most 20 committed mutations and 200 stored
events per branch

**Scale/Scope**: one backend process, a bounded executor, one published snapshot shared by every
visitor, a handful of scenario kinds in the mutation catalog

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | How this plan honours it | Verdict |
|---|---|---|
| I. Evidence over fluency | The diff is computed from the projected rows, not from generated text. The verdict comes from the deterministic case checks of the scenario. A value that no row supports cannot appear. The reason of every rejection names the rule that failed. | Pass |
| II. Numbers come from code | Every amount on the mutation path is an integer minor unit or a `Decimal` string. The projector computes the new payout, never a model. The frontend renders the returned strings and calculates nothing. | Pass |
| III. Read-only and least privilege | The published snapshot opens read only. A visitor action only appends to the branch event log of its own session. No route accepts a SQL statement, a file path or a URL. The base ledger file is never opened for writing by the sandbox. | Pass |
| IV. Reproducible without credentials | The whole suite runs offline with the scripted model, the prebuilt fixtures and the fixed seed. Postgres is started from a container in the local run and in the continuous integration run, so no hosted service is needed to reproduce the result. | Pass |
| V. Truthful labels | Every event appended by a mutation carries the origin `sandbox`. Every response carries the schema version, the branch id, the branch revision and the base snapshot hash. An answer produced before a mutation is marked stale against the original snapshot and is never shown as the current result. | Pass |
| VI. Legacy where it teaches, modern where it matters | The Python core stays the single source of truth for the event model, the projector and the invariants, and the CLI, the Streamlit demo and the web application share it. The web application submits typed commands and renders responses. | Pass |
| VII. Test first, measure always | Every task in the story phases ships a test written before the implementation. The suite measures the canonical hash, the isolation failures, the rejection rate and the latency, and the adversarial isolation test is a release gate. | Pass |

No principle needs an exception, so the complexity tracking table stays empty.

## Project Structure

### Documentation (this feature)

```text
specs/002-r2-visitor-sandbox/
├── spec.md              # the feature specification: stories, requirements, entities, criteria
├── plan.md              # this file: the technical context, the constitution check and the structure
└── tasks.md             # the task list, one phase per user story, with the checkpoints
```

### Source Code (repository root)

```text
ledgerlens/
├── sandbox/                     # NEW: the branch layer, owned by the Python core
│   ├── __init__.py              # the public names of the package
│   ├── branch.py                # SandboxBranch, the fork, the status and the reset
│   ├── mutation.py              # the typed mutation catalog, the validation and the preview
│   ├── projector.py             # the branch projection, the canonical hash and the diff
│   ├── invariants.py            # the named business invariants and their evaluation
│   ├── store.py                 # the BranchStore interface and the two implementations
│   └── ttl.py                   # the hard time to live, the expiry check and the cleanup job
├── api/
│   ├── sandbox.py               # NEW: the FastAPI facade of the branch endpoints and the SSE stream
│   └── ledger_service.py        # existing read only ledger service, unchanged
└── sim/                         # existing: the event store, the projector and the scenarios, reused
    ├── events.py
    ├── projector.py
    └── scenarios.py

tests/
└── sandbox/                     # NEW: the sandbox suite, offline
    ├── conftest.py              # the branch fixture, the session fixture and the store fixture
    ├── test_branch_fork.py      # the fork and the immutability of the base snapshot
    ├── test_mutation_preview.py # the preview and the typed validation
    ├── test_mutation_commit.py  # the commit, the idempotency and the conflict
    ├── test_projector_diff.py   # the projection, the canonical hash and the diff
    ├── test_invariants.py       # the business invariants and the rollback
    ├── test_isolation.py        # the two visitor isolation test
    ├── test_reset.py            # the reset determinism test
    └── test_ttl.py              # the expiry and the cleanup

apps/web/                        # NEW: the Next.js application (Task 5 of the architecture document)
└── features/sandbox/
    ├── api/sandboxClient.ts     # the typed client of the versioned branch endpoints
    ├── types.ts                 # the types generated from the branch contract
    ├── useBranch.ts             # the hook that holds the branch state and the revision
    ├── BranchPanel.tsx          # the panel that shows the status, the revision and the expiry
    ├── MutationForm.tsx         # the typed form that previews and then commits
    ├── DiffView.tsx             # the before and after view and the verdict
    └── sandbox.css              # the styles of the panel

docker-compose.yml               # NEW: the Postgres service for the local run and for CI
```

**Structure Decision**: the branch logic lives entirely in the Python core under `ledgerlens/sandbox/`,
because the projector, the event store and the invariants are the authority for every amount and
every verdict, and because the Streamlit demo and the CLI must be able to use the same code. The
FastAPI facade stays thin and lives under `ledgerlens/api/`, next to the existing read only ledger
service. The web application lives under `apps/web/features/sandbox/`, owns its own lockfile and
never imports Python types. The tests live under `tests/sandbox/`, next to the existing test
folders, and the Postgres dependency is a container declared in `docker-compose.yml`.

### Local and continuous integration setup

Docker is the expected setup for the Postgres dependency, both for a local run and for the
continuous integration run. The same image that the local run uses is the image the pipeline
builds and starts, so a failure in the pipeline is reproducible on a laptop with one command.

```text
docker compose up -d postgres          # start the database with the published port and credentials
docker compose run --rm api pytest tests/sandbox   # run the suite against it
docker compose down -v                  # remove the volume and the data
```

The pipeline in `.github/workflows/gate.yml` starts the same service definition before the test
step, so the sandbox suite runs in the pipeline exactly as it runs locally. The offline flag
`LEDGERLENS_OFFLINE=1` is set in both, and no provider key is present in either.

### The store interface

`ledgerlens/sandbox/store.py` declares the `BranchStore` protocol with the operations the domain
needs: create a branch, read a branch, append events idempotently, read the events of a branch,
delete the events of a branch, list the expired branches and delete a branch. `PostgresBranchStore`
implements it over the `sandbox_branches`, `sandbox_events` and `sandbox_commands` tables.
`FileBranchStore` implements the same protocol over a directory of per branch files, used by the
fast unit tests and as the fallback when no database is available. The domain code in `branch.py`,
`mutation.py` and `projector.py` depends on the protocol only, never on a driver, so the two
implementations pass the same contract test suite.

## Complexity Tracking

No violation of the constitution principles is needed, so this table is empty.
