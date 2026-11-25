---
description: "Task list for cold start guided replay"
---

# Tasks: Cold start guided replay

**Input**: Design documents from `specs/007-r1-cold-start-guided-replay/`

**Prerequisites**: plan.md (required), spec.md (required), the recording and the reader that already exist
(`ledgerlens/replay/bundle.py`, `ledgerlens/replay/site_export.py`,
`apps/web/features/replay/ReplayViewer.tsx`, `apps/web/lib/replay/reducer.ts`) and the decisions
[ADR-013](../../docs/decisions/ADR-013-public-trace-as-a-versioned-contract.md),
[ADR-014](../../docs/decisions/ADR-014-replay-bundle-with-manifest-and-hash.md),
[ADR-042](../../docs/decisions/ADR-042-the-site-of-the-demo-serves-the-published-artifacts.md),
[ADR-060](../../docs/decisions/ADR-060-the-surfaces-that-answer-a-person-carry-the-sentence-of-the-ai-agent.md),
[ADR-074](../../docs/decisions/ADR-074-a-case-ends-in-a-decision-and-the-decision-belongs-to-the-code.md) and
[ADR-075](../../docs/decisions/ADR-075-the-site-publishes-two-catalogs-and-each-bundle-declares-the-one-it-belongs-to.md)

**Tests**: Every task that changes the behaviour of the site ships its test before its code, and the gate of the
frontend `scripts/gate_web.sh` is green before the commit. A test that must fail before the change names the file
it lives in and what it refuses.

**Organization**: Tasks are grouped by the milestone that delivers them, and the tasks of a milestone touch disjoint
files so that they can be worked on in parallel. The ids of this specification start at T701, above the highest id
used by `specs/001-*` through `specs/006-*`, and they never collide with them.

## Format: `[ID] [P?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[DELIVERED]**: the task is done, and the sentence names what it delivered
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `ledgerlens/`, `tests/`, `scripts/`, `data/`, `docs/` at repository root
- **Frontend tree**: `apps/web/` holds the site, its units under `apps/web/tests/unit/` and its end to end tests
  under `apps/web/tests/e2e/`
- Paths shown below assume single project

## Milestone A, the guide is data

**Purpose**: the list of the steps of the cold start, readable without a browser.

- [x] T701 Write the test in `apps/web/tests/unit/features/replay-guide.test.ts` that fails while a step of the
  guide names no region of the reader, while the last step of the guide carries no limitation, while the guide
  does not name the capture it walks, and while a step states a verdict that the bundle does not carry. The test
  reads the guide of `apps/web/lib/replay/guide.ts` and the catalog of `apps/web/lib/replay/catalog.ts`
  - **DELIVERED**: `apps/web/tests/unit/features/replay-guide.test.tsx`: the test reads the guide and the catalog and refuses a step with no region, a last step with no limitation, a guide with no capture and a verdict the bundle does not carry.
- [x] T702 Write `apps/web/lib/replay/guide.ts` with the ordered list of the steps of the cold start of the
  scenario S01, each step carrying the region of the reader it names, the sentence that explains it and the kind
  of the step, and the docstring of the module says what the file is and why the guide is data and not code that
  draws the page
  - **DELIVERED**: `apps/web/lib/replay/guide.ts`: the ordered steps of the cold start of S01, each with the region, the sentence and the kind, and the docstring says why the guide is data and not code that draws the page.

## Milestone B, the page that walks the visitor

**Purpose**: the path that opens the guided case and draws the steps over the reader.

- [x] T703 Write the test in `apps/web/tests/unit/features/replay-guide.test.ts` that fails while the component of
  the guide draws a step whose region does not exist in the reader, and the test that fails while the fork that
  the last step links to names a scenario whose base hash differs from the one that the recording declares in
  `apps/web/public/replay/index.json`
  - **DELIVERED**: `apps/web/tests/unit/features/replay-guide.test.tsx`: the component draws no step whose region the reader does not have, and the fork names the base hash the recording declares in `apps/web/public/replay/index.json`.
- [x] T704 Write the component `apps/web/features/replay/GuidedTour.tsx` that draws the steps of the guide over
  the reader of `apps/web/features/replay/ReplayViewer.tsx`, with the docstring of the component saying why the
  guide names regions and does not own the layout, and open the guided path from
  `apps/web/app/(public)/replay/page.tsx` with the scenario S01 already chosen and with no request to the backend
  - **DELIVERED**: `apps/web/features/replay/GuidedTour.tsx` draws the steps over the reader, the reader owns the regions, and the guided path opens from `apps/web/app/(public)/replay/page.tsx` with S01 chosen and no request to the backend.

