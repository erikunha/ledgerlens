# LL-V3-R20-01 - Verified feedback to evaluation and training

**Status:** design proposed; not yet implemented. **Strategic lens:** Compounding and Proof of Work. **Audience:** ML engineer. **Dependencies:** R4 evaluation, R12 memory, R13 security.

## User outcome

Convert genuine discovered failure patterns into regression and, where warranted, improved specialized models.

## Ownership and compatibility

Keep evaluation truth separate from reviewer observations; dataset registry stores `gold/silver/unverified`, source hashes, permission and split.

## Typed interfaces and persisted state

`FeedbackRecord {run_id,claim_id,verdict,corrected_value,evidence_refs,reviewer_role,trust_tier}` and immutable `DatasetRevision` with train/validation/test hashes.

## Algorithm and execution contract

Collect failure, ask for evidence-backed correction, review labels, deduplicate, contamination-check, write versioned fixture, run current baseline, then optionally tune reranker/intent model and compare on untouched holdout.

## Security, invalid states and recovery

A visitor cannot poison shared model training set; public demo feedback remains sandbox-only unless maintainer-reviewed. Do not store real PII.

## Acceptance scenarios (Given / When / Then)

- Synthetic model-generated answer cannot become gold without review.
- Same source case cannot occur across train/test via alias.
- Worse holdout results prevent promotion.
- Archived experiment remains reproducible.

## Metrics, evidence and regression gates

Heldout performance, data leakage count, calibration and cost, negative outcomes explicitly preserved.

## Definition of done and rollback

Dataset cards and model cards with architecture, license, limitations and rollback; optional research module.

No claim of implementation is made by this spec. Shipped status requires passing exact executable tests, a source revision, a sanitized replay/trace, and known limitations in release notes.
