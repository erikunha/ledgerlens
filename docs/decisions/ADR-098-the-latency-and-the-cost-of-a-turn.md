---
type: adr
status: accepted
date: 2026-11-24
---

# ADR-098: The latency and the cost of a turn

Status: accepted. Date: 2026-11-24.

## Context

[ADR-054](ADR-054-the-agent-loop-has-a-ceiling-in-every-path.md) gave the agent loop a ceiling in every path,
and it said that the value of `max_wall_seconds` would come back with the measurement of the latency of a
turn. The milestone of [specs/005](../../specs/005-r4-runtime-latency-and-cost-per-case/spec.md) is that
measurement, and this record is the coming back that ADR-054 asked for.

The measurement of the latency of the offline run is in `data/eval/report_latency.md`: over the 31 cases of
`eval_cases`, the p50 of the end to end of the plumbing of the turn is 10 milliseconds and the p95 is 30
milliseconds, by the nearest rank method, on the machine of the maintainer. The measurement is the latency of
the plumbing of the turn, because the model of the offline run is the scripted model, and the report says so.

The cost of the offline run is in `data/eval/report_cost.md`: the price of the model of the offline run is
unknown, and the report publishes no total, because an unknown price is unknown and never zero. The cost of
the human review of the run is 50 USD under the assumption of 10 minutes and 30 USD of an hour, and the
sensitivity of the review to the rate is published next to it.

## Decision

**The latency of a turn is published with the hardware, the denominator, the set and the role of the set, the
cost of a turn is published with the provenance of every price, an unknown price is unknown and never zero,
and the value of `max_wall_seconds` of the shipped paths stays 120 seconds until the measurement of the
latency with the provider says otherwise.**

1. **The latency of a turn is published with the hardware, the denominator, the set and the role of the
   set.** The percentile is the nearest rank, so the p50 and the p95 of a series are values of the series and
   never an interpolation, and the denominator is the count of the cases that produced a measurement. A
   latency over a tuning set is a tendency and not a generalization, and the report says so.
2. **The cost of a turn is published with the provenance of every price.** The price of the model of the
   offline run is unknown, and the report publishes no total: an unknown price is unknown and never zero. The
   cost of the human review is an assumption of the run, with the minutes and the rate as fields and the
   source named, and the sensitivity of the review to the rate is published next to it.
3. **A case that a cap cut is named as cut and not as a wrong answer.** The report of the evaluation names
   the cases a cap cut, because a case that was cut did not answer wrong, it was cut.
4. **The value of `max_wall_seconds` of the shipped paths stays 120 seconds.** The measurement of the offline
   run is the latency of the plumbing, and it cannot move the cap of the paths that talk to a provider. The
   measurement that moves the cap is the measurement of the latency with the provider, which runs by hand with
   a key, and the cap stays 120 seconds until that measurement says otherwise.

## Alternatives considered

- **To move the cap of the wall clock with the measurement of the offline run.** Refused. The offline run
  measures the plumbing of the turn with the scripted model, and a cap of the paths that talk to a provider
  moved by the plumbing would be a cap moved by a number that never saw a provider.
- **To publish the total of the run with the price of the model of the deployment.** Refused. The price of
  the model of the deployment is not the price of the offline run, and a total published with a price of
  another run is a total that means nothing.
- **To count a case that a cap cut as a wrong answer.** Refused. A case that was cut did not answer wrong,
  and counting it as wrong would publish a correctness that is worse than the correctness of the agent.

## Consequences

- **The latency of the turn is measured by `scripts/measure_latency.py`** and published in
  `data/eval/report_latency.md`, with the hardware, the denominator, the set and the role of the set.
- **The cost of the turn is measured by `scripts/measure_cost.py`** and published in
  `data/eval/report_cost.md`, with the provenance of every price, the missing pricing and the sensitivity of
  the review to the rate.
- **The guard of the numbers runs in the gate**: `tests/eval/test_runtime_numbers_documentation.py` refuses a
  published number of the latency or of the cost that does not name the set, the role, the denominator and
  the hardware.
- **The cap of the wall clock of the shipped paths is unchanged**, and the measurement that moves it is the
  measurement with the provider, by hand.

## Links

- [ADR-054, the agent loop has a ceiling in every path](ADR-054-the-agent-loop-has-a-ceiling-in-every-path.md)
- [the report of the latency](../../data/eval/report_latency.md)
- [the report of the cost](../../data/eval/report_cost.md)
- [the specification of the milestone](../../specs/005-r4-runtime-latency-and-cost-per-case/spec.md)
