# Release train - staged portfolio delivery, 2026 Q4 through 2027+

Release IDs are monotonic; dates are **provisional planning windows**, not promises. Each release has explicit entrance and exit gates. The intent is to ship a high-impact demo as soon as R1 exists, rather than building infrastructure indefinitely.

## R0 - Baseline integrity and refactoring seam (entry point)

**Value:** known-good Python core and reproducible demo artifact. **Dependencies:** current `main`. **Deliverables:** run all existing tests; fix critical blockers; record exact `git SHA` and scenario hashes; define `RunContext`, TraceEvent normalization, port for provider factory; isolate Streamlit from new UI; read-only baseline; documented current benchmark limitations. **Exit:** existing offline gate passes; one genuine sample run can be captured to a validated, redacted JSON bundle; no changes to core money semantics.

## R1 - Public guided replay (first portfolio release)

**Value:** visitors can understand the system with no key. Deliver landing, scenario gallery, payment ledger, step replay, trace inspector, evidence citations, architecture page, static evaluation results and responsive design. **Exit:** 5 replay scenarios load on web and mobile; no model calls; all replay data traceable and versioned; a11y smoke and E2E; actual screenshots and GitHub README refreshed. **Publish this release publicly.**

## R2 - Isolated editable Scenario Lab

**Value:** visitors run meaningful experiments. Build session isolation, snapshot fork, mutation preview/apply/reset, deterministic projector, before/after diff, stale replay detection, sandbox tests, event-derived audit trail. **Exit:** 2 visitor isolation E2Es, conflict/idempotency, reset hash, 3 editable cases (FX refund, duplicate charge, dispute deadline if projector event added), arbitrary input rejected; deterministic computations honest.

## R3 - Live BYOK agent and Model Selector

**Value:** full genuine LLM runs. Implement scoped credential lifecycle, provider registry (OpenAI first), model probe, budgets, FastAPI run coordinator, event SSE, cancellation and resumption, ability to rerun agent on visitor branch. **Exit:** redaction and owner-check tests, no provider credential persistence, hard timeouts/quota, default demo works keyless, one live end-to-end provider tested, cost disclosure.

## R4 - Evaluation/Model Arena

**Value:** code and architecture demonstrated empirically. Build A/B/C comparison, equivalent case sets, failure gallery, per-claim verdicts, cost/latency charts, coverage/CI, locked holdout evaluation, comparative traces. **Exit:** published benchmark includes sample sizes, uncertainty, datasets, hardware, known failures and unachieved targets; no false calibrated performance claim.

## R5 - Portfolio production hardening

**Value:** demo remains reliable for recruiters. Performance budgets, accessibility comprehensive, public security review, runbooks, sharing of sanitized run artifacts, deployment/rollback, web analytics privacy decisions, docs/tutorial, video walkthrough. **Exit:** E2E matrix green; low-cost hosting measured; static fallback works without backend; controlled release and rollback tested.

## R6 (optional) - Advanced agent architecture as experiment

**Value:** demonstrate architectural reasoning rather than showy complexity. Add selective specialist review/parallelization as experimental D; evaluate accuracy, false positives, cost per correct case, p95 latency vs C. **Exit:** public report shows measured gains or honestly documents why multiagent was rejected. No unbounded team-agent loops.

## R7 (optional) - Model behavior and robustness studio

**Value:** educational deeper platform. Interactive failure injection library, controllable tool responses, memory controls, calibration comparisons, evaluation slice explorer, new provider adapters or local mode documentation. **Exit:** scenarios are safe and reproduce test outcomes; all advanced capability claims verified. Not required for initial LinkedIn launch.

## Prioritization

- **P0 public:** R0→R1.
- **P1 differentiator:** R2→R4.
- **P2 polish:** R5.
- **Research only:** R6/R7 if evidence justifies.

## Milestone decision framework

Each release must improve at least one: visitor comprehension, empirical trust, ability to explore real system behavior, or senior-level engineering signal. Stop adding features when marginal career signal is lower than engineering/maintenance cost.
