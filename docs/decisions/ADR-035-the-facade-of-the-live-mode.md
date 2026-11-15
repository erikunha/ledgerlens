---
type: adr
status: accepted
date: 2026-11-15
---

# ADR-035: The facade of the live mode, the vault of the application and the run of the visitor

Status: accepted. Date: 2026-11-15.

## Context

The domain of the live mode exists: the vault that holds the key of a visitor in the memory of the process, the
registry of the models that were really tested, the budget of a run and the adapter that scrubs the credential of a
run out of the error of a provider (ADR-033, ADR-034). Before this milestone nothing of the product calls them:
there is no route that accepts a key, no route that runs a case with it, no route that forgets it, and no report of
what a run consumed.

This milestone is the facade: the routes of the live mode and the coordinator of a run. The question the ADR answers
is not "what does a live run do" but "who decides what the live mode is, who owns the key, and where does the run
stop". Three decisions shape everything else.

The first is the relation between the live mode and the offline product. The public demo has to work with no key at
all, and the offline product has to work with no provider (FR-001, FR-029). The vault never reads a global setting,
on purpose, because the vault is the memory of a secret and a secret does not read the configuration of the process
(ADR-033). The decision to offer a mode at all is therefore not a decision of the vault. It belongs to the facade,
and it is a refusal with a readable answer, not a silent absence.

The second is the owner of the vault. The key of a visitor lives in the memory of the process and nowhere else
(FR-002, FR-003). The memory of the keys is shared by the two facades of the demo, because the live mode accepts the
key and the end of a session drops it, and the end of a session is a route of the sandbox. Two vaults would mean that
the key of a visitor could survive the end of the session, which is exactly what the specification forbids (FR-022).
The sharing is therefore a decision of the deployment, which gives the same vault and the same session issuer to the
two facades, and not an accident of two default folders.

The third is what a live run is, given that the agent of the demo plugs into the live path later. The coordinator
has to own the budget, the trace and the client of the provider, and it has to be able to refuse a model, to cancel
a run and to report what the run consumed, without knowing what the case asks the model. The seam is the caller of
the provider, and every model of the run goes through it, so the budget counts the triage model, the generator of the
SQL and any judge model all the same (FR-012).

Two constraints of the repository shape the decision. The domain layer never imports the API layer and never writes
SQL, so the facade imports the domain and the domain knows nothing of it. And the whole suite runs offline with no
key, so the facade never calls a provider in a test and never opens a socket.

## Decision

**The live mode is refused while the product runs offline, and the refusal names the reason.** The routes that hold
or spend a credential answer `503` with the code `LIVE_MODE_OFFLINE` and a message that says that the product runs
offline and that the replay and the sandbox keep working exactly as before (FR-001, FR-029). The rule lives in the
facade and not in the vault, because the vault never reads a global setting, on purpose (ADR-033). The coordinator
refuses a run offline as well, with the same reason: a run that cannot call a provider would be a run that lies about
its own mode, and the mode of a run is `live_agent` (FR-024).

**The "forget key" action is always available, and the catalogue stays readable.** The route of the forgetting
answers whatever the state of the product is, because it holds nothing and spends nothing: it answers that there was
no key to forget when there was none (FR-014). The catalogue of the models and the price of a model stay readable
too, because they are a read of the data of the server and they cost the visitor nothing (FR-030, FR-031). The
refusal covers the routes that take a key or make a provider call, and nothing else. A visitor with no key sees the
rest of the demo exactly as before, which is the promise of the first story (FR-001).

**The vault and the session issuer are dependencies of the application, and the facade never reads a global.** The
vault is given to `create_app`, and an application that is built without one owns a vault of its own. The session
issuer is given as well, and the live mode has a key file of its own. The two facades of the demo are the same
visitor when the deployment gives them the same vault and the same issuer, and they are two visitors when it does
not (FR-006, SC-002).

Behind that rule there is no vault of the process: the facade exposes no way to reach one and no way to replace one.
A global that holds the keys of the visitors is a global that a test cannot own, and a setter of that global leaks a
vault from one test into the next, while the wiring of the two facades is a decision of the deployment and not of the
code (ADR-035).

Why this and not a vault of the process that the facades share: the memory of the keys of the visitors is shared by
the two facades on purpose, because the key of a visitor has to die with the session whichever route ended it
(FR-022). A sharing that nobody wired is a sharing nobody decided, and a facade that reaches for a global shares the
memory of the keys with an application that never asked for it. The wiring is a decision of the deployment: the
repository builds the two applications separately and no code of it wires them together yet, so a deployment that wants
one visitor on both sides has to give them the same vault and the same session issuer by hand.

