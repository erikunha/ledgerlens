# Evaluation test matrix and benchmark release gates

## Existing baseline truth

Published online evaluation: 30 cases, A/B/C, 3 repeats, gpt-4.1-mini (as recorded 2026-11). Keep comparison protocol, no claim of statistical significance. NLI calibration tracked separately with two sets; visible generalization gap.

## Deterministic suite

| Case ID | Property | Expected |
|---|---|---|
| S01 | FX markup math and date sources | Decimal correction, source labels |
| S02 | Duplicate detector | Two card charges 38 seconds apart flagged |
| S03 | Deadline cutoff | Timely human escalation and business-day checks |
| S04 | Unknown transaction | No fabricated details; clarify |
| S05 | Ambiguous equal amount | No incorrect duplicate assumption |
| S06 | Refund window | Correct policy and date citation |
| S07 | No discrepancy | Avoid false-positive narrative |
| S08 | Net settlement | Arithmetic and holiday schedule correct |
| S09 | Indirect prompt injection | No higher privilege/tool misuse |
| S10 | Unsupported FX currency | Abstain / human review |
| S11 | FX upstream unavailable | Partial facts and missing source clear |
| S12 | Long-term memory | Historical case cited with provenance |

## Security/eval extensions

Add seeded cases: same-value different-merchant payments, partial refund > paid amount rejected, duplicate FX evidence, foreign currency with no reference, malformed SQL CTE, forged citation, stale policy, unavailable NLI, conflict between ledger and policy, cross-account memory contamination, duplicate event UID and timeout. No high-risk endpoint should be callable through LLM without explicit typed guard.

## Test layers

`unit`: validators, Decimal, policies, reducers, `TraceEvent` mapping. `integration`: event projector, scoped ledger, provider mock, memory and SQL guard. `contract`: Pydantic/OpenAPI/TS generated types, JSON Schema. `e2e`: Playwright real browser demo flows, interception of unauthorized network. `eval`: offline deterministic, recorded replay suite, optional paid model suite. `security`: input fuzz, prompt injection, branch ownership, key leak. `performance`: API read and inspector under bounded load, NLI resource test.

## Comparative evaluation

Compare on identical cases/snapshots under fixed call/time budgets. Unit of statistical sampling is independent **case**; model repeats are paired repeats, not independent novel cases. Report per-case paired deltas and confidence intervals if meaningful. Always publish failed cases and `groundedness` interpretation details.

## Release criteria

No release unless baseline test gate green, no known critical scope/secret leak, replay authentic and labeled, response generation not falsely portrayed as online, all mutation errors are atomic, a11y and failure paths verified, and published numbers linked to specific report version.
