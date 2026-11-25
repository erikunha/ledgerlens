---
type: adr
status: accepted
date: 2026-11-24
---

# ADR-085: The retry of a failed model is wired into the triage of the run and into the model of the graph

Status: accepted. Date: 2026-11-24.

## Context

ADR-084 decided what a fallback has to carry to be allowed: a consent of the deployment, the budget that is left, the
model of the cascade that is not the one that failed, and a reason when nothing is left. It also said, in its
consequences, that the wiring into the loop of the agent was not there yet: the module decided and reserved, and
the caller called, and no caller of a retry inside the loop of the agent existed.

The module was therefore a promise that nothing delivered. A deployment that set `LEDGERLENS_FALLBACK_ATTEMPTS` got
no retry at all, and the rate of the fallback that the comparison of the routes publishes is a zero that says the
question was not asked.

Wiring it is not one seam but two, and the two do not have the same owner:

- the triage of the run is a call of a model that the integrator makes itself, outside the graph of the agent, and
  the caller of that call is the integrator;
- the model of the graph is a call of a model that the graph makes through its own middleware, and the reservation
  of the calls of the graph sits in the middle of that chain.

Two things made the first attempt at the wiring wrong, and both are visible in the review of the code:

- the seam of the triage called the model that had just failed one more time, so the run spent the money of a call
  that nobody planned and the count of the calls of the run was not the count of the calls that happened;
- the retry ran inside the reservation of the graph, so the reservation booked the tokens of the model of the retry
  under the model that had failed, and the money of the retry was priced as the money of another model.

A third thing was wrong in the same place: the count of the retries that happened was mutable state of the agent,
and the agent serves the turns of a session, so a turn that started while another was running spent the retry of the
other one.

## Decision

**The retry is wired into the two places where a model of the run fails, the triage of the run and the model of the
graph, and the rules of ADR-084 hold there as they do in the module.**

1. **The two seams, and only the two.** The triage of the run is retried when it fails, and the model of the graph
   is retried when it fails. The models that the tools call, the statement that reads the ledger and the rewrite of
   the search of the policies, are not wired, and the page of the routing says so.
2. **The retry never repeats a model that this task already tried.** The call that failed already happened and the
   money of it is already spent, and the rule of ADR-084 that the retry is never the model that just failed holds in
   the wiring as well as in the module. The rule is wider than the neighbour: a cascade that holds the same model at
   two levels, or a retry whose model was the model of a failure that came before it in the same task, stops the
   retry, because the money of that failure would be spent twice for the same task.
3. **The retry is outside the reservation of the graph.** The reservation books the usage of a call under the model
   of that call, and a retry that ran inside it would book the tokens of the model of the retry under the model that
   failed. Outside, every attempt of the turn is reserved under its own model, and the reservation of the graph
   does not reserve the call of the retry a second time: the fallback reserves it, with the plan of the retry, and
   the usage of that call answers that reservation.
4. **The model of the retry is built before it is reserved.** A deployment that cannot build the model of the retry
   has no call of it, and a reservation of a call that never happens is money that the run of a visitor does not
   owe. The build of the model is therefore before the reservation, and a build that fails stops the run with the
   reason.
5. **The plan of the retry reaches the caps.** The reservation of the retry carries the input the retry is about to
   send and the output it asks for, so the cap of the money and the cap of the tokens are checked before the call
   and the money of a retry the budget does not cover is never spent (FR-009). The plan of the retry of the triage
   is the whole prompt of the triage, its system message included, and not the complaint alone: the system message
   is the largest part of the call, and a plan built from the complaint alone would undercount the call by two
   orders of magnitude and would let a cap pass a call that does not fit. The first attempt of a call of the graph
   carries no plan, because the path of the demo and of the evaluation has no planner of its calls yet, and the
   caps of the tokens and of the money of that call are checked against what the provider reported. The first
   attempt of the triage carries no plan either, and its usage never reaches the coordinator, as the consequences
   of this decision say.
6. **The consent counts the retries of a task, and a task is a call of a model.** The triage is a task and each
   call of the graph is a task of its own, so a task that fails gets the retries the deployment consented to and
   the task that comes after it gets its own. Nothing is counted in the agent and nothing is shared by the turns of
   a session.
7. **The caller that holds the provider builds the model of a retry.** The integrator never builds a model of a
   retry by itself: it takes the factory from the caller, and a caller without one, which is the live path of the
   visitor, has no runner and no middleware at all. The live path holds the credential of the visitor and not the
   key of the server, and a retry built with the key of the server would spend a money that nobody counts
   (ADR-037, ADR-054).
8. **The decision of the retry is in the trace and the reason of a stop is in the result.** The decision is a value
   and the trace of the turn carries it, with the model of the retry and the reason of it. A turn that stops because
   the retry did not happen comes back as a result that names the reason, and not as an exception that nobody reads.
   The cap that the coordinator recorded is the cap the result names, when the budget is the one that refused the
   retry, and the failure of the provider is in the reason of the stop. The result is the answer of a turn that owns
   the counting: a turn whose budget belongs to the caller raises the stop, because the caller is the one that has
   to read it.
9. **The side that holds the provider is the one that reserves the call, and a turn that does not own the counting
   refuses the retry.** The reservation of a call of a model belongs to the side that holds the provider (ADR-054),
   and a second counter would count the same call twice. A turn that does not own the counting therefore has no
   reservation of its own, and a retry that nobody reserves would spend the money of the run outside the caps of the
   run, so the retry stops with the reason.