## Milestone C, the proofs the package asks for

**Purpose**: the claims of the guided path, each one held by a test that fails before the change.

- [x] T705 [P] Write the test in `apps/web/tests/e2e/guided-replay.spec.ts` that fails while the guided path
  issues a request that leaves the site, that fails while the path asks for a key, and that fails while the reader
  draws an event that the bundle does not carry
  - **DELIVERED**: `apps/web/tests/e2e/guided-replay.spec.ts`: the guided path issues no request that leaves the site, asks for no key, and the reader draws no event the bundle does not carry.
- [x] T706 [P] Write the test in `apps/web/tests/unit/features/replay-guide.test.ts` that fails while the state of
  the reader after two seeks to the same position differs from the state after the first, and that fails while the
  order of the events shown is not the order of the events of the bundle of
  `apps/web/public/replay/sandbox/s01/events.jsonl`
  - **DELIVERED**: `apps/web/tests/unit/features/replay-guide.test.tsx`: two seeks to the same position rebuild the same state, and the events shown are the events of the bundle in the order of the bundle.
- [x] T707 [P] Write the test in `apps/web/tests/unit/features/replay-viewer.test.tsx` that fails while a citation
  of the recorded scenario resolves to a record other than the one it names, that fails while a citation whose
  source is absent produces a nearest match instead of a stated refusal, and that fails while the money of a cited
  row is rounded to a float instead of being read as the exact `Decimal` string of the row
  - **DELIVERED**: `apps/web/tests/unit/features/replay-viewer.test.tsx` and `apps/web/lib/replay/citations.ts`: a citation resolves to the record it names, an absent source is a stated refusal, and the money of a cited row is the exact decimal text.
- [x] T708 [P] Write the test in `apps/web/tests/unit/features/replay-viewer.test.tsx` that fails while a missing
  artifact of `apps/web/public/replay/` produces an empty trace without a reason, and that expects the refusal to
  name the file it looked for and the command `scripts/export_replay_site.py` that rebuilds it
  - **DELIVERED**: `apps/web/tests/unit/features/replay-viewer.test.tsx` and `apps/web/lib/api/replay.ts`: a missing artifact is refused with the name of the file and the command `scripts/export_replay_site.py` that rebuilds it.

## Milestone D, the path with a keyboard and on a phone

**Purpose**: the entrance of a public repository works for everyone who arrives.

- [x] T709 [P] Extend the test in `apps/web/tests/e2e/a11y.spec.ts` so that it fails while a control of the
  guided path cannot be reached with the keyboard, and while the announced region of the step does not carry the
  step
  - **DELIVERED**: `apps/web/tests/e2e/a11y.spec.ts`: every control of the guided path is reached with the keyboard, and the region the step announced carries content.
- [x] T710 [P] Extend the test in `apps/web/tests/e2e/mobile.spec.ts` so that it fails while a control of the
  guided path is smaller than 44 pixels, and while the path overflows the viewport at the width of a small phone
  - **DELIVERED**: `apps/web/tests/e2e/mobile.spec.ts`: the controls of the guided path are at least 44 pixels, and the path never overflows the viewport of a small phone.
- [x] T711 [P] Extend the test in `apps/web/tests/unit/features/replay-viewer.test.tsx` so that it fails while the
  guide presents a recorded run as a live one, and so that it fails while a bundle whose manifest was tampered
  with is drawn instead of being refused with its reason
  - **DELIVERED**: `apps/web/tests/unit/features/replay-viewer.test.tsx`: the guide never presents the recorded run as a live one, and a bundle whose events were tampered with is refused with the integrity reason.

## Milestone E, the record of the milestone

**Purpose**: the decisions the milestone took are written down where the repository keeps them.

- [x] T712 Write the record of the milestone in `docs/decisions/` with the next number after ADR-077, which states
  that the guide is data that names regions of the reader, that it adds no verdict of its own, that the guided path
  asks no provider and that the three minutes of the design package stays a hypothesis until a consented
  measurement exists, and link it from `docs/decisions/README.md` with
  `uv run python scripts/build_docs_index.py`
  - **DELIVERED**: `docs/decisions/ADR-100-the-guide-of-the-cold-start-is-data-that-names-regions-of-the-reader.md`: the guide is data that names regions, adds no verdict, asks no provider, and the three minutes stays a hypothesis.
