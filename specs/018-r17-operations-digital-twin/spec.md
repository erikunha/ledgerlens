# Feature Specification: Operations digital twin

**Feature Branch**: `feature/v3`

**Created**: 2026-11-23

**Status**: Draft

**Input**: Design documents: [R17-04, operations digital twin simulation](../../docs/design/advanced-specs/R17-04-operations-digital-twin-simulation.md),
[ADR-009, public data first and simulation only for the gaps](../../docs/decisions/ADR-009-public-data-first-simulation-for-gaps.md),
[ADR-018, the branch layer and the store interface](../../docs/decisions/ADR-018-branch-layer-and-store-interface.md),
[ADR-021, a typed mutation and an atomic commit](../../docs/decisions/ADR-021-typed-mutation-and-atomic-commit.md),
[ADR-022, the reset and the staleness](../../docs/decisions/ADR-022-reset-and-staleness.md),
[ADR-032, the state of the branch and the hash](../../docs/decisions/ADR-032-the-state-of-the-branch-and-the-hash.md),
[ADR-073, the published bundle carries the evidence its verdict was computed on](../../docs/decisions/ADR-073-the-published-bundle-carries-the-evidence-its-verdict-was-computed-on-and-it-is-reproducible.md),
[ADR-075, the site publishes two catalogs](../../docs/decisions/ADR-075-the-site-publishes-two-catalogs-and-each-bundle-declares-the-one-it-belongs-to.md),
[ADR-P007, one evidence-first agent by default](../../docs/design/adrs/ADR-P007-no-multiagent-by-default.md),
[ADR-P009, the privacy scope of the public project](../../docs/design/adrs/ADR-P009-privacy-scope.md) and
[the release train, the R17 contract](../../docs/design/roadmap/RELEASE-TRAIN-2027-2030.md). User description: "The
repository has a seeded generator of payments, a deterministic projector and an event-sourced sandbox for the
visitor. It has no model of how cases arrive, how many analysts there are, how a queue behaves when it never
drains, and no way to compare two policies over the same arrivals. The twin adds that, and every number it
publishes says which world it measured."

## What exists today and what the package proposes

The package of the frozen import is a design note, not an implementation, and it was written for a greenfield
plan. It says: reuse the seeded event generator and the immutable source, extend them with simulated arrival,
service, escalation and policy events, and compare two policies over an identical generated event stream.

Most of the generator it wants to reuse already exists in the repository.

| What the package names | What the repository has | What is missing |
|---|---|---|
| seeded event generator | `ledgerlens/sim/config.py` with `SimConfig.seed` defaulting to 42, `ledgerlens/sim/events.py` with an append-only event log, `ledgerlens/sim/projector.py` with the deterministic projector, and `ledgerlens/sim/scenarios.py` with twelve planted scenarios whose truth lives in `data/scenarios.json` | the arrival process, the service and capacity model, the escalation events and the policy events |
| immutable source | the public data of `data/`, the committed sample and the lock of `data/sources.lock.json`, under ADR-009 | nothing, this part is already in force |
| compare under paired policies | the sandbox branch layer of `ledgerlens/sandbox/` gives a typed mutation, an atomic commit and a diff that is a read | the pairing of two policies over one arrival stream and the comparison of the outcomes |
| `SimulationManifest {truth_hash, source_provenance, assumptions}` | the bundle manifest of `ledgerlens/replay/bundle.py` already carries the sha256 of every file, the commit of the code and the digest of the snapshot | a manifest for a simulation, which is not a recording of a run |

Three things the package assumes do not exist and this specification does not pretend otherwise.

1. **There is no review queue and no staff.** The package puts `staff_count` and `review_policy` in the
   configuration of the twin. The repository has no queue of cases awaiting a decision and no model of a person.
   The twin therefore models a capacity, a count of slots, and it names the slots, and it never says that a human
   took a case. The decision a case waits for is the one the verifier computes today in
   `ledgerlens/verify/escalation.py`.