10. **A signal of the graph is not a model that failed.** An interrupt of the graph goes up and is not retried.
11. **The comparison of the routes builds no runner.** The arms of the comparison are one model in the four slots and
    the model of each slot, and a retry would take an arm out of what it claims to be. The rate of the fallback of
    the comparison is therefore still not measured, and the zero it publishes says that the question was not asked.
12. **The name of the model of the triage comes from the deployment when it named the slot of the triage, and from
    the model of the caller otherwise.** The router names the model of each slot the way the deployment named it, and
    the retry of the triage reads the name of the slot of the triage to find the neighbour of the retry in the
    cascade. A caller that routed nothing names no slot, and the retry then reads the name of the model of the
    triage itself. The model of the graph is not named this way: the graph knows the model it is running with, and
    the retry of a call of the graph reads that one. The names of the other three slots reach the run as the model
    objects of their slots, and the retry does not read them.

## Alternatives considered

- **To keep the retry inside the reservation of the graph.** Refused. The reservation books the usage of a call
  under the model of that call, and a retry inside it is priced as the model that failed.
- **To let the fallback reserve the call and the reservation of the graph reserve it again.** Refused. A call
  counted twice is a run whose accounting is a lie, and the caps of the run would be checked twice for the same
  money.
- **To count the retries of the turn and not of the task.** Refused. The consent of the deployment says how many
  retries a failed task may get (ADR-084), and a turn is not a task: the triage and each call of the graph are
  tasks of their own.
- **To keep the count of the retries in the agent.** Refused. The agent serves the turns of a session, and a count
  that the turns share is a count that two turns that overlap spend between them.
- **To wire the models that the tools call as well.** Not now. The statement that reads the ledger and the rewrite
  of the search of the policies are calls of tools and not calls of the graph, and wiring them is a piece of work
  of its own.
- **To use the middleware of the library that falls back to another model.** Refused. It does not read the consent
  of the deployment and it does not read the budget of the turn, and the two are the rules of this repository.

## Consequences

- **The repository has the wiring of the retry**, in `ledgerlens/agents/fallback.py` (`FallbackRunner` and
  `FallbackMiddleware`) and in `ledgerlens/agents/integrator.py` (`build_integrator`, `run_triage` and
  `_triage_with_fallback`), with the test in `tests/routing/test_fallback_in_the_run.py`: the triage that is
  retried, the model that failed that is never called again, the usage of the retry that is booked under the model
  of the retry, the plan of the retry that reaches the caps of the money, the decision in the trace, the reason in
  the result, a reservation that is not charged for a call that never happens and the count of the retries by task.
  The live path of the visitor has its own test, in `tests/byok/test_live_case.py`: it builds no runner and no
  middleware of the retry.
- **A stop leaves a decision in the trace too.** The trace of a turn that stopped because the retry did not happen
  carries the decision of the stop, with its action, its reason, its attempts and its strategy. The decision of a
  stop carries no model, because no model ran the retry, and the reason names the model that the retry would have
  used when there was one: the reader of the trace sees a run that stopped and why, and not only a run that stopped.
- **The demo and the evaluation pass the factory of the model of a retry, and the demo names no slot.** The demo
  and the evaluation hold the provider of the deployment, so they build the model of a retry themselves. The demo
  names no slot of the router, so the name of the model of the triage comes from the model of the triage itself.
- **The shipped paths behave exactly as before.** The default of the settings is no retry, so no run of the demo,
  of the evaluation or of the catalogue spends a call that the plan did not ask for, and the integrator of a
  deployment that said nothing carries no runner of the retry and no middleware of the retry. The reservation and
  the wall behind the tools are the middlewares it always carried.
- **The live path of the visitor keeps its own counting and its own model.** The live path builds no runner, and
  the visitor's run keeps the one model of ADR-037.
- **The offline mode has no retry.** The scripted model of the offline mode has no name in the cascade of the
  deployment, so the neighbour of the retry is not found and the run stops with the reason.
- **The tokens of the triage are not in the report of the coordinator.** The chain of the triage answers with the
  plan and not with the message of the provider, and the tokens of the provider are in the message. The reservation
  of the triage, and the reservation of its retry, therefore wait for a usage that never arrives, and the repair
  call of a triage whose answer cannot be read is a call of a model that the budget of the turn does not count.
  The gap is of the triage path and not of the wiring: the tokens of the triage are in the trace of the run, the
  plan of the retry of the triage is the whole prompt, and closing the gap is a piece of work of its own.
- **The rate of the fallback of the comparison of the routes is still not measured**, and this decision says why:
  the comparison builds no runner at all.

## Links

- [ADR-034, the registry of the tested models, the two costs of a run and the endpoint](ADR-034-the-registry-the-budget-and-the-endpoint.md)
- [ADR-037, the case of the demo runs on a bridge over the caller](ADR-037-the-case-of-the-demo-runs-on-a-bridge-over-the-caller.md)
- [ADR-054, the agent loop has a ceiling in every path](ADR-054-the-agent-loop-has-a-ceiling-in-every-path.md)
- [ADR-078, the model of each slot is chosen by the work it does](ADR-078-the-model-of-each-slot-is-chosen-by-the-work-it-does.md)
- [ADR-083, the routing is measured against one model over the same cases, and every number carries its set](ADR-083-the-routing-is-measured-against-one-model-over-the-same-cases-and-every-number-carries-its-set.md)
- [ADR-084, the fallback of a run happens only with a consent of the deployment and with the budget that is left](ADR-084-the-fallback-of-a-run-happens-only-with-a-consent-of-the-deployment-and-with-the-budget-that-is-left.md)
- [the page of the routing](../routing.md)
- [the module of the fallback](../../ledgerlens/agents/fallback.py)
- [the test of the wiring](../../tests/routing/test_fallback_in_the_run.py)
