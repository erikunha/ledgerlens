# Implementation backlog - scoped, testable and reviewable

Each item is a candidate PR or a narrowly scoped group of PRs. Dependencies are release-based. For implementation, split tasks further if a PR exceeds reviewable size. **Everything below is planned, not already shipped.**

| ID | Priority | Deliverable | Acceptance |
|---|---|---|---|
| LL-R0-01 | P0 | Record baseline git SHA, lock dependencies and run offline tests | Version and command output in validation record; no unrelated refactor |
| LL-R0-02 | P0 | `RunContext` injected into core | No shared global per-visitor model key/path; old tests unchanged |
| LL-R0-03 | P0 | Public `TraceEvent` schema / normalizer | Every known Span maps or fails explicitly; schema tests |
| LL-R0-04 | P0 | Replay capture tool + redaction | Genuine provider run sanitized, hashed, JSON validated |
| LL-R0-05 | P0 | Snapshot base hash verification | Immutable base hash validated before every branch |
| LL-R0-06 | P0 | Reconcile verifier calibration metadata | Dataset count, hashes and 43-vs-30 discrepancy resolved; report reproducible |
| LL-R1-01 | P0 | Next.js shell, landing, nav | Runs on mobile, keyboard, clear no-key CTA |
| LL-R1-02 | P0 | Guided scenario catalog | 5 playable recorded scenarios, truthful mode labels |
| LL-R1-03 | P0 | Ledger UI & transaction detail | Account scope, table filters, meaningful monetary formatting |
| LL-R1-04 | P0 | Replay controls and store | Pause/step, no model HTTP or mutations, stable event ordering |
| LL-R1-05 | P0 | Evidence/claim inspector | Verifier status and evidence provenance per claim |
| LL-R1-06 | P0 | Architecture/Eval static pages | Source links and benchmark caveats accurate |
| LL-R1-07 | P0 | Accessibility and frontend E2E | Axe scan plus manual keyboard pass and mobile smoke |
| LL-R2-01 | P0 | Anonymous session + temp branch model | Two visitors cannot access each other's ledger |
| LL-R2-02 | P0 | Branch event storage and deterministic projector | Reset hash equal base; no direct domain table UPDATE |
| LL-R2-03 | P1 | Typed mutation parser/preview | Invalid inputs rejected atomically, diff correct |
| LL-R2-04 | P1 | FX sandbox mutation | Output Decimal and evidence change consistent; stale replay detected |
| LL-R2-05 | P1 | Duplicate payment mutation | Distinct IDs, duplicate detector behavior consistent |
| LL-R2-06 | P1 | Tool outage simulation | Clear unavailable state and escalation, no fictitious FX |
| LL-R2-07 | P1 | Scenario editor UI and reset | Before/after visible, revision conflict 409 handled |
| LL-R3-01 | P0 | Provider registry + tested capability list | Only tested tool-calling models enabled |
| LL-R3-02 | P0 | Ephemeral BYOK secret handles | No leak/storage; cross-session requests denied |
| LL-R3-03 | P0 | Run coordinator with hard budgets | Bounded model calls, tools, memory, timeout, concurrency |
| LL-R3-04 | P1 | FastAPI live run endpoints/SSE | Typed events, reconnect sequence, cancel, partial trace |
| LL-R3-05 | P1 | Frontend selector / key consent modal | Costs and retention visible, Forget key effective |
| LL-R3-06 | P0 | BYOK adversarial and mock-provider tests | No secrets in logs; no arbitrary URLs/models |
| LL-R4-01 | P1 | Evaluation manifest and report versioning | Model/sample/protocol/hash with each metric |
| LL-R4-02 | P1 | Architecture A/B/C comparison | Same dataset and snapshot; no misleading chart |
| LL-R4-03 | P1 | Verifier calibration and failure explorer | Displays .786/.625 nuance with proper denominators |
| LL-R4-04 | P1 | Extended held-out scenarios | New seeds, adversarial cases and uncertainty analysis |
| LL-R4-05 | P1 | Model Arena UI | Paired cases, quality/latency/cost, actual trace drilldown |
| LL-R5-01 | P1 | Hosted deploy and static fallback | Recorded replay usable through API outage |
| LL-R5-02 | P1 | Security hardening + incident runbooks | Origin/CSRF, rate limits, TTL, threat-model checks |
| LL-R5-03 | P1 | Professional README, source tour and video | Claims directly supported by tests and code |
| LL-R5-04 | P1 | Telemetry, cost and performance gates | Published budget and actual measured results |
| LL-R6-01 | P2 | Controlled specialist reviewer graph | Feature flag, bounded state and tool permissions |
| LL-R6-02 | P2 | D-vs-C experiment | If no gain, disable D and publish negative result |
| LL-R7-01 | P2 | Robustness/fault playground | Safe corpus, explicit outcomes, no external code |

## Cross-cutting acceptance template

Each task should be implemented with: objective, prerequisites, file inventory and owner module, `Given/When/Then` behavioral cases, Pydantic/JSON/OpenAPI contract diffs, error states, security impacts, tests, docs, migration/rollback and a link to a reproducible demonstration. PRs should not modify unrelated modules. CI must validate generated contract clients to prevent silent drift.

## First three PRs

1. **LL-R0-01:** establish executable baseline and add `verification/baseline.md` with actual test results and version hashes.
2. **LL-R0-03:** add a typed `TraceEvent` normalizer and tests for S01/S09/S10 using current spans; no UI changes.
3. **LL-R0-04:** capture and sanitize one genuine run bundle and make a tiny static viewer. Only after this succeeds start building Next.js screen set.
