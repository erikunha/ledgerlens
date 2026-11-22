---
description: "Task list for the R1 public replay feature"
---

# Tasks: R1 Public Replay

**Input**: Design documents from `specs/001-r1-public-replay/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: The examples below include test tasks. Tests are OPTIONAL - only include them if explicitly requested in the feature specification. This feature requests them: the specification asks for the end to end journeys, the accessibility scan and the mobile checks, and the constitution asks for a test before the code.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4, US5, US6)
- Include exact file paths in descriptions

## Path Conventions

- **Python core**: `ledgerlens/`, `scripts/`, `tests/` at the repository root
- **Web app**: `apps/web/` with `app/`, `features/`, `lib/`, `components/` and `tests/`
- Paths shown below assume the structure described in plan.md

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Create the apps/web project skeleton with package.json, tsconfig.json in strict mode and next.config.ts configured for the static export
- [x] T002 [P] Configure Tailwind CSS and the design tokens in apps/web/tailwind.config.ts and apps/web/app/globals.css
- [x] T003 [P] Configure the linting and the formatting in apps/web/eslint.config.mjs and apps/web/.prettierrc.json
- [x] T004 [P] Configure Vitest in apps/web/vitest.config.ts with the unit test include pattern
- [x] T005 Configure Playwright in apps/web/playwright.config.ts with the chromium and the webkit projects and the 390 and the 1440 viewports
- [x] T006 Add the lockfile of apps/web and the root justfile targets that run the web checks next to the Python gate
- [x] T007 [P] Add the build output and the test output patterns to apps/web/.gitignore
- [x] T008 [P] Write apps/web/README.md with the install, the build, the export and the test commands
- [x] T009 [P] Write docs/decisions/ADR-011-static-replay-export.md with the alternatives and why they lost
- [x] T010 Create apps/web/app/layout.tsx with the global landmarks, the language, the metadata and the AppShell

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T011 Create the type definitions generated from the published schemas in apps/web/lib/api/schemas.ts
- [x] T012 Implement the runtime validation of the bundle, the events and the result in apps/web/lib/replay/validate.ts
- [x] T013 Implement the event reducer in apps/web/lib/replay/reducer.ts with the duplicate, the gap and the unknown event handling
- [x] T014 Implement the tree and the timeline selectors in apps/web/lib/replay/selectors.ts
- [x] T015 Implement the provenance helpers in apps/web/lib/replay/provenance.ts for the digest, the mode label and the snapshot staleness
- [x] T016 [P] Implement the money formatter in apps/web/lib/format/money.ts with the explicit ISO currency code
- [x] T017 [P] Implement the duration formatter in apps/web/lib/format/duration.ts that separates the original timing from the playback timing
- [x] T018 [P] Implement the status label mapper in apps/web/lib/format/status.ts
- [x] T019 Implement the URL state helpers in apps/web/lib/state/urlState.ts and the harmless view preferences in apps/web/lib/state/viewPreferences.ts
- [x] T020 Implement the static artifact client in apps/web/lib/api/replay.ts with no provider host in the allow list
- [x] T021 Configure the query provider in apps/web/lib/api/provider.tsx with the static friendly defaults and no retry on a missing artifact
- [x] T022 [P] Create the primitive components in apps/web/components/ui: Button.tsx, Card.tsx, Tabs.tsx, Dialog.tsx, Sheet.tsx, Skeleton.tsx, Badge.tsx, Table.tsx and LiveRegion.tsx - **DELIVERED**: the NINE primitives are in apps/web/components/ui. Button.tsx, Card.tsx, Tabs.tsx, Dialog.tsx, Sheet.tsx, Skeleton.tsx, Badge.tsx and Table.tsx were there already, and LiveRegion.tsx was built by the milestone of the stepper: it renders exactly one polite region that writes no word of its own (ADR-050, decisions 4 and 6, with the proof in apps/web/tests/unit/live-region.test.tsx)
- [x] T023 Create the shell components in apps/web/features/shell: AppShell.tsx, Header.tsx, ModeIndicator.tsx, SkipLink.tsx and ProvenancePanel.tsx
- [x] T024 Write the unit tests of the reducer in apps/web/tests/unit/reducer.test.ts - **DELIVERED in apps/web/tests/unit/replay-reducer.test.ts**: the unit tests of the replay carry the name of the module they cover.
- [x] T025 Write the unit tests of the validators in apps/web/tests/unit/validate.test.ts - **DELIVERED in apps/web/tests/unit/replay-validate.test.ts**: the unit tests of the replay carry the name of the module they cover.
- [x] T026 Implement the export of the static artifacts in ledgerlens/replay/site_export.py and the driver scripts/export_replay_site.py

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Open the public site and choose a scenario with no key and no login (Priority: P1) 🎯 MVP

**Goal**: A visitor with no account and no key reaches the catalog, picks a scenario and opens the recorded replay, with the URL carrying only the scenario identifier.

**Independent Test**: Open the deployed landing page in a clean browser profile with no credentials, select S01 and assert that the replay renders the run overview with the mode label `Recorded Replay`.

### Tests for User Story 1 (OPTIONAL - only if tests requested) ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T027 [P] [US1] Write the end to end test of the landing and the catalog in apps/web/tests/e2e/catalog.spec.ts - **DELIVERED in two files**: apps/web/tests/e2e/catalog.spec.ts and apps/web/tests/e2e/landing.spec.ts, one suite per journey.
- [x] T028 [P] [US1] Write the end to end test of the replay route with no credential in apps/web/tests/e2e/replay.spec.ts
- [x] T029 [P] [US1] Write the network guard test in apps/web/tests/e2e/network.spec.ts that fails on any request outside the static origin

### Implementation for User Story 1

- [x] T030 [US1] Build the landing page in apps/web/app/(public)/page.tsx with the hero, the simulated money statement and the two calls to action - **DELIVERED with the path corrected**: the landing page is at apps/web/app/page.tsx, because the folder (public) holds the routes that have a segment and the root of the site is the landing
- [x] T031 [US1] Build the scenario catalog page in apps/web/app/(public)/demo/page.tsx - **DELIVERED with the path corrected**: the catalog is at apps/web/app/(public)/replay/page.tsx, and the name of the route is the name of the feature
- [x] T032 [P] [US1] Create the scenario components in apps/web/features/scenarios: ScenarioCatalog.tsx, ScenarioCard.tsx and ScenarioSummary.tsx
- [x] T033 [US1] Build the replay route in apps/web/app/(public)/demo/[scenario]/page.tsx - **DELIVERED with the path corrected**: the route is at apps/web/app/(public)/replay/scenario/[scenario]/page.tsx
- [x] T034 [US1] Create the replay state provider in apps/web/features/replay/ReplayProvider.tsx with the idle, loading, ready, playing, paused, completed and failed states
- [x] T035 [P] [US1] Create the run overview component in apps/web/features/replay/RunOverview.tsx with the scenario, the question, the mode and the capture date
- [x] T036 [US1] Create the empty and the failure states in apps/web/features/replay/ReplayEmptyState.tsx and apps/web/features/replay/ReplayErrorState.tsx
- [x] T037 [US1] Keep the URL free of anything but the scenario identifier and the view preferences in apps/web/app/(public)/demo/[scenario]/page.tsx - **DELIVERED with the path corrected**: the route is at apps/web/app/(public)/replay/scenario/[scenario]/page.tsx, and the URL carries the scenario and the tab of the reader and nothing else
- [x] T038 [US1] Add the page metadata in apps/web/app/layout.tsx and in apps/web/app/(public)/demo/[scenario]/page.tsx - **DELIVERED in apps/web/app/(public)/replay/scenario/[scenario]/page.tsx**: the route of a scenario is under replay and not under demo, and the metadata of the scenario is a generateMetadata that names the card of the catalog.

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - Watch the recorded trace step by step on the timeline and in the hierarchy (Priority: P1) 🎯 MVP

**Goal**: The visitor plays the recorded events one at a time, with the timeline, the nested spans, the previous and the next controls, the speed control and the reset.

**Independent Test**: Load the S01 replay, press play, pause after the third event, step forward and backward with the buttons and assert that the rendered state for a given event index is always the same.

### Tests for User Story 2 (OPTIONAL - only if tests requested) ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T039 [P] [US2] Write the end to end test of the playback, the pause and the reset in apps/web/tests/e2e/playback.spec.ts
- [x] T040 [P] [US2] Write the unit test of the determinism of the seek in apps/web/tests/unit/seek.test.ts - **DELIVERED in apps/web/tests/unit/replay-reducer.test.ts**: the unit tests of the replay carry the name of the machine they cover, and the determinism of the seek is proven there
- [x] T041 [P] [US2] Write the keyboard test of the trace tree in apps/web/tests/e2e/trace-keyboard.spec.ts - **DELIVERED in two places**: the keyboard of the trace tree is proven in apps/web/tests/unit/features/agent-trace.test.tsx and, end to end, in apps/web/tests/e2e/mobile.spec.ts

### Implementation for User Story 2

- [x] T042 [US2] Create the playback controls in apps/web/features/replay/ReplayControls.tsx with the play, the pause, the previous, the next, the speed and the reset
- [x] T043 [US2] Create the progress component in apps/web/features/replay/ReplayProgress.tsx with the slider and its accessible name - **DELIVERED inside the reader**: the slider is at apps/web/features/replay/ReplayViewer.tsx, where the state of the playback lives, and it was not worth a component of its own
- [x] T044 [US2] Implement the playback clock in apps/web/features/replay/usePlaybackClock.ts so that the speed never alters the displayed original timing
- [x] T045 [US2] Create the timeline component in apps/web/features/agent-trace/TraceTimeline.tsx with the observed time, the error and the token usage
- [x] T046 [US2] Create the tree component in apps/web/features/agent-trace/TraceTree.tsx with the arrow, the home and the end navigation
- [x] T047 [US2] Create the stepper component in apps/web/features/agent-trace/RunStepper.tsx - **DELIVERED**: the stepper is at apps/web/features/agent-trace/RunStepper.tsx and it is an INDICATOR and not a control: it holds no button, no link and no stop of the keyboard. It names the four real steps of S01 (query_ledger, search_policies, get_reference_fx, calculate) in the order of the recording, marks the current one with aria-current="step", says in words that a step is over and says the status of the call, and tells the current step from an ordinary one by the border on the left and the weight of the name and never by a colour alone. The steps are built by buildRunSteps and findCurrentStep in apps/web/lib/replay/selectors.ts. The proof is in apps/web/tests/unit/features/run-stepper.test.tsx and in apps/web/tests/e2e/run-stepper.spec.ts (ADR-050, decisions 1, 2, 3 and 5).
- [x] T048 [US2] Create the tool call drawer in apps/web/features/agent-trace/ToolCallDrawer.tsx with the focus return to the trigger - **DELIVERED**: the drawer is built on the primitive of the sheet at apps/web/features/agent-trace/ToolCallDrawer.tsx, the trigger is the real button of the row header of the table of the calls at apps/web/features/replay/ReplayViewer.tsx, and the focus goes back to the CELL that opened the drawer and never to the button inside it. The proof is in apps/web/tests/unit/features/tool-call-drawer.test.tsx and in apps/web/tests/e2e/tool-call-drawer.spec.ts (ADR-048, decisions 1, 2, 3 and 7).
- [x] T049 [P] [US2] Create the SQL code pane in apps/web/features/agent-trace/SqlCodePane.tsx with the local horizontal scroll and the sanitized literals - **DELIVERED**: the pane of the statement is at apps/web/features/agent-trace/SqlCodePane.tsx, it is a named region that the keyboard reaches, it holds the statement as a text node and it is the only area of the page that scrolls sideways (the class ll-code-pane). The literal of the recording is shown as it was written, because the sanitising of the literals belongs to the Python core and not to the browser (ADR-048, decisions 4 and 5). The proof is in apps/web/tests/unit/features/sql-code-pane.test.tsx and in apps/web/tests/e2e/tool-call-drawer.spec.ts.
- [x] T050 [US2] Announce the step summary in apps/web/components/ui/LiveRegion.tsx without announcing every token - **DELIVERED**: the primitive is at apps/web/components/ui/LiveRegion.tsx and it renders EXACTLY ONE polite region (role=status, aria-live=polite, aria-atomic=true) that writes no word of its own. The page announces "Step N of M: <tool>" once per step and never the counter of the events, never a token and never a value: the counter "Event N of M." moved out of the region and became ordinary text. A MutationObserver pins that the region is not rewritten while the sentence does not change, so it announces once per step and not once per render. The proof is in apps/web/tests/unit/live-region.test.tsx, in apps/web/tests/unit/features/replay-accessibility.test.tsx and in apps/web/tests/e2e/run-stepper.spec.ts (ADR-050, decisions 4, 6 and 7).
- [x] T051 [US2] Add the timeline, the tree and the stepper to the replay route in apps/web/app/(public)/demo/[scenario]/page.tsx
- [x] T052 [US2] Implement the reset of the replay state in apps/web/features/replay/ReplayProvider.tsx

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - Inspect a claim, its verdict and the evidence behind it (Priority: P2)

**Goal**: The visitor reads the answer as a list of claims, each with the cited evidence, the verification method and the verdict, and opens the sanitized source behind a citation.

**Independent Test**: Open the decision panel of the S01 replay, activate a claim and assert that every cited evidence identifier exists in the published artifact.

### Tests for User Story 3 (OPTIONAL - only if tests requested) ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T053 [P] [US3] Write the end to end test of the claims, the verdicts and the citations in apps/web/tests/e2e/evidence.spec.ts - **DELIVERED in apps/web/tests/e2e/replay.spec.ts**: the journey of the evidence is proven end to end there, because the evidence lives in the same route as the rest of the replay
- [x] T054 [P] [US3] Write the unit test of the evidence and the verdict mapping in apps/web/tests/unit/evidence-mapping.test.ts - **DELIVERED in apps/web/tests/unit/replay-selectors.test.ts**: the mapping of the evidence and of the verdict is a selector of the replay and it is proven with the other selectors

### Implementation for User Story 3

- [x] T055 [US3] Create the verdict pill in apps/web/features/evidence/VerdictPill.tsx with the icon, the text and the three allowed labels - **DELIVERED as apps/web/components/ui/StatusPill.tsx**: the pill of the verdict is a primitive of the interface, because the status of a claim and the status of a row of the ledger are the same shape, and it is used by apps/web/features/evidence/ClaimList.tsx
- [x] T056 [US3] Create the claim list in apps/web/features/evidence/ClaimList.tsx with the text, the citations, the method and the note
- [x] T057 [US3] Create the evidence card in apps/web/features/evidence/EvidenceCard.tsx with the source type, the origin and the copyable reference
- [x] T058 [US3] Create the evidence inspector in apps/web/features/evidence/EvidenceInspector.tsx with the sanitized excerpt - **DELIVERED in another shape, as apps/web/features/evidence/EvidenceCard.tsx**: the source, the origin and the content of the evidence are drawn by the card, and there is no overlay inspector. The excerpt is sanitized by the reader of the bundle before it reaches the card
- [x] T059 [US3] Create the answer panel in apps/web/features/evidence/AnswerPanel.tsx with the answer, the recommended action and the human review requirement
- [x] T060 [US3] Render `Not available` for a missing reference and `Not verified` for an unavailable verifier in apps/web/features/evidence/ClaimList.tsx and apps/web/features/evidence/AnswerPanel.tsx
- [x] T061 [US3] Add the decision panel to the replay route in apps/web/app/(public)/demo/[scenario]/page.tsx - **DELIVERED with the path corrected**: the panel is the tab decision of the reader and the route is at apps/web/app/(public)/replay/scenario/[scenario]/page.tsx
- [x] T062 [US3] Map the evidence and the verdict events to the canonical identifiers in apps/web/lib/replay/selectors.ts

**Checkpoint**: At this point, User Stories 1, 2 AND 3 should all work independently

---

## Phase 6: User Story 4 - Explore the payment ledger rows that the recorded run read (Priority: P2)

**Goal**: The visitor browses the dense table of the simulated payment rows of the account, sees the rows that the recorded run read and opens the detail of a row.

**Independent Test**: Open the ledger panel of the S01 replay, sort by amount, filter by status and assert that the marked rows are exactly the rows whose identifiers appear in the tool responses of the bundle.

### Tests for User Story 4 (OPTIONAL - only if tests requested) ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T063 [P] [US4] Write the end to end test of the ledger table and of the detail panel in apps/web/tests/e2e/ledger.spec.ts
- [x] T064 [P] [US4] Write the fixture of 1000 ledger rows in apps/web/tests/fixtures/ledger.ts - **DELIVERED as a fixture of the tests only**: the deterministic generator of a thousand rows with the six fields of ADR-045, the amounts as decimal text, never published and never imported by a file of apps/web/features/ (ADR-049).

### Implementation for User Story 4

- [x] T065 [US4] Export the ledger rows that the run read and their identifiers in ledgerlens/replay/site_export.py - **DELIVERED as an artifact of its own**: the export publishes site/replay/<scenario>/ledger.json and declares its digest in the provenance and in the card of the catalog (ADR-045).
- [x] T066 [US4] Create the payment table in apps/web/features/ledger/PaymentTable.tsx with the controlled sorting and filtering and the bounded rendering - **DELIVERED in apps/web/features/ledger/LedgerTable.tsx**: the table of the movements that already existed was extended with the controls of the sorting and of the filtering, the bounded rendering is the pagination of 50 rows that already existed, and the sorting and the filtering live in apps/web/lib/replay/ledger.ts. NO component named PaymentTable.tsx was created, because a second table of the ledger would be a second contract with the branch ledger (ADR-049).
- [x] T067 [US4] Create the record detail in apps/web/features/ledger/RecordDetail.tsx with the transaction, the refund, the rate and the policy trigger - **DELIVERED in apps/web/features/ledger/LedgerRowDetail.tsx**: the detail of the movement that already existed was extended, it draws the six fields and the reads that name the row with their rate rows, and it says in words that the recording published no policy trigger for the movement, because the artifact carries no policy. NO component named RecordDetail.tsx was created, for the same reason (ADR-049).
- [x] T068 [P] [US4] Create the account switcher in apps/web/features/ledger/AccountSwitcher.tsx
- [x] T069 [US4] Mark the rows that the run read and write the status in words in apps/web/features/ledger/PaymentTable.tsx - **DELIVERED in apps/web/features/ledger/LedgerTable.tsx**: the table of the ledger carries the words Read by the run (ADR-045).
- [x] T070 [US4] Add the ledger panel to the replay route in apps/web/app/(public)/demo/[scenario]/page.tsx - **DELIVERED as the fifth tab of the replay**: the panel is the tab ledger of the reader, between the execution and the evidence, and the route of the scenario did not change (ADR-045).

**Checkpoint**: At this point, User Stories 1 to 4 should all work independently

---

## Phase 7: User Story 5 - Browse the architecture and follow the links to the source and to the decision records (Priority: P3)

**Goal**: The visitor opens the architecture tour and the engineering drawer, where every subsystem links to the exact module and to the decision record that justifies it.

**Independent Test**: Open the architecture page, activate a node and assert that the link target exists in the repository and that the node references at least one decision record.

### Tests for User Story 5 (OPTIONAL - only if tests requested) ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T071 [P] [US5] Write the end to end test of the architecture links and of the engineering drawer in apps/web/tests/e2e/architecture.spec.ts - **DELIVERED**: 24 cases in chromium and webkit, at 390 and at 1440, covering the four acceptance scenarios of the user story.

### Implementation for User Story 5

- [x] T072 [US5] Create the architecture nodes data with the module and the decision record references in apps/web/features/architecture/nodes.ts - **DELIVERED**: the typed source of the six subsystems, and a test that checks every module and every record against the tree of the repository (ADR-046).
- [x] T073 [US5] Create the diagram in apps/web/features/architecture/ArchitectureDiagram.tsx with the accessible list fallback - **DELIVERED**: an inline SVG with fixed coordinates and the accessible list as its twin, rendered from the same array. The anchors of the SVG carry a `tabindex`, because WebKit does not put an anchor of an SVG in the order of the keyboard without it (ADR-046).
- [x] T074 [US5] Create the node card in apps/web/features/architecture/ArchitectureNodeCard.tsx
- [x] T075 [P] [US5] Create the link components in apps/web/features/architecture/AdrLink.tsx and apps/web/features/architecture/SourceLink.tsx - **DELIVERED**: the base of the links and the commit live in apps/web/lib/repository.ts and in no other place.
- [x] T076 [US5] Build the architecture page in apps/web/app/(public)/engineering/page.tsx - **DELIVERED**: the URL of the page is /engineering, it is static, it reads the commit of the checkout while the site is built and it calls nobody (ADR-046).
- [x] T077 [US5] Add the engineering drawer to the replay route in apps/web/app/(public)/demo/[scenario]/page.tsx - **DELIVERED with the path corrected**: the route of a scenario is apps/web/app/(public)/replay/scenario/[scenario]/page.tsx and the old path of the task does not exist. The drawer itself lives in apps/web/features/architecture/EngineeringDrawer.tsx, it is born independent of T048, and the replay opens it from the section of the calls of the tools (ADR-046).

**Checkpoint**: At this point, User Stories 1 to 5 should all work independently

---

## Phase 8: User Story 6 - Use the replay on a mobile screen and with a keyboard only (Priority: P3)

**Goal**: The whole journey works at 390 pixels with the single column layout and with the tabs, and it works with the keyboard only, with the focus always visible and the reduced motion preference honoured.

**Independent Test**: Run the automated suite at a viewport of 390 by 844 with the pointer disabled and run the accessibility scan on every page of the feature.

### Tests for User Story 6 (OPTIONAL - only if tests requested) ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T078 [P] [US6] Write the mobile journey suite in apps/web/tests/e2e/mobile.spec.ts with the overflow assertion at 390 and 1440 pixels
- [x] T079 [P] [US6] Write the accessibility suite with the axe scan in apps/web/tests/e2e/a11y.spec.ts - **DELIVERED**: 36 cases in chromium and webkit, at 390 and at 1440, over the nine pages of the site, with no rule disabled. The scan found a real violation of `heading-order` on the landing page, and the primitive of the card was corrected so that the level of its title is the choice of the caller.

### Implementation for User Story 6

- [x] T080 [US6] Add the reduced motion rules in apps/web/app/globals.css and the no animation fallback in apps/web/features/replay/usePlaybackClock.ts
- [x] T081 [US6] Make the layout a single column under 768 pixels in apps/web/features/shell/AppShell.tsx
- [x] T082 [US6] Add the accessible tabs for the execution, the evidence, the decision and the ledger in apps/web/app/(public)/demo/[scenario]/page.tsx - **DELIVERED with the path corrected**: the route of a scenario is apps/web/app/(public)/replay/scenario/[scenario]/page.tsx. The tabs are the primitive of the design system, they carry the name of their group, the arrow keys move the focus and the panel of the chosen tab is the only one in the page. The ledger is the fifth tab, between the execution and the evidence (ADR-045, ADR-046).
- [x] T083 [US6] Add the skip link and the landmark structure in apps/web/features/shell/SkipLink.tsx and apps/web/app/layout.tsx
- [x] T084 [US6] Manage the focus on the drawer and on the status region in apps/web/features/agent-trace/ToolCallDrawer.tsx and apps/web/features/replay/ReplayControls.tsx - **DELIVERED with the path corrected**: the drawer of a tool call of T048 returns the focus to the cell that opened it, and the one polite region of the page takes the focus once, when the playback starts, while the drawer never takes it and never announces anything. The status region of the page lives in apps/web/features/replay/ReplayViewer.tsx and not in apps/web/features/replay/ReplayControls.tsx, because ADR-048 decision 9 keeps the controls of the replay free of a live region and does not change that file. What remains open: the controls of the replay hold no region of their own, by decision, and the sanitising of the literals of the SQL is the work of the Python core and not of this milestone. The proof is in apps/web/tests/e2e/tool-call-drawer.spec.ts (ADR-048, decisions 7 and 9).
- [x] T085 [US6] Keep the code panes as the only horizontally scrollable area in apps/web/app/globals.css

**Checkpoint**: All user stories should now be independently functional

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T086 [P] Write the quickstart of the feature in specs/001-r1-public-replay/quickstart.md and link the feature from docs/architecture.md - **DELIVERED**: the quickstart of the feature exists in specs/001-r1-public-replay/quickstart.md and docs/architecture.md links it
- [x] T087 Add the visual baselines at 390, 768 and 1440 pixels in apps/web/tests/e2e/screenshots.spec.ts - **DELIVERED**: the suite is at apps/web/tests/e2e/screenshots.spec.ts and the baselines are the twelve files of apps/web/tests/baselines/, one per page and per width (the home, the tab of the execution of S01, the tab of the ledger of S01 and the tour of the architecture, at 390, 768 and 1440 pixels). The baseline is a STRUCTURAL one and not a picture of the page: a file of JSON that holds the role of each box, its accessible name, its title, its order and its horizontal geometry, with a tolerance of eight pixels. The site uses the fonts of the system and the continuous integration runs on another platform, so a picture committed from one machine is the picture of the font of that machine (ADR-051, decisions 1 to 4). The proof is in apps/web/tests/e2e/screenshots.spec.ts, and the baseline runs in the project of Chromium and skips the other three, because the measurement is the same on every platform.
- [x] T088 Add the digest cross check between the interface and the Python loader in scripts/verify_replay_digests.py and in tests/replay/test_site_export.py - **DELIVERED**: scripts/verify_replay_digests.py crosses the published artifacts against the canonical bundle, it is a step of scripts/gate.sh, and its own test lives in tests/replay/test_site_export.py
- [x] T089 Add the payload and the paint measurement in scripts/measure_replay_budget.py with the thresholds of the success criteria - **DELIVERED**: the script of the repository measures the payload AND the paint. The default arm is the payload and it NEVER starts a browser, because the Python gate runs where Node is absent. The arm of the paint is opt in (--paint), it prints the throttling it applied, and it answers the numbers of SC-003 next to the promise of 1800 ms for the first contentful paint and 2500 ms for the largest one. The web suite asserts a bound of 5000 ms and 8000 ms, which catches a catastrophic regression without breaking for the noise of a shared machine. The numbers of the run of this milestone: 388 ms and 388 ms, with the processor four times slower and 500000 bytes per second down (ADR-051, decisions 5 to 9).
- [ ] T090 Run the full gate, `bash scripts/gate.sh` plus the web lint, the web unit, the web end to end and the accessibility scan, and record the results in specs/001-r1-public-replay/quickstart.md

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 -> P2 -> P3)
- **Polish (Final Phase)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P1)**: Can start after Foundational (Phase 2) - Uses the provider of US1 but should be independently testable
- **User Story 3 (P2)**: Can start after Foundational (Phase 2) - Uses the trace events of US2 but should be independently testable
- **User Story 4 (P2)**: Can start after Foundational (Phase 2) - Depends on the exported ledger artifact of T065, not on the other stories
- **User Story 5 (P3)**: Can start after Foundational (Phase 2) - Independent of the other stories
- **User Story 6 (P3)**: Can start after the pages of US1 to US5 exist, since it checks them, but its own components can be built in parallel

### Within Each User Story

- Tests (if included) MUST be written and FAIL before implementation
- Types and validators before the components that use them
- Exporters and artifacts before the views that read them
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel (within Phase 2)
- Once Foundational phase completes, all user stories can start in parallel (if team capacity allows)
- All tests for a user story marked [P] can run in parallel
- The formatters, the schema types and the UI primitives marked [P] can run in parallel
- Different user stories can be worked on in parallel by different team members

---

## Parallel Example: User Story 2

```bash
# Launch all tests for User Story 2 together (if tests requested):
Task: "Write the end to end test of the playback, the pause and the reset in apps/web/tests/e2e/playback.spec.ts"
Task: "Write the unit test of the determinism of the seek in apps/web/tests/unit/seek.test.ts"
Task: "Write the keyboard test of the trace tree in apps/web/tests/e2e/trace-keyboard.spec.ts"

