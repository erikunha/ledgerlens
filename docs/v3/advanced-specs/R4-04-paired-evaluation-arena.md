# LL-V3-R4-04 - Paired evaluation arena

**Status:** design proposed; not yet implemented. **Strategic lens:** Probabilistic Thinking and Proof of Work. **Audience:** Applied AI engineer. **Dependencies:** R0, existing `data/eval/report_online.md`.

## User outcome

Make comparisons of A/B/C/D reproducible and resistant to metric cherry-picking.

## Ownership and compatibility

Existing `ledgerlens/eval` remains source. A/B/C historical reports are preserved with their known 0.73 equivalent trajectory shortfall; new runs versioned independently.

## Typed interfaces and persisted state

`ExperimentManifest` v3 with exact dataset, source SHA, seed, model, pricing snapshot, evaluator, N repetitions, run IDs, architecture variant; API may serve immutable results by experiment ID.

## Algorithm and execution contract

Freeze cases and eval evaluation criteria; execute all variants with same snapshot and case ordering; compute case-level deltas, threshold, quality/latency/cost metrics; stratify by intent/complexity; uncertainty via paired bootstrap or an explicitly declared method; report no result when comparator missing.

## Security, invalid states and recovery

Sensitive prompts/evidence redacted from public export; stored scorer version cannot be silently changed after leaderboard displayed; no provider spend without consent.

## Acceptance scenarios (Given / When / Then)

- Missing run for one case: paired cohort excludes/marks it, never silently zero.
- Changed judge version: experiment ID and output differs.
- Score 0.73 vs target 0.80: UI shows failed target.
- Provider failure on run: output labeled failed, not ignored.

## Metrics, evidence and regression gates

Correctness, groundedness, trajectory strict/equivalent, false escalation, token/compute/review costs, p50/p95, sample and CI.

## Definition of done and rollback

Publish frozen manifest, re-run command, artifact hash, failure gallery and limitations. Rollback scorer by choosing prior immutable manifest.

No claim of implementation is made by this spec. Shipped status requires passing exact executable tests, a source revision, a sanitized replay/trace, and known limitations in release notes.
