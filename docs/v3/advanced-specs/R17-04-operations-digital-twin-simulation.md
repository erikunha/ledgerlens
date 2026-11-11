# LL-V3-R17-04 - Operations digital twin simulation

**Status:** design proposed; not yet implemented. **Strategic lens:** Second-Order Thinking and Follow the Bottleneck. **Audience:** Financial-ops engineer. **Dependencies:** R2 sandbox, R9 economics, R10 queue.

## User outcome

Explore changing case arrival rates, merchant mix and policy exceptions without relying on bank production data.

## Ownership and compatibility

Reuse seeded event generator and immutable source while extending with simulated arrival, service, escalation and policy events; distinguish from historical UCI data and real service outcomes.

## Typed interfaces and persisted state

`SimulationConfig {seed,horizon,arrival_distribution,case_mix,provider_failure_rates,review_policy,staff_count}` and `SimulationManifest {truth_hash,source_provenance,assumptions}`.

## Algorithm and execution contract

Sample events deterministically from configured distributions; project ledger states and queues; run under paired policies using identical generated event streams; compare error exposure, throughput and per-case cost.

## Security, invalid states and recovery

Simulator never connects to external payment APIs. Assumption strength and scenario validity shown on every chart; no real-loss claims.

## Acceptance scenarios (Given / When / Then)

- Seed 42 yields same canonical manifest.
- Policy A/B uses identical arrival stream.
- Infinite queue detected and labeled.
- Invalid negative number of staff rejected.
- Event ordering stable after projector restart.

## Metrics, evidence and regression gates

Oracle consistency, replay reproducibility, workload/performance and user ability to interpret uncertainty.

## Definition of done and rollback

Distribution documentation, property tests, toy manual reference and bounded-run resource tests.

No claim of implementation is made by this spec. Shipped status requires passing exact executable tests, a source revision, a sanitized replay/trace, and known limitations in release notes.
