---
type: adr
status: accepted
date: 2026-11-25
---

# ADR-104: The routing reads the registry and the budget and never writes them, and the comparison of the routes is a hypothesis until it is measured

Status: accepted. Date: 2026-11-25.

## Context

ADR-078 decided that the model of each slot of a run is chosen by the task the slot does, ADR-083 decided that
the routing is measured against one model over the same cases, and ADR-084 and ADR-085 decided the fallback of
a run. The milestone of [specs/016](../../specs/016-r15-inference-routing-and-finops/spec.md) is the inference
routing and the cost of the run, and this record writes down the rules that bind the routing to the registry,
to the budget and to the live path, and the honesty of the numbers of the comparison.

## Decision

**The routing reads the registry and the budget and never writes them, the live path keeps one model, the
price of a model that was not verified is unknown and never zero, and the comparison of the routes is a
hypothesis until it is measured.**

### The routing reads the registry and the budget and never writes them

The router chooses the model of each slot over the candidates of the cascade, and the candidates come from the
registry of the providers. The router reads the registry and the budget of the run, and it never writes either:
the registry is the truth about the models, the budget is the truth about the money, and a router that wrote
them would be a router that decides with two truths.

### The live path keeps one model

A live run has exactly one model (ADR-037), and the four slots of the agent of the demo are the model of the
run. The routing does not touch the live mode of the visitor: the comparison of the routes is a measurement
over the cohort of the evaluation, and it is not a measurement of the live mode.

### A price that was not verified is unknown and never zero

The snapshot of a price carries the source and the day it was last verified, and a price that was never
verified has no amounts. A price of zero would say that the call was free, and a call is never free. A price
whose day is older than the freshness the caller declares is stale, and the snapshot says so.

### The comparison of the routes is a hypothesis until it is measured

The routing is a hypothesis about the money until the comparison measures it, and the comparison is published
with the set it was measured over. A number without its dataset is a claim about nothing in particular, and
the page of the routing carries the numbers of the measurement and the digest of the cohort.

## Consequences

- The router never accepts an address of a server that a visitor wrote, and a model a human chose is never
  silently replaced.
- The decision of the routing is written once and never changed, and the store of the decisions refuses a
  second write.
- The live run asks for one model in every request, and the trace names it for the four slots.
- The bundle of a routed run names the model of each slot next to the task it did.

## Links

- [the specification of the milestone](../../specs/016-r15-inference-routing-and-finops/spec.md)
- [ADR-078, the model of each slot is chosen by the work it does](ADR-078-the-model-of-each-slot-is-chosen-by-the-work-it-does.md)
- [ADR-083, the routing is measured against one model](ADR-083-the-routing-is-measured-against-one-model-over-the-same-cases-and-every-number-carries-its-set.md)
- [ADR-037, the case of the demo runs on a bridge over the caller](ADR-037-the-case-of-the-demo-runs-on-a-bridge-over-the-caller.md)
