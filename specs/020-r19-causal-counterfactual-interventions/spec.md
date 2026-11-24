# Feature Specification: Causal counterfactual interventions

**Feature Branch**: `feature/v3`

**Created**: 2026-11-23

**Status**: Draft

**Input**: Design documents: [R19-02, causal counterfactual interventions](../../docs/v3/advanced-specs/R19-02-causal-counterfactual-interventions.md),
[ADR-013, the public trace is a versioned contract](../../docs/decisions/ADR-013-public-trace-as-a-versioned-contract.md),
[ADR-028, the diff and the history are reads of the branch](../../docs/decisions/ADR-028-the-diff-and-the-history-are-reads.md),
[ADR-032, the state of the branch and the hash](../../docs/decisions/ADR-032-the-state-of-the-branch-and-the-hash.md),
[ADR-074, a case ends in a decision and the decision belongs to the code](../../docs/decisions/ADR-074-a-case-ends-in-a-decision-and-the-decision-belongs-to-the-code.md),
ADR-P007 ([one evidence-first agent by default](../../docs/v3/adrs/ADR-P007-no-multiagent-by-default.md)), ADR-P009
([the privacy scope of the public project](../../docs/v3/adrs/ADR-P009-privacy-scope.md)) and
[the release train, the R19 contract](../../docs/v3/roadmap/RELEASE-TRAIN-2027-2030.md). User description: "The
repository can change one field of a branch and read the diff. It cannot say whether a difference was caused by
the change or by something that moves with it, and it never says what would have happened if the reference rate
had been different. This specification adds declared interventions over a registry of structural functions, so
that a difference in a synthetic world can be traced to an intervention, and so that a link the registry does not
declare is reported as unknown."

## What exists today and what the package proposes

The package proposes a structural function registry over the rules of the exchange rate, of the policies, of the
settlement and of the review, a typed `Intervention` and a run that fixes the base seed and every exogenous event,
changes one field and recomputes the descendants along a declared graph. It is a design note of the frozen import
and none of it exists.

What the repository has is the mechanic without the model.

| What the package names | What the repository has | What is missing |
|---|---|---|
| the intervention changes one field and the descendants follow | the sandbox branch of `ledgerlens/sandbox/`: a typed mutation, an atomic commit, a deterministic projector and a diff that is a read under ADR-028 | the registry that says which node depends on which, and the difference between a diff and a cause |
| fix the base seed and the exogenous events | the generator of `ledgerlens/sim/`, with the seed 42 and the append-only log | the twin of the previous specification, with the arrival stream that a comparison reads twice |
| the result carries before and after facts, invariants and unsupported causal claims | the invariants of `ledgerlens/sandbox/invariants.py` and the money invariants of the projector | the report of the intervention, with the unsupported claims named |
| the structural functions over FX, policy, settlement and review | the code of `ledgerlens/sim/fx.py`, `ledgerlens/sim/pipeline.py`, `ledgerlens/sim/gaps.py`, `ledgerlens/sim/calendars.py`, `ledgerlens/tools/calculator.py` and `ledgerlens/verify/escalation.py` | the registry that declares the nodes and the edges over that code |
| no learned causality from observational correlations | the guard of the release train for R8: the link graph of the evidence is not a causal model | the guard as a rule of the code, and the sensitivity of the result to the assumptions |

Three adaptations the port makes.

1. **A diff is not a cause, and the registry is what tells them apart.** The sandbox already computes the
   difference between two states. The port keeps that difference and adds the declaration: a node that changes
   because of the intervention is a descendant in the registry, and a node that changes for a reason the registry
   does not declare is reported as `unknown`, with the reason. The package itself accepts this fallback, when it
   says that the rollback is a pure scenario diff.
2. **The intervention is inside the synthetic world and stays there.** The package says that an intervention must
   not be presented as a prediction of the outcome of a real merchant. The port makes that a rule of the result:
   every statement of the result says that it is a statement about the simulation, and the guard is a test that
   reads the report and refuses a sentence that claims a real outcome.
3. **The counterfactual is not the observation.** A rate that is observed to move with a policy is a correlation,
   and the evidence graph of the repository links a claim to its evidence without saying that one caused the other.
   The port keeps that separation: the registry declares the dependencies that the code actually implements, and a
   node that is not in the registry is never a descendant.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Change the reference rate and see what follows, and what does not (Priority: P1)

