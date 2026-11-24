---
description: "Task list for the inference routing and the cost of the run"
---

# Tasks: The inference routing and the cost of the run

**Input**: Design documents from `specs/016-r15-inference-routing-and-finops/`

**Prerequisites**: plan.md (required), spec.md (required), the design package
(`docs/v3/advanced-specs/R15-02-model-router-with-budgeted-fallback.md`), the decisions that already bind
(`docs/decisions/ADR-034-the-registry-the-budget-and-the-endpoint.md` and
`docs/decisions/ADR-037-the-case-of-the-demo-runs-on-a-bridge-over-the-caller.md`) and the decision that this
milestone starts, ADR-078 (in preparation)

**Tests**: Every task that changes the behaviour of the repository ships its test before its code, and the gate
of the Python side is green before the commit. The whole suite runs offline with `LEDGERLENS_OFFLINE=1` and no
key, and the provider is the fake adapter of the repository. A task that is delivered says so, with
**DELIVERED** and the evidence of what it delivered.

**Organization**: Tasks are grouped by the four parts of the plan, and the tasks of a group touch disjoint
files so that they can be worked on in parallel. The ids of this milestone start above the ids of `specs/001-`
through `specs/006-` and they are continuous inside this milestone. The folder `tests/routing/` is created by
T241, and the tests of the registry and of the budget that the routing reads stay where they are:
`tests/byok/` and `tests/api/`.

## Format: `[ID] [P?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[DELIVERED]**: the task is done, and the sentence names what it delivered
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `ledgerlens/`, `tests/`, `scripts/`, `data/`, `docs/` at repository root
- Paths shown below assume single project

## Part A, the decision that comes first

**Purpose**: a routing that nobody decided is a routing that drifts.

- [ ] T240 [P] Write ADR-078 in `docs/decisions/ADR-078-the-routing-between-models-by-task.md`, with the
  status proposed and the date of the day, and write down the direction of the decision: the routing layer
  chooses the model of each of the four slots by the task the slot does, the verifier stays deterministic and
  is never a model, the routing is a fixed cascade that the deployment declares, it never accepts an address
  of a server that a visitor wrote, every decision is immutable metadata of the trace and a price that was not
  verified is unknown and never zero, a model chosen by a human is never silently replaced and a live run has
  exactly one model
- [ ] T241 [P] Write the test in `tests/routing/test_adr_078_exists.py` that reads the file of ADR-078 in
  `docs/decisions/` and expects the routing between models by task, the fixed cascade, the honesty rules, the
  trace metadata and the rule of the one model of a live run
- [ ] T242 [P] Link ADR-078 from `docs/decisions/README.md` by running `uv run python scripts/build_docs_index.py`,
  which generates the index, and expect the new row of the index in the diff

## Part B, the decision of the routing and its store

**Purpose**: the record that makes a comparison between two routes readable at all.

- [ ] T243 [P] Add the typed decision of the routing to `ledgerlens/schemas.py`, with the docstring of the
  class saying what it carries and why, and write the test in `tests/routing/test_routing_decision.py` that
  expects the case, the task, the risk tier, the models that were allowed, the model that was chosen, the
  reason, the budget, the price snapshot and the path of the run, and that expects a second write of the same
  decision to be refused
- [ ] T244 [P] Write the module `ledgerlens/routing/decision_store.py` with the docstring saying that a
  decision is written once and never changed and that the store refuses a second write, and write the test in
  `tests/routing/test_decision_store.py` that expects the refusal of the second write and that expects the
  decision of a run to be readable after the run ended
- [ ] T245 [P] Write the module `ledgerlens/routing/price_snapshot.py` with the docstring saying that the
  snapshot of a price carries its source and the day it was last verified and that it says that it is stale
  when it is older than the freshness the registry declares, and write the test in
  `tests/routing/test_price_is_never_invented.py` that expects no dollar amount for a model without a
  verified price and that expects the label that a price is stale

## Part C, the router, the cascade and the trace

**Purpose**: the choice of the model is a choice by the task and by the capability of the provider.

