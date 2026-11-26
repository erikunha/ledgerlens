# Evaluation Science, Reliability and Reproducibility

## Source of truth and baseline

The current repo reports A/B/C correctness roughly 0.17/0.55/0.82 across 30 cases with three repetitions; C equivalent unordered trajectory around 0.73 vs goal 0.80. These are **repository-reported historical evaluations**, not results rerun for this v3 document. Current verification report also notes LangSmith 429 quota; don't claim current experiment traces are hosted if they aren't.

## Hierarchy of evaluation

1. Unit/domain: Decimal conversions, ledger invariants, SQL guard, date arithmetic, event projections.
2. Component: triage parser, policy retrieval, FX clients, memory isolation, verifier numeric rules.
3. Run: tool trajectory, output schema, coverage, citations, abstention, latency, cost.
4. Thread: clarification→follow-up, memory retrieval, case resolution or escalation.
5. System: concurrent sessions, partial outage, redaction, rate limits and reviewer workflows.
6. Operational/economic: cost per correct, queue pressure, false negative harm under documented assumptions.
7. Adversarial: prompt injection, memory poisoning, forged evidence, tool error, provider drift.
8. Human comprehension: can a third party reliably explain why the result is correct?

## Experimental rigor

Freeze dataset seed, split and hashes; compare paired runs on same branch, policy revisions and provider model version; keep holdout private from prompt optimization; declare sample size and uncertainty. Repeated tests at temperature 0 can still vary. Use deterministic checks for numerical facts, human-judged evaluation criteria for ambiguous outcomes, and calibrate any LLM judge for agreement and bias. Don't report untested regression fixes as measured improvements.

## Selective prediction

For each confidence/abstention threshold compute coverage, error-on-covered, false escalation, false auto-resolution, review count and cost. Show a risk-coverage plot and calibration (ECE/Brier score) only when the confidence score actually corresponds to an estimated probability and ground-truth events are labeled. Uncalibrated confidence displays as heuristic score, not '92% sure'.

## Failure taxonomy

`retrieval_miss`, `stale_policy`, `wrong_fx_date`, `wrong_arithmetic`, `unsupported_currency`, `sql_guard_reject`, `tool_timeout`, `tool_unavailable`, `memory_poison`, `cross_account_attempt`, `unsupported_claim`, `false_escalation`, `unsafe_non_escalation`, `budget_exceeded`, `malformed_tool`, `hallucinated_citation`, `provider_schema_drift`, `duplicate_event`, `user_interface_misleading`.

Each failure becomes: immutable failing case, minimal reproduction, expected oracle, mitigation, regression test, cost/latency impact and an explicit status. Avoid 'fixes' that merely reduce evaluation coverage.

## Advanced benchmark program

- Controlled A/B/C vs D/E with statistical uncertainty and case-level paired diffs.
- Retrieval ablation: FAISS/dense/BM25/hybrid/rerank at constant evidence budget.
- Verifier ablation: raw NLI, deterministic, combined; false positive/negative breakdown.
- Routing ablation: fixed model, dynamic router, cheap-first cascade.
- Multiagent ablation: supervisor, parallel, reviewer; overhead and out-of-budget failure.
- Security regression: agent tool misuse attack success rate under test-only sandbox.
- Temporal drift: policy version changes and previously valid answers.
- Human-facing explanation studies: task comprehension before/after trace visualization.

See `roadmap/RELEASE-TRAIN-2027-2030.md` for phase criteria. Evaluation metrics alone are not evidence of real business outcomes.
