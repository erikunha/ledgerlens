# Feature Specification: R3 - Bring your own key, the model registry and the run budget

**Feature Branch**: `feature/v3`

**Created**: 2026-11-11

**Status**: Draft

**Input**: The visitor brings their own model provider key. The demo runs the real agent with that key, inside a hard
budget, with the key held only in the server memory of the session, and with the public demo still fully usable when
there is no key at all.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The visitor runs a case with their own key (Priority: P1)

A visitor reads the replay and wants to see the same case run with a real model. They pick a provider and a model from
the catalogue, read the cost disclosure, type their key in a password field, set a budget and run one case. The run
uses their key, in their session, and the interface shows the calls and tokens as they happen.

**Why this priority**: The replay proves the engineering; the live run proves the agent works with a real model. It is
the last piece because it is the only one that costs money and handles a secret.

**Independent Test**: With a valid key in the environment of a test, one case runs end to end, the trace carries the
mode `live_agent`, and the visitor sees the budget being consumed.

**Acceptance Scenarios**:

1. **Given** the visitor is on the live mode page, **When** they choose a provider, a model and paste a key, **Then**
   the interface shows the cost disclosure and the budget fields before anything is sent.
2. **Given** a key was accepted, **When** the visitor sets a maximum of 4 model calls and starts the run, **Then** the
   run stops at the 5th attempt to call the model, and the interface says the budget was the reason.
3. **Given** a run in progress, **When** the visitor clicks "Forget key", **Then** the key is dropped, the next call
   fails, and the interface says the key is gone.
4. **Given** no key at all, **When** the visitor browses the site, **Then** every replay and sandbox feature works
   exactly as before.

---

### User Story 2 - The visitor sees what the run cost (Priority: P2)

A visitor wants to know what the run consumed before it finishes. The interface shows the calls made, the tokens
reported by the provider, the elapsed time and the cost. When the provider does not publish a price, the interface says
the price is unknown instead of inventing a number.

**Why this priority**: The constitution demands that money numbers are never invented. A cost estimate that is a guess
is worse than no cost estimate.

**Independent Test**: A run with a provider that reports tokens and one without a published price both show a cost
panel, and the second one says unknown.

**Acceptance Scenarios**:

1. **Given** a provider that reports token counts, **When** the run finishes, **Then** the panel shows the observed
   tokens, the calls and the elapsed time.
2. **Given** a provider whose price is not in the registry, **When** the visitor opens the cost panel, **Then** it
   says the price is unknown and shows no dollar amount.
3. **Given** a run that was cut by the budget, **When** the visitor opens the cost panel, **Then** it says the run was
   cut and by which limit.

---

### User Story 3 - The key never reaches a file, a log or a trace (Priority: P1)

A visitor who brings a key must be able to trust that the key did not land anywhere durable. The key lives in the
server memory of the session, is never written to disk, never appears in the trace, in the logs, in the error message
or in the URL, and disappears when the session ends.

**Why this priority**: A leaked key is the worst failure this feature can have. It is the reason the feature exists
last.

**Independent Test**: A forced provider exception carrying the key is inspected in the logs, the trace, the error the
visitor sees and the telemetry. The key is in none of them.

**Acceptance Scenarios**:

1. **Given** a provider that raises an exception containing the key, **When** the visitor sees the error, **Then** the
   key is absent from the message and the interface says the key was not stored.
2. **Given** a session with a key, **When** the session is reset or the server restarts, **Then** the key no longer
   works.
3. **Given** two visitors in two sessions, **When** one of them runs, **Then** the other one cannot reference or use
   the first one's credential handle.
4. **Given** the visitor looks at the URL of any page, **Then** there is no key or credential handle in it.

---

### User Story 4 - The visitor picks a model that can actually do the job (Priority: P2)

A visitor picks a model. The catalogue only offers models that were tested for the capabilities the agent needs, and a
model that lacks native tool calling is refused with a readable reason instead of being silently replaced.