2. **There is no arrival process.** The generator of `ledgerlens/sim/` produces the events of the ledger, and the
   number of cases is fixed by the scenario. The twin adds the arrival of the cases as a modelled process with a
   declared distribution.
3. **The twin is not a recording.** A run of the twin is a simulation, not a run of the agent. It is not a bundle
   of the replay, it does not go into `data/eval/replay/` and it does not go into `data/eval/replay-real/`. The two
   published catalogs keep the bundles of the agent and of nothing else. A twin run that is published is published
   as a simulation artifact, with the same digest discipline as the catalogs and never as a bundle of the agent.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run the twin twice and get the same world (Priority: P1)

The engineer configures a horizon of ninety days, an arrival distribution, a mix of merchants and a capacity of six
slots, and runs the twin with the seed 42. The run produces a canonical manifest: the same bytes, the same hash of
the truth, the same provenance and the same assumptions as the run before it. A second run on another machine, with
another version of the dictionary of the generator, produces the same manifest.

**Why this priority**: the whole value of the twin is that a reader can rerun it and see the same world. A twin
whose manifest changes between two runs is a story, not a tool, and every comparison it produces is a comparison of
two different worlds.

**Independent test**: run the twin twice with the seed 42 into two directories and compare the bytes of the
canonical manifest of the two runs. Run it a third time with a different hash seed of the interpreter and compare
again. The three manifests are byte for byte equal.

### User Story 2 - Compare two policies over one stream of arrivals (Priority: P1)

The engineer wants to know what changes if the review policy escalates a different set of cases. The twin runs the
two policies over the same generated stream of arrivals: the stream of the base run is written once, and the second
run reads it instead of generating a second one. The comparison names the cases that changed, the money that
changed, the number of cases that reached the capacity and the cost per case, and every money figure is computed
with `Decimal`.

**Why this priority**: the comparison of two policies is the reason the twin exists. Two runs with two streams
compare two different worlds, and the difference they show belongs to the randomness of the arrivals and not to the
policy.

**Independent test**: run the twin twice with two different review policies over one stored arrival stream, and
assert that the digest of the stream is the one the second run recorded and not a new one. Assert that the
comparison names at least one case whose decision changed, and recompute the cost per case of the comparison with
`Decimal` and expect the number the comparison published.

### User Story 3 - Read a queue that never drains as a label, not as a number (Priority: P1)

The engineer raises the arrival rate until the capacity of the slots is too small. The twin detects that the queue
of the pending cases does not drain inside the horizon, labels the run `queue_never_drains`, and refuses to publish
the throughput of the run as a number of cases served per day, because that number would describe a run that never
reached a steady state.

**Why this priority**: the throughput of a run that never drained is not a measurement, it is an artifact of the
horizon. Publishing it as a number would put a false measurement in the same place as the real ones.

**Independent test**: configure a capacity of one slot and an arrival rate that exceeds the service rate, run the
twin, and assert that the manifest carries the label `queue_never_drains` and that the throughput field of the
comparison is absent and not zero.

### User Story 4 - Be refused a configuration that cannot be simulated (Priority: P1)

The engineer writes a configuration with a negative number of slots, a horizon of zero days, an arrival rate that is
not a rate, or a mix of merchants that names a merchant that does not exist. The twin refuses the configuration with
a readable reason and a non zero exit code, and it refuses before it writes anything.

**Why this priority**: a twin that accepts a negative capacity produces a run that looks like a measurement and
means nothing. The refusal is the same discipline the rest of the repository uses: refuse with a reason, not with a
traceback.

**Independent test**: pass each one of the four invalid configurations and assert that the run exits with a non zero
code, that the message names the field that is wrong, and that the output directory holds no manifest.

### User Story 5 - Read what the twin assumes next to every number (Priority: P2)

The engineer reads the manifest of a run and sees the distribution of the arrivals, the capacity, the mix of the
merchants, the failure rate of the provider that was assumed, and the source of every one of them. Every chart of
the comparison carries the assumptions of the run that produced it, and no chart says a number that is about real
payment operations.

