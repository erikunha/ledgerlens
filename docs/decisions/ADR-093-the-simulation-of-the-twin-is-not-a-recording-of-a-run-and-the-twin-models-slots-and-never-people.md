---
type: adr
status: accepted
date: 2026-11-24
---

# ADR-093: The simulation of the twin is not a recording of a run, and the twin models slots and never people

Status: accepted. Date: 2026-11-24.

## Context

The design package
[LL-V3-R17-04, operations digital twin simulation](../v3/advanced-specs/R17-04-operations-digital-twin-simulation.md)
proposes a twin of the operations: a modelled arrival process, a capacity of slots, a labelled condition of
the run and a paired comparison of two policies over one stream of arrivals. The repository can generate a
world of payments, project it deterministically and let a visitor change one field of a branch and read the
diff, but it cannot say how cases arrive, how many cases a team can carry at once, what a queue does when it
never drains, or what changes when a review policy changes.

The milestone of [specs/018](../../specs/018-r17-operations-digital-twin/spec.md) adds the twin, and the
question that shapes every decision of it is the difference between a measurement and a model: the arrival
distribution is a model and is labelled as one everywhere it appears, because the repository has no arrival
data and a count of arrivals presented as a measurement would be a false claim.

## Decision

**The manifest of a simulation is canonical and carries the digest of the truth, the provenance, the
assumptions, the digest of the arrival stream and the commit of the code, the twin models slots and never
people, and a run of the twin is never a bundle of the agent.**

1. **The manifest of a simulation is canonical.** It has no clock and no path of the machine, so two runs of
   the same configuration produce the same bytes on two machines. It carries the digest of the truth it was
   computed on, the provenance of the source, the assumptions of the model, the digest of the arrival stream,
   the commit of the code and the label of the run.
2. **The twin models slots and never people.** The repository has no people in it, and a number of people
   would be a claim the twin cannot support. The twin models a number of slots and a service time per case,
   and the report says "slots" and never "analysts".
3. **A run of the twin is never a bundle of the agent.** The two published catalogs hold the recordings of
   the agent and nothing else, and a run of the twin never goes into `data/eval/replay/` or into
   `data/eval/replay-real/`. The check of the export of the gate keeps passing after every task of the
   milestone.
4. **The arrival distribution is a model and is labelled as one.** The repository has no arrival data, so the
   twin takes the distribution as a parameter, writes it in the manifest, and never presents a count of
   arrivals as a measurement. The distribution of the shipped configuration is documented in
   [the page of the twin](../twin.md) with the reasoning.
5. **A run whose queue never drains carries the label and publishes no throughput.** The throughput of a run
   that never drained is a property of the horizon and not of the system, and a number that does not exist is
   never published as a number.
6. **A paired comparison reads one arrival stream.** The second run of a paired comparison reads the stored
   stream and refuses to generate another one, because a comparison over two streams measures the difference
   between the streams and not the difference between the policies.
7. **Every money figure of the twin is a `Decimal`.** The cost per case is an exact division, and it is
   undefined with a reason when the denominator is zero, because a cost of zero would say the case was free.

## Alternatives considered

- **To fit the arrival distribution over the cases of the repository.** Refused. The cases of the repository
  were not arrivals of a real operation, so a distribution fitted over them would be a distribution of
  nothing. The distribution is a parameter of the model, and it is labelled as one.
- **To model the capacity as a number of people.** Refused. The repository has no people in it, and a number
  of people would be a claim the twin cannot support. The twin models slots and a service time per case.
- **To publish the throughput of a run whose queue never drains.** Refused. The throughput of such a run is a
  property of the horizon and not of the system, and a number that does not exist is never published as a
  number.
- **To generate the arrival stream twice for a paired comparison.** Refused. A comparison over two streams
  measures the difference between the streams and not the difference between the policies, and the second run
  reads the stored stream and refuses to generate another one.
- **To write a run of the twin into the catalogs of the recordings.** Refused. The catalogs hold the
  recordings of the agent and nothing else, and a run of the twin is a simulation and not a recording.

## Consequences

- **The repository has the twin**, in `ledgerlens/sim/twin/`: the configuration (`config.py`), the arrival
  stream (`arrivals.py`), the manifest (`manifest.py`), the run (`run.py`), the queue (`queue.py`), the
  paired comparison (`compare.py`) and the report (`report.py`), with the tests in `tests/sim/twin/`.
- **The page of the twin is [the page of the twin](../twin.md)**, with the arrival distribution of the
  shipped configuration and the reasoning of it, the vocabulary of the twin, the meaning of every label of a
  run and the difference between a measurement and a model.
- **The check of the twin is in the gate**, with a run of the seed 42 over a short horizon, the comparison of
  the manifest against the expected bytes and the check that the two published catalogs are untouched.
- **The twin runs no model and touches no payment network**, and every figure it publishes is a number about
  the synthetic world it simulated, with the assumptions that produced it.

## Links

- [ADR-009, the public data first and the simulation for the gaps](ADR-009-public-data-first-simulation-for-gaps.md)
- [ADR-032, the state of the branch and the hash](ADR-032-the-state-of-the-branch-and-the-hash.md)
- [the page of the twin](../twin.md)
- [the specification of the milestone](../../specs/018-r17-operations-digital-twin/spec.md)
- [the design package](../v3/advanced-specs/R17-04-operations-digital-twin-simulation.md)
