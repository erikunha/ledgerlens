# Feature Specification: The inference routing and the cost of the run

**Feature Branch**: `feature/v3`

**Created**: 2026-11-23

**Status**: Draft

**Input**: Design documents: `docs/v3/advanced-specs/R15-02-model-router-with-budgeted-fallback.md`,
`docs/v3/ai/03-MODEL-GATEWAY-ROUTING.md`, `docs/v3/ai/02-SPECIALIST-ROSTER.md`, and the decisions already in
force: `docs/decisions/ADR-034-the-registry-the-budget-and-the-endpoint.md`,
`docs/decisions/ADR-037-the-case-of-the-demo-runs-on-a-bridge-over-the-caller.md`,
`docs/decisions/ADR-013-public-trace-as-a-versioned-contract.md`,
`docs/decisions/ADR-073-the-published-bundle-carries-the-evidence-its-verdict-was-computed-on-and-it-is-reproducible.md`.
The decision that this specification starts is ADR-078 (in preparation), the routing between models by task.
User description: "The repository already holds a server side allowlist of tested models, a budget that counts
every model of a run, two costs that are never mixed and a price that is absent when it was not verified. It
has no router: one model serves the whole run. This specification ports the router as ADR-078 starts it, with
the four slots the repository already has, with the fixed cascade, and with the honesty rules of the
repository: no silent replacement of a human choice, no invented price, one model per live run and every
decision recorded as immutable trace metadata."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Read the decision of the router as it is recorded (Priority: P1)

A run is routed and the decision is read. It names the case, the task the slot does, the risk tier of the
case, the models that were allowed, the model that was chosen, the reason of the choice, the budget the slot
had and the price snapshot the choice was made against. The decision is written once and never changed, so a
reader of the trace of a run knows what the run did and cannot find a version of it that says something else.

**Why this priority**: the decision of the router is the record that makes a comparison between two routes
readable at all. A record that can change is not a record.

**Independent test**: route one case, read the decision in the trace, and expect the nine fields, and then
expect that a second write to the same decision is refused.

### User Story 2 - Keep the model of a live run the one the visitor chose (Priority: P1)

A visitor picks a model and runs a case. The run uses that model for the whole run: the four slots of the
agent, the model of the investigation, the model of the triage, the model that writes the SQL and the policy
model, are four views of that one model, and the model does not change in the middle of the run. A run that
would have to change the model stops with the reason and does not substitute another model.

**Why this priority**: ADR-037 and FR-013 already bind this, and the reason is the promise of the live mode:
a visitor who chose a model must not be shown a result that another model produced under the name of the one
they chose.

**Independent test**: run a live case with a scripted provider, expect one model in every call of the
request, and expect the trace to name that model for the four slots.

### User Story 3 - Read unknown when the price was not verified (Priority: P1)

The registry holds a model whose price was never verified. A run routes a task to it and the cost panel
shows no dollar amount at all and says that the price is unknown. A price that was verified but is older than
the freshness the registry declares is shown with the label that it is stale and with the day it was verified.
Zero is never the answer: a run that called a model and shows a cost of zero says the model was free, and it
was not.

**Why this priority**: the repository decided this in ADR-034 and the package decides it again, and money that
is invented is worse than money that is absent.

**Independent test**: run a cost report over a model without a verified price and expect no dollar amount and
the sentence that the price is unknown, and run it over a model with a price that is older than the
freshness and expect the label that it is stale.

### User Story 4 - Route the light work and the investigation to the declared models (Priority: P1)

The deployment declares a cascade: a first model for the light work and a more capable model for the
investigation. The router chooses the model of each slot by the task the slot does, on the intent and the
risk that were verified before the routing, and on the capability the provider really has. A model whose tool
calling was never tested is disabled with the reason, and it is never chosen. The verifier is not a model and
it is never routed: it stays deterministic.

**Why this priority**: the cascade is the shape of the decision of ADR-078, and the capability of the
provider is the only ground the choice may stand on.

**Independent test**: configure a cascade of two profiles, run a case whose triage is light and whose
investigation is not, and expect the two slots to be routed to the two profiles, and expect a profile whose
tool calling was never tested to be refused with the reason.