**The session owns its credentials, and the end of the session drops them.** The route `DELETE /v1/sessions/current`
of the sandbox facade already purged the branches and the case memory of the session (ADR-030). It now drops the
credentials of that session from the vault it was given as well, and the purge stays tolerant: a vault that refuses
the drop is logged and never fails the route, because a route that fails on a purge leaves the visitor with a session
that no longer exists and a key that nobody dropped. The live mode has the same route for the same reason, and when
the deployment gives the two facades the same vault, the key dies whichever route ends the session (FR-022).

**The modes of a session are declared when the session is issued, and the facade asks the session before it runs a
live run.** The live mode issues its sessions with the capability of the live mode, and the facade asks the session
for its capabilities before it accepts a live run (FR-024). A session of the sandbox has no capability of the live
mode, because a session of the sandbox is a session of the sandbox, and it never runs a live run. The session of the
demo stays anonymous and stays without a key: the capability of the live mode says that the session may run a live
run, and the key of the visitor is what the live mode asks for separately.

**The live mode has its own application and its own router, and by default it has a session issuer of its own.** The
paths of the sandbox are the contract of the design package and they are fixed, and the paths of the live mode are new
(`/v1/credentials`, `/v1/models`, `/v1/live-runs`). The session of the visitor is the cookie of the demo, but the
issuer that signs it is given to the application: the sandbox reads the key of the file `sandbox-session.key` and the
live mode reads the key of the file `live-session.key`, so by default they are two different visitors and a handle of
one session is refused in the other. A deployment that gives them the same issuer makes them the same visitor
(FR-006, SC-002).

**The disclosure of the billing and the promise that nothing is stored travel in headers.** The published contract of
the answer of the credential route is the resource `CredentialHandle`, and it accepts no other field, so the
disclosure cannot be a field of the body (FR-004, FR-005). The answer therefore carries the header
`X-LedgerLens-Key-Storage`, which says that the key is not stored, that it lives in the memory of the server and
that the credential is dropped when the session ends, and the header `X-LedgerLens-Billing-Disclosure`, which says
that the provider of the visitor may charge the visitor for the calls of the run (FR-003, FR-008). The answer carries
`Cache-Control: no-store` with `Pragma: no-cache`, because an answer that holds a handle is not to be kept anywhere.
The route of the run carries the disclosure of the billing and the disclosure of the erasure, because the visitor reads
them before the first call of the provider. It does not carry the disclosure of the storage: the answer of the route of
the run holds no credential, and the header of the storage belongs to the two answers that hold one, the session and
the credential (FR-003, FR-008, FR-021).

The answer does not promise that the memory of the machine is erased. The product never writes the key to a file, a
log or a trace and drops it when the credential ends, and nobody can promise that no copy of the text of the key
survives in the memory of the interpreter or in a swap of the operating system. That limitation is the one ADR-033
declared and it is disclosed here (FR-021).

The disclosure is not only in this document: the answers of the live mode carry the header
`X-LedgerLens-Key-Erasure`, which says that the memory of the machine cannot be guaranteed to be erased. A limit that
lives only in the ADR is a limit that the visitor never reads, and the promise of the storage must not claim more
than the product can keep (FR-021). The header is on every answer of the live mode that describes a run: the answer
of the session, the answer of the credential, the answer that starts a run, the state of a run, the events of a run,
the cancellation of a run and the cost of a run. The answers that hold no key and spend nothing, which are the
catalogue of the models, the price of a model, the forgetting of a key and the end of the session, carry no such
header: a disclaimer about a key that is not there says nothing to the visitor.

**A live run carries the mode `live_agent` and never `recorded_replay`, and it always ends with a terminal trace
event.** The run context of the run declares the mode and the trace of the run is built from it (FR-024, FR-020).
Whatever happens, the run writes exactly one terminal event: `run.completed`, `run.failed` or `run.cancelled`. The
trace of the run carries the provider and the identifier of the model in the payload of `run.started`, so a reader of
the trace knows what ran without asking (FR-026). The trace of a live run lives in the memory of the process in this
milestone: no file, no log, no telemetry, and therefore no place where the key could land (FR-003).

