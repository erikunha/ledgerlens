---
type: adr
status: accepted
date: 2026-11-11
---

# ADR-015: The run context enters the core, and the case memory is no longer global

Status: accepted. Date: 2026-11-11.

## Context

The product keeps the state of an execution in three places that hold for the whole machine: the runtime folder of the
configuration, where the case memory lives; the session dictionary of the Streamlit application, where the routed models
of each account live; and the global ledger, which the account reaches through an isolated copy.

With one execution and one visitor, none of that shows. The design package plans the opposite: in the R2 phase several
visitors play at the same time, each one with their own branch of the snapshot. Then the global folder becomes shared
state: the case memory of one visitor shows up in the answer of another, and the trace does not say whose execution it
was.

The LL-V3-R0-06 task asks for a `RunContext` in Python, and the LL-V3-R0-02 acceptance says it directly: the context
injected in the core, with no global path and no global model key per visitor, and the old tests unchanged.

## Decision

The `RunContext` is a frozen object in `ledgerlens/run_context.py`. It carries the identity and the scope of an
execution: the execution and session identifiers, the account, the mode, the snapshot hash, the model profile
identifier, the prompt and policy versions, the trace schema version, the budget, the deadline and the memory folder.
The fields the later phases still do not have, such as `branch_id` and `branch_revision`, exist in the object and are
optional.

The context enters the core through `build_integrator`, which gains the parameter. With a context, the case memory is
created in the session folder inside the runtime folder; without a context, it stays in the global folder, exactly
where it was. The change is migratable: nothing changes for who does not pass a context, and a memory injected by hand
still wins.

The same happens in the legacy `build_executor_integrator`, so both paths answer the same question about whose execution
it was.

The identity is kept on the agent, so the trace, the result and the replay bundle can all say whose execution it was,
without the caller carrying it around. `Integrator.identity()` returns the run, the session, the account, the branch
and the snapshot hash, and returns nothing when there is no context, instead of inventing one.

The `mode` does not come from the caller. When the context does not declare one, the mode comes from the process
configuration, which is what decides whether the product is scripted or live. A declared mode wins over the
configuration, but not the other way round: a deterministic execution cannot be labelled as live by the carelessness of
the caller. A mode outside the contract is refused when the context is built, because a frozen dataclass does not
validate types by itself.

The `session_id` lands in a path, so it has to look like an identifier: a pattern that allows letters, digits, dots,
hyphens and underscores, and refuses a separator or a dot segment. The identifiers of the application are generated
today, and in the R2 phase the identifier can come from a visitor, so the refusal happens at construction.

The budget and the deadline enter as a structure, with everything optional. They are not applied inside the agent yet:
the budget only becomes a ceiling when the phase that implements it arrives, and the model price is not always known.
What is in the object is the place, and the place is what lets the R3 phase wire the limit without changing the
signature again.

The isolation is proven in the data and not only in the path: the test writes a case in one session and asserts the
other session does not read it. The seeded cases are shared and read-only by design, so the proof is about what a
session writes.

## Alternatives considered

- **Pass the session as a parameter in each function.** It is what the product already does with the `thread_id`, and it
  is the shortest path. It is not enough: the per-visitor state is several things at once, and one parameter per
  function is the fastest way back to a global.
- **Move the case memory inside the Streamlit application.** The Streamlit session is already per visitor. But the case
  memory is also read outside Streamlit, in the tests and in the evaluation, and a state that only exists on the screen
  does not serve the rest of the product.
- **Keep the context in a module variable.** It is global state with a nice name, and the test still passes. No.
- **Wait for the R2 phase and do the context all at once.** The R2 sandbox arrives with a new interface and new data, and
  the migration path becomes expensive to review when there are two changes at the same time.

## Consequences

- The case memory is no longer global when there is a context, and the session folder appears in
  `data/runtime/sessions/`.
- The old tests do not change: without a context, the path is the one it always was.
- The `RunContext` is the way to declare whose execution it is. The trace, the replay bundle and the result can carry
  the same identity.
- The budget and the deadline are in the object and are not applied yet. This is a declared debt: whoever reads the
  context sees a ceiling that does not hold anything yet.
- The `build_integrator` still reads the global configuration for the model and for the triage model when they are not
  injected, and the tools still take the ledger and the index from the configuration when they are not given a path.
  This slice delivered the identity of the execution and the memory per session; the rest of the injection the package
  asks for is the work of the later phases, the ADR-004 on the swap between the scripted model and the real one, and the
  ADR-009 on the origin of the ledger and of the index.
- The Streamlit session dictionary of the routed models per account stays as it is for now. It is per visitor already,
  because the Streamlit session is, and it becomes the object of the R2 phase when the visitor identity becomes
  explicit.