### User Story 5 - Refuse a server URL that a visitor wrote (Priority: P1)

A request names the address of a server. The router refuses it, and the refusal names the rule that stopped
it. The router only ever chooses among the models of the allowlist of the server, and the address of a
provider comes from the registry and not from a request.

**Why this priority**: the endpoint of a provider is the boundary between the demo and the network of the
machine that runs it, and ADR-034 already decided where the list of the endpoints lives.

**Independent test**: ask the router to route to a model that carries an address of the visitor and expect the
refusal with the name of the rule.

### User Story 6 - Fall back only when a strategy and a budget allow it (Priority: P1)

A task fails with a provider error. The router falls back only when a pre-consented strategy of the
deployment allows it and the remaining budget of the run covers it. A failure with no retry budget stops the
run with an explicit reason and no further spending. The router never raises the spend of a run by itself and
never changes the data provider of a run outside the consent of the visitor.

**Why this priority**: the package says it, and a router that spends more than the plan of the run without
asking is the opposite of a budget.

**Independent test**: make the provider fail, expect a fallback with the strategy of the deployment, and then
run it again with an empty budget and expect the run to stop with the reason and no further call.

### User Story 7 - Read in the published recording which model did which task (Priority: P2)

A published recording of a case is read. It says which model did the triage, which model did the
investigation, which model wrote the SQL and which model read the policies, so a reader can see the division of
the work and not only the answer.

**Why this priority**: the package asks for the division of the work to be visible, and the published bundle
of the repository is read by strangers.

**Independent test**: read a published bundle of a routed run and expect the model of each slot next to the
task it did.

### User Story 8 - Compare two routes over the same cases (Priority: P2)

Two routes are compared over the same cohort of cases, with the same snapshot, and the comparison reports the
accuracy by intent, the cost per correct case, the p95 of the latency, the rate of fallback and the mix of
models, with the denominator of every number and the set it was measured over.

**Why this priority**: a router that nobody measured is a preference, and the package asks for a comparison
over the same cohort.

**Independent test**: run the comparison and expect both routes over the same cases, with the denominator and
the set of every number.

### Edge Cases

- A task whose risk tier was not verified before the routing: the router does not guess the tier, it routes
  to the model of the heavier tier and says that the tier was not verified.
- A model of the registry whose price snapshot is old: the choice is still made, and the cost is labeled stale.
- Two slots that need two different capabilities and the cascade holds one model: the slot runs with the model
  it has and the trace says that the capability was missing, or the run is refused when the capability is the
  one the task needs.
- A visitor who chose a model that the cascade would not have chosen: the choice of the visitor is the choice
  and nothing is substituted.
- A run that used no model: the cost of the run is unknown and shows no dollar amount.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001** (ADR-078 in preparation): The routing decision is typed and carries the case, the task of the
  slot, the risk tier, the models that were allowed, the model that was chosen, the reason, the budget and the
  price snapshot, and it is written once and never changed.
  - Test: `tests/routing/test_routing_decision.py` expects the nine fields and expects a second write of the
    same decision to be refused.
- **FR-002** (ADR-078 in preparation): The router chooses the model of each of the four slots of the
  repository, the model of the agent, the triage model, the model that writes the SQL and the policy model, by
  the task the slot does, and the verifier stays deterministic and is never routed.
  - Test: `tests/routing/test_router_by_task.py` expects a decision per slot with its task, and expects that
    the verifier of `ledgerlens/verify/` is not in the set of the routed models.
- **FR-003** (ADR-078 in preparation and ADR-037, FR-013): The routing of the live path is the one model of
  the run: the four slots are four views of that model, the model does not change in the middle of the run,
  and a run that would have to change it stops with the reason.
  - Test: `tests/routing/test_live_run_keeps_one_model.py` expects one model in every request of a live run
    and expects the trace to name that model for the four slots.
- **FR-004** (ADR-078 in preparation): A model chosen by a human is never silently replaced, in any path.
  - Test: `tests/routing/test_human_choice_is_kept.py` expects the choice of the visitor to be the decision of
    the router and expects no substitution.
- **FR-005** (ADR-078 in preparation and ADR-034, FR-011): A price that was not verified is absent and never
  zero, and a price that is older than the freshness the registry declares is labeled stale with the day it
  was verified.
  - Test: `tests/routing/test_price_is_never_invented.py` expects no dollar amount for a model without a
    verified price and expects the label that a price is stale.