**Why this priority**: Silently swapping the model would make the comparison dishonest, and a broken tool call in the
middle of a run wastes the visitor's money.

**Independent Test**: A model profile without the `tool_calling` capability is refused at selection time, and the
message names the missing capability.

**Acceptance Scenarios**:

1. **Given** the catalogue lists only tested models, **When** the visitor opens the model picker, **Then** each entry
   shows its tested status and its capabilities.
2. **Given** a model without native tool calling, **When** the visitor tries to select it, **Then** the selection is
   refused and the interface names the missing capability.
3. **Given** a model identifier that is not in the allowlist, **When** it is requested directly, **Then** the request
   is refused by the server.

---

### User Story 5 - The visitor can stop a run (Priority: P3)

A visitor starts a run and wants to stop it. Cancelling stops the calls that have not started, marks the run as
cancelled, and leaves the partial trace visible so the visitor can read what happened up to that point.

**Why this priority**: It protects the visitor's budget and it is required for the session to end cleanly.

**Independent Test**: A cancelled run ends with the status `cancelled`, the trace has a terminal event, and no further
provider call happens.

**Acceptance Scenarios**:

1. **Given** a run in progress, **When** the visitor cancels it, **Then** the run ends as cancelled and the interface
   says so.
2. **Given** a cancelled run, **When** the visitor reads the trace, **Then** the partial trace is visible and ends with
   a terminal event.
3. **Given** a provider call already in flight when the cancellation arrives, **Then** the interface says the
   cancellation of that call was best effort and not guaranteed.

---

### Edge Cases

- What happens when the visitor pastes a key with a valid shape but the provider rejects it?
- What happens when the provider returns a 429 and the retry policy has no budget left?
- What happens when the provider reports tokens but the registry has no price for the model?
- What happens when the provider hangs and the wall clock limit fires?
- What happens when the visitor switches model in the middle of a run?
- What happens when the credential handle of another session is sent in a request?
- What happens when the provider endpoint is changed to a link-local address such as `169.254.169.254`?
- What happens when the key is pasted with surrounding whitespace or a newline?
- What happens when the provider returns a tool call that the parser cannot read?
- What happens when the session expires while a run is in progress?
- What happens when the provider works but the model has no tool calling support, on an architecture that needs it?
- What happens when the budget is exhausted exactly between two tool calls?

### Requirements *(mandatory)*

#### Functional Requirements

- **FR-001**: The system MUST keep the replay and sandbox features fully usable when no key is present.
- **FR-002**: The system MUST hold the key only in the server process memory, bounded, with a time to live.
- **FR-003**: The system MUST NEVER write the key to a file, a database, a log, a trace, an analytics event or a URL.
- **FR-004**: The system MUST NEVER return the raw key to the client in any response.
- **FR-005**: The system MUST return an opaque handle, the expiry and the provider when the key is accepted.
- **FR-006**: The system MUST bind the credential handle to the session and refuse it in another session.
- **FR-007**: The system MUST create the provider client per run and MUST NOT mutate the process environment or the
  global settings for a visitor.
- **FR-008**: The system MUST show the billing disclosure and the budget before the first provider call.
- **FR-009**: The system MUST apply hard caps on model calls, tool calls, output tokens and wall clock time.
- **FR-010**: The system MUST report the observed cost and the estimated cost separately.
- **FR-011**: The system MUST say the price is unknown when the registry has no verified price, and MUST NOT show a
  dollar amount in that case.
- **FR-012**: The system MUST count the calls of every model used in the run, including the triage model, the SQL
  generator and any judge model.
- **FR-013**: The system MUST forbid changing the model in the middle of a run and require a new run identifier.
- **FR-014**: The system MUST expose a "forget key" action that is always available and takes effect immediately.
- **FR-015**: The system MUST refuse a model profile that lacks a capability the selected architecture requires.
- **FR-016**: The system MUST only offer models from a server side allowlist of tested profiles.
- **FR-017**: The system MUST refuse a provider endpoint that is not an allowed HTTPS endpoint, and MUST refuse
  link-local and loopback addresses in public mode.