**Why this priority**: the assumptions are the model. A number without the assumption that produced it invites a
reader to believe that the twin measured something about the world.

**Independent test**: read the manifest of a run and assert that it carries the assumptions of the configuration, the
provenance of the source and the digest of the truth. Read the report of a comparison and assert that every figure
carries the reference to the run it came from, and assert that no sentence of the report describes the result as a
measurement of real operations.

### User Story 6 - Keep the order of the events after the projector restarts (Priority: P2)

The engineer stops the projector in the middle of a run and starts it again over the same log. The events that the
projector reads after the restart are the same events, in the same order, with the same ids, and the state of the
projected tables is the same as the state before the stop.

**Why this priority**: a twin whose state depends on when the projector was restarted cannot be compared with
another twin, because the reader does not know which of the two worlds they are looking at.

**Independent test**: build a run, project it, take the digest of the projected tables, rebuild the projector over
the same log and assert that the digest of the tables is the one before and that the order of the ids of the events
is the same.

### Edge Cases

- A horizon shorter than the time a case takes to be served: the run is labelled `queue_never_drains` and the
  comparison publishes no throughput.
- A capacity of zero slots: refused, because a run with no slot is not a simulation.
- A provider failure rate of one: every case of the run fails, the run is still published, and the comparison says
  that the failure rate is an assumption and not a measurement of a provider.
- A merchant of the mix that has no cases in the ledger: the mix is refused with the name of the merchant, because a
  mix that names nothing measures nothing.
- A run of the twin that produced no case at all: published with the count of zero and with the label that says the
  arrival distribution produced nothing, never as a success.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The configuration of the twin is a typed record with a seed, a horizon, an arrival distribution, a mix
  of merchants, a failure rate of the provider, a review policy and a capacity of slots. A configuration that names
  a negative capacity, a horizon of zero, a rate outside the interval of a rate, a merchant that is not in the
  ledger or an unknown field is refused with a readable reason before anything is written.
  - Test: `tests/sim/twin/test_config.py` expects the refusal of each invalid configuration, the name of the
    field in the message, and an output directory that holds no manifest.
- **FR-002**: The run of the twin is deterministic in the seed. Two runs of the same configuration produce a
  canonical manifest with the same bytes, the same hash of the truth, the same provenance and the same assumptions.
  - Test: `tests/sim/twin/test_determinism.py` runs the twin three times, twice with a different hash seed of the
    interpreter, and expects the three manifests to be byte for byte equal.
- **FR-003**: The manifest of a run carries the digest of the truth it was computed on, the provenance of the
  source, the assumptions of the configuration and the commit of the code that produced it.
  - Test: `tests/sim/twin/test_manifest.py` reads the manifest of a run and expects the four fields, and expects the
    digest of the truth to change when the truth changes.
- **FR-004**: The manifest is canonical. The bytes of the manifest of a run do not depend on the order of the keys,
    on the path of the machine that wrote it or on the clock.
  - Test: `tests/sim/twin/test_manifest.py` writes the same manifest twice with the keys in a different order and
    expects the same bytes, and expects the bytes to hold no path of the machine and no timestamp.
- **FR-005**: The arrivals are a modelled process with a declared distribution, sampled from the seed of the run.
  The stream of the arrivals is written once and its digest is recorded in the manifest.
  - Test: `tests/sim/twin/test_arrivals.py` expects the count of the arrivals to follow the declared distribution
    over a long horizon, and expects the digest of the stream to be recorded in the manifest.
- **FR-006**: A paired comparison runs two policies over one arrival stream. The second run reads the stream of the
  first and does not generate another one, and the comparison names the cases whose decision changed.
  - Test: `tests/sim/twin/test_paired_comparison.py` expects the digest of the stream of the second run to be the one
    of the first, and expects the comparison to name at least one changed case.
