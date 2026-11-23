# LL-V3-R11-02 - Budgeted specialist dispatch

**Status:** design proposed; not yet implemented. **Strategic lens:** Asymmetric Bets and Systems Thinking. **Audience:** Staff engineer and AI platform developer. **Dependencies:** R6 prototype, R8 evidence, R10 review, R11 studio.

## User outcome

Compare multiagent dispatch patterns with strict access controls and observable cost/quality.

## Ownership and compatibility

Dispatcher in Python owns policy and tool registry; `InvestigationState` v2 adapts baseline. Specialties may be deterministic functions or LLM agents.

## Typed interfaces and persisted state

`agent-plan` schema v3 for DAG; edge dependencies validated acyclic; runtime caps per role and aggregate; typed result `AgentStepResult {status, refs, spend, error}`; trace exports.

## Algorithm and execution contract

Validate DAG and permission intersections, schedule independent nodes under concurrency cap, enforce max attempts/tokens/USD/deadline, join only matching snapshot and known evidence IDs, deterministic verification before summary.

## Security, invalid states and recovery

Never let delegation expand account/branch scope; unknown tool blocked; no unrestricted remote MCP calls in public demo; reason about partial result/abstention.

## Acceptance scenarios (Given / When / Then)

- Circular dependency rejected at planning.
- Parallel output does not exceed global budget.
- Specialist claims `other-account` -> blocked.
- Agent disagreement over exact amounts -> numeric validator wins or abstains.
- Crash/retry does not duplicate sandbox events.

## Metrics, evidence and regression gates

Quality and cost per correct vs single agent C, max depth, p95, critical path, policy denials, user clarity.

## Definition of done and rollback

Pre-registered paired eval and full failure traces. If no gain, leave feature opt-in with published negative result.

No claim of implementation is made by this spec. Shipped status requires passing exact executable tests, a source revision, a sanitized replay/trace, and known limitations in release notes.
