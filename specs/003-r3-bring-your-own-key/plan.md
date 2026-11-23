# Implementation Plan: R3 - Bring your own key, the model registry and the run budget

**Branch**: `feature/v3` | **Date**: 2026-11-11 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/003-r3-bring-your-own-key/spec.md`

## Summary

The R3 feature lets a visitor run a real case with their own provider key. The key arrives over HTTPS, is held only in
the server process memory of the session, and is dropped on request, on expiry or on restart. The run uses a model from
a server side allowlist of tested profiles, inside a hard budget that the visitor sets, and every event of the run
carries the mode `live_agent`.

The technical approach is deliberately narrow. The Python core stays the authority and gains three pieces: a
`CredentialVault` that lives in process memory, a `ProviderRegistry` that is the only thing allowed to name a provider
and a model, and a live run coordinator that builds a per-run chat model with the visitor credential injected at
construction. Nothing global is mutated: no `os.environ` change, no global settings change, no client singleton shared
between visitors.

The frontend consumes the same versioned schemas the replay uses. The live mode adds a consent panel, a model picker
and a budget form, and it renders the cost report. The replay and the sandbox do not change.

## Technical Context

**Language/Version**: Python 3.12 for the core, TypeScript strict for the web app
**Primary Dependencies**: `langchain-openai` and `langchain-core` for the provider adapters, FastAPI for the facade, SSE
for the event stream, the existing `RunContext` and `TraceEventStream` for identity and events
**Storage**: in-process memory for the credential vault and the cost ledger. No database, no disk. The session
identifier and the credential handle are bound in the same process
**Testing**: pytest with a fake provider adapter, Playwright for the end to end path
**Target Platform**: Linux server, one process, browser on desktop and mobile
**Project Type**: web service plus a static front end
**Performance Goals**: the live run starts within one second of the request, the SSE stream delivers each event within
200 ms of its emission
**Constraints**: no key on disk, no key in a URL, no key in a trace, no global configuration change, hard caps on
calls, tokens and wall clock, the demo works with no key at all
**Scale/Scope**: one public visitor per session, a handful of sessions at a time, one live run at a time per session

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | How the plan obeys it |
|---|---|
| I. Evidence over fluency | The live run produces the same evidence and verdict structure as the replay. A live answer with no evidence is marked unsupported by the same verifier, not by the interface. |
| II. Numbers come from code | The cost report is computed by Python with `Decimal`. The provider price comes from the registry, and when it is missing the panel says unknown. The model never estimates a cost. |
| III. Read-only and least privilege | The live path uses the same read-only ledger connection and the same SQL guard. The visitor credential is scoped to one session and one provider, and the provider allowlist is server side. |
| IV. Reproducible without credentials | The offline path is untouched. The whole demo, and the whole test suite, run with `LEDGERLENS_OFFLINE=1` and no key. The live path is a separate, opt-in branch. |
| V. Truthful labels | Every live event carries `live_agent`, every replay carries `recorded_replay`. The consent panel states that the visitor's provider may charge them and that LedgerLens does not store the key. |
| VI. Legacy where it teaches, modern where it matters | The live path uses the same `create_agent` integrator as the offline path. The difference is the chat model instance, not a second architecture. |
| VII. Test first, measure always | The vault, the registry and the budget coordinator each get unit tests with a fake provider before they are wired to the facade. The cost report is measured, not eyeballed. |

**Complexity check**: the credential vault and the registry are the two pieces with real risk, and both are small and
isolated. The plan fits in one release with no dependency on R2 beyond the `RunContext` that already exists.

## Project Structure

### Documentation (this feature)

```text
specs/003-r3-bring-your-own-key/
├── spec.md              # This file's source (the feature specification)
├── plan.md              # This file
├── research.md          # Phase 0: provider adapter limits, zeroization limits, retry policy
├── data-model.md        # Phase 1: CredentialHandle, ModelProfile, CostReport, RunBudget usage
├── quickstart.md        # Phase 1: how to run a live case locally and how to revoke
├── contracts/
│   ├── credential-handle.schema.json   # the handle and the expiry, never the secret
│   ├── model-profile.schema.json        # the catalogue entry
│   └── live-run-request.schema.json     # the budget and the model choice
└── tasks.md             # Phase 2: the task list
```

### Source Code (repository root)

```text
ledgerlens/
├── byok/
│   ├── __init__.py
│   ├── vault.py          # CredentialVault: in-process memory, bounded, with a TTL
│   ├── registry.py       # ProviderRegistry and ModelProfile: the only allowlist
│   ├── budget.py         # the budget coordinator: caps, counters, observed and estimated cost
│   ├── adapter.py        # the provider adapter interface and the fake one for the tests
│   └── errors.py         # the refusals with a readable reason
├── api/
│   ├── byok.py           # the facade endpoints for credentials, catalogue and live runs
│   └── live_run.py       # the live run coordinator and its SSE stream
├── run_context.py        # already carries the budget; the live path fills it
└── observability/
    └── trace_event.py    # already carries the mode; the live path sets live_agent