- **FR-007**: Every money figure of a run and of a comparison is computed with `Decimal`, and the cost per case is
  the exact division of the total by the number of the cases, and it is undefined with a reason when the
  denominator is zero.
  - Test: `tests/sim/twin/test_paired_comparison.py` recomputes the cost per case with `Decimal` and expects the
    number the comparison published, and expects the reason when the denominator is zero.
- **FR-008**: A queue that does not drain inside the horizon is labelled `queue_never_drains`, and the throughput of
  the run is not published as a number.
  - Test: `tests/sim/twin/test_queue.py` expects the label and the absence of the throughput for a capacity that is
    too small, and expects a throughput number for a capacity that is large enough.
- **FR-009**: The order of the events of a run does not depend on when the projector was restarted. The digest of
  the projected tables after a rebuild is the digest before the rebuild.
  - Test: `tests/sim/twin/test_projector_restart.py` projects a run, rebuilds the projector over the same log and
    expects the same digest of the tables and the same order of the ids of the events.
- **FR-010**: The twin never connects to a payment API and never performs a financial write. Every number it
    produces comes from the simulator, from the committed ledger and from the declared assumptions.
  - Test: `tests/sim/twin/test_no_external_calls.py` runs the twin with the network disabled and expects the run to
    finish, and expects no module of `ledgerlens/sim/twin/` to import `ledgerlens.api`.
- **FR-011**: The report of a comparison carries the assumptions of the run that produced it next to every figure,
    and no sentence of the report describes the result as a measurement of real payment operations.
  - Test: `tests/sim/twin/test_report.py` reads the report and expects the reference to the run next to every
    figure, and expects that the report holds no sentence that claims a saving or a loss in a real operation.
- **FR-012**: A run of the twin is not a bundle of the agent. It does not go into `data/eval/replay/` and it does
    not go into `data/eval/replay-real/`, and the two published catalogs keep only the recordings of the agent.
  - Test: `tests/sim/twin/test_not_a_replay_bundle.py` expects the twin to write no directory under
    `data/eval/replay/` and none under `data/eval/replay-real/`, and expects the catalogs of the site to be
    unchanged by a run.
- **FR-013**: The twin reads the ledger through the read-only surface of the domain and never speaks SQL of its
    own in the domain layer.
  - Test: `tests/sim/twin/test_domain_boundary.py` reads the modules of `ledgerlens/sim/twin/` with `ast` and
    expects no module to import `ledgerlens.api` and no module to carry a SQL string.

### Key Entities

- **Configuration of the twin**: the typed record of the seed, the horizon, the arrival distribution, the mix of the
  merchants, the failure rate of the provider, the review policy and the capacity of the slots.
- **Arrival stream**: the ordered list of the cases that arrived inside the horizon, generated once from the seed
  and read by every run of a paired comparison.
- **Manifest of a run**: the canonical record of the digest of the truth, the provenance of the source, the
  assumptions, the digest of the arrival stream, the commit of the code and the labels of the run.
- **Label of the run**: the named condition of the run, for example `queue_never_drains` or `steady_state`. A run
  without a label is a run whose condition was not determined, and it is not published.
- **Paired comparison**: the difference between two runs over one arrival stream, with the cases that changed, the
  money that changed and the assumptions of both runs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The manifest of two runs of the same configuration with the seed 42 is byte for byte equal, and the
  third run with a different hash seed of the interpreter is equal to the two.
- **SC-002**: The manifest of a run carries the digest of the truth, the provenance of the source, the assumptions
  and the commit of the code.
- **SC-003**: A paired comparison reads one arrival stream, and the digest of the stream of the second run is the
  digest of the first.
- **SC-004**: Every money figure of a comparison is recomputable with `Decimal`, and the cost per case of a run
  with no case is undefined with a reason.
- **SC-005**: A run whose queue does not drain carries the label `queue_never_drains` and publishes no throughput.
- **SC-006**: An invalid configuration is refused before anything is written, with the name of the field that is
  wrong.
- **SC-007**: The projected tables of a run are the same after a rebuild of the projector, and the order of the ids
  of the events is the same.