- **FR-018**: The system MUST redacts the key from logs, traces, error messages and telemetry, even when the key
  arrives inside a provider exception.
- **FR-019**: The system MUST stop the calls that have not started when the run is cancelled, and MUST label the
  cancellation of a call already in flight as best effort.
- **FR-020**: The system MUST write a terminal trace event when the run ends, whatever the reason.
- **FR-021**: The system MUST disclose that memory zeroization cannot be guaranteed by the runtime.
- **FR-022**: The system MUST expire the credential when the session expires, on explicit reset and on server restart.
- **FR-023**: The system MUST bound the number of failures before the credential is dropped.
- **FR-024**: The system MUST label every live run with the mode `live_agent` and MUST NOT label a replay as live.
- **FR-025**: The system MUST expose the run budget in the same `RunContext` object the rest of the core uses.
- **FR-026**: The system MUST record the provider and the model identifier in the trace of the run.
- **FR-027**: The system MUST refuse a run when the requested model identifier is not in the allowlist.
- **FR-028**: The system MUST NOT make any real financial operation, in any mode.
- **FR-029**: The system MUST keep the deterministic offline path free of any provider call.
- **FR-030**: The system MUST expose the catalogue with the tested status and the capabilities of each model.
- **FR-031**: The system MUST show the pricing provenance and the date of the last verification when a price exists.
- **FR-032**: The system MUST treat a provider timeout as terminal for the run, with the partial trace kept.

#### Key Entities

- **ProviderRegistry**: the allowlist of providers and models that the server is allowed to call, with the capabilities
  of each model and the provenance of its price.
- **ModelProfile**: the exact provider identifier, the tested capabilities, the allowed models, the pricing provenance
  and the last verified date, and the status.
- **CredentialHandle**: the opaque handle, the provider, the creation time and the expiry. It never carries the secret.
- **CredentialVault**: the in-process memory that maps handles to secrets, bounded and expiring.
- **RunBudget**: the caps of a run, already part of the `RunContext`.
- **CostReport**: the observed cost, the estimated cost, the calls, the tokens and the elapsed time of a run.
- **LiveRun**: a run that calls a real provider, with its status, its model and its trace.

### Success Criteria *(mandatory)*

#### Measurable Outcomes

- **SC-001**: The key never appears in any file, log, trace or response body, verified by an adversarial test that
  raises a provider exception containing the key.
- **SC-002**: A credential handle from one session is refused in another session in 100 percent of the attempts.
- **SC-003**: No run exceeds the wall clock cap, in 100 percent of the attempts.
- **SC-004**: No run exceeds the model call cap, in 100 percent of the attempts.
- **SC-005**: The interface never shows a dollar amount for a model without a verified price.
- **SC-006**: Every live run ends with a terminal trace event, in 100 percent of the runs.
- **SC-007**: The cost panel appears within one second of the run finishing.
- **SC-008**: The public demo, with no key, keeps every replay feature working, in 100 percent of the test runs.
- **SC-009**: The catalogue lists only models whose tool calling was tested, in 100 percent of the entries.
- **SC-010**: A cancelled run makes no further provider call after the cancellation is acknowledged.
- **SC-011**: The key survives in memory for no longer than the declared time to live.
- **SC-012**: No page of the demo carries a key or a credential handle in its URL.

### Assumptions

- The visitor has a provider account and a key that they are willing to spend on this run.
- The provider supports the HTTP transport the adapter needs, and the adapter is under test for the models in the
  catalogue.
- The demo server runs a single process with bounded memory, and the credential vault lives in that process.
- The visitor understands that their provider may charge them, and that LedgerLens does not store the key.
- The price of the models changes over time, so the registry carries the date of the last verification and can be
  refreshed in a controlled way.
- The public demo does not fund inference, so the live mode is opt-in and always paid for by the visitor.