The engineer intervenes on the reference rate of a day and leaves everything else alone. The result says which
nodes are descendants of the reference rate in the registry, which of them changed, which of them did not change
even though a reader might expect them to, and it says that the applied rate of the past was not rewritten.

**Why this priority**: the whole difference between an observation and an intervention is that the intervention
changes one thing and the world answers. If the applied rates of the history move when the reference rate of the
day moves, the tool is rewriting the past and every comparison it makes is meaningless.

**Independent test**: run the intervention on the reference rate and assert that the applied rate of every
transaction of the ledger is the one it had before the intervention, and assert that the result names the
descendants that changed and the ones that did not.

### User Story 2 - Read a link the registry does not declare as unknown (Priority: P1)

The engineer intervenes on a merchant policy and a node changes that the registry does not connect to the
merchant policy. The result does not say that the intervention caused it. The result says `unknown`, names the node
and names the edge that is missing from the registry, and the report of the intervention carries the claim as an
unsupported causal claim.

**Why this priority**: the danger of a causal tool is a silent cause. A claim of a cause that the registry does not
support is exactly the claim a reader cannot check, and it is the claim that does the most damage.

**Independent test**: intervene on a node and assert that a node that changes without a declared edge is reported
as `unknown` with the missing edge named, and assert that the report lists it under the unsupported causal claims.

### User Story 3 - Compare two interventions over the same world (Priority: P1)

The engineer wants to know what a change of the policy and a change of the rate do together. The intervention that
changes two things is an explicit compound intervention, it names both targets, and it is run over the same base
seed and the same exogenous events as the two single interventions that it is compared against.

**Why this priority**: two changes at once look like a change of one thing, and a reader who sees one number for
two interventions cannot tell which one produced it.

**Independent test**: run the two single interventions and the compound one over the same base and assert that the
compound one names both targets, that the exogenous stream has the same digest in the three runs and that the
result of the compound one is not the sum of the two results.

### User Story 4 - See the money change exactly, or see that it did not change (Priority: P1)

The engineer intervenes on a rule that moves an amount. The result says which amount changed, from which value to
which value, computed with `Decimal`, and it says which amounts did not change. A result that says "the cost went
up" without the two values is not a result a reader can check.

**Why this priority**: the money of the repository is `Decimal` everywhere, and a causal report that publishes a
float or a direction without the two values breaks that discipline.

**Independent test**: run an intervention that moves an amount and assert that the two values are `Decimal`, that
the difference recomputed with `Decimal` is the published difference and that every amount that did not change is
named as unchanged.

### User Story 5 - Read that the answer depends on the assumption it rests on (Priority: P2)

The engineer runs the intervention with one assumption and then with another, for example with a different service
time, and reads how much the answer moves. The result carries the sensitivity of the answer to the assumptions it
names, and it says that the answer is a function of the assumption and not only of the intervention.

**Why this priority**: a counterfactual is only as good as the assumptions it rests on, and a reader who does not
see the sensitivity reads a number as a fact.

**Independent test**: run the same intervention under two assumptions and assert that the result carries the
sensitivity, and that the two results carry the assumption that produced them.

### User Story 6 - Read that the intervention is a statement about a simulation (Priority: P1)

The engineer reads the report of the intervention and sees, on every statement of cause, that it is a statement
about the simulated world and not about the outcome of a real merchant. The report never says what a merchant
would have received.

**Why this priority**: the package is explicit that the intervention must not be presented as a prediction of a
real outcome, and a reader of a public laboratory deserves the same discipline the repository applies everywhere
else.

**Independent test**: read the report of an intervention and assert that no sentence says what would have happened
to a real merchant, and assert that every sentence of cause names the simulation.

### Edge Cases

- An intervention on a node that the registry does not know: refused with the reason and the name of the node.
- An intervention whose value is not valid for the node, for example a negative capacity or a rate outside the
  interval of a rate: refused before anything is written.
- An intervention on a node with a date outside the horizon of the world: refused with the reason, because the
  world has no state for that date.
