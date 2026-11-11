# Architecture Decision Records (proposed)

These ADRs apply to the **public portfolio extension**, not retroactive changes to the existing repository. They should be accepted or adjusted by the maintainer before implementation. Existing repo ADR-001..010 remain the historical source of truth for the original Python project.

| ADR | Decision | Status |
|---|---|---|
| [P-001](ADR-P001-preserve-python-core.md) | Preserve Python domain/agent core, add Next.js + FastAPI facade | Proposed |
| [P-002](ADR-P002-replay-truthfulness.md) | Distinguish replay, sandbox, live | Proposed |
| [P-003](ADR-P003-sandbox-events.md) | Event-sourced isolated visitor branches | Proposed |
| [P-004](ADR-P004-byok-ephemeral.md) | Ephemeral BYOK with opt-in and hard limits | Proposed |
| [P-005](ADR-P005-sse-trace-protocol.md) | Versioned trace envelope + SSE | Proposed |
| [P-006](ADR-P006-eval-governance.md) | Measurement-first evaluation and negative cases | Proposed |
| [P-007](ADR-P007-no-multiagent-by-default.md) | No multiagent until verified gain | Proposed |
| [P-008](ADR-P008-portfolio-deployment.md) | Low-cost single host/static fallback | Proposed |
| [P-009](ADR-P009-privacy-scope.md) | Public data only, no external payments | Proposed |
