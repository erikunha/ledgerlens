---
type: adr
status: accepted
date: 2026-11-15
---

# ADR-037: The case of the demo runs on a bridge over the caller of the run

Status: accepted. Date: 2026-11-15.

## Context

The seam of the case exists since the facade landed. The coordinator of a live run builds a `ModelCaller` for the
run, and it calls the case with that caller and with the plan of the run: the case is the code that decides what to
ask the model. The default case asks the model once, with the question of the request. FR-012 says more than that:
the system must count the calls of EVERY model used in the run, and it names the triage model, the SQL generator and
any judge model.

The agent of the demo is not that default case, and it is not close to it. The agent of the demo is a LangChain
graph built by `build_integrator`, with six tools, a triage chain, a verifier and a long-term memory. It talks to
the world through chat models: the model of the agent, which picks the tools and writes the answer, the triage
model, which reads the complaint and writes the plan, the model that writes the SQL of `query_ledger`, and the policy
model, which rewrites the question of the policy search. Four slots, four models, and every one of them spends the
money of the visitor when it answers.

The problem is not that the agent has models. The problem is that the budget of the run only counts what goes
through the `ModelCaller` of the run, and the agent of the demo, built the way it is built, does not go through it.
A model instance that is anything other than a bridge over the caller is invisible to the budget: its calls are not
reserved, not counted, not traced and not capped. The cap on the calls of the models would then be a cap on the calls
of the coordinator, and the report of the run would show a bill that is not the bill of the run. The promise of the
live mode is that the visitor sees what the run really spent, and a model outside the caller breaks that promise
silently.

There is a second hole of the same kind, on the side of the tools. The case of a run may run tools, and a tool that
runs outside the caller is a tool whose execution nobody counted: the cap on the calls of the tools would not hold
it, and the trace of the run would not say which tool ran (FR-026).

There is a third thing, and it is the one that would have broken the promise the hardest. Three places of the
repository fall back to the model of the configuration when they are given none: the model of the agent and the
triage model in `ledgerlens/agents/integrator.py`, the model that writes the SQL in `ledgerlens/tools/sql.py` and the
model that rewrites the question of the policy search in `ledgerlens/tools/policies.py`. That model is
`get_chat_model()`, and online that is the key of the server, read from the `.env` of the machine. A live run that
fell back to it would spend the money of the operator with the key of the operator, outside the budget of the
visitor, outside the trace of the run and outside the report of the cost (FR-007, FR-018).

And there is one model that must NOT be counted, so that the milestone does not lie in the other direction: the judge
of the demo is the local NLI cross-encoder of `ledgerlens/verify/nli.py`. It is not a provider model, it never calls
a provider, it runs on the machine of the server, and its cost is not the money of the visitor.

## Decision

**The run hands the agent of the demo a chat model that is a bridge over the caller of the run.** The bridge is a
LangChain chat model whose every generation is one call of `caller.complete`, and every tool of the case is wrapped
so that every execution of it reserves one call of the budget through `caller.call_tool`. The agent of the demo is
not rewritten: `build_integrator` already takes a model for each of the four slots that FR-012 names, and the live
mode fills the four with the bridge.

**The bridge is the only place where the turn of LangChain and the turn of the domain meet.** A message of the
domain carries the role, the content and, when the role asks for it, the calls of the tools; the request of the
domain carries the schemas of the tools the model may call; the answer of the domain carries the text of the
provider and the calls it asked for, with the arguments of a call as the text the provider sent. The bridge reads a
turn of LangChain into that request and reads that answer back into the turn of LangChain, the calls of the tools
included, so the agent runs its loop exactly as it always ran it. The model of the request is always the model of
the run: the bridge asks the caller and never decides a model of its own, because a run that asked the provider for
another model would compare two models under one identifier and the trace of the run would lie about what ran
(FR-013).

The text of the arguments travels inside the domain: the budget, the trace and the request of the domain see the
text the provider sent, byte for byte, and a text that is not a JSON text at all travels unchanged. The wire
converters of the domain are NOT on this path: the live path is the bridge, the caller, the adapter and the client
of the provider, and the client of the provider parses the arguments into a mapping before it sends them. The
promise of the text therefore holds inside the process, not in the body of the request of the provider (FR-009).

**The four slots of the agent are the four bridges of the run, and the judge of the demo is not one of them.** The
model of the agent, the triage model, the model that writes the SQL and the policy model are bridges over the
caller of the run, so the budget counts all four the same way and the report of the run shows the calls of each of
them. The judge of the demo, the local NLI cross-encoder, is NOT a provider model: it is not reserved, not counted
and not capped by the budget of the run, because it never calls a provider and its cost is not the money of the
visitor. A judge that were a provider model would have to be the bridge too, exactly like the four slots.

**The case of the demo never falls back to the model of the configuration.** The live mode fills every slot, so
none of the three fallbacks of the repository is ever taken, and a test proves it by making the fallback raise. The
rule is written down because the fallback is a default and a default is a promise that the live mode cannot keep:
online, `get_chat_model()` is the key of the server in the `.env` of the machine (FR-007).