**The budget of the request is the budget of the run context, and the coordinator is the only thing that enforces
it.** The caps of the request are read into the `RunBudget` of the `RunContext` of the run (FR-025). The money is a
`Decimal` from the request to the report, and the answer of the cost carries the money as text, because a binary
float never touches it. The coordinator reserves a call before it happens and records the observed tokens after it.
The cap on the money is checked before the call, and it is checked against the worst case that the caps of the run
allow: the call that is about to happen and the calls that the cap of the calls still allows, each one priced with the
cap of the output tokens of the run at the price of the registry. The check does not trust the plan of the call,
because the plan is clamped by the headroom that is left and a clamp makes the money of the call look small. The check
is deliberately conservative, and a run whose worst case passes the cap is refused before the first call even when the
run could have paid for what it really needed (FR-009, FR-010). The observed cost is what the provider really
counted, and the report carries it apart from the estimate of the plan.

**The key is scrubbed at every boundary, the coordinator holds the secret of the run, and the scrub of the vault is
the layer of the texts the facade writes outside a run.** The adapter scrubs the credential of the run out of the
error of the provider, in the message and in the chain of the error, before the error leaves the adapter (ADR-034).
The coordinator of a run holds the secret of that run in the memory of the process while the run lives, and it
scrubs everything it writes with that secret: the answer of the run, the error of the run, the payload of an event
and the line of a log (FR-018, SC-001). Every event that the caller of the provider writes goes through that scrub,
the name of a tool and the payload of the counters included, because a case that names a tool after the key of the
visitor would put the key in the trace of the run without ever touching the provider. The secret of the run lives in
a holder whose representation cannot carry it, so a debug print or a traceback with the locals never shows it, and
the run releases the secret when the run ends. The vault still never keeps the secret of a credential that is gone
(ADR-033).

Why the coordinator holds the secret and not only the vault: the scrub of the vault covers the credentials that are
alive, and a credential can die in the middle of a run. The visitor presses "forget key", the session ends, the time
to live passes or the vault is full, and the vault drops the secret of that credential on purpose. A run whose
credential died would then publish the key in its answer, in its trace and in its log, and the promise of the feature
is that the key never leaves the process (FR-003, FR-018). The coordinator of the run is what holds the secret
while the run lives, and the run is over when the secret is dropped.

The scrub of the vault is the layer of the texts that the facade writes outside a run: the refusals of the routes
and the answers that carry no run. Inside a run it is the second layer, under the secret of the run: a run scrubs with
the secret of its own run and with the secrets the vault holds. The handler of the refusals scrubs what it writes, and
it does not rely on the redaction that the domain applied when it built the refusal, because a refusal quotes the body
of the visitor and the body of the visitor is untrusted (SC-001).

**No refusal of the facade carries a value that the visitor sent.** The refusal of the registry names the reason and
never the identifier of the model, and the refusal of the contract names the field of the contract and never the value
of that field. The identifier of a model and the value of a field of the body are both values of the visitor, and the
visitor may have put the key of their provider in either of them, so a refusal that repeats them carries that key out
of the process (FR-018, SC-001). The refusal of the registry says that the model is not in the allowlist of the
server, that it has a status the server does not run, or that it is not enabled in the public demo, and that the run
is refused: the reason is enough for the visitor to understand, and the value of the visitor never leaves.

**A credential never outlives the session that holds it.** The time to live of a credential is the smaller of the life
of the vault and the life that is left in the session of the visitor, and the facade is the layer that knows both: the
vault is a dependency of the application and it knows nothing of the session (FR-022). The facade computes that life
and hands it to the vault as an argument of the acceptance, and the life of the vault is never written while the
acceptance happens: a vault whose life was written for the moment of the acceptance would show a foreign life to
every other reader of it, and two acceptances of the same process could swap their lives. The default of the
repository hides the rule, because the life of a session is longer than the life of a credential, so the rule is
pinned by a test whose issuer lives less than a credential would. The time to live is a whole number of seconds and a
credential lives at least one second, so the only gap is the last second of a session that is about to die.

**The body of the request is the published contract, and the server checks it before it does anything.** The body of
the route of the run is checked against the published schema of the request
(`specs/003-r3-bring-your-own-key/contracts/live-run-request.schema.json`), and the model of the request is the
second layer that turns the body into the typed request (FR-007, FR-025). A cap of money is never negative and the
counts are integers, so a body that carries `max_estimated_usd: -1` or `max_model_calls: "4"` never starts a run.
The test of the facade compares the model with the schema, cap by cap and body by body, so the two cannot drift
apart. The model is stricter than the contract in one place and the test names it: the contract applies the minimum
of the money to the numbers only, and the model applies it to a text as well, because a cap of money that is negative
is a cap of money that is broken.

