# Implementation Plan: R1 Public Replay

**Branch**: `feature/v3` | **Date**: 2026-11-11 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-r1-public-replay/spec.md`

**Note**: This document follows the structure of the implementation plan template of the specification toolkit, filled in for this feature.

## Summary

The R1 slice delivers the public face of LedgerLens as a statically exported Next.js application that plays a recorded agent investigation to any visitor who opens it, with no API key, no login and no call to a model provider.

The approach is deliberately small and honest. The Python core keeps producing the artifacts it already produces: a replay bundle with the events of an execution and a manifest that declares the mode, the provenance and the digests. A small export step turns those bundles into static artifacts for the web application. The web application consumes the published JSON schemas and the recorded artifacts and does nothing else: it renders the trace, it reduces the events when the visitor seeks, it shows the claims with the verdicts the core produced, it shows the ledger rows the run read, and it links the architecture to the modules and to the decision records.

Because the replay needs no backend, the deployment is a static export behind a content delivery network. The consequence is the strongest promise of the feature: loading and playing a replay makes zero requests to a model provider, to an exchange rate service or to any write endpoint, and an automated test proves it.

The work splits into six user stories: the entry with no key, the step-by-step trace, the claims with the evidence, the ledger rows, the architecture links, and the mobile and keyboard operation.

## Technical Context

**Language/Version**: TypeScript 5 in strict mode on Node 20 LTS, Next.js 15 with the App Router, React 19

**Primary Dependencies**: Next.js 15 (App Router, static export), React 19, TanStack Query for the remote state and the cancellation, TanStack Table for the ledger rows with controlled sorting and filtering, Tailwind CSS with design tokens, Radix UI primitives with shadcn style components, Zod for the runtime validation of the published artifacts, Playwright with `@axe-core/playwright` for the end to end and accessibility suites, Vitest for the unit tests of the reducer

**Storage**: Versioned static JSON artifacts under `data/eval/replay/<scenario>/` in the repository, exported to `apps/web/public/replay/<scenario>/` for the site. No database, no session store, no cache server. The only client storage is a harmless view preference.

**Testing**: Vitest for the unit tests of the reducer and of the validators, Playwright for the end to end journeys at 390 and 1440 pixels, `@axe-core/playwright` for the automated accessibility scan, `pytest` for the Python side of the export and of the integrity checks, and `bash scripts/gate.sh` for the Python gate

**Target Platform**: Any current browser, served as static files over HTTPS from a content delivery network. No server runtime, no GPU, no database.

**Project Type**: Web application, static export, inside a repository whose core is a Python library

**Performance Goals**: Largest contentful paint under 2.5 seconds and first contentful paint under 1.8 seconds on a throttled mid-range connection, compressed payload of one scenario under 400 kilobytes, interactions at 60 frames per second, a sort or a filter of the 1000 row ledger under 200 milliseconds

**Constraints**: Static export only, so no server-side data fetching and no secret in the client; zero requests to model providers during a replay; the browser performs no financial arithmetic and no verification; WCAG 2.2 level AA; no horizontal overflow at 390 and 1440 pixels; every label of the replay stays truthful and never says "live"

**Scale/Scope**: Three curated scenarios at first (S01, S09, S10), six pages, about forty components, one public artifact bundle per scenario of a few hundred kilobytes

## Boundaries and contracts

- The frontend consumes the versioned JSON schemas of the design package, namely `docs/v3/contracts/schemas/replay-bundle.schema.json`, `docs/v3/contracts/schemas/trace-event.schema.json` and `docs/v3/contracts/schemas/public-investigation-result.schema.json`, and the recorded artifacts that follow them. It never re-implements a domain rule: verification, decimal arithmetic, policy reading, the query guard and the escalation rules stay in Python.
- The Python core stays the authority. The verdicts, the amounts, the statuses and the recommended action of the interface are read from the published result, and the browser only formats them with the platform number formatter. A value that the artifact does not carry is rendered as unavailable, never invented.
- The artifacts are immutable and hashed. The interface shows the digests and the provenance, and it refuses an artifact whose digest does not match its manifest.
- The static export carries no secret of any kind: no key, no session token, no private dataset. The URL carries the scenario identifier and harmless view preferences only.

## Constitution Check

*GATE: must pass before the research phase. Re-check after the design phase.*

| Principle | How this plan obeys it |
|---|---|
| I. Evidence over fluency | Every claim shown by the interface carries the evidence identifiers it cites, and the evidence inspector opens the sanitized source excerpt with its origin. A citation without a matching evidence renders as `Not available` and blocks a supported status, so an unsupported claim can never look supported. The final answer is presented as a list of claims with verdicts, never as a confident paragraph. |
| II. Numbers come from code | No amount, difference, fee or conversion is computed in the browser. The interface formats the string that the published result already carries, with an explicit ISO currency code. The only client arithmetic is the sum of a playback clock, which is visual timing and never touches a financial value. |
| III. Read-only and least privilege | The feature is a static export: there is no write path at all, no session and no credential. Loading and playing a replay makes zero requests to a model provider, to an exchange rate service or to any write endpoint, and an automated test asserts it. The recorded tool calls are shown with sanitized literals, exactly as they were captured. |
| IV. Reproducible without credentials | The artifacts are regenerated by the capture script in the offline mode, with the scripted model and the recorded exchange rate, from the fixed seed of the public dataset. A visitor needs no key, and the automated suite needs no key. The published digests let a third party confirm that the artifact is the same one. |
| V. Truthful labels | The mode label of a replay is `Recorded Replay`, the caption `Scripted fixture` appears for a scripted bundle, and the word "live" never labels a replay. The captured mode, the capture timestamp, the model profile, the code commit hash, the snapshot hash and the bundle digests are displayed. The playback speed never alters the original measured timings, and a bundle with a different snapshot hash is labelled as having a stale provenance instead of being presented as the same case. |
| VI. Legacy where it teaches, modern where it matters | The web application is new and modern, and it never imports the legacy Streamlit application nor the internal trace internals. It consumes the stable public event contract through the normalizer that the Python core already provides, so the internal span shape can change without touching the interface. |
| VII. Test first, measure always | The reducer, the validator and the selectors are covered by unit tests written before the components. The journeys are covered by Playwright tests with the accessibility scan and with the mobile viewport, and the published numbers (payload size, paint timings, event counts, digest equality) are measured by scripts whose output is versioned. |

*Result: PASS. No violation needs to be justified, so the complexity tracking stays empty.*

## Project Structure

### Documentation (this feature)

```text
specs/001-r1-public-replay/
├── plan.md              # This file, the implementation plan of the slice
├── spec.md              # The feature specification with the user stories and the requirements
├── tasks.md             # The task list that implements the specification
├── research.md          # The decisions taken during the research phase
├── data-model.md        # The entities of the feature and their relations
├── quickstart.md        # The commands that run the feature locally
└── contracts/           # The contracts the frontend consumes
    ├── replay-bundle.schema.json     # Copied from the design package, pinned version
    ├── trace-event.schema.json        # Copied from the design package, pinned version
    └── public-investigation-result.schema.json
