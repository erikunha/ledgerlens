---
type: adr
status: accepted
date: 2026-11-24
---

# ADR-084: The fallback of a run happens only with a consent of the deployment and with the budget that is left

Status: accepted. Date: 2026-11-24.

## Context

ADR-078 decided that the model of each slot of a run is chosen by the task the slot does, and it wrote the decision
down before the run starts. The rule is right about the shape of the work, and it has a price: the lightest model of
the cascade that fits a task is the one that fails first when the task turns out to be harder than it looked. The
triage that reads a complaint and the rewrite of the search of the policies are cheap and easy, and the statement
that reads the ledger and the answer with the tools are the ones that can fail on a case nobody saw coming.

A failure of a model is not a failure of the run. The design package asks for exactly this: `R15-02-model-router-with-budgeted-fallback.md`
says that the router executes a bounded task, runs the verifier and, optionally, falls back when a pre-consented
strategy supports it and the remaining budget covers it. The routing specification of the ported package repeats it
as FR-008 and as SC-008: a fallback happens only with a strategy and with a budget, and a failure with no budget
stops the run with the reason.

The repository had the router and did not have the fallback. The comparison of the two routes that ADR-083
published carries a rate of fallback of zero in the two arms, and the zero says that the question was not asked:
the module of the fallback of the package was never ported, and the run had nothing to fall back to.

The fallback is the one place of a run where a call happens that the plan of the run did not ask for. Two rules
follow from that, and they are the rules of the package: a retry never raises the spend of a run by itself, and it
never happens without a consent that somebody gave before the run.

Two ways were open to the repository, and one of them was refused:

- **To fall back to another model whenever a model fails.** Refused. A run that decides by itself to spend more
  than it was given is not a run with a budget, and the router would be the one that raises the spend of the
  visitor.
- **To let the fallback spend what the plan of the run did not reserve.** Refused for the same reason: the retry
  uses the budget that is left, and the caps of the run are read and never written by the routing.

## Decision

**A fallback happens only when a pre-consented strategy of the deployment allows it and the remaining budget covers
it. The router never raises the spend of a run by itself, and a failure with no retry left stops the run with the
reason and with no further call.**

1. **The consent is a setting of the deployment, and the default is no retry at all.** `LEDGERLENS_FALLBACK_ATTEMPTS`
   says how many retries a failed task may get, and `LEDGERLENS_FALLBACK_DIRECTION` says in which direction of the
   cascade they go. A deployment that says nothing gets no retry, and the run stops with the reason that nobody
   consented to a fallback.
2. **The retry asks for more and not for less, by default.** The cascade goes from the lightest model to the most
   capable one, and a model that failed a task is a model that was not capable enough for it, so the retry takes
   the next model above. A deployment that wants the other direction says so.
3. **The budget is asked before the call and not after.** The reservation of the retry is what checks the caps, and
   it happens before the provider is called, so the money of a retry the budget does not cover is never spent
   (FR-009). The caps of the run are the same before and after the decision.
4. **The decision is a value, and the reservation is a step of its own.** The decision carries the action, the
   model, the reason, the number of the attempts and the strategy, and it moves nothing: a decision that changed
   the counters of the budget in the middle of the run would be a decision nobody could reason about. The
   reservation comes after the decision and before the call, and it carries the identifier of the model the way
   the coordinator counts it and the tokens the caller plans, because a cap of the tokens and a cap of the money
   are caps of a planned call and not of a call without a plan.
5. **The retry is never the model that just failed.** Two providers may know a model by the same name, and the
   name of the deployment carries the provider, so the neighbour of the retry is looked for by the name with the
   provider and by the position of the model in the cascade, which is what the router decides by.
6. **The module decides and reserves, and the caller calls.** The caller holds the provider, the client and the
   trace, and a module that called the provider itself would be a second way of calling a model.
7. **The run stops with the reason.** A failure with no retry left, no consent or no budget raises
   `FallbackStopped`, whose message is the reason of the decision. A run that stops without saying why is a run
   that a reader cannot tell from a run that broke.
8. **The live path of the visitor keeps its own counting.** The side that holds the provider is the one that
   reserves the call (ADR-054), and a second counter would count the same call twice.

## Alternatives considered

- **To retry with the same model.** Refused. The same model fails the same task, and a retry that spends the
  budget of the run for the same answer is a call the plan of the run did not ask for.
- **To make the fallback a decision of the router and not of the deployment.** Refused. The router chooses among
  the models that the deployment allowed, and a retry is a call that the deployment has to have consented to.
- **To let the fallback happen and to report the spend afterwards.** Refused. The cap has to be checked before the
  money is spent, and a report that arrives after the call is a report of a bill that was already paid.

## Consequences

- **The repository has the module of the fallback and the rules of it**, in `ledgerlens/agents/fallback.py`, with
  the test in `tests/routing/test_budgeted_fallback.py`: the fallback with the strategy, the stop with the reason
  when no consent or no budget covers the retry, the cap of the money refusing a retry that does not fit, the
  caps of the run unchanged by the decision and the decision moving no counter.
- **The shipped paths behave exactly as before.** The default of the settings is no retry, so no run of the demo,
  of the evaluation or of the catalogue spends a call that the plan did not ask for.
- **The wiring into the loop of the agent is not there yet.** The module decides and reserves, and the caller
  calls, and the caller of a retry inside the loop of the agent is a piece of work that this decision does not
  claim. The rate of the fallback of the comparison of the routes is therefore still not measured.
- **The retry is a value that the trace can carry**, so a reader of a recording of a run that retried sees the model
  of the retry and the reason of it.
- **A cap of the money only refuses a retry whose price the registry verified.** The price of `gpt-4.1` was never
  verified in this repository, so a retry of that model is not refused by the cap of the money, and the other caps
  of the run hold it instead (FR-011).

## Links

- [ADR-034, the registry of the tested models, the two costs of a run and the endpoint](ADR-034-the-registry-the-budget-and-the-endpoint.md)
- [ADR-054, the agent loop has a ceiling in every path](ADR-054-the-agent-loop-has-a-ceiling-in-every-path.md)
- [ADR-078, the model of each slot is chosen by the work it does](ADR-078-the-model-of-each-slot-is-chosen-by-the-work-it-does.md)
- [ADR-083, the routing is measured against one model over the same cases, and every number carries its set](ADR-083-the-routing-is-measured-against-one-model-over-the-same-cases-and-every-number-carries-its-set.md)
- [the page of the routing](../routing.md)
- [the module of the fallback](../../ledgerlens/agents/fallback.py)
- [the test of the fallback](../../tests/routing/test_budgeted_fallback.py)