- [ ] T246 [P] Create the package `ledgerlens/routing/` with the module `__init__.py` and the module
  `ledgerlens/routing/cascade.py`, whose docstring says what a cascade is and why the deployment declares it,
  and write the test in `tests/routing/test_cascade_is_declared.py` that expects the two profiles of the
  cascade to be chosen for the two tasks and that expects a profile whose tool calling was never tested to be
  refused with the reason
- [ ] T247 [P] Write the module `ledgerlens/routing/router.py` with the docstring saying that the router
  chooses the model of a slot by the task the slot does, on the intent and the risk verified before the
  routing and on the capability the provider really has, and that it never accepts an address of a server that
  a visitor wrote, and write the test in `tests/routing/test_router_by_task.py` that expects a decision per
  slot with its task and that expects the verifier of `ledgerlens/verify/` to be absent from the routed models
- [ ] T248 [P] Write the test in `tests/routing/test_no_free_form_endpoint.py` that asks the router to route to
  a model that carries an address of the visitor and expects the refusal with the name of the rule, beside the
  check of the endpoint of `ledgerlens/byok/adapter.py`
- [ ] T249 [P] Write the test in `tests/routing/test_live_run_keeps_one_model.py` that runs a live case of
  `ledgerlens/api/live_case.py` with the scripted provider and expects one model in every request of the run
  and that expects the trace to name that model for the four slots
- [ ] T250 [P] Write the test in `tests/routing/test_human_choice_is_kept.py` that routes a case with the
  model of the visitor and expects the decision to name that model and to expect no substitution of the
  cascade
- [ ] T251 [P] Write the test in `tests/routing/test_trace_records_the_route.py` that reads the events of
  `ledgerlens/observability/trace_event.py` produced by a routed run and expects the decision of the routing,
  and that reads the bundle of `ledgerlens/replay/bundle.py` and expects the model of each slot next to the
  task it did
- [x] T252 [P] Write the module `ledgerlens/routing/fallback.py` with the docstring saying that a fallback
  happens only when a pre-consented strategy allows it and the remaining budget covers it and that the router
  never raises the spend of a run by itself, and write the test in `tests/routing/test_budgeted_fallback.py`
  that expects the fallback with the strategy and that expects the run to stop with the reason and no further
  call when the budget of `ledgerlens/byok/budget.py` is empty - **DELIVERED**: the module is
  `ledgerlens/agents/fallback.py`, next to the router of ADR-078 and not in a package of its own, because the
  routing of the repository lives in `ledgerlens/agents/routing.py`. It holds the strategy of the deployment
  (`LEDGERLENS_FALLBACK_ATTEMPTS` and `LEDGERLENS_FALLBACK_DIRECTION`, with no retry as the default), the
  decision as a value and the stop with the reason (`FallbackStopped`). The budget is asked BEFORE the call, so
  the money of a retry the budget does not cover is never spent, and the caps of the run are never changed by the
  decision (ADR-084). The wiring of the retry inside the loop of the agent is NOT there yet: the module decides
  and the caller calls, and the rate of the fallback of the comparison of the routes is still not measured.

## Part D, the comparison and the publication

**Purpose**: a router that nobody measured is a preference.

- [ ] T253 [P] Write the script `scripts/measure_routing.py` that runs two routes over the same cohort of
  cases with the same snapshot and writes the accuracy by intent, the cost per correct case, the p95 of the
  latency, the rate of fallback and the mix of models with their denominator, and write the test in
  `tests/routing/test_route_comparison.py` that expects both arms over the same cases and that expects the
  denominator and the set of every number
- [ ] T254 [P] Write the page `docs/routing.md` with the cascade, the nine fields of the decision, the rules of
  the honesty of the routing and the numbers of the comparison with the set they were measured over, and with
  the sentence that a number without its dataset is a claim about nothing in particular
- [ ] T255 [P] Write the test in `tests/routing/test_routing_is_published.py` that reads `docs/routing.md` and
  expects the cascade, the nine fields, the rules and the numbers with their set, and that expects the page to
  exist even when the comparison was never run
- [ ] T256 [P] Write the record of the milestone in `docs/decisions/` with the next number after ADR-078, which
  writes down that the routing reads the registry and the budget and never writes them, that the live path
  keeps one model, that the price of a model that was not verified is unknown and that the comparison of the
  routes is a hypothesis until it is measured, and link it from `docs/decisions/README.md`
