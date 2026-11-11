# ADR-P006: Benchmark governance and evidence-rich negative results

**Status:** proposed. **Context:** current reports are useful but have small sample size; verifier has calibration/generalization gap; different metrics are easy to misuse for marketing.

**Decision:** publish exact provenance for every benchmark; separate deterministic assertions, judge scores, groundedness, trajectory and escalation. Report confidence intervals when justified, per-case failures and calibration sets separately; establish locked holdout and predeclared gates. Replay artifacts are not proof of statistically significant generalization.

**Alternatives:** cherry-picked hero cases or a single "accuracy" number (untrustworthy). **Consequence:** Evaluation Lab displays limitations prominently. **Rollback:** display original report with exact caveats until expanded evaluation is ready.