- An intervention that changes nothing: published with an empty list of changed nodes and the statement that the
  intervention had no effect inside the world.
- Two interventions on the same node in the same run: refused, because the compound intervention is the way to do
  that and it names both values.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The registry of the structural functions declares the nodes and the edges of the world of the
  repository over the exchange rate, the policies, the settlement and the review. A node that is not in the
  registry is never a descendant of anything.
  - Test: `tests/causal/test_registry.py` expects the nodes of the four families, expects every edge to name the
    two nodes it connects, and expects that a node outside the registry has no edge at all.
- **FR-002**: An intervention is a typed record with the branch, the target, the value, the assumptions, the
  dependent nodes and the digest of the exogenous stream of the world. An intervention on an unknown node, on a
  node with an invalid value or on a date outside the horizon is refused with a readable reason before anything is
  written.
  - Test: `tests/causal/test_intervention.py` expects the three refusals, the name of the field that is wrong and an
    output directory that holds no result.
- **FR-003**: The run of an intervention fixes the base seed and the exogenous stream, changes the one field of the
  target and recomputes the descendants along the edges of the registry.
  - Test: `tests/causal/test_engine.py` expects that the digest of the exogenous stream of two runs over the same
    base is the same, and that the changed nodes are the descendants of the target in the registry.
- **FR-004**: A node that changes without a declared edge is reported as `unknown`, with the missing edge named,
    and it is listed as an unsupported causal claim.
  - Test: `tests/causal/test_unknown_links.py` expects the status `unknown`, the name of the missing edge and the
    claim in the list of the unsupported causal claims.
- **FR-005**: An intervention on the reference rate does not rewrite the applied rate of the history. The applied
    rate of every transaction of the ledger is the one it had before the intervention.
  - Test: `tests/causal/test_engine.py` expects every applied rate of the ledger to be unchanged after the
    intervention.
- **FR-006**: An intervention on a merchant policy changes only the periods that the policy covers, and the
  result names the periods it covered.
  - Test: `tests/causal/test_engine.py` expects the named periods and expects every changed node outside those
    periods to be unchanged.
- **FR-007**: The money of the result is a `Decimal` and the difference between the two values recomputed with
  `Decimal` is the published difference. A result that names a direction names the two values.
  - Test: `tests/causal/test_report.py` expects the two values, the difference and the `Decimal` type, and expects
    the list of the amounts that did not change.
- **FR-008**: A compound intervention names both of its targets and is a separate record from a single one. The
    result of a compound intervention is not the sum of the results of its two targets.
  - Test: `tests/causal/test_compound.py` expects both targets in the record and expects the result of the
    compound to differ from the sum of the two single results.
- **FR-009**: The result of an intervention carries the assumptions it rests on, and the sensitivity of the result
  to the assumptions it names.
  - Test: `tests/causal/test_sensitivity.py` expects the assumptions and the sensitivity, and expects the two
    results under two assumptions to carry the assumption that produced them.
- **FR-010**: Every statement of cause of the report says that it is a statement about the simulation. No sentence
    of the report says what a real merchant would have received.
  - Test: `tests/causal/test_report.py` reads the report and expects that no sentence claims a real outcome and
    that every sentence of cause names the simulation.
- **FR-011**: The invariants of the world hold after the intervention. An intervention that breaks an invariant is
    refused and the world is left as it was.
  - Test: `tests/causal/test_invariants.py` expects the refusal for an intervention that breaks a money invariant
    and expects the state of the world to be the one before the intervention.
- **FR-012**: The intervention does not write to the ledger of the repository and does not touch the published
    catalogs. The result is a record of a simulation and not a bundle of the agent.
  - Test: `tests/causal/test_not_a_replay_bundle.py` expects that the run writes nothing under `data/eval/replay/`
    and nothing under `data/eval/replay-real/`, and that the export of the site still passes its check.

### Key Entities

- **Registry of the structural functions**: the declaration of the nodes of the world and of the edges between
  them, with the reason of each edge and the function that implements it.
- **Node**: one quantity or one rule of the world: a reference rate of a day, an applied rate, a policy of a
  merchant, a settlement, an escalation.
- **Intervention**: the typed record of the target, the value, the assumptions, the dependent nodes and the digest
  of the exogenous stream.
