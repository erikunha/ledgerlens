# Implementation handoff for coding agents and human reviewers

This pack is a **specification**, not authorization to modify the original GitHub repo. When implementation is requested, inspect current `main`, re-run baseline and reconcile architectural decisions with changes since audit commit. Work in small, reversible PRs.

## First implementation slice

1. Read original `README`, `AGENTS/CLAUDE` if present, `docs/architecture`, test/eval reports and existing runtime.
2. Run `uv sync --extra dev --extra app --extra api`; `LEDGERLENS_OFFLINE=1 bash scripts/gate.sh`; record exact results and artifacts.
3. Define `TraceEvent` Pydantic schema and adapter from `Span`. Write tests against S01, S09, S10 output, including redaction.
4. Capture a **genuine recorded run**, with model key supplied by maintainer outside repo, review and sanitize bundle; run schemas and hash validation.
5. Create minimal Next.js landing and one guided replay that renders the saved events; test keyboard and no model calls.
6. Only then implement sandbox. Never implement BYOK before isolation and redaction gates.

## Source-of-truth hierarchy

- Existing Python financial rules, projector, schemas and tests own business behavior.
- This document pack owns target UX, public API and non-functional requirements until an ADR revises it.
- OpenAPI and JSON Schemas are interface *design* sources; generated clients must match actual services after implementation.
- Tests and actual runtime evidence override optimistic assumptions in this spec.

## Agent execution instructions (for future implementation)

- Claim one `LL-Rx-yy` task per branch; inspect affected files and failing tests before editing.
- Prefer additive adapters over rewrites. Don't disable/skip tests to make a feature appear complete.
- For each PR: purpose, files touched, tests added, actual commands/run results, screenshots if UI, rollback, unresolved risks.
- Keep data origin and seeded scenario math intact; no hardcoded fake benchmark improvements.
- Do not create a hosted, free, owner-paid LLM endpoint.
- Never copy user-provided API keys into code/logs, and never store keys in generated replay.
- Do not call a mode "Live" unless actual provider request occurred and its evidence captured.
- Schema migrations need migration/readers for old replay bundles; preserve public permalinks.
- When unsure of intended model capability, add a test/probe and mark unsupported; don't assume based on name.

## Deterministic output expectations

A PR adding a feature must have `Given / When / Then` tests for success, invalid input, auth/scope, cancellation/timeout, replay behavior and data integrity. E2E must exercise the same Pydantic/agent engine that the frontend actually invokes. If a UI sketch cannot be implemented without duplicating domain logic in TS, revise architecture before coding.

## Recommended demo review questions

- Can a cold reviewer tell scripted/replay/live apart?
- Does evidence link to actual data and rule? Can a false claim show `not enough evidence`?
- If a key is revoked, can any new model call still happen?
- Does changing a sandbox event change the right projected values, and only for that visitor?
- Are tool permissions enforced by code, regardless of agent instructions?
- Is the experimental claim supported by enough cases, with failure examples?

## Implementation non-goals

No new billing system, no real payment writes, no large-scale multi-tenant architecture, no organization management and no massive rewrite of the simulator for cosmetic UI features.