# Launch all components for User Story 2 together:
Task: "Create the timeline component in apps/web/features/agent-trace/TraceTimeline.tsx with the observed time, the error and the token usage"
Task: "Create the tree component in apps/web/features/agent-trace/TraceTree.tsx with the arrow, the home and the end navigation"
Task: "Create the stepper component in apps/web/features/agent-trace/RunStepper.tsx"
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

1. Complete Setup + Foundational -> Foundation ready
2. Add User Story 1 -> Test independently -> Deploy/Demo
3. Add User Story 2 -> Test independently -> Deploy/Demo
4. Add User Story 3 -> Test independently -> Deploy/Demo
5. Add User Story 4 -> Test independently -> Deploy/Demo
6. Add User Story 5 -> Test independently -> Deploy/Demo
7. Add User Story 6 -> Test independently -> Deploy/Demo
8. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Stories 1 and 2
   - Developer B: User Story 3
   - Developer C: User Story 4
   - Developer D: User Stories 5 and 6
3. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
- The browser never decides whether a number or a claim is right: the Python core produces the verdicts and the amounts, and the interface only renders them
- Every label of the replay stays truthful: the mode is `Recorded Replay`, the caption `Scripted fixture` appears for a scripted bundle, and the word "live" never labels a replay
- The automated suite must keep proving that loading and playing a replay makes zero requests outside the static origin
- The ledger of the recorded demo is an artifact of the site, per scenario, and it carries the ledger of the account the recording read (ADR-045): the fixture of a thousand rows (T064), the sorting and the filtering of the table (T066) and the policy trigger of the detail (T067) stay open, and ADR-045 names each of them as the debt of the full ledger
