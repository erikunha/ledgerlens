---
type: adr
status: accepted
date: 2026-11-14
---

# ADR-034: The registry of tested models, the two costs of a run and the endpoint of a provider

Status: accepted. Date: 2026-11-14.

## Context

The live mode of the demo lets a visitor run a real case with a key of their own. Three questions have to be answered
before the first provider call happens, and each of them is a promise the visitor reads.

The first is which model runs. The visitor picks a model from a list, and the specification says that the list is
the server's list and not the visitor's text: the system must only offer models from a server side allowlist of tested
profiles (FR-016), and it must refuse a run whose requested model identifier is not in that allowlist (FR-027). The
reason is in the design note `LL-R3-02`: the first public release enables only the models whose native tool calling was
really tested, and an API that answers with a catalogue is not proof of anything, so the smoke test is the proof. A
model that lacks the capability the architecture needs is refused with a readable reason instead of being silently
replaced (FR-015), because a comparison between two models that the visitor did not choose is a lie.

The second is what the run costs. The panel of the cost shows the calls, the tokens, the elapsed time and the money,
and the money has to be honest in a way that is hard to be (FR-010). The observed cost is what the provider reported
and the estimated cost is what the run planned, and they are two numbers and never one number dressed as the other.
The hardest case is the price the registry does not have: the constitution says that a number that is invented is
worse than no number at all, and the specification says the same about the price (FR-011). A model whose price was
never verified shows no dollar amount anywhere, and the panel says that the price is unknown.

The third is where the server calls. The visitor brings a key, and the key is used against an endpoint. An endpoint
that a visitor can point anywhere is a way into the network of the machine that runs the demo, and the address
families that reach the machine itself are the dangerous ones: the link-local range, where the metadata of a cloud
machine lives, and the loopback range, where the services of the host live (FR-017). The check has to be decidable
without a network, because a check that needs a socket is a check that cannot be proved by a test.

Three constraints of the repository shape the decision. The domain layer never imports the API layer and never writes
SQL, so the registry, the budget and the adapter are domain objects with no persistence. Every module carries a
docstring, an `__all__` and a test with a scripted model, and the clock is injected, because a wall clock cap that is
proved by waiting proves nothing. And the whole suite runs offline with no key, so the provider is a fake in the
tests and the price is data in the repository.

## Decision

**What exists today is the domain, and the facade of the live mode is the task of the next milestone.** The registry
refuses a model that is not in the allowlist, the coordinator of the budget refuses a run that would break a cap, and
the adapter refuses an endpoint that the demo may not call and scrubs the key of the run out of the error of the
provider. There is no server of the live mode yet: there is no facade that answers the requests of the visitor, so
every refusal of this ADR is raised by the domain, and it is the facade of the next milestone that will turn those
refusals into answers for the visitor.

**The registry is a server side allowlist of tested profiles, and it is data.** `ledgerlens/byok/registry.py` holds the
allowlist next to the code that reads it, so the price of a model and the day the price was last verified travel with
the model they belong to. The catalogue answers only the profiles of the allowlist whose tool calling was really
exercised, that are enabled in the public demo and that declare the capability that the agent of the demo needs
(FR-015, FR-016, SC-009). A profile that was not tested carries the status `experimental` or `disabled` and is not in
the catalogue, and the registry refuses it with its status in the message rather than dropping it silently (FR-027). The
identifier may be the profile identifier or the model identifier the provider knows, because the interface shows one
and the request may carry the other.

**A price that was not verified is absent and is never a guess.** The price of a profile carries its source, the day
it was last verified and the two amounts, and a profile whose price was not verified carries no amount at all
(FR-011). The registry answers the price of a model with None when it does not have a verified one, and None means
unknown, never zero. A price is money, so it is a `Decimal` from the contract to the report, and the contract carries
it as text or as a number that the domain parses into a `Decimal`, because a binary float never touches money. A
payload of the contract that cannot be read is refused with a refusal of the family and a readable message, and not
with the error of the language: a bad payload is an answer of a server, and the caller has to be able to read what is
wrong with it (FR-030, FR-031). A price whose payload is incoherent with its source is refused the same way: a price
that was never verified carries no amount at all, and a price with a known source carries the day it was verified and
both of its amounts.

