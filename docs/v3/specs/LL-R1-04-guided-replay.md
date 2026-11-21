# SPEC LL-R1-04 - Honest guided replay (first public vertical slice)

**Status:** implementation-ready design, P0. **Outcome:** recruiter tests an authentic recorded agent case without an API key, cold-start delay or provider spend.

## User flow

Landing → Select S01 → open Ledger context → press Play → observe plan/tool/evidence/verifier events → explore source → link to `data/eval`/code → Reset replay. URL may encode replay ID only. Do not create accounts.

## Input and artifacts

Replay bundles conform to `contracts/schemas/replay-bundle.schema.json`: `capture_kind`, `recorded_at`, `scenario_id`, `snapshot_sha256`, `code_sha`, prompt/policy/model versions, final result, trace events. A **real_model_recorded** artifact must be captured from real model execution and reviewed for secrets; a **scripted_fixture** is explicitly labeled. Do not take the spec's `contracts/examples/replay-bundle-example.json` as a genuine recorded model run.

## Frontend state machine

```text
idle -> loading -> ready -> playing <-> paused -> completed
               \-> failed
```

Playback clock affects visual timing only; captured `duration_ms` retains original measured latency. Seek to event N rebuilds view state by reducing events `[0..N]` deterministically. `evidence.added` must map to canonical evidence ID. `claim.verdict` must map to an existing claim. Jump between steps with keyboard buttons, not only slider. Accessible live status uses concise announcements, not every token.

## Rendering contracts

- `RunOverview`: scenario name, question, data/mode, model recorded, capture date.
- `TraceTimeline`: spans and nested tool calls, observed times, errors and token usage when reported.
- `EvidenceInspector`: clicking citation opens source excerpt and origin.
- `AnswerPanel`: final validated answer, verdicts, unsupported claims, human review.
- `EngineeringDrawer`: file/ADR links and explanation of SQL guard/Decimal/verification.

## Acceptance

- Mobile 390px and desktop 1440px work; no important horizontal overflow.
- Simulated payment amount correctly formatted and account-scoped.
- Fetching a replay triggers zero HTTP calls to model providers, FX live services or write APIs.
- Altering playback speed does not change event order or displayed original timing.
- Missing evidence shows `Not available` and blocks green supported status.
- A replay is invalid for modified sandbox branch; UI shows stale provenance and cannot compare as same snapshot.
- Empty/error states and keyboard operation tested in Playwright/axe and manual navigation.

## Tests and budgets

Unit test reducer on event ordering/dedup and seek; integration test trace schema and provenance; E2E story on S01, S09 and S10. Target loading fast on ordinary connection; measure LCP and payload compressed size. Release cannot be called "live".
