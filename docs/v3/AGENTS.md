# AGENTS.md - proposed project instructions for future implementation

**Scope:** this file describes how an engineering agent should work *when a maintainer explicitly authorizes implementation*. The spec itself is design-only and does not authorize editing the upstream repository.

## Objective

Build an honest, interactive portfolio demo around existing LedgerLens Python logic; preserve safety, financial invariants and measured correctness. Public replay without keys is P0. Never turn this into a real payment processor.

## Working rules

1. Read the repository files, current tests and relevant `docs`/ADRs before changing code. Reconcile target spec with current `main`; do not assume the audit SHA remains current.
2. Work one `roadmap/IMPLEMENTATION-BACKLOG.md` item per small PR. Do not modify unrelated behavior.
3. Keep agent, simulator, verification and money calculations in Python. UI TypeScript must consume versioned API schemas, not reimplement domain logic.
4. Preserve original seeded fixtures and immutable base hash. Per-visitor sandbox writes are typed, atomic and temporary.
5. Expose all observable public state using stable versioned contracts; never couple React to LangChain internal callbacks.
6. Replay must be labeled; never misrepresent scripted/recorded events as fresh model calls.
7. Before any BYOK work, make per-session isolation and secrets redaction tests green. Keys remain transient server-side and usage bounded.
8. No model result can authorize unscoped SQL, actual financial writes, server processes, arbitrary URLs or cross-session data.
9. Never publish benchmark gains without actual repeatable eval outputs, sample sizes and model/dataset hashes.
10. Mark unavailable verifier data explicitly; do not claim automatic fact-checking is perfect.
11. For every feature write positive, negative, adversarial and failure-path tests; run existing Python gate and web build/E2E as applicable.
12. Document what was executed, observed and not validated. A fail is preferable to an invented successful result.

## Checklists

Before PR: update local main, install locked dependencies, reproduce baseline, inspect ownership boundaries. After PR: typecheck/lint/unit/integration/E2E, schema validation, security review, a11y, docs/ADR, recorded exact commands and rollbacks.

## Architecture references

Begin with `README.md`, `docs/01-REPOSITORY-AUDIT.md`, `docs/05-SYSTEM-ARCHITECTURE.md`, `docs/06-AGENT-RUNTIME-AND-TOOLING.md`, `docs/10-SECURITY-AND-THREAT-MODEL.md`, `contracts/openapi.yaml` and `roadmap/RELEASE-TRAIN.md`.


## LedgerLens v3 strategic extension (2026-11-11)

- Follow existing baseline `ledgerlens/` Python core, tests and contracts; v3 design files are **not an implementation**.
- Read `strategy/00-STRATEGIC-INTELLIGENCE-STACK.md`, `ai/CAPABILITY-ATLAS.md` and `roadmap/RELEASE-TRAIN-2027-2030.md` before implementing a new capability.
- Do not cut research ideas based on arbitrary artificial scope; select actual work by independent measurable experiment and explicit dependency.
- A spec document does not mark a feature shipped. For every shipped item attach source SHA, tests, actual trace/fixture and honest known limits.
- Keep real-world financial side effects prohibited; sandbox edits only; time, money and data scopes explicit.
- Multiagent, new frameworks and additional models require paired evaluation vs simpler baseline.
- Prevent disclosure of BYOK, visitor data, sensitive trace contents, and never pretend replay/recorded outputs are new inference.
- Technical public claims require a reproducible artifact; economic claims require labeled assumptions or actual measured evidence.