apps/web/
├── app/
│   ├── (public)/live/page.tsx          # the live mode page
│   └── api/live/[handle]/route.ts      # the SSE bridge
├── features/
│   ├── models/                          # the model picker, the consent panel, the budget form
│   │   ├── ModelSelector.tsx
│   │   ├── ApiKeyDialog.tsx
│   │   ├── BudgetForm.tsx
│   │   └── CostReport.tsx
│   └── evals/                           # the cost panel, reused by the run inspector
└── lib/api/
    └── live.ts          # the generated client types from the contracts

tests/
├── byok/
│   ├── test_vault.py        # the key never leaves memory, the handle does not cross sessions
│   ├── test_registry.py     # only the allowlist answers, the capability refusal
│   ├── test_budget.py       # the caps stop the run, the counters are right
│   └── test_live_run.py     # the terminal event, the mode, the partial trace on cancel
├── api/
│   └── test_byok_api.py     # the handle endpoint never returns the secret
└── replay/                  # unchanged, and it must stay green
```

## Design Notes

**The credential never returns to the client.** The endpoint that accepts the key returns a handle, the provider and
the expiry. The handle is an opaque random string, and it is bound to the session in the vault. A handle presented in
another session is refused, not looked up.

**The model is chosen from the registry, never from the request.** The request carries a profile identifier, the server
resolves it against the allowlist. A model identifier that is not in the allowlist is refused before any provider call,
and a model that lacks the capability the architecture needs is refused with the capability named.

**The budget is enforced by the coordinator, not by the caller.** The caps live in the `RunBudget` of the
`RunContext`, and the coordinator checks them before each provider call and before each tool call. When a cap fires,
the run ends with a terminal event that says which cap fired. The visitor can see the count going up while the run
happens, because the counts travel as events.

**The cost has two numbers and one honest gap.** The observed cost is what the provider reported. The estimated cost is
what the registry price says, and it is only shown when the registry has a verified price with a date. When there is no
price, the panel says unknown and shows no dollar amount, because an invented dollar amount is worse than no number.

**The client is built per run.** The provider client is created at the start of the run with the credential injected in
the constructor. There is no shared client between visitors, and no environment variable is set. Two visitors on two
providers at the same time cannot cross-contaminate, because there is no shared mutable state to contaminate.

**Cancellation is honest about itself.** Cancelling stops the calls that have not started. A call already in flight at
the provider cannot be guaranteed to stop, and the interface says so rather than pretending the call was cancelled.

## Deferred Work

- More providers. The first release supports one provider, the one the dependencies already cover. A second provider
  comes with its own adapter and its own capability tests, not as a configuration change.
- Streaming responses from the provider to the browser. The SSE stream carries trace events, not token by token
  completion.
- A persistent record of what a visitor spent. The cost ledger lives in memory for the session and is dropped with it.
- Multiple live runs at the same time in one session. The first release runs one at a time.
