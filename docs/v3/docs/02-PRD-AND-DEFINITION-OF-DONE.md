# Product requirements document - LedgerLens Lab

## Positioning

**One-line:** An interactive, evidence-first financial agent laboratory demonstrating how AI investigates simulated payment problems, uses constrained tools, verifies claims and handles uncertainty.

**Primary audience:** international engineering recruiters, hiring managers, staff/principal engineers, AI founders and practitioners reviewing an Applied AI / Full-stack engineering portfolio. Secondary: developers learning agent evaluation and security.

**Business model:** none. Public showcase only. No real money, merchant onboarding, bank connectivity or payment processing. Visitor keys are optional and funded by visitors.

## User journeys

### P1 - recruiter in 90 seconds
1. Land on clean hero, understand that this is an engineering demo and see source/test evidence.
2. Click **Try guided case**; choose an FX refund discrepancy.
3. View sample ledger, select record, start replay.
4. Observe agent plan → tools → evidence → verifier → response, with crisp timeline and trustworthy labels.
5. See "What changed vs a plain LLM?" comparison and link to GitHub/report.

**Acceptance:** fully usable without login/API key; first meaningful interaction <= 2 clicks; UI renders on mobile/desktop; no infinite loading; every graph metric indicates source and protocol.

### P2 - engineering manager exploring technical decisions
1. Enter Architecture Tour, choose the read-only SQL guard, evidence checker or data simulator.
2. Inspect the exact input/output at a tool boundary; see prohibited mutation test.
3. Review source link and ADR, compare limitations and known failures.
4. Open Eval Lab, inspect a failed case and its trace.

**Acceptance:** each important claim is linked to code, fixture or recorded run; failed results are visible, not hidden.

### P3 - curious visitor experimenting with simulated data
1. Create isolated scenario branch from named seed.
2. Apply a constrained mutation (e.g. change applied refund FX rate, change dispute deadline, add duplicate payment).
3. Preview impact and validate business invariants.
4. Run deterministic checks and optionally the live agent; compare to baseline.
5. Reset branch to original seed; download non-sensitive case manifest.

**Acceptance:** no other visitor sees changes; original dataset remains byte-identical; invalid mutation is rejected; state reset returns original canonical hash.

### P4 - developer bringing their own model
1. Open Live Agent, choose supported provider and model from capability registry.
2. Acknowledge billing/privacy notice and submit key over HTTPS.
3. Test credentials with a limited, non-billable or minimal-cost check where supported; show actual expected cost or "unknown".
4. Set max calls/tokens/time/spend and run one case.
5. Revoke credentials; verify key is no longer accepted.

**Acceptance:** no server persistence of key, provider-scoped context and session, no raw secrets in traces/error/analytics, timeouts/quotas, clear cleanup on expiry.

## Epics and high-level functional requirements

| ID | Requirement | Priority | Proof |
|---|---|---|---|
| FR-001 | Guided scenario gallery and recorded traces | P0 | Five realistic playable cases, truthful replay labels |
| FR-002 | Ledger portal with account-specific activity | P0 | Customer/merchant view, filters and record context |
| FR-003 | Agent trace inspector | P0 | Nested spans, inputs/outputs, SQL, timing, citations |
| FR-004 | Evidence and claim verification view | P0 | Each claim has verdict, method, source and limitation |
| FR-005 | Architecture tour and README story | P0 | Source/ADR links and diagram verified against code |
| FR-006 | Isolated scenario branching and reset | P0 | No writes to source; isolation and re-projection tests |
| FR-007 | Constrained scenario editor with preview | P1 | Valid mutations, deterministic before/after diff |
| FR-008 | Live BYOK with provider/model selection | P1 | Scoped secret lifecycle, budget, cost transparency |
| FR-009 | Model/architecture comparison | P1 | Same snapshot + case; normalized metrics and provenance |
| FR-010 | Evaluation lab with local baseline data | P1 | Published failures, sample sizes and score definitions |
| FR-011 | Security failure playground | P1 | Prompt injection and SQL guard demonstrations, safe only |
| FR-012 | Export/share reproducible artifact | P1 | Sanitized bundle with version and checksums |
| FR-013 | Accessible mobile/desktop UX | P0 | WCAG 2.2 AA targeted; keyboard E2E checks |
| FR-014 | Operations/hosting controls | P0 | Rate limits, cleanup, health, no leaking accounts/keys |
| FR-015 | Optional multi-agent comparison | P2 | Measured gain vs simpler baseline; otherwise do not ship |
| FR-016 | Optional local model instructions | P2 | Works only in self-hosted/local deployment; no false localhost access claims |

## Non-functional requirements (initial targets, not achieved metrics)

- **Uptime:** demo fallback should remain accessible even if model providers/backends fail. Static Guided Replay can be CDN-hosted.
- **User-perceived:** first contentful view quick on ordinary 4G; target LCP <2.5 s on representative hardware, interaction responsiveness under 200 ms for common UI actions. Measure with Lighthouse/Web Vitals rather than promise.
- **Accessibility:** WCAG 2.2 AA target; full keyboard usage; focus management; chart and trace alternatives; reduced-motion option; 44px touch targets where practicable.
- **Isolation:** zero cross-visitor case, memory or key leaks in adversarial integration tests; account switch resets context; branch data has a hard TTL.
- **Safety:** no write-capable real payment tools; all scenario operations validated and executed in an ephemeral database only; SQL reader has AST guard + read-only connection + time limit.
- **Observability:** every run has a distinct run ID, versioned events, timestamps, explicit mode/model/status and redaction; never log secrets or complete private request bodies by default.
- **Reproducibility:** record dataset/snapshot manifest checksum, scenario modifications, prompt version, code revision, model/provider parameters and eval version.
- **Accuracy:** not a single made-up target; use explicit metrics for extraction, hallucination/grounding, tool trajectories, escalation, false positives, cost and latency.

## Negative states and recovery paths

Wrong BYOK key → actionable error without echoing secret; rate limit → bounded retry; provider timeout → stopped run and preserved partial trace; insufficient evidence → clear abstention; verifier unavailable → label unverified (never silently mark supported); replay not available → static fallback text; sandbox mutation invalid → no changes and precise error; session expired → reset and request consent again.

## Definition of ready for every feature

Hypothesis, user journey, measurable outcome, API contract, data provenance, security classification, expected failure states, tests, access needs, and decision about whether it works in replay, sandbox and live.

## Definition of done for each feature

Implementation + deterministic test + focused E2E (where UI), a11y checks, telemetry without sensitive data, docs updated, source link correct, failure/rollback handling, mode distinctions visible, benchmark/regression delta recorded and PR reviewed.

## Release exclusions

No real funds, cardholder data, unconsented data uploads, banking credential connections, free unlimited use of proprietary paid models, multitenant SaaS database, or fabricated production metrics. Do not label a feature "real-time" unless it actually performs live work.
