# SPEC LL-R4-03 - Verifier calibration and benchmark integrity repair

**Status:** P0 metadata correctness / P1 expanded evaluation. **Context:** Repo sources do not currently present an internally consistent narrative for verifier sample counts and live generalization.

## Evidence from inspected repo

- `data/eval/verification_set.jsonl`: **43** nonblank records (observed via GitHub read).
- `data/eval/verification_live.jsonl`: **40** records.
- `data/eval/eval_cases.jsonl`: **30** agent evaluation records.
- `data/eval/report_online.json`: `verification.cases=43`, `accuracy=1.0` for the reported verification run.
- `ledgerlens/verify/thresholds.json`: embedded calibration metadata references `verification_set:30`, `verification_live:40`, `combined:0.786`, `verification_live:0.625`, `verification_set:1.0`.

The 43/30 discrepancy may arise from datasets updated after calibration; **do not infer cause until git history and benchmark code are investigated**. The 43-case report is not evidence of independent calibration generalization, especially if thresholds were tuned on related examples.

## Required correction

1. Define immutable `EvalDatasetManifest` with file SHA256, record count, source, labeling version, split role (`tuning`, `validation`, `held_out`), scenario seed and contamination policy.
2. Pin threshold selection to explicit tuning manifest hash, NLI model version and hyperparameter sweep log. Do not calculate accuracy against a moving file with same name.
3. Add independent held-out verification cases with different case templates/text/source structures. No threshold tuning against final holdout.
4. Recompute current calibration and case-level confusion matrices, preserving historical reports under versioned IDs. If original 30-case corpus unavailable, mark old report's exact dataset unrecoverable, do not invent historic numbers.
5. Update README, UI and JSON results with correct sample counts, confidence/uncertainty and protocol. Distinguish agent correctness from verifier classification accuracy.
6. Add CI check that stored `records_count == actual JSONL records` and `sha256 == file hash` for every referenced dataset. Missing/changed dataset fails the report build.

## Additional eval requirements

- Report negative controls where there is not enough evidence, contradiction and unsupported benign claims.
- Use at least paired case deltas for false-supported/false-contradicted and human-review rates.
- Calculate exact-money rules in code; NLI should not overrule deterministic contradictions.
- Show "which cases failed" and direct claim/evidence sample in Eval Lab.
- If NLI model isn't loaded, `verification_status=unavailable`; this is not a pass.

## Acceptance tests

- Given stale `thresholds.json` counts, report/build fails with explicit mismatch.
- Given 43-case current file, manifest accurately records 43 and exact checksum.
- Given locked holdout, threshold tuning scripts refuse to write/peek unless designated validation step.
- Given unsupported answer, it appears in per-case report even if aggregate correctness rises.
- Given model output unchanged but prompt parser changed, CI reports changed extraction/trajectory rather than silently rewriting past data.
- Public metrics no longer state "verifier 100% accurate" without naming dataset and restrictions.