- **SC-008**: The twin runs with the network disabled, and no module of the twin imports `ledgerlens.api` and none
  carries a SQL string.
- **SC-009**: A run of the twin leaves `data/eval/replay/` and `data/eval/replay-real/` untouched, and the export of
  the site still passes its check.
- **SC-010**: The report of a comparison carries the assumptions next to every figure and holds no claim about a
  real operation.

## Assumptions

- The generator of `ledgerlens/sim/` is the base of the twin, and its seed of 42 and its twelve planted scenarios
  stay as they are. The twin extends the generator and does not rewrite it.
- The capacity of the slots is a number of slots and not a number of people. The twin has no model of a human and
  makes no statement about a reviewer.
- The review policy of the twin is the escalation that `ledgerlens/verify/escalation.py` computes today. The twin
  does not add a second escalation.
- The arrival distribution is a model, not a measurement. The repository has no arrival data, and ADR-009 keeps the
  public data for the gaps and the simulation for what does not exist. The arrival of the cases is one of those
  gaps.
- The failure rate of the provider is an assumption of the run and never a measurement of a provider.
- The comparison of two policies is a comparison inside the synthetic world of the twin. It is not a statement about
  the merchants of the ledger and not a claim about a saving.
- The twin is new work. Nothing in this specification is built yet.

## Out of scope

- The learning of a model, the routing of a model and the multiagent topology. ADR-P007 keeps the runtime a single
  agent with a deterministic verifier, and the twin runs no model at all.
- The queue of the live mode. The twin simulates a capacity and does not schedule the work of a person.
- The extraction of documents and the causal interventions, which are the specifications of the folders that follow.
- The publication of a twin run in the site. The twin publishes its manifest and its report, and the publication of
  an artifact is the work of the proof-of-work export.
- The rewrite of the generator, of the projector and of the sandbox.

## Design documents

- [R17-04, operations digital twin simulation](../../docs/design/advanced-specs/R17-04-operations-digital-twin-simulation.md)
- [ADR-009, public data first and simulation only for the gaps](../../docs/decisions/ADR-009-public-data-first-simulation-for-gaps.md)
- [ADR-018, the branch layer and the store interface](../../docs/decisions/ADR-018-branch-layer-and-store-interface.md)
- [ADR-021, a typed mutation and an atomic commit](../../docs/decisions/ADR-021-typed-mutation-and-atomic-commit.md)
- [ADR-022, the reset and the staleness](../../docs/decisions/ADR-022-reset-and-staleness.md)
- [ADR-032, the state of the branch and the hash](../../docs/decisions/ADR-032-the-state-of-the-branch-and-the-hash.md)
- [ADR-073, the published bundle carries the evidence its verdict was computed on](../../docs/decisions/ADR-073-the-published-bundle-carries-the-evidence-its-verdict-was-computed-on-and-it-is-reproducible.md)
- [ADR-075, the site publishes two catalogs](../../docs/decisions/ADR-075-the-site-publishes-two-catalogs-and-each-bundle-declares-the-one-it-belongs-to.md)
- [ADR-P007, one evidence-first agent by default](../../docs/design/adrs/ADR-P007-no-multiagent-by-default.md)
- [ADR-P009, the privacy scope of the public project](../../docs/design/adrs/ADR-P009-privacy-scope.md)
- [the release train, the R17 contract](../../docs/design/roadmap/RELEASE-TRAIN-2027-2030.md)
- [the implementation plan of this specification](plan.md) and [its tasks](tasks.md)

## Status

Nothing in this specification is built. The repository holds the seeded generator, the deterministic projector and
the sandbox branch layer that the twin builds on, and it holds none of the arrival process, of the capacity model,
of the paired comparison and of the manifest of a simulation.

The decision this specification needs is written down before the first task: the manifest of a simulation, its
assumptions and the rule that a run of the twin is never a bundle of the agent. That record is the next free
number of `docs/decisions/` (ADR-079 at the time of writing; check
[the index of the decisions](../../docs/decisions/README.md) before creating the file). It does not change any
accepted record.
