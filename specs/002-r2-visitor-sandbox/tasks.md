---
description: "Task list for the isolated visitor sandbox branches feature"
---

# Tasks: Isolated visitor sandbox branches

**Input**: Design documents from `specs/002-r2-visitor-sandbox/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: The examples below include test tasks. Tests are OPTIONAL - only include them if explicitly requested in the feature specification.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root
- **Web app**: `backend/src/`, `frontend/src/`
- **Mobile**: `api/src/`, `ios/src/` or `android/src/`
- Paths shown below assume single project - adjust based on plan.md structure

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 [US1] Create the package `ledgerlens/sandbox/` with `ledgerlens/sandbox/__init__.py` that exports the public names of the branch layer and carries the module docstring that says what it does and why
- [ ] T002 [P] [US1] Add the `psycopg` dependency to the `api` extra in `pyproject.toml` and refresh `uv.lock` with `uv lock`
- [ ] T003 [P] [US1] Add the sandbox settings to `ledgerlens/config.py`: the database url, the branch idle ttl in seconds, the branch absolute ttl in seconds and the maximum committed mutations per branch
- [ ] T004 [P] [US1] Create `docker-compose.yml` with the `postgres` service on image `postgres:16`, the published port, the credentials from the environment, the named volume and a healthcheck, plus the `api` service that runs the image with `LEDGERLENS_OFFLINE=1`
- [ ] T005 [P] [US1] List the sandbox variable names in `.env.example` with no values: the database url and the two ttl values
- [ ] T006 [P] [US2] Write `ledgerlens/sandbox/schema.sql` with the tables `sandbox_branches`, `sandbox_events` and `sandbox_commands`, the unique index on `(branch_id, event_uid)`, the unique index on `(branch_id, idempotency_key)` and the `expires_at` index
- [ ] T007 [P] [US2] Write `scripts/apply_sandbox_schema.py` that applies `ledgerlens/sandbox/schema.sql` to the configured database and is safe to run twice
- [ ] T008 [P] [US1] Start the `postgres` service from `docker-compose.yml` in the test step of `.github/workflows/gate.yml` before `uv run pytest`, so the pipeline runs the same image the local run uses

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T009 [US1] Define the `BranchStore` protocol in `ledgerlens/sandbox/store.py` with `create_branch`, `get_branch`, `append_events`, `read_events`, `delete_events`, `list_expired` and `delete_branch`, plus the `SandboxBranchRow` and `SandboxEventRow` dataclasses
- [ ] T010 [US1] Implement `PostgresBranchStore` in `ledgerlens/sandbox/store.py` over the three tables of `ledgerlens/sandbox/schema.sql`, with the append done as `INSERT ... ON CONFLICT DO NOTHING` so the append is idempotent
- [ ] T011 [P] [US1] Implement `FileBranchStore` in `ledgerlens/sandbox/store.py` over a directory of per branch files, with the same semantics as the Postgres one, used by the fast unit tests and as the fallback when no database is configured
- [ ] T012 [US2] Define the `MutationCommand` and the `MutationResult` dataclasses in `ledgerlens/sandbox/mutation.py`, with the kind, the payload, the optional reason, the expected revision and the idempotency key
- [ ] T013 [US2] Declare the accepted mutation catalog in `ledgerlens/sandbox/mutation.py` with `refund.apply_fx_adjustment`, `payment.simulate_duplicate`, `chargeback.change_deadline`, `tool.fx_outage` and `record.inject_untrusted_note`, each bound to the JSON schema of `docs/v3/contracts/schemas/scenario-mutation.schema.json`
- [ ] T014 [US2] Implement the payload validation in `ledgerlens/sandbox/mutation.py` that rejects an unknown kind with `UNKNOWN_MUTATION_TYPE`, a read only field with `READ_ONLY_FIELD`, a wrong precision with `INVALID_AMOUNT`, a currency mismatch with `CURRENCY_MISMATCH` and an effective date outside the window with `INVALID_EFFECTIVE_DATE`
- [ ] T015 [US2] Implement the amount helpers in `ledgerlens/sandbox/mutation.py` that parse and format money as integer minor units and `Decimal` strings, with no floating point anywhere on the path
- [ ] T016 [US2] Implement the branch projection in `ledgerlens/sandbox/projector.py` that rebuilds the derived tables from the base snapshot plus the events of the branch, reusing `ledgerlens/sim/projector.py` and `ledgerlens/sim/events.py`
- [ ] T017 [US2] Implement the canonical hash of a branch in `ledgerlens/sandbox/projector.py` with the same canonical serialisation used for the base snapshot, so that the two hashes are comparable
- [ ] T018 [US2] Implement the diff builder in `ledgerlens/sandbox/projector.py` that returns the ordered list of changed records with the value before, the value after and the kind of value, and the ordering is stable across reads
- [ ] T019 [US3] Implement the case verdict in `ledgerlens/sandbox/projector.py` that runs the deterministic checks of the scenario over the current projection and returns one of the declared outcome labels of that scenario
- [ ] T020 [US2] Define the `Invariant` dataclass and the evaluation function in `ledgerlens/sandbox/invariants.py` with the named rules of the scenarios: positive finite FX rate, refund not above the captured amount, deadline not before the opening date, valid state transition and no double settlement

---

## Phase 3: User Story 1 - Fork an immutable base snapshot into a private branch (Priority: P1) 🎯 MVP

**Goal**: A visitor forks a published scenario into a private branch with an opaque id, revision 0 and the base canonical hash, and the published bytes never change.

**Independent Test**: Fork S01 in a fresh session, read the branch status and the branch ledger, and compare the hash of the published snapshot file before and after.

### Tests for User Story 1 (OPTIONAL - only if tests requested) ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T021 [P] [US1] Write the fork test in `tests/sandbox/test_branch_fork.py` that asserts the branch id matches `^sb_[0-9a-f]{24}$`, the revision is 0 and the base hash equals the hash of the published snapshot
- [ ] T022 [P] [US1] Write the immutability test in `tests/sandbox/test_branch_fork.py` that hashes `data/ledger.db` and `data/scenarios.json` before and after a fork and asserts the hashes are equal
- [ ] T023 [P] [US1] Write the store contract test in `tests/sandbox/test_branch_fork.py` that runs the same assertions against `FileBranchStore` and `PostgresBranchStore`

### Implementation for User Story 1

- [ ] T024 [US1] Implement the `SandboxBranch` dataclass in `ledgerlens/sandbox/branch.py` with the branch id, the owner session, the base snapshot id, the base canonical hash, the revision, the current canonical hash, the created time, the expiry time, the state and the resource counters
- [ ] T025 [US1] Implement the id generation in `ledgerlens/sandbox/branch.py` that returns `sb_` plus 24 hexadecimal characters from `secrets`, with no session, scenario or path information in the id
- [ ] T026 [US1] Implement the fork in `ledgerlens/sandbox/branch.py` that reads the base snapshot read only, computes the base canonical hash, creates the branch through the store and returns it at revision 0
- [ ] T027 [US1] Implement the owner check in `ledgerlens/sandbox/branch.py` that refuses a branch whose owner session does not match the calling session, with a generic answer that does not disclose that the branch exists
- [ ] T028 [US1] Implement the reuse rule in `ledgerlens/sandbox/branch.py` so that a second fork of the same scenario by the same session returns the existing branch instead of creating another one
- [ ] T029 [US1] Write the branch fixture in `tests/sandbox/conftest.py` that gives a session id, a store, a fork of S01 and a helper that reads the branch status
- [ ] T030 [US1] Add the `POST /v1/sandboxes` and `GET /v1/sandboxes/{id}` routes in `ledgerlens/api/sandbox.py` that fork the branch and return the status with the schema version, the branch id, the revision and the base hash

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - Preview a typed mutation and then commit it (Priority: P1)

**Goal**: A visitor previews a typed mutation without any write and then commits it as an append only event, with the idempotency and the revision rules enforced.

**Independent Test**: Preview a `refund.apply_fx_adjustment` on S01, assert the branch revision, hash and event count do not move, then commit it and assert the revision rises by exactly one.

### Tests for User Story 2 (OPTIONAL - only if tests requested) ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T031 [P] [US2] Write the preview test in `tests/sandbox/test_mutation_preview.py` that asserts the preview returns the before and the after amounts as decimal strings with the currency, and that the revision, the hash and the event count of the branch are unchanged
- [ ] T032 [P] [US2] Write the typed validation test in `tests/sandbox/test_mutation_preview.py` that asserts an unknown kind answers `422` with `UNKNOWN_MUTATION_TYPE`, a read only field answers `422` with `READ_ONLY_FIELD` and a wrong precision answers `422` with `INVALID_AMOUNT`
- [ ] T033 [P] [US2] Write the idempotency test in `tests/sandbox/test_mutation_commit.py` that submits the same key and payload twice and asserts one event, the identical revision, the identical hash and the identical diff
- [ ] T034 [P] [US2] Write the idempotency mismatch test in `tests/sandbox/test_mutation_commit.py` that asserts the same key with a different payload answers `409` with `IDEMPOTENCY_MISMATCH` and appends nothing
- [ ] T035 [P] [US2] Write the conflict test in `tests/sandbox/test_mutation_commit.py` that sends two commits with the same expected revision and asserts exactly one succeeds, the other answers `409` with `REVISION_CONFLICT` and the canonical hash does not move

### Implementation for User Story 2

- [ ] T036 [US2] Implement the preview in `ledgerlens/sandbox/mutation.py` that validates the command, projects it in memory over the current branch state and returns the computed outcome without writing an event
- [ ] T037 [US2] Implement the event synthesis in `ledgerlens/sandbox/mutation.py` that turns a validated command into the sandbox events, with the origin label `sandbox` and a command id that ties the events to the request
- [ ] T038 [US2] Implement the commit in `ledgerlens/sandbox/mutation.py` that opens one transaction, checks the idempotency key, checks the expected revision, appends the events, projects them, checks the invariants, bumps the revision, stores the new canonical hash and commits
- [ ] T039 [US2] Implement the rollback path in `ledgerlens/sandbox/mutation.py` so that a failed invariant check or a failed projection leaves the branch on the previous revision with the previous hash
- [ ] T040 [US2] Implement the idempotency lookup in `ledgerlens/sandbox/mutation.py` that returns the stored answer of a previous request with the same key and the same payload hash
- [ ] T041 [US2] Implement the resource limits in `ledgerlens/sandbox/branch.py` that refuse a twenty first mutation and a two hundred and first event with `429`, and that refuse a payload over 32 kilobytes and a note over 300 characters
- [ ] T042 [US2] Implement the account scoping in `ledgerlens/sandbox/branch.py` so that every read returns only the rows of the account of the branch
- [ ] T043 [US2] Add the `POST /v1/sandboxes/{id}/mutations/preview`, `POST /v1/sandboxes/{id}/mutations` and `GET /v1/sandboxes/{id}/ledger` routes in `ledgerlens/api/sandbox.py` with the `Idempotency-Key` header and the `expected_revision` body field

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - Read the deterministic diff and the verdict of the case (Priority: P1)

**Goal**: The visitor reads a stable before and after diff and the verdict of the case, both computed from the projected rows.

**Independent Test**: Commit one FX adjustment on S01, read the diff twice and assert the two payloads are byte identical and name every changed record.

### Tests for User Story 3 (OPTIONAL - only if tests requested) ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T044 [P] [US3] Write the diff test in `tests/sandbox/test_projector_diff.py` that asserts the diff lists the refund and the transaction with the before values of the base and the after values of the projection
- [ ] T045 [P] [US3] Write the diff stability test in `tests/sandbox/test_projector_diff.py` that reads the same revision twice and asserts the two payloads are byte identical
- [ ] T046 [P] [US3] Write the rebuild test in `tests/sandbox/test_projector_diff.py` that rebuilds the branch from its events alone and asserts the canonical hash equals the hash reported after the commit, for S01, S02 and S03

### Implementation for User Story 3

- [ ] T047 [US3] Implement the diff response model in `ledgerlens/sandbox/projector.py` with the entries, the verdict, the base hash and the current hash
- [ ] T048 [US3] Implement the invariant evaluation in `ledgerlens/sandbox/invariants.py` for the named rules of each scenario, with the readable reason of a failure
- [ ] T049 [US3] Implement the rollback on a failed invariant in `ledgerlens/sandbox/mutation.py` so that the branch keeps the previous hash and the response carries the failing invariant name
- [ ] T050 [US3] Add the `GET /v1/sandboxes/{id}/diff` route in `ledgerlens/api/sandbox.py` that returns the diff with the schema version
- [ ] T051 [P] [US3] Create `apps/web/features/sandbox/types.ts` with the types of the branch status, the diff, the verdict and the error envelope, generated from the versioned contract
- [ ] T052 [P] [US3] Create `apps/web/features/sandbox/DiffView.tsx` that renders the before and after values as the strings returned by the server, shows the verdict label and never calculates a value in the browser

**Checkpoint**: At this point, User Stories 1, 2 AND 3 should all work independently

---

## Phase 6: User Story 4 - Reset the branch and get the original canonical hash back (Priority: P2)

**Goal**: A reset drops the events of the branch and returns the base canonical hash, with every earlier answer marked stale.

**Independent Test**: Fork S01, commit two mutations, reset, and assert the revision is 0, the hash equals the fork time hash and the ledger equals the base ledger row for row.

### Tests for User Story 4 (OPTIONAL - only if tests requested) ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T053 [P] [US4] Write the reset determinism test in `tests/sandbox/test_reset.py` that asserts the canonical hash after a reset equals the hash recorded at fork time and that the revision is back at 0
- [ ] T054 [P] [US4] Write the reset content test in `tests/sandbox/test_reset.py` that asserts the branch ledger after a reset equals the base ledger row for row and that the event count is 0
- [ ] T055 [P] [US4] Write the hash mismatch test in `tests/sandbox/test_reset.py` that stores a wrong base hash and asserts the branch is refused with `HASH_MISMATCH`

### Implementation for User Story 4

- [ ] T056 [US4] Implement the reset in `ledgerlens/sandbox/branch.py` that deletes the events and the commands of the branch, restores the base canonical hash, sets the revision to 0 and returns the base hash
- [ ] T057 [US4] Implement the staleness marking in `ledgerlens/sandbox/branch.py` so that every answer, trace and replay produced before the reset is marked stale against the original snapshot hash
- [ ] T058 [US4] Add the `POST /v1/sandboxes/{id}/reset` route in `ledgerlens/api/sandbox.py` that returns the base hash and the new revision

**Checkpoint**: At this point, User Stories 1 to 4 should all work independently

---

## Phase 7: User Story 5 - Work on the same scenario without seeing another visitor work (Priority: P2)

**Goal**: Two visitors on the same scenario never see each other branch, each other events or each other case memory.

**Independent Test**: Mutate in the first session, then read the diff and the ledger of the second session, and assert the base values, plus a generic `404` on a direct read of the other branch.

### Tests for User Story 5 (OPTIONAL - only if tests requested) ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T059 [P] [US5] Write the two visitor isolation test in `tests/sandbox/test_isolation.py` that forks S01 in two sessions, mutates in the first one and asserts the second one still reads the base values, the base hash and an event count of 0
- [ ] T060 [P] [US5] Write the cross branch read test in `tests/sandbox/test_isolation.py` that reads the branch, the diff and the ledger of the other session and asserts `404` with a generic message and no disclosure of the owner or of the existence
- [ ] T061 [P] [US5] Write the cross branch write test in `tests/sandbox/test_isolation.py` that sends a mutation against the branch of the other session and asserts `404`, no event anywhere and an unchanged hash on the first branch
- [ ] T062 [P] [US5] Write the case memory isolation test in `tests/sandbox/test_isolation.py` that writes a case in the first session and asserts the second session finds no case written by the first one

### Implementation for User Story 5

- [ ] T063 [US5] Apply the owner check to every route in `ledgerlens/api/sandbox.py`, so that the status, the ledger, the diff, the preview, the commit, the reset and the undo all refuse a branch of another session with a generic `404`
- [ ] T064 [US5] Scope the case memory path of the sandbox to the session through `ledgerlens/run_context.py`, so that the memory directory of a branch is the session directory and never a shared folder
- [ ] T065 [US5] Fill the branch id, the branch revision and the base snapshot hash in `ledgerlens/run_context.py` when an execution runs inside a branch, so that every trace and every answer carries them
- [ ] T066 [P] [US5] Create `apps/web/features/sandbox/useBranch.ts` that holds the branch state, the revision and the expiry of the current session only, and clears them when the session ends

**Checkpoint**: At this point, User Stories 1 to 5 should all work independently

---

## Phase 8: User Story 6 - Meet an expired branch with a clear message (Priority: P3)

**Goal**: A branch has a hard time to live, every access after the expiry answers `410`, and the stored rows and events disappear automatically.

**Independent Test**: Fork a branch with a short time to live, wait for it, and assert `410` with `BRANCH_EXPIRED` and that the stored rows and events are gone.

### Tests for User Story 6 (OPTIONAL - only if tests requested) ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T067 [P] [US6] Write the expiry test in `tests/sandbox/test_ttl.py` that forks a branch with a short time to live, waits for it and asserts a read and a mutation both answer `410` with `BRANCH_EXPIRED`
- [ ] T068 [P] [US6] Write the cleanup test in `tests/sandbox/test_ttl.py` that runs the cleanup and asserts the branch rows and its events are deleted and that the published snapshot is untouched
- [ ] T069 [P] [US6] Write the refork test in `tests/sandbox/test_ttl.py` that asserts a new fork after the expiry starts at revision 0 with the base canonical hash

### Implementation for User Story 6

- [ ] T070 [US6] Implement the expiry computation in `ledgerlens/sandbox/ttl.py` with the idle ttl of 60 minutes, the absolute ttl of 4 hours and the server clock as the only authority
- [ ] T071 [US6] Implement the expiry check in `ledgerlens/sandbox/branch.py` that answers `410` with `BRANCH_EXPIRED` on any access to an expired branch
- [ ] T072 [US6] Implement the cleanup job in `ledgerlens/sandbox/ttl.py` that deletes the expired branches and their events, and that can run as a scheduled task or from the command line

**Checkpoint**: At this point, User Stories 1 to 6 should all work independently

---

## Phase 9: User Story 7 - Undo the last mutation on the branch (Priority: P3)

**Goal**: An undo returns the branch to the previous revision and hash, and records the undo as a new event instead of deleting history.

**Independent Test**: Commit one mutation on S01, undo it, and assert the hash equals the hash before the commit and the revision is back at 0.

### Tests for User Story 7 (OPTIONAL - only if tests requested) ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T073 [P] [US7] Write the undo test in `tests/sandbox/test_reset.py` that asserts the canonical hash and the revision after an undo equal the values before the commit
- [ ] T074 [P] [US7] Write the empty undo test in `tests/sandbox/test_reset.py` that asserts an undo on a branch at revision 0 answers `409` with `NOTHING_TO_UNDO` and leaves the branch untouched

### Implementation for User Story 7

- [ ] T075 [US7] Implement the undo in `ledgerlens/sandbox/mutation.py` that appends an undo event, rebuilds the projection without the undone event, and returns the previous revision and hash, or answers `409` with `NOTHING_TO_UNDO`
- [ ] T076 [US7] Add the `POST /v1/sandboxes/{id}/undo` route in `ledgerlens/api/sandbox.py` and mark the undone event in the branch history without removing it

**Checkpoint**: All user stories should now be independently functional

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T077 [P] [US3] Publish the branch lifecycle over server sent events in `ledgerlens/api/sandbox.py` with a monotonically increasing sequence, a heartbeat and a resume by the last event id
- [ ] T078 [P] [US2] Create `apps/web/features/sandbox/api/sandboxClient.ts` with the typed calls to the versioned branch endpoints and the parsing of the error envelope
- [ ] T079 [P] [US2] Create `apps/web/features/sandbox/MutationForm.tsx` that previews the typed command, shows the reason of a rejection and commits only after a valid preview
- [ ] T080 [P] [US1] Create `apps/web/features/sandbox/BranchPanel.tsx` and `apps/web/features/sandbox/sandbox.css` that show the status, the revision, the expiry, the simulated label and the reset action
- [ ] T081 [US6] Add the rate limit and the session limit checks to the facade in `ledgerlens/api/sandbox.py`, so that a branch cannot be created beyond the per session cap and a request over the limit answers `429`
- [ ] T082 [P] [US2] Write the documentation in `docs/api/sandbox.md` with the endpoints, the status codes, the error codes and the mutation catalog, and the decision record in `docs/decisions/ADR-011-sandbox-branch-store.md` with the alternatives and why they lost

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3)
- **Polish (Final Phase)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P1)**: Can start after Foundational (Phase 2) - Uses the fork of US1 through the fixture, but must be testable on its own with a prepared branch
- **User Story 3 (P1)**: Can start after Foundational (Phase 2) - Uses the projection of US2, but the diff builder and the verdict are testable on their own
- **User Story 4 (P2)**: Can start after Foundational (Phase 2) - Needs the events of US2 to have something to reset
- **User Story 5 (P2)**: Can start after Foundational (Phase 2) - Needs two branches, which the fork of US1 already provides
- **User Story 6 (P3)**: Can start after Foundational (Phase 2) - Needs the branch rows of US1
- **User Story 7 (P3)**: Can start after Foundational (Phase 2) - Needs a committed mutation from US2

### Within Each User Story

- Tests (if included) MUST be written and FAIL before implementation
- Models before services
- Services before endpoints
- Core implementation before integration
- Story complete before moving to next priority

### Critical Path

- T001 through T010 gate everything else, because every story needs a branch and a store
- T024 through T026 gate the first visitor journey, the fork
- T036 through T043 gate the mutation loop, the preview and the commit
- T047 through T050 gate the diff and the verdict
- T059 through T062 are the release gate, the isolation suite

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel (within Phase 2)
- Once Foundational phase completes, all user stories can start in parallel (if team capacity allows)
- All tests for a user story marked [P] can run in parallel
- Models within a story marked [P] can run in parallel
- Different user stories can be worked on in parallel by different team members
- The four frontend files of Phase 10 are independent of each other and of the Python work

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: "Write the fork test in tests/sandbox/test_branch_fork.py"
Task: "Write the immutability test in tests/sandbox/test_branch_fork.py"
Task: "Write the store contract test in tests/sandbox/test_branch_fork.py"

# Launch all models for User Story 1 together:
Task: "Create the package ledgerlens/sandbox/ with ledgerlens/sandbox/__init__.py"
Task: "Create docker-compose.yml with the postgres service"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test User Story 1 independently
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 → Test independently → Deploy/Demo
4. Add User Story 3 → Test independently → Deploy/Demo
5. Add User Story 4 → Test independently → Deploy/Demo
6. Add User Story 5 → Test independently → Deploy/Demo
7. Add User Story 6 and User Story 7 → Test independently → Deploy/Demo
8. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 and User Story 2
   - Developer B: User Story 3 and User Story 4
   - Developer C: User Story 5, User Story 6 and User Story 7
3. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- The tasks of Phase 1 and Phase 2 carry the label of the earliest story that depends on them, so that every task of the list is traceable to a story
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
- The suite runs offline with `LEDGERLENS_OFFLINE=1` and with no provider key, and it needs the `postgres` service of `docker-compose.yml` for the store contract test
- The same image that `docker-compose.yml` builds runs in the continuous integration job, so a pipeline failure is reproducible locally
