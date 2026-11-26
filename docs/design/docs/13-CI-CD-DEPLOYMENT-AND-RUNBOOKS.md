# Quality gates, CI/CD, release and operational runbooks

## CI pipelines

### `core.yml` (every PR)
- Set up pinned Python 3.12 + uv lock; install test extras, run Ruff, pytest, schema checks and existing `scripts/gate.sh` offline.
- Run event store/projector canonical-hash replay and account scope isolation tests. Check `data/scenarios.json` / source NOTICE attribution and replay bundle validity.
- Run SQL guard negative cases and verifier deterministic rules.
- Run secrets detection and dependency audits with triaged exceptions; avoid displaying env or test dummy credentials in public logs.

### `web.yml` (every PR)
- Node/pnpm pinned and lockfile; TypeScript strict, ESLint, unit/component tests, OpenAPI client generation/diff, build.
- Playwright happy paths for replay, scenario mutation, reset, key opt-in (fake provider), trace inspection, responsive and keyboard use.
- `@axe-core/playwright` for automated checks; manual audits for screen reader/focus/contrast and zoom.
- Screenshots against approved baselines, with reviewable diffs. No screenshot as sole correctness evidence.

### `replay-capture.yml` (manual + on model/prompt changes)
- Require explicit operator/provider credential; run limited seeded suite locally/CI secret store, sanitize and validate; record code/model/policy/snapshot hashes and costs.
- Review artifacts before publishing; never automatically commit a replay with raw provider prompts/key.
- Compare against expected outcomes and prior captured bundles, fail on unsafe regression, publish versioned release artifacts.

### `release.yml` (on tagged releases)
- Run all above gates plus API/Pydantic contract tests, cross-session security, failure injection and smoke deploy.
- Generate changelog and updated screenshots after verifying actual UI. Freeze sample hash and artifact manifest.
- Deploy CDN/static replay before optional Live backend; rollback via tagged container/artifact version.

## E2E critical matrix

| ID | Journey | Must verify |
|---|---|---|
| E2E-001 | Landing → S01 → replay → trace → source | no key; no network model call |
| E2E-002 | S01 branch → FX change → preview → commit | ledger diff correct, old trace stale |
| E2E-003 | Sandbox reset | exact base hash restored |
| E2E-004 | Two browsers edit different branches | zero cross-leak |
| E2E-005 | S09 malicious note | tool policy maintained; no payment mutation |
| E2E-006 | S10 unsupported rate | abstention/escalation visible |
| E2E-007 | BYOK dummy key → one run → revoke | no key persisted, no post-revoke SDK call |
| E2E-008 | Provider 500/timeout mid-run | partial trace, error, budget stop |
| E2E-009 | Live run SSE reconnect | sequence dedupe, final state truthful |
| E2E-010 | Account switch | conversation/memory/scope reset |
| E2E-011 | Keyboard mobile 390px | all essential operations accessible |
| E2E-012 | Eval metric drilldown | correct data version and source |

## Release health and SLO draft

- Public static replay: target 99.9% availability (dependent on hosting), with synthetic monitoring.
- Live API: useful demo target 99% availability initially, but no public uptime claims until observed; tests define expected behavior under cold starts.
- Error budget: no cross-session or BYOK leak allowed; service may fail closed and fall back to replay.
- Performance: p95 read API response <500ms on local sample in target hosted hardware, p95 replay first meaningful interaction <2.5s, interactive UI input response <200ms. Live LLM duration not under full system control; show actual measurement.
- Limits: configurable e.g. 2 concurrent live runs/backend, 1 live run/session, maximum 60s/run; profile and adjust. These are starter budgets, not universal targets.

## Runbooks

**Provider down**: detect normalized error, stop retries at budget, preserve partial trace, notify visitor, maintain replay; no fail-open into unchecked model.

**Verifier timed out**: mark `partial/unavailable`, abstain if high-risk, do not render supported green, offer replay or rerun with different supported config.

**Session leakage suspicion**: disable sandbox/live endpoints via flag, keep static replay, collect minimal secure metadata, investigate ownership checks, rotate cookie signing key, invalidate sessions.

**Unexpected spend / abuse**: disable BYOK registration or live runs, enforce concurrency/rate limits, audit host egress and provider activity; no owner-funded free API mode by default.

**Outdated replay**: mark and keep known version while recording fresh runs; restore hash-provenanced bundles on rollback.

**DB corruption**: restore immutable published base, wipe transient branches (disclosed), validate `canonical_hash`, rerun fixtures; do not repair by hand-editing production demo copy.

**Model removed/deprecated**: mark profile retired, block new runs, keep recorded historical artifact with date; refresh tested registry and eval before re-enable.

## Documentation and ops artifacts

`SECURITY.md`, `PRIVACY-DEMO.md`, `CONTRIBUTING.md`, `docs/architecture.md`, `docs/decision-records/`, `docs/replay-provenance.md`, `docs/model-support.md`, `docs/evaluation-methodology.md`, `.env.example` with no secrets, `CODEOWNERS` optional, `LICENSE`, `NOTICE`, `healthz`, rollback instructions, `Makefile/justfile`, issue template, PR checklist, tests/eval report.

## Budget discipline

A portfolio project must not become a money sink. Prefer static replay for 90% of visits. Estimate hosting and provider costs every month; cap and alert on backend egress/resource usage. Do not pay for always-on GPU. Publish an explicit maintenance and operational burden section when selecting integrations.
