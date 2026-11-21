# Frontend platform, design system and accessibility

## Goal

Present deep financial and agentic workflows with a calm, credible visual language suitable for senior engineering interviews. **Not** a colorful generic AI dashboard. The strongest UI interactions are dense transaction data, inspectable evidence, deterministic scenario controls and trace timelines.

## Stack

- Next.js App Router + React + TypeScript strict; server components for static marketing/docs, client components for interactive lab.
- TanStack Query for remote state/cancellation/invalidation; TanStack Table for ledger rows, sorting, filters and controlled state; TanStack Virtual for large result lists only when profiling justifies.
- Tailwind CSS + Radix UI primitives or shadcn/ui for accessible components. Custom design tokens for typography, spacing, surfaces and semantic states; not vendor-specific brand imitation.
- React Hook Form + Zod for mutation forms; generate runtime API types from OpenAPI; validate both frontend and Pydantic backend.
- Syntax highlighting for SQL/JSON; optional lightweight graph visualization with React Flow/D3, always backed by accessible tabular representation.
- Playwright for E2E; @axe-core/playwright for detectable accessibility violations, supplemented by manual keyboard/screen-reader tests.

## Information architecture component tree

```text
apps/web/
  app/
    (public)/page.tsx
    demo/page.tsx
    lab/layout.tsx
    lab/ledger/page.tsx
    lab/scenarios/page.tsx
    lab/runs/[id]/page.tsx
    lab/arena/page.tsx
    research/evals/page.tsx
    engineering/page.tsx
  features/
    shell/                Header, mode badge, nav, layout
    scenarios/            Catalog, scenario fixture, branch editor
    ledger/               Account switch, statement table, details
    agent-trace/          Run events, trace tree, stepper, timeline
    evidence/             Evidence cards, citations, verdict graph
    models/               BYOK modal, model profile selector, budget
    evals/                Comparison table, data charts, failures
    architecture/         Diagrams, ADR links, source explorer
  lib/api/                Generated client/types, SSE adapter
  lib/state/              URL state and session-scoped view state
  components/ui/          Accessible primitives / design tokens
  tests/e2e/              Critical visitor journeys
```

## UI patterns

**DataTable:** controlled sorting/filtering/pagination, status cues with text (not color only), row header, accessible table name, keyboard navigation, quick search. Currency uses `Intl.NumberFormat` with explicit ISO currency. Query params store only harmless filters, not secrets.

**TraceTree:** rows for nested spans; expandable details with step index, precise wall-time/tokens, metadata and source. Keyboard Arrow Up/Down/Home/End navigation where tree pattern is implemented correctly; otherwise use semantic nested lists/buttons. Avoid thousands of DOM nodes; virtualize if necessary.

**EvidenceCard:** stable ID, source type, extracted snippet, timestamp, source origin and copyable reference. Missing/unverified references displayed as such, not silently omitted.

**VerdictPill:** `supported`, `contradicted`, `not enough evidence`, with icon+text; separate `verifier unavailable` from verdict.

**BudgetMeter:** estimated and observed tokens/calls/time; never show invented USD pricing. Display warning when price is unknown.

**ScenarioMutationForm:** schema-driven fields, immediate validation, preview before commit, accessible error descriptions and undo/reset.

**ModeIndicator:** persistent neutral label `Recorded`, `Deterministic`, `Live`; explanation tooltip. Never badge all pages identically for decoration.

## Design system foundations

Typography: use a legible sans font with a monospace companion for IDs, SQL and JSON. Neutral palette; use semantic green/red/amber only for real verification statuses and urgency. Spacing scale 4px increments. Default light/dark available if it doesn't delay critical UX; avoid overdesign. Components: `AppShell`, `PageHeader`, `AccountSwitcher`, `PaymentTable`, `RecordDetail`, `EvidenceInspector`, `RunStepper`, `TraceTree`, `ToolCallDrawer`, `VerdictList`, `ScenarioCard`, `MutationPreview`, `ModelSelector`, `ApiKeyDialog`, `EvalComparison`, `FailureCase`, `SourceLink`.

## Responsive design

- 1440px+: ledger main + evidence drawer or 2/3-panel Run Inspector.
- 768-1439px: two pane or tabs, avoid narrow chat columns.
- <768px: single column with sticky bottom CTA when appropriate; ledger cards + detail drawer; trace and evidence are accessible tabs; full text readable without horizontal scrolling.
- 320px viewport: no clipped essential content; monospace SQL scrolls only in code pane.

## Interaction/focus

Loading states announce status (`role=status` or accessible live region), not constantly verbose. After "Run", focus the status region once; after result focus heading or result summary; after modal close return focus to trigger. Keyboard users can run everything, expand trace, copy evidence and reset sandbox. Provide visible skip link, reduced-motion mode, sufficient color contrast, semantic time and number labels.

## Frontend performance and resilience

Server-render static pages and use code-split for lab; avoid importing heavy graph/chart/editor code into Landing. SSE events batched into render frames to reduce re-renders; normalized `RunEventStore` keyed `(run_id,seq)`, memoized tree selectors. No client-side financial arithmetic beyond *display*; backend returns authoritative Decimal strings. No secrets in query cache, dev tools logs or URL. Errors are localized to panel; a provider 503 cannot take down Landing/Recorded Replay.

## Storybook and screenshots

Develop story variants: loading, empty, error, unsupported model, contradicting verdict, no evidence, long SQL, 1000 ledger entries, mobile, dark/high-contrast, screen-reader labels. Screenshot baselines at 390, 768, 1440 px, plus zoom 200%. Test at least one Windows Chromium and macOS WebKit-like browser when feasible. Published screenshots must come from the implemented app; do not publish mocks as verified live behavior.

## UX acceptance

First visitor can complete curated case without reading docs or entering key; no on-screen API credentials except scoped opt-in form; screen reader announces why a claim is unsupported; all actions have visible feedback and error recovery; marketing/demo links do not 404; every interactive filter is reflected in state coherently; no 600-line single component equivalent of legacy Streamlit app.