- **FR-006** (ADR-078 in preparation): The routing is a fixed cascade that the deployment declares: a first
  model for the light work and a more capable model for the investigation, chosen on the intent and the risk
  that were verified before the routing and on the capability the provider really has, and a model whose
  capability was not tested is disabled with the reason and is never chosen.
  - Test: `tests/routing/test_cascade_is_declared.py` expects the two profiles of the cascade to be chosen for
    the two tasks, and expects a profile whose tool calling was never tested to be refused with the reason.
- **FR-007** (ADR-078 in preparation and ADR-034, FR-017): The router chooses only among the models of the
  allowlist of the server and refuses an address of a server that came from a request.
  - Test: `tests/routing/test_no_free_form_endpoint.py` expects the refusal of a model that carries an address
    of the visitor, with the name of the rule.
- **FR-008** (the package and ADR-034, FR-009): A fallback happens only when a pre-consented strategy of the
  deployment allows it and the remaining budget covers it, the router never raises the spend of a run by
  itself, and a failure with no retry budget stops the run with an explicit reason.
  - Test: `tests/routing/test_budgeted_fallback.py` expects the fallback with the strategy, and expects the run
    to stop with the reason and no further call when the budget is empty.
- **FR-009** (ADR-078 in preparation and ADR-013): Every routing decision is an event of the public trace, and
  the published recording of a routed run names the model of each slot next to the task it did.
  - Test: `tests/routing/test_trace_records_the_route.py` reads the events of a routed run and expects the
    decision, and reads the bundle of `ledgerlens/replay/bundle.py` and expects the model of each slot.
- **FR-010** (the package): The comparison of two routes uses the same cohort of cases and the same snapshot,
  and every number carries its denominator and the set it was measured over.
  - Test: `tests/routing/test_route_comparison.py` expects both arms over the same cases, with the denominator
    and the set of every number.
- **FR-011** (ADR-078 in preparation): The decision of ADR-078 is written before the code of the routing, and
  the routing does not change any accepted decision of the repository.
  - Test: `tests/routing/test_adr_078_exists.py` expects the file of ADR-078 in `docs/decisions/` with the
    routing between models by task, the fixed cascade, the honesty rules and the trace metadata.

### Key Entities

- **Routing decision**: the typed and immutable record of one choice of a model for one slot of one case.
- **Task**: what the slot does, one of the four the repository has: the investigation, the triage, the reading
  of the ledger and the reading of the corpus.
- **Risk tier**: the tier of the case that was verified before the routing decided.
- **Allowed models**: the profiles of the allowlist of the server that carry the capability the task needs and
  whose status is not disabled.
- **Price snapshot**: the price of the chosen model with its source and the day it was last verified, and the
  label that says it is stale when it is older than the freshness the registry declares.
- **Cascade**: the declared order of the models of a deployment, from the light work to the investigation.
- **Fallback strategy**: the pre-consented rule that says when a task may be tried again with another model of
  the cascade.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every routing decision carries its nine fields and cannot be written twice.
- **SC-002**: The four slots of the agent are routed by their task, and the verifier is never among the
  routed models.
- **SC-003**: A live run uses one model for the whole run and the trace names it for the four slots.
- **SC-004**: A model chosen by a human is never replaced.
- **SC-005**: A model without a verified price shows no dollar amount and says that the price is unknown, and
  a stale price is labeled stale.
- **SC-006**: The cascade declared by the deployment is the one that routes, and a profile that was never
  tested is disabled with the reason.
- **SC-007**: A model that carries an address of a visitor is refused, with the name of the rule.
- **SC-008**: A fallback happens only with a strategy and a budget, and a failure with no budget stops the run
  with the reason.
- **SC-009**: The published recording of a routed run names the model of each slot next to its task.
- **SC-010**: The comparison of two routes is over the same cohort, with the denominator of every number.
- **SC-011**: ADR-078 exists in `docs/decisions/` and was written before the code of the routing.

## Design documents

