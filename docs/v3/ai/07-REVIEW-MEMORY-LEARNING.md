# Human-AI Review, Feedback, Active Learning and ModelOps

## Review is an operational product, not a button

Review task carries: case snapshot, current claims/verdicts, missing evidence, risk class, proposed explanation/action, agent/tool versions, costs, prior approvals and reversible sandbox action. Reviewer chooses approve explanation, request evidence, correct factual field, mark model error, mark policy conflict, escalate further, or abstain. Every action is versioned and attributable to a simulated role; public users are not financial reviewers.

## Active learning loop

1. Route uncertain/novel/high-loss cases to feedback queue; avoid sampling only easy successes.
2. Collect reviewer feedback with independent source references.
3. Split labels into `gold_verified`, `silver_expert`, `model_generated_unverified`; never train treating the latter as truth without review.
4. Deduplicate, detect contamination and PII; version datasets and licenses.
5. Build adversarial/regression suite; benchmark current model.
6. Evaluate calibration, quality, cost and robustness; require holdout benefit.
7. Deploy behind experiment flag; compare paired runs and rollback.

## Model experimentation

Prompt optimization, few-shot selection, rerankers, retrieval tuning, NLI threshold calibration, model distillation, small specialized classifier, constrained fine-tuning and active sampling. Fine-tuning becomes a research capability only when data quality, licensing, privacy and independent improvement are verified. Never present feedback-based examples as 'continuous learning' when model weights are unchanged.

## Memory governance

Approved long-term memory changes require a durable source and scoped owner. Model-inferred facts remain hypotheses. Provide inspect, delete, reset, compare versions and poisoning simulation. Retained experiment replay must reference original memory snapshot, not silently current memory.

## Operations metrics

Reviewer minutes/case, queue age, SLA scenarios, agreement between reviewers, unsupported-case proportion, reviewer override reasons, misclassification cost under assumptions, model-quality gain from reviewed feedback, drift and leakage.