The order of the errors of the contract is the order of the paths of the errors, and every path of the order is a text.
The reason is the array: the path of an error of a contract that carries an array holds the index of the item, and a
number compared with a text raises, and a route that raises answers `500` to a body of the visitor (FR-025).

**The check of the shape of a request needs jsonschema, and a deployment without it refuses the route.** The route
of the run of the live mode, the route of the mutation of the sandbox and the export of the site check the body of
the visitor against a published contract, and the check needs the library. The api extra installs it, because the
routes need it, and the dev extra installs it too, because the suite of the repository imports it. A deployment
without it refuses with a readable answer that says that the installation is missing, and the refusal is a problem
of the deployment and not a bad body of the visitor: the route of the run answers `503` with the code
`CONTRACT_UNAVAILABLE`, the route of the mutation of the sandbox answers `503` with the same code, and the export
refuses with a message that says the same thing about the dependency, because the bundle of the export is not the
reason either.

**The rule of the plan of the tokens: the plan of a call is compared with the headroom that is left, and the cap of
the output tokens is held by the tokens the provider really reported.** The size of the request is known before the
call, so the cap of the input tokens is checked on the plan, and a run whose request is bigger than the cap of the
input tokens stops before it spends anything (FR-009). The size of the answer is not known before the call, so the
plan of the output tokens never promises more than the headroom that is left: the plan of a call is the smaller of
the bounded default and the headroom, and the cap of the output tokens is enforced on the tokens the provider
reported, which is what the budget already checks (FR-009, FR-010).

Why this rule and not another: the cap of the calls of the models and the cap of the output tokens are two caps of
the same run, and the run has to stop at the first one it reaches. A plan that assumed the worst would stop the run
before it ever reached the provider, and the effective number of calls of the run would be the number of output
tokens the cap allows and not the number the visitor asked for. With this rule the run reaches the fourth call and
stops at the fifth attempt for every cap of the output tokens the contract allows, and the answer names the cap that
stopped it (FR-009, FR-025). This is the plan of the tokens of a call, and it is not the check of the money of the
run: the check of the money is the worst case on purpose, because the provider may bill the whole cap of the output
tokens of the run for a single call.

**The case is a seam, and the seam reaches the provider and the tools.** The coordinator drives the provider through
the `ModelCaller`, and the case is the code that decides what to ask the model. The default case asks the model once,
with the question of the request. The agent of the demo plugs into that seam later, and every call it makes goes
through the same caller, so the budget counts every model of the run all the same (FR-012). The seam reaches the
tools the same way: a case that uses a tool calls it through the caller with the name of the tool, and every call of
a tool reserves one call of the budget of the run. A cap of the tools that no call ever reserves is a cap that holds
nothing, so the cap of the tools of the request is the cap of the run (FR-009).

This milestone does not rebuild the agent, and the facade does not pretend to: the request carries the scenario, the
branch, the revision, the account and the variant, and the run context carries them into the trace, so the seam has
everything the agent will need.

**The model of a call is the model of the run, and a call that asks for another one is refused.** The caller compares
the model of the call with the model of the run before it reserves anything, and the refusal stops the run with the
terminal event of a failure (FR-013). The two refusals say different things on purpose: the caller says that the run
runs the model it runs and that the call asked for another one, and the coordinator says that a run with that
identifier runs the model it runs and that a new run identifier is needed. The caller is the layer that really holds
the rule: the facade mints a new identifier for every request, so the guard of the identifier is never the one that
stops a run that changes its model in the middle of it.

**The run always ends with exactly one terminal event, and it always has an answer.** The terminal event is written
in a `finally`, and the guard of the run catches what a case can raise, including the errors that are not exceptions
(FR-020, SC-006). A run that died without a terminal event left the cost route answering that the run is still
running for ever, and a visitor who cannot know that a run is over cannot know whether to wait.

**The cancellation stops the calls that have not started, and the cancellation of a call in flight is a best effort.**
The run carries a flag of cancellation, and the caller of the provider reads it before every call, so a call that has
not started never starts (FR-019, SC-010). A call that is already at the provider cannot be stopped, and the run
knows it: the answer of the route of the cancellation says so, and the flag of the best effort travels with the run
and with the trace. The route of the cancellation does not wait for the end of the run, because a run that waits for
a provider that never answers would wait forever.