**The observed cost and the estimated cost are two separate numbers.** `ledgerlens/byok/budget.py` reports the cost
over the tokens the provider counted and the cost over the tokens the run planned, and the two are never mixed
(FR-010). When a model of the run has no verified price, neither cost is a number: a partial sum would hide the model
whose price is missing, and the report says that the price is unknown instead (FR-011). The report also says whether
the cap on the money was authoritative, because a cap that cannot be evaluated cannot hold a run.

A run that called no model has no price at all. The cost of a run that never called is not a price of anything, and a
zero would read as "the model was free", so the report of such a run says that the price is unknown and shows no
dollar amount at all (FR-010, FR-011).

**The budget counts every model of the run.** The coordinator counts the calls of the triage model, of the generator
of the SQL and of any judge model, and it counts a model the run did not declare as well, because the cap is about the
money and not about the model (FR-012). A model that reports a usage without a reservation is named in the report: the
counting is right, and a call that nobody reserved is a call the caller has to see. That call counts against the cap of
the calls of the models all the same, and it consumes the cap for the calls that come after it, because the call
happened and the money of the visitor was spent whatever the plan of the run said. The run stops when the number of
calls passes the cap, the way it stops for any other call (SC-004). The caps live in the `RunBudget` of
the run context, which is the object the rest of the core already uses (FR-025), and the coordinator is the only thing
that enforces them: it is asked before a call whether the call is allowed and it is told after it what the provider
reported, because the cap has to be checked before the money is spent and the observed tokens only exist after the
provider answered. The run stops at the attempt that would break a cap, and the refusal names the cap that stopped it
(FR-009).

The wall clock cap is checked before a call of a model, before a call of a tool and after a call, because a run that
spends its time in the tools of the agent spends it without calling a model. The cap on the money is checked on the
tokens the run planned and again on the tokens the provider reported, because the provider is the only one who knows
what the call cost. A reservation that carries a planned count of tokens that is negative is refused before anything is
reserved, because a negative count takes the accounting of the run backwards; a planned count of zero is a plan, and it
says that no token is planned. The count the provider reported is checked the same way, because the provider is
untrusted input: a count that is negative or that is not a number is refused and the run stops, and the tokens the
provider really reported are recorded anyway, so the report says what the provider said (FR-009). The clock is
injected, so the wall clock cap is proved by moving a clock and not by waiting (SC-003).

**The endpoint of a provider is an allowed HTTPS endpoint, and never a link-local or a loopback address in public
mode.** `ledgerlens/byok/adapter.py` holds the published endpoints of each provider and compares the endpoint of the
run with them, so the server calls what the provider publishes and nothing else (FR-017). The check is a pure
function of the text of the endpoint: it resolves no name and opens no connection, so a test proves it without a
network, and the refusal names the reason that stopped it and carries the machine-readable code of the rule that
stopped it, the way the refusals of the sandbox carry a code. In public mode a link-local address and a loopback
address are refused before the allowlist is consulted, because those addresses reach the machine itself and not the
provider. The adapter is built per run, the credential goes into the constructor of the client and nowhere else, and
neither the environment of the process nor the global settings of the configuration are ever touched (FR-007).

**The refusals of the three modules belong to the family of the live mode.** The refusals are raised from
`ledgerlens/byok/errors.py`, so a caller catches the whole family with one name and a refusal always carries a
readable reason. The model that is not allowed and the endpoint that is refused are the two reasons that the shared
module did not name yet, and they live in the module that raises them. A payload of a published contract that cannot
be read is a refusal of the family too, and not the error of the language (FR-030, FR-031).

## Alternatives considered

