# LL-V3-R9-03 - Cost per correctly resolved case

**Status:** design proposed; not yet implemented. **Strategic lens:** Follow the Money and Opportunity Cost. **Audience:** Ops leader and platform engineer. **Dependencies:** R4 paired evaluations and R8 evidence.

## User outcome

Compare architecture costs using comparable cases, exact units and explicit assumptions rather than token-count vanity.

## Ownership and compatibility

Create Python `ledgerlens/economics` module using Decimal, independent from agent generation. Frontend can change assumptions but cannot compute authoritative totals.

## Typed interfaces and persisted state

Input proposed `economic-run` v3; backend accepts per-case observed costs, simulator assumptions, case correctness oracle, run IDs, same-cohort markers. Output includes undefined `cost_per_correct` when denominator=0, provenance and flags.

## Algorithm and execution contract

Use `model+compute+review+error_assumption` per case; sum only non-overlapping categories. Normalize to USD with dated rate if currencies differ. Compare A vs B only when same cases, snapshot and evaluation criteria. Compute `Σcost / Σcorrect`; report total coverage, missing pricing, range and reason.

## Security, invalid states and recovery

A public user can enter assumptions only for their own ephemeral experiment. Never label synthetic loss as real. No floating point money.

## Acceptance scenarios (Given / When / Then)

- Given zero correct cases, when computing, then cost per correct is null with explanation.
- Given unknown provider price, then USD total is not reported as measured.
- Given unequal case cohorts, comparison is blocked.
- Given duplicate loss classification, invariant flags double counting.

## Metrics, evidence and regression gates

Accuracy against hand-checked Decimal fixtures; denominator/units/provenance visible; sensitivity to review rate and model price.

## Definition of done and rollback

Include deterministic economics unit suite, UI disclosure for assumptions, downloadable exact manifest; rollback panel, preserve manifests.

No claim of implementation is made by this spec. Shipped status requires passing exact executable tests, a source revision, a sanitized replay/trace, and known limitations in release notes.