**The bridge lives in the API layer.** The `ModelCaller` lives there, and the domain must never import the API. The
domain carries the turn, the bridge carries the translation, and the two halves of the milestone stay in their own
layer.

**The cancellation of the run is not swallowed by the agent.** The caller raises `RunCancelled` before the next call
of the case, and the case turns any failure of a cancelled run back into the cancellation, because the agent of the
demo catches the failures of its triage and of its follow-up on purpose, and a cancellation is not a failure of the
triage: it is the end of the run (FR-019).

### What this milestone does not have

- **No real provider call.** The milestone wires the agent to the caller and proves it with the fake adapter of the
  domain. The route that starts a live run still runs the default case, and the agent of the demo is not yet the
  case of the route.
- **No scoped ledger of the visitor.** The case reads the ledger of the configuration, because the branch of the
  visitor and the ledger that belongs to the account are the work of another milestone. The tools of the demo read
  what they always read.
- **No frontend.** The visitor sees nothing of this milestone. The mode of the run is still `live_agent` and the
  answer of the run is still the answer of the coordinator.
- **No second model in a run.** A run has one model, the one of the allowlist, and the four slots of the agent are
  four views of that one model, not four models. The model of a run may not change in the middle of it (FR-013).
- **The local NLI judge is not counted.** It is not a provider model, so it is not part of the bill of the visitor.

### What it costs

`build_integrator` does not take the tools, so the tools it builds are wrapped after it built them and the graph of
the agent is bound a second time over the wrapped tools. The agent itself changes nothing: the same six tools, the
same verifier, the same memory, the same prompt and the same checkpointer. The price of that is one extra graph
built per case, and the gain is that every tool of the case reserves one call of the budget of the run.

## Alternatives considered

- **Rewrite the agent of the demo around `ProviderRequest` and `ProviderResponse`.** The agent would then speak the
  domain directly and no bridge would be needed. It loses the loop of tools, the six tools and the verifier of the
  demo, and it duplicates the agent for the offline mode, which is the mode that has to keep working exactly as it
  is. A second agent is two agents to keep, and the demo is not the place to start that.
- **Give the agent the chat model of the adapter, with the credential of the run inside it, and count the calls with
  a callback of LangChain.** The adapter builds such a model (`adapter.chat_model`), and it is the obvious thing to
  do. It breaks FR-012 in two ways: the model talks to the provider WITHOUT the caller, so the money of the call is
  spent before anybody checks the cap, and a callback of LangChain can only count a call AFTER it happened, so the cap
  would be a report of the calls and not a cap on them. A handler cannot stop a provider that is already answering.
- **Move the `ModelCaller` into the domain, so that the agent may use it without the API.** The interface of the
  caller would then exist in two places, and the domain would carry the trace of the run and the secret of the run,
  which are the business of the API layer. The gain is a convenience for one module, and the cost is a layer that
  the repository decided to keep clean.
- **Count the calls of the tools with a callback of LangChain too, instead of wrapping the tools.** The same
  objection as above, and one more: a callback that fails to book the call does not stop the tool from running, so a
  tool would run outside the budget. The wrapper reserves the call BEFORE the tool runs, so a tool that breaks a cap
  never runs at all.
- **Give the case its own client of the provider and count the calls at the boundary of the adapter.** The adapter
  would then have to know the budget, and the budget would have to be known before the call, which is a property of
  the caller and not of the adapter. The counting would live in two places, and the second one would be the one that
  decides whether the run may spend.
- **Count the judge of the demo as a model of the run.** The judge is a local cross-encoder that never calls a
  provider, and a cap of the calls of the models that stopped the run because of it would be a cap that stops a run
  for a cost the visitor is not paying.

## Consequences

- Every model call of the case of the demo is a call of the caller of the run: reserved before it happens, counted
  after it happens, traced with its provider and its model, and stopped by the caps of the run (FR-009, FR-012).
- The report of the run shows the bill of the run: the calls of the triage model, of the model that writes the SQL,
  of the policy model and of the model of the agent are all of them in the same counters, under the model of the run
  (FR-012).
- Every execution of a tool of the case reserves one call of the budget, and the trace of the run says which tool
  ran (FR-009, FR-026).
- The live mode never reaches the model of the configuration, so the key of the server never pays for a run of a
  visitor and never appears in a run of a visitor (FR-007, FR-018).
- The domain of the live mode grows a contract that carries a whole turn, and the API layer grows the bridge that
  speaks it. The domain never imports the API, and the API never puts a number of the run into the domain.
- The cancellation of the run stops the next call of the case, and the run ends as cancelled and not as a mystery.
- A tool of the case that the agent did not call is not counted, and a tool that the agent called twice is counted
  twice: the count follows what the agent did, not what the case planned.
- The agent of the demo keeps working exactly as it worked offline: the bridge is a chat model and a tool, nothing
  else, and the offline path of the repository never touches the API layer.
- The milestone leaves two things for the next one: the route that starts a live run still runs the default case
  instead of the case of the demo, and the ledger that the case reads is the ledger of the configuration and not a
  ledger scoped to the visitor.