- **Let the visitor type the model identifier.** The catalogue would be a suggestion and the server would call
  whatever the request asked for. The specification forbids it twice (FR-016, FR-027), and a model that was never
  tested with the tools of the agent breaks in the middle of the run and spends the money of the visitor while it
  breaks.
- **Let the server swap a model that lacks the capability for one that has it.** The run would finish and the panel
  would show a number that belongs to another model. The comparison the visitor came for would be a comparison of
  something else, and nothing in the trace would say so (FR-015).
- **Publish the catalogue of every model the provider offers.** The list would be long and mostly untested, and the
  design note says that the catalogue of the API is not proof of anything (FR-016). The catalogue of the demo holds
  what was really exercised and nothing else.
- **Show a price that was estimated from a nearby model or from a table of the past.** The visitor would see a dollar
  amount that nobody checked, and the specification says the price is unknown when it was not verified (FR-011). The
  absent number is honest and the invented one is not.
- **Show the cost as the sum of the observed and of the estimated cost.** The panel would carry one number that means
  two things, and the visitor could not tell what the run really spent (FR-010). The two numbers are reported apart.
- **Show a partial cost when the price of one model of the run is unknown.** The number would be smaller than the
  truth and would look complete. A partial sum of a run is not a cost, so the report shows no amount at all.
- **Count only the calls of the model the run declared.** The triage model and the judge would be free, and the cap on
  the money would not be the cap on the money (FR-012). Every model of the run is counted, whoever it is, and a call
  that nobody reserved counts as well.
- **Check the caps after the call, when the tokens are known.** The visitor would pay for the call that broke the
  budget before the run noticed. The cap is checked before the call, on the tokens the run planned, and the observed
  tokens are checked again because the provider is the only one who knows what it produced.
- **Resolve the name of the endpoint to know whether it is private.** The check would need a resolver and a network,
  and the answer would change with the moment. The check reads the text of the endpoint, and the allowlist of the
  published endpoints already refuses every host the server has no reason to call.
- **Let the endpoint of the provider be configured in the deployment.** A deployment that points the demo at its own
  gateway is a deployment that has to be trusted with the key of every visitor. The list of the published endpoints is
  data in the repository, and a new provider arrives with its own adapter and its own tests.
- **Keep the provider client in the environment of the process for the duration of the run.** The key would reach every
  log of the process and every child process, and the specification forbids it (FR-007). The client is built per run
  with the key in its constructor.

## Consequences

- The catalogue of the demo holds only the models whose tool calling was really tested, and each entry shows its
  status and its capabilities (FR-030). A model that is not in the catalogue is refused by the registry of the domain
  and not by the interface alone.
- A price that exists carries its provenance and the day it was last verified (FR-031), and a price that was not
  verified is absent. The cost panel of a model without a verified price shows no dollar amount at all (SC-005).
- The cost report of a run carries the calls of every model, the tokens, the elapsed time, the observed cost, the
  estimated cost and the cap that stopped the run when one stopped it. The observed cost and the estimated cost are
  two fields and never one. A run that called no model shows no dollar amount at all, because the price of a run that
  never called is not a price of anything.
- The budget of a run lives in the `RunBudget` of the run context, so the same caps are visible to the interface, to
  the coordinator and to the trace of the run (FR-025). The run stops at the attempt that would break a cap, and the
  refusal names the cap.
- The clock of the budget is injected. The wall clock cap of a run is proved by a test and not by a slow test, and no
  test of this slice waits for a second to pass.
- The endpoint of a provider is data in the repository, and the check of the endpoint is a pure function of its text.
  A link-local address and a loopback address are refused in public mode, and the refusal names the reason.
- The provider of a run is a fake in the tests. The tests of the registry, of the budget and of the adapter open no
  socket and read no key, and the whole slice runs offline with no key at all.
- The domain layer grows three modules and three tests, and the live mode has no persistence: the modules import
  nothing of the API layer and write no SQL.