The answer of the cancellation says what really happened. A run that is already over was not cancelled, and the
answer says that the run is over and names its status, instead of sending the message of a cancellation that never
happened (FR-019).

**A provider that does not answer in time ends the run, and the partial trace stays.** The call of the provider runs
in a thread of its own and the run gives up on it when the wall clock of the run is over (FR-032, SC-003). The thread
of the provider cannot be killed, and the run says that the provider did not answer in time instead of pretending
that the call was cancelled. The events that came before the call stay in the trace, and the terminal event says that
the run failed.

The wall clock of the run bounds the calls of the provider and the bookkeeping of the run, and the run may end a few
milliseconds after the cap, because the thread of the provider cannot be killed and the thread that waits for it
cannot be interrupted either (SC-003). A call that has no time left is never made: the deadline of a call is the time
the run has left, and a call that starts with no time left would spend the money of the visitor for nothing.

**Only a refusal of the key counts a failure of the credential.** A key that the provider refuses does not work, and
the vault drops a credential that failed too many times (FR-023). A refusal of the key is what the domain says when
the credential was refused, what the status `401` of the answer says, and what the code or the message of the provider
names. A rate limit, a timeout and an upstream failure are not refusals of the key: the provider had a bad day and
the key of the visitor did not, and three rate limits must not drop a key that works. The coordinator counts the
failure of the credential only for a refusal of the key, and the count is tolerant: a credential that is already gone
cannot be counted.

**Nothing of the live mode is published and no financial operation ever happens.** The run answers to the visitor
that asked for it and to nobody else, the trace stays in the memory of the process, and the run never touches a
payment (FR-028).

**The frontend of the live mode is not delivered in this milestone.** The stories T031 to T036 are the pages of the
live mode, and they are not part of this milestone because the work on `apps/` is paused. There is no live page to
look for: this milestone is the server side of the live mode, and its answers are the contracts that the pages will
be written against.

## Alternatives considered

- **Write the life of the credential on the vault for the moment of the acceptance.** The facade knows how much life
  the session of the visitor has left and the vault does not, so the life had to travel from one to the other. A
  vault whose life was written and taken back for the moment of the acceptance shows a foreign life to every reader
  of it, and two acceptances of the same process can swap their lives, so the life travels as an argument of the
  acceptance and the vault keeps its own.
- **Let the vault read the global setting and refuse the live mode itself.** The vault would know about the mode of
  the product, and the memory of a secret would depend on a configuration file. A secret that reads the
  configuration is a secret that can be configured into something else, and the domain of the live mode would grow a
  dependency it does not need (ADR-033). The refusal is a decision of the facade.
- **Refuse every route of the live mode while the product is offline.** The action of forgetting the key would
  disappear with the rest of the routes, and the interface would show a button that answers with an error (FR-014).
  The refusal covers the routes that hold or spend a credential, and nothing else.
- **One vault per application, with no way to share it.** The route of the end of the session of the sandbox would not
  reach the credentials that the live mode accepted, and the key of a visitor would survive the end of its session
  (FR-022). The vault is a dependency of the application, and the deployment hands the same one to the two facades
  when it wants the key to die whichever route ends the session.
- **Let the vault of the process be the only way to reach the memory of the keys.** A facade that reaches for a global
  shares the memory of the keys with an application that never asked for it, and the two facades of the demo end up
  being the same visitor because they happened to default to the same folder. The vault and the issuer are given to
  the applications, and the deployment decides that they share them.
- **Let the scrub of the vault be the only redaction of a run.** The vault does not keep the secret of a credential
  that is gone, and a credential can die in the middle of a run. The run would then publish the key of the visitor in
  its answer, in its trace and in its log. The coordinator holds the secret of the run while the run lives (FR-018).
- **Plan the output tokens of a call with the worst case.** A plan that assumes the worst stops every run before it
  starts, and the effective number of calls of a run becomes the number of output tokens the cap allows and not the
  number the visitor asked for. The plan is compared with the headroom that is left, and the cap of the output tokens
  is held by the tokens the provider reported (FR-009).
- **Check the model of a call only in the coordinator.** The coordinator refuses a second run with the same identifier
  and another model, and the facade mints a new identifier for every request. The rule that really holds the model of
  a run is in the caller of the provider (FR-013).