```

### Source Code (repository root)

```text
apps/web/
├── package.json
├── pnpm-lock.yaml
├── next.config.ts                    # output: "export", no image optimizer at runtime
├── tsconfig.json                     # strict: true, noUncheckedIndexedAccess
├── tailwind.config.ts
├── postcss.config.mjs
├── eslint.config.mjs
├── vitest.config.ts
├── playwright.config.ts               # projects: chromium, webkit; 390 and 1440 viewports
├── app/
│   ├── layout.tsx                    # AppShell, SkipLink, global landmarks
│   ├── globals.css                   # Design tokens, reduced motion rules
│   ├── (public)/
│   │   ├── page.tsx                  # Landing: hero, honest metrics, two calls to action
│   │   ├── demo/
│   │   │   ├── page.tsx              # Scenario catalog
│   │   │   └── [scenario]/page.tsx   # Guided replay route
│   │   └── engineering/page.tsx      # Architecture tour with the diagram and the links
│   ├── features/
│   │   ├── shell/                    # AppShell, Header, ModeIndicator, SkipLink, ProvenancePanel
│   │   ├── scenarios/                # ScenarioCatalog, ScenarioCard, ScenarioSummary
│   │   ├── replay/                   # ReplayProvider, ReplayControls, RunOverview, ReplayProgress
│   │   ├── agent-trace/              # TraceTimeline, TraceTree, RunStepper, ToolCallDrawer, SqlCodePane
│   │   ├── evidence/                 # EvidenceInspector, EvidenceCard, ClaimList, VerdictPill, AnswerPanel
│   │   ├── ledger/                   # PaymentTable, RecordDetail, AccountSwitcher
│   │   └── architecture/             # ArchitectureDiagram, ArchitectureNodeCard, AdrLink, SourceLink
│   ├── lib/
│   │   ├── api/                      # client.ts, replay.ts, schemas.ts (types generated from the schemas)
│   │   ├── replay/                   # reducer.ts, selectors.ts, validate.ts, provenance.ts
│   │   ├── state/                    # urlState.ts, viewPreferences.ts
│   │   └── format/                   # money.ts, duration.ts, status.ts
│   ├── components/ui/                # Button, Card, Tabs, Dialog, Sheet, Skeleton, Badge, Table, LiveRegion
│   └── tests/
│       ├── unit/                     # reducer.test.ts, seek.test.ts, validate.test.ts, evidence-mapping.test.ts
│       ├── e2e/                      # replay.spec.ts, evidence.spec.ts, ledger.spec.ts,
│       │                              # architecture.spec.ts, a11y.spec.ts, mobile.spec.ts, network.spec.ts
│       └── fixtures/                 # bundles.ts, scenarios.ts, ledger.ts, network.ts
ledgerlens/
└── replay/
    └── site_export.py                 # NEW: writes the static artifacts of the site from a bundle
scripts/
└── export_replay_site.py              # NEW: calls the export for every published scenario
tests/
└── replay/
    └── test_site_export.py            # NEW: digest, redaction and completeness of the exported artifacts
docs/
└── decisions/
    └── ADR-011-static-replay-export.md   # NEW: why the replay is a static export
```

**Structure Decision**: The web application lives in `apps/web` with its own `package.json` and lockfile, as the architecture document of the design package prescribes, so that the Python core is never forced into a JavaScript toolchain. The route groups follow the information architecture of the design package, restricted to the six pages this slice needs: the landing, the scenario catalog, the replay, the architecture tour, and the panels that the replay itself holds (the trace, the evidence, the decision and the ledger). The Python side stays the authority and only gains one module, `ledgerlens/replay/site_export.py`, which turns a bundle into the static artifacts and never touches the domain rules.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violation. The plan adds one web application, one export module and one script, and it keeps the existing Python core, the existing public dataset and the existing design package untouched.
