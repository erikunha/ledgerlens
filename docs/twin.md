# The operations digital twin

The twin simulates the operations of a payment business over a modelled arrival process: how cases arrive,
how many cases a team can carry at once, what a queue does when it never drains, and what changes when a
review policy changes. The twin runs no model and touches no payment network. Every number it publishes is a
number about the synthetic world it simulated, and every figure carries the assumptions that produced it.

## A measurement and a model

The one thing the twin is careful about is the difference between a measurement and a model. The repository
has no arrival data, so the arrival distribution of the twin is a **model**, and it is labelled as one
everywhere it appears. A count of arrivals of the twin is never a measurement of a real operation.

## The arrival distribution of the shipped configuration

The shipped configuration of the twin uses exponential inter-arrival times with the rate of 6 cases per hour,
over a horizon of 480 minutes, with the mix of the kinds of the cases (a half of refunds, a third of
chargebacks, a sixth of fx questions). The distribution was chosen because the arrival of a case is the
arrival of a customer, and the exponential inter-arrival time is the standard model of such arrivals. It is a
model of the repository, and it is not a measurement of a real operation: the repository has no arrival data,
and ADR-009 keeps the public data for the parts that exist and the simulation for the gaps.

## The vocabulary of the twin

| Word | What it means |
| --- | --- |
| slot | A capacity of the operation. The twin models slots and never people, because the repository has no people in it. |
| service time | The time a slot takes to serve a case, in minutes. |
| arrival stream | The cases that arrive over the horizon, generated once from the seed and read by every run of a comparison. |
| review policy | Which kinds of the cases are escalated to a review. The policy `shipped` is the policy of the repository. |

## The labels of a run

A run of the twin is in one of two states, and the label of the run says which:

| Label | What it means |
| --- | --- |
| `steady_state` | The queue drained over the horizon, and the throughput of the run is a property of the system. |
| `queue_never_drains` | The arrivals outpace the service over the whole horizon, and the run publishes no throughput, because the throughput of such a run is a property of the horizon and not of the system. |

## The paired comparison

A paired comparison of two review policies reads one arrival stream, and the second run refuses to generate
another one, because a comparison over two streams measures the difference between the streams and not the
difference between the policies. The comparison names the cases whose decision changed, and the cost per case
of each policy is the work of the reviews it asked for over the cases of the stream, recomputed with
`Decimal`.

A comparison is a comparison inside a synthetic world. It is never a statement about a real operation.

## Links

- [the specification of the milestone](../specs/018-r17-operations-digital-twin/spec.md)
- [ADR-093, the simulation of the twin is not a recording of a run](decisions/ADR-093-the-simulation-of-the-twin-is-not-a-recording-of-a-run-and-the-twin-models-slots-and-never-people.md)
- [ADR-009, the public data first and the simulation for the gaps](decisions/ADR-009-public-data-first-simulation-for-gaps.md)
- [the package of the twin](../ledgerlens/sim/twin/)
