# LL-V3-R10-03 - Human review queue simulator

**Status:** design proposed; not yet implemented. **Strategic lens:** Follow the Bottleneck and Theory of Constraints. **Audience:** Support operations / engineer. **Dependencies:** R9 economics, R10 review model.

## User outcome

Demonstrate when verifying more claims helps trust but saturates limited human review capacity.

## Ownership and compatibility

Build discrete-event simulator in Python `ledgerlens/economics/queue.py`, not LLM-calculated waiting times. All defaults are fictional and marked as such.

## Typed interfaces and persisted state

`QueueExperiment {arrival_events, case_mix, reviewers, review_time_distribution, threshold, seed, horizon_minutes}` -> timestamped queue events plus utilization, throughput, backlog and waiting-time distribution.

## Algorithm and execution contract

Stable priority queue with events `(at, sequence, type)`; enqueue when case review flagged; serve as reviewer becomes free; predict overload when utilization >=1; track unfinished at horizon; use same seed to compare policies; optionally show Little’s Law only when stable assumptions hold.

## Security, invalid states and recovery

No visitor identity in queue model. Never interpret queue capacity as real customer staffing, or UI latency as analyst work time.

## Acceptance scenarios (Given / When / Then)

- Seed replay yields same reviewer scheduling.
- With zero reviewers, jobs queue without divide-by-zero.
- With overloaded system, no finite analytical steady-state wait reported.
- Prioritization cannot silently starve critical cases (track fairness).
- Different policies compare equal arrival distribution.

## Metrics, evidence and regression gates

Queue length vs time, wait p50/p95, throughput, reviewer utilization, false escalation, error rate and sensitivity.

## Definition of done and rollback

Property tests, hand-solvable toy fixtures, visual assumptions. Rollback via feature flag; no changes to production `InvestigationResult`.

No claim of implementation is made by this spec. Shipped status requires passing exact executable tests, a source revision, a sanitized replay/trace, and known limitations in release notes.