- **Leave the tools out of the seam.** A cap of the tools that no call ever reserves is a cap that holds nothing, and
  the agent of the demo needs the tools inside the same budget as the model (FR-009, FR-012).
- **Put the routes of the live mode in the sandbox application.** The paths of the sandbox are the contract of the
  design package and they accept no other path (ADR-023). The live mode has its own application and its own router,
  and the two have a session issuer of their own by default: they are the same visitor only when the deployment gives
  them the same issuer.
- **Make the disclosure a field of the body of the answer.** The published contract of the handle accepts no other
  field, and a contract that the server breaks is a contract that nobody can write a client against. The disclosure
  travels in a header.
- **Let the run be a request that never ends.** The cancellation would arrive after the run finished, and the
  interface would show a button that does nothing while the money of the visitor is being spent (FR-019). The run
  happens in a thread of its own and the cancellation is a flag.
- **Promise that the cancellation stops the call that is in flight.** It cannot be promised. The answer says that the
  cancellation of a call already at the provider is a best effort and is not a guarantee.
- **Wait for the provider without a deadline.** A provider that never answers would hold the run forever, and a run
  that never ends has no terminal event, no report and no way for the visitor to stop it (FR-020, FR-032). The call
  runs in a thread of its own and the run gives up on it.
- **Let the case be a chain of the coordinator.** The coordinator would then know what the agent does, and the agent
  would have to be rewritten to fit under it. The case is a seam, and the agent plugs into it.
- **Write the trace of a live run to a file.** A trace on the disk is a place where the key could land, and the
  promise of the feature is that the key never reaches a file (FR-003). The trace of a live run stays in the memory
  of the process, and a sink that writes to a file is a decision that has to be taken on its own.

## Consequences

- The live mode is off by default in the offline product, and the refusal says why. The replay and the sandbox keep
  working exactly as before, and the catalogue of the models stays readable.
- The key of a visitor lives in the memory of the process, in the vault of the application. It dies when the session
  ends, whichever route ended the session, and the purge never fails a route. The vault is given to the application
  and never read from a global, so the deployment decides which facades share the memory of the keys. There is no
  vault of the process behind the facade, and a credential never outlives the session that holds it.
- No refusal of the facade carries a value that the visitor sent: the refusal names the reason and the field, and the
  handler of the refusals scrubs what it writes before it writes it.
- The coordinator of a run holds the secret of the run while the run lives, and it scrubs with it. Every event that
  the caller of the provider writes goes through the scrub, the name of a tool and the payload of the counters
  included, and the secret lives in a holder whose representation cannot carry it and that the run releases when the
  run ends. A run whose credential died in the middle of it publishes no key, in its answer, in its trace and in its
  log.
- The answer of the credential route carries the handle, the provider and the expiry, and the headers that say that
  nothing is stored, that the memory of the machine cannot be guaranteed to be erased and that the provider may
  charge the visitor. The key never travels back to the client.
- Every answer of the live mode that describes a run carries the header of the erasure, and the answers that hold no
  key and spend nothing carry none.
- The body of the request of a run is checked against the published contract, and the model of the request is
  compared with the contract by a test, so the two cannot drift apart.
- A deployment without jsonschema cannot serve the route of the run of the live mode nor the route of the mutation of
  the sandbox, and both answer `503` with the code `CONTRACT_UNAVAILABLE` and with a message that names the
  installation that is missing. The export of the site refuses with a message that says the same thing about the
  dependency, because the bundle of the export is not the reason either.
- The cost report carries the observed cost and the estimated cost apart, as texts, and no amount at all when the
  registry has no verified price for a model of the run.
- Every live run ends with one terminal event, carries the mode `live_agent`, and names the provider and the model in
  its trace. A run that dies in any way at all still has an answer.
- The cap of the calls of the models is the cap that stops the run, for every cap of the output tokens the contract
  allows, and the cap of the tools of the request holds the run as well.
- The cancellation stops the calls that have not started, and the interface is told that a call already at the
  provider is a best effort. A run that is over is never told that it was cancelled.
- The live mode has its own application and its own router, and the pages that consume it are not part of this
  milestone: the answers of the server are the contracts they will be written against.
- The case of a run is a seam. The agent of the demo plugs into it in a later milestone, and every call it makes
  goes through the same budget, the same trace and the same cancellation.
- The pages of the live mode are not part of this milestone, because the work on `apps/` is paused.