- [R15-02 Model router with budgeted fallback](../../docs/v3/advanced-specs/R15-02-model-router-with-budgeted-fallback.md)
- [Model Gateway, Provider Selection and Agent FinOps](../../docs/v3/ai/03-MODEL-GATEWAY-ROUTING.md)
- [Agent Roles and Boundaries](../../docs/v3/ai/02-SPECIALIST-ROSTER.md)
- [ADR-034: The registry of tested models, the two costs of a run and the endpoint](../../docs/decisions/ADR-034-the-registry-the-budget-and-the-endpoint.md)
- [ADR-037: The case of the demo runs on a bridge over the caller](../../docs/decisions/ADR-037-the-case-of-the-demo-runs-on-a-bridge-over-the-caller.md)
- [ADR-013: The public trace is a versioned contract](../../docs/decisions/ADR-013-public-trace-as-a-versioned-contract.md)
- [ADR-073: The published bundle carries the evidence its verdict was computed on](../../docs/decisions/ADR-073-the-published-bundle-carries-the-evidence-its-verdict-was-computed-on-and-it-is-reproducible.md)

## Status

**What exists in the repository today.** The server side allowlist of the tested profiles lives in
`ledgerlens/byok/registry.py`, with the capability each profile declares, the status that says what was
really exercised and a price that is absent when it was not verified, and it refuses a model that is not in
the allowlist and a model that lacks the capability the architecture needs (ADR-034). The coordinator of
`ledgerlens/byok/budget.py` counts the calls of every model of a run, checks the caps before and after the
call, and reports the observed cost and the estimated cost apart. The four slots of the agent are the ones of
`ledgerlens/api/live_case.py`, the model of the agent, the triage, the SQL and the policy, and they are
filled with a bridge over the caller of the run. The configuration of `ledgerlens/config.py` builds one model
from `LEDGERLENS_MODEL`, and the chain of `ledgerlens/chains/router_legacy.py` routes a question between two
chains, which is a different thing: it routes a question and not a model.

**What the package proposes.** A gateway with a versioned routing, a decision that is typed and carries the
case, the type of the case, the risk tier, the allowed models, the chosen model, the reason, the budget and
the price snapshot, and that is an immutable metadata of the trace, a selection of the cheapest eligible model
of the registered profile or of the pinned choice of the visitor, an optional fallback supported by a
pre-consented strategy and by the remaining budget, a conformance test of the mock adapters, and a rollback
to a single chosen model.

**What this specification changes.** The routing is by the task of the slot and by a cascade that the
deployment declares, not by a price that is read at the moment of the choice. The cheapest eligible model is
not the rule: the rule is the cascade, because the point of the routing is the capability of the provider and
the risk of the case, and a price that nobody verified is not a price. The live path keeps one model for the
whole run, because ADR-037 and FR-013 already bind it and a live run that changed the model in the middle
would compare two models under one identifier. The router never accepts an address of a server from a
request.

**What is still to be built.** The typed decision and its store, the router itself, the cascade of the
deployment, the price snapshot with its freshness, the fallback strategy, the events of the trace, the
comparison of the routes and the decision of ADR-078 itself. None of it exists, and the router is the first
thing that ADR-078 must be written before.

## Assumptions

- The decision of ADR-078 is written before the code of the routing, and this specification does not change
  any accepted decision of the repository. The accepted decisions stay as they are.
- The risk tier of a case is verified before the routing. The repository has no tier of risk today, and a tier
  that was guessed would make the reason of the routing a guess.
- The freshness of a price snapshot is a property the registry declares, and the label of a stale price comes
  from it.
- No number of this specification says that a cascade is cheaper or better than one model. The measure is the
  comparison of FR-010, over the set that the manifest of the datasets names, and it is a hypothesis until it
  is measured.

## Out of scope

- The adaptive policy that learns the route from an observed comparison. The package itself calls it a
  research item for the future, and a learned route would be a decision made by a model about which model to
  use.
- The ensembles of several models. The package asks for them only when an independent evaluation shows a
  benefit, and none does today.
- The local mode of a model that the visitor runs. The registry of the server is the list of the models of the
  demo.
- The change of the live path. The live path keeps one model, and this specification does not touch it.
- The frontend of `apps/web/`. The interface of the routing is the trace, the cost panel and the published
  recording.
