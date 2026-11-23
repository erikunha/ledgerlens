# LL-V3-R9-06 - Risk weighted decision utility

**Status:** design proposed; not yet implemented. **Strategic lens:** Follow the Incentives and Second-Order Thinking. **Audience:** AI safety researcher. **Dependencies:** R9 cost engine + R10 review tasks.

## User outcome

Explore when faster/cheaper agents produce worse outcomes due to false decisions under loss asymmetry.

## Ownership and compatibility

Python economics model consumes confusion-matrix-like typed labels and hypothetical impact values; no actual payment movement.

## Typed interfaces and persisted state

Inputs: confusion counts by class, `P(error|cohort)` if calibrated, per-class loss in Decimal USD, reviewer time, abstention. Outputs: expected risk cost, uncertainty ranges, risk-coverage curve and scenario assumptions.

## Algorithm and execution contract

For mutually exclusive error classes compute expected loss; if overlaps, first partition or annotate. Compare auto resolution, review and abstention under same case mix and capacities. Distinguish subjective policy risk weights from observed event rates.

## Security, invalid states and recovery

Visitor cannot coerce production payouts; no normative regulatory recommendation; expose uncertainty and missing probabilities.

## Acceptance scenarios (Given / When / Then)

- Overlapping error categories flagged before summation.
- Uncalibrated confidence cannot be interpreted as probability.
- Unknown impact produces unknown expected loss.
- False accept and false reject appear separately.

## Metrics, evidence and regression gates

Risk-coverage, calibration if inputs valid, review minutes, quality and expected utility under assumptions.

## Definition of done and rollback

Unit tests including overlap/unknown, benchmark report with caveats; no magic ROI claims.

No claim of implementation is made by this spec. Shipped status requires passing exact executable tests, a source revision, a sanitized replay/trace, and known limitations in release notes.
