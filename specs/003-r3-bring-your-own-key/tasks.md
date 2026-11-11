# Tasks: R3 - Bring your own key, the model registry and the run budget

**Input**: Design documents from `specs/003-r3-bring-your-own-key/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: The examples below include test tasks. Tests are written first and must fail before the implementation.

**Organization**: Tasks are grouped by user story so each story can be implemented independently, tested independently
and delivered as an MVP increment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to
- Include exact file paths in descriptions

**Path Conventions**:
- Core: `ledgerlens/` at the repository root
- Web app: `apps/web/`
- Tests: `tests/` at the repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 Create the `ledgerlens/byok/` package with `__init__.py` in ledgerlens/byok/__init__.py
- [ ] T002 [P] Create the facade module ledgerlens/api/byok.py with the router skeleton
- [ ] T003 [P] Create the live run coordinator module ledgerlens/api/live_run.py
- [ ] T004 [P] Add the web app folder apps/web/ with the package manifest and the TypeScript strict configuration
- [ ] T005 [P] Create the live mode page apps/web/app/(public)/live/page.tsx
- [ ] T006 [P] Create the feature folder apps/web/features/models/ with the picker, the dialog, the budget form and the cost report
- [ ] T007 [P] Create the docker compose file docker-compose.yml with the demo server service, used by the local run and by the CI
- [ ] T008 [P] Add the byok dependencies to pyproject.toml under the api extra, pinned in uv.lock
- [ ] T009 [P] Create the test folder tests/byok/ with an __init__.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T010 Define the CredentialHandle dataclass in ledgerlens/byok/vault.py, with the handle, the provider, the created and the expires time, and never the secret
- [ ] T011 Implement the CredentialVault in ledgerlens/byok/vault.py, holding the secret in process memory only, bounded, with a time to live
- [ ] T012 [P] Implement the ModelProfile dataclass and the ProviderRegistry in ledgerlens/byok/registry.py, with the capabilities, the pricing provenance and the last verified date
- [ ] T013 [P] Implement the refusal errors in ledgerlens/byok/errors.py, one per reason, each with a readable message
- [ ] T014 [P] Define the provider adapter interface and the fake adapter in ledgerlens/byok/adapter.py, so the tests never touch the network
- [ ] T015 Implement the budget coordinator in ledgerlens/byok/budget.py, with the caps, the counters and the cost accounting
- [ ] T016 Wire the budget into the RunContext in ledgerlens/run_context.py, filling the budget that already exists there
- [ ] T017 Define the CostReport dataclass in ledgerlens/byok/budget.py, with the observed cost, the estimated cost, the calls, the tokens and the elapsed time
- [ ] T018 [P] Write the contracts in specs/003-r3-bring-your-own-key/contracts/: credential-handle.schema.json, model-profile.schema.json and live-run-request.schema.json
- [ ] T019 [P] Generate the client types from the contracts into apps/web/lib/api/live.ts
- [ ] T020 [P] Write the quickstart in specs/003-r3-bring-your-own-key/quickstart.md, with how to run a live case locally and how to revoke

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - The visitor runs a case with their own key (Priority: P1) 🎯 MVP

**Goal**: The visitor picks a provider and a model, gives a key, sets a budget and runs a case with a real model.

**Independent Test**: With a fake provider adapter in the test, one case runs end to end, the trace carries the mode
`live_agent`, the budget is consumed as it goes, and the interface shows the run.

### Tests for User Story 1 ⚠️

> **NOTE**: Write these tests FIRST, ensure they FAIL before implementation

- [ ] T021 [P] [US1] Test the credential endpoint never returns the secret in tests/api/test_byok_api.py
- [ ] T022 [P] [US1] Test the run respects the model call cap in tests/byok/test_budget.py
- [ ] T023 [P] [US1] Test the run respects the wall clock cap in tests/byok/test_budget.py
- [ ] T024 [P] [US1] Test the live run ends with a terminal event and the mode live_agent in tests/byok/test_live_run.py
- [ ] T025 [P] [US1] Test the run refuses a model identifier outside the allowlist in tests/api/test_byok_api.py

### Implementation for User Story 1

- [ ] T026 [P] [US1] Implement the credential endpoint in ledgerlens/api/byok.py, returning the handle, the provider and the expiry
- [ ] T027 [US1] Implement the forget key endpoint in ledgerlens/api/byok.py, dropping the handle immediately
- [ ] T028 [US1] Build the per-run chat model in ledgerlens/byok/adapter.py, with the credential injected in the constructor and no global change
- [ ] T029 [US1] Implement the live run coordinator in ledgerlens/api/live_run.py, wiring the budget, the trace stream and the adapter
- [ ] T030 [US1] Implement the SSE stream of the live run in ledgerlens/api/live_run.py, emitting the budget counters as events
- [ ] T031 [US1] Implement the ModelSelector in apps/web/features/models/ModelSelector.tsx, showing the tested status and the capabilities
- [ ] T032 [US1] Implement the ApiKeyDialog in apps/web/features/models/ApiKeyDialog.tsx, with the password field, the disclosure and the no-store header
- [ ] T033 [US1] Implement the BudgetForm in apps/web/features/models/BudgetForm.tsx, with the four caps and their default values
- [ ] T034 [US1] Implement the live mode page in apps/web/app/(public)/live/page.tsx, with the picker, the dialog, the form and the run view
- [ ] T035 [US1] Implement the SSE bridge in apps/web/app/api/live/[handle]/route.ts
- [ ] T036 [US1] Add the consent text to the live mode page, saying the provider may charge and that the key is not stored

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - The visitor sees what the run cost (Priority: P2)

**Goal**: The visitor sees the calls, the tokens, the elapsed time and the cost, and the interface says unknown when
the price is unknown.

**Independent Test**: A run with a provider that reports tokens and one without a published price both show a cost
panel, and the second one says unknown and shows no dollar amount.

### Tests for User Story 2 ⚠️

- [ ] T037 [P] [US2] Test the counters include the triage model and the SQL generator in tests/byok/test_budget.py
- [ ] T038 [P] [US2] Test the estimated cost is absent when the registry has no price in tests/byok/test_budget.py
- [ ] T039 [P] [US2] Test the observed cost and the estimated cost are reported separately in tests/byok/test_budget.py
- [ ] T040 [P] [US2] Test the cost report says which cap cut the run in tests/byok/test_budget.py

### Implementation for User Story 2

- [ ] T041 [P] [US2] Implement the cost accumulation in ledgerlens/byok/budget.py, reading the token counts the provider reports
- [ ] T042 [P] [US2] Implement the price lookup in ledgerlens/byok/registry.py, returning unknown instead of a guess
- [ ] T043 [US2] Implement the cost report endpoint in ledgerlens/api/byok.py
- [ ] T044 [US2] Implement the CostReport component in apps/web/features/models/CostReport.tsx, with the unknown case
- [ ] T045 [US2] Show the live budget counters while the run happens, in apps/web/app/(public)/live/page.tsx
- [ ] T046 [US2] Reuse the cost panel in the run inspector, in apps/web/features/evals/CostPanel.tsx

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - The key never reaches a file, a log or a trace (Priority: P1)

**Goal**: The key lives in the server memory of the session only, and never appears in a file, a log, a trace, an error
message, a URL or another session.

**Independent Test**: A forced provider exception carrying the key is inspected in the logs, the trace, the error the
visitor sees and the telemetry. The key is in none of them.

### Tests for User Story 3 ⚠️

- [ ] T047 [P] [US3] Test the key in a provider exception never reaches the trace in tests/byok/test_live_run.py
- [ ] T048 [P] [US3] Test the key in a provider exception never reaches the logs in tests/byok/test_live_run.py
- [ ] T049 [P] [US3] Test a credential handle of another session is refused in tests/byok/test_vault.py
- [ ] T050 [P] [US3] Test the credential is dropped on session expiry in tests/byok/test_vault.py
- [ ] T051 [P] [US3] Test the vault holds nothing on disk in tests/byok/test_vault.py
- [ ] T052 [P] [US3] Test a link-local provider endpoint is refused in tests/api/test_byok_api.py
- [ ] T053 [P] [US3] Test two sessions on two providers do not cross the keys in tests/byok/test_live_run.py

### Implementation for User Story 3

- [ ] T054 [P] [US3] Add the redaction of the credential to the trace boundary in ledgerlens/observability/trace_event.py, reusing the existing redact
- [ ] T055 [P] [US3] Add the credential scrub to the error handler in ledgerlens/api/byok.py
- [ ] T056 [US3] Bind the credential handle to the session in ledgerlens/byok/vault.py, refusing it in another session
- [ ] T057 [US3] Expire the credential on the time to live in ledgerlens/byok/vault.py, with a sweep on every access
- [ ] T058 [US3] Bound the number of failures before the credential is dropped in ledgerlens/byok/vault.py
- [ ] T059 [US3] Drop the credential on server restart and on session reset in ledgerlens/byok/vault.py
- [ ] T060 [US3] Refuse a provider endpoint that is not an allowed HTTPS endpoint, in ledgerlens/byok/adapter.py
- [ ] T061 [US3] Refuse link-local and loopback addresses in public mode, in ledgerlens/byok/adapter.py
- [ ] T062 [US3] Send the credential request with no-store and no body logging in ledgerlens/api/byok.py
- [ ] T063 [US3] Strip the key from the URL and the client cache in apps/web/features/models/ApiKeyDialog.tsx

**Checkpoint**: At this point, User Stories 1, 2 AND 3 should all work independently

---

## Phase 6: User Story 4 - The visitor picks a model that can actually do the job (Priority: P2)

**Goal**: Only tested models are offered, and a model without the needed capability is refused with a readable reason.

**Independent Test**: A model profile without the `tool_calling` capability is refused at selection time, and the
message names the missing capability.

### Tests for User Story 4 ⚠️

- [ ] T064 [P] [US4] Test a model without tool calling is refused with the capability named in tests/byok/test_registry.py
- [ ] T065 [P] [US4] Test only the allowlist answers the catalogue in tests/byok/test_registry.py
- [ ] T066 [P] [US4] Test the price carries its provenance and its date in tests/byok/test_registry.py

### Implementation for User Story 4

- [ ] T067 [P] [US4] Implement the capability check in ledgerlens/byok/registry.py, refusing a model that lacks what the architecture needs
- [ ] T068 [US4] Implement the catalogue endpoint in ledgerlens/api/byok.py, with the tested status and the capabilities
- [ ] T069 [US4] Resolve the profile identifier against the allowlist in ledgerlens/api/live_run.py, refusing an unknown one
- [ ] T070 [US4] Show the capability list in the ModelSelector, in apps/web/features/models/ModelSelector.tsx
- [ ] T071 [US4] Refuse a model in the server, not only in the interface, in ledgerlens/api/live_run.py

**Checkpoint**: At this point, User Stories 1 to 4 should all work independently

---

## Phase 7: User Story 5 - The visitor can stop a run (Priority: P3)

**Goal**: Cancelling stops the run, leaves the partial trace visible and says the cancellation of an in-flight call was
best effort.

**Independent Test**: A cancelled run ends with the status `cancelled`, the trace has a terminal event, and no further
provider call happens.

### Tests for User Story 5 ⚠️

- [ ] T072 [P] [US5] Test a cancelled run makes no further provider call in tests/byok/test_live_run.py
- [ ] T073 [P] [US5] Test a cancelled run ends with the terminal event in tests/byok/test_live_run.py
- [ ] T074 [P] [US5] Test the in-flight cancellation is labelled as best effort in tests/byok/test_live_run.py

### Implementation for User Story 5

- [ ] T075 [P] [US5] Implement the cancellation token in the live run coordinator in ledgerlens/api/live_run.py
- [ ] T076 [US5] Implement the cancel endpoint in ledgerlens/api/byok.py
- [ ] T077 [US5] Emit the terminal event on cancellation in ledgerlens/api/live_run.py, keeping the partial trace
- [ ] T078 [US5] Implement the cancel button and the best effort label in apps/web/app/(public)/live/page.tsx
- [ ] T079 [US5] Stop the SSE stream on cancellation in apps/web/app/api/live/[handle]/route.ts

**Checkpoint**: At this point, all user stories should now be independently functional

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T080 [P] Document the live mode in docs/architecture.md, with the credential lifecycle and the budget enforcement
- [ ] T081 [P] Document the zeroization limitation in docs/decisions/, as an ADR
- [ ] T082 [P] Add the adversarial key test to the offline gate, in tests/byok/test_vault.py
- [ ] T083 [P] Add the end to end test of the live path with the fake adapter, in apps/web/tests/e2e/live-run.spec.ts
- [ ] T084 [P] Add the accessibility check of the live page in apps/web/tests/e2e/live-run.spec.ts, with axe
- [ ] T085 Run the quickstart validation from specs/003-r3-bring-your-own-key/quickstart.md
- [ ] T086 [P] Add the live mode to the README, with the disclosure and the limitation
- [ ] T087 Run `bash scripts/gate.sh` and confirm the offline path never calls a provider

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
- **Polish (Final Phase)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - depends on US1 for the run it reports the cost of
- **User Story 3 (P1)**: Can start after Foundational (Phase 2) - should land with US1, because a key that leaks makes
  the feature worthless
- **User Story 4 (P2)**: Can start after Foundational (Phase 2) - the registry is already there from Phase 2
- **User Story 5 (P3)**: Can start after US1, because it cancels the run US1 starts

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Contracts before the client types
- The vault and the registry before the endpoints
- The coordinator before the SSE stream
- The API before the interface

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel
- Once Foundational phase completes, US3 and US4 can proceed in parallel with US1
- All test tasks for a user story marked [P] can run in parallel
- The three feature folders under apps/web/features/models/ are different files and can be built in parallel

---

## Implementation Strategy

### MVP First (User Story 1 plus User Story 3 only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. Complete Phase 5: User Story 3, because the key handling is not separable from the run
5. **STOP and VALIDATE**: Test the live path independently, with the fake adapter
6. Keep US2, US4 and US5 for the next slices

### Incremental Delivery

1. Complete Setup + Foundational, then US1 + US3, then validate the run with a fake adapter
2. Add US4, so the visitor only sees models that work
3. Add US2, so the visitor sees what the run cost
4. Add US5, so the visitor can stop a run
5. Each story adds value without breaking previous ones

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate the story independently
- The offline path must stay green at every checkpoint: the live feature is additive