- **Descendant**: a node that the registry declares to depend on the target of the intervention.
- **Unknown**: the status of a node that changed and that the registry does not connect to the target. It is not a
  cause and it is never presented as one.
- **Unsupported causal claim**: the named statement of the report that a change was caused by the intervention
  while the registry does not support it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The registry names the nodes of the four families and every edge names the two nodes it connects.
- **SC-002**: The three invalid interventions are refused with the name of the field that is wrong and write
  nothing.
- **SC-003**: Two runs over the same base carry the same digest of the exogenous stream, and the changed nodes are
  the descendants of the target in the registry.
- **SC-004**: A node that changes without a declared edge is reported as `unknown` and is listed as an
  unsupported causal claim.
- **SC-005**: An intervention on the reference rate leaves every applied rate of the ledger unchanged.
- **SC-006**: The money of the result is a `Decimal` and every difference recomputes exactly.
- **SC-007**: The compound intervention names both targets and its result is not the sum of the two single
  results.
- **SC-008**: The result carries its assumptions and the sensitivity to them.
- **SC-009**: No sentence of the report says what a real merchant would have received, and every sentence of cause
  names the simulation.
- **SC-010**: The run writes nothing under the two published catalogs and the export of the site still passes its
  check.
- **SC-011**: The whole suite runs offline with `LEDGERLENS_OFFLINE=1`, with no key and no network.

## Assumptions

- The registry declares the dependencies that the code of the repository already implements. It does not declare a
  dependency that the code does not have, and it is not a model of the payment business of the world.
- The world is the synthetic world of the simulator and of the twin. An intervention is a statement about it and not
  about a merchant of the ledger of the corpus.
- The exogenous stream of a run is the arrival stream of the twin of the specification of the twin. That
  specification is not built yet, so this one waits for it for the parts that need the stream and works with the
  seed of the generator for the rest.
- The sensitivity of a result is computed by running the intervention under a second assumption. It is a
  measurement of the sensitivity and not an interval of confidence.
- The identification of a cause is a property of the registry and not of the data. No result of this specification
  learns a cause from an observation.
- Nothing in this specification is built yet.

## Out of scope

- The learning of a causal model from the data. The registry is written by hand and the code is the source of the
  edges.
- The publication of an intervention in the site. The result is a record of a simulation.
- The extraction of documents, which is the specification that follows the twin, and the feedback loop, which is
  the specification that follows the extraction.
- Any claim about a real merchant, a real bank or a real policy of the world.

## Design documents

- [R19-02, causal counterfactual interventions](../../docs/v3/advanced-specs/R19-02-causal-counterfactual-interventions.md)
- [ADR-013, the public trace is a versioned contract](../../docs/decisions/ADR-013-public-trace-as-a-versioned-contract.md)
- [ADR-028, the diff and the history are reads of the branch](../../docs/decisions/ADR-028-the-diff-and-the-history-are-reads.md)
- [ADR-032, the state of the branch and the hash](../../docs/decisions/ADR-032-the-state-of-the-branch-and-the-hash.md)
- [ADR-074, a case ends in a decision and the decision belongs to the code](../../docs/decisions/ADR-074-a-case-ends-in-a-decision-and-the-decision-belongs-to-the-code.md)
- [ADR-P007, one evidence-first agent by default](../../docs/v3/adrs/ADR-P007-no-multiagent-by-default.md)
- [ADR-P009, the privacy scope of the public project](../../docs/v3/adrs/ADR-P009-privacy-scope.md)
- [the release train, the R19 contract](../../docs/v3/roadmap/RELEASE-TRAIN-2027-2030.md)
- [the implementation plan of this specification](plan.md) and [its tasks](tasks.md)

## Status

Nothing in this specification is built. The repository holds the sandbox that computes a difference between two
states, the generator that produces the world and the invariants that a state must keep, and it holds none of the
registry, of the intervention, of the engine and of the report.

The decision this specification needs is written down before the first task: the registry is the only source of a
dependency, a change without a declared edge is unknown, and a result never speaks about a real outcome. That
record is the next free number of `docs/decisions/` (ADR-081 at the time of writing; check
[the index of the decisions](../../docs/decisions/README.md) before creating the file). It does not change any
accepted record.
