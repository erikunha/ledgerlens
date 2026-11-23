---
type: adr
status: accepted
date: 2026-11-14
---

# ADR-030: The case memory of a sandbox session lives in the folder of the session

Status: accepted. Date: 2026-11-14.

## Context

Two halves of the isolation of the R2 sandbox existed and did not meet.

The branch layer knows the owner of every branch, and it stores that owner in the canonical form of the session
identifier, because the owner lands in a path of the store and a filesystem may ignore the case of a name
([ADR-018](ADR-018-branch-layer-and-store-interface.md)). The run context already scopes the case memory of the
product to a session: `RunContext.resolve_memory_dir()` answers `<runtime_dir>/sessions/<canonical session id>`, and
without a context the memory stays in the global runtime folder of the configuration
([ADR-015](ADR-015-run-context-in-the-core.md)).

What was missing was the link between the two. The sandbox produced no run context for its branches, so an execution
inside a branch had no context and wrote its cases in the global runtime folder. Nothing said which memory belonged
to a branch, and nothing proved that a case written by one visitor was invisible to another one, which is what
FR-027 asks for.

Two details made the link impossible to build as it stood.

The owner of a branch is stored in the canonical form of the identifier, and the canonical form holds the escape
marker `%`, which the pattern of a declared identifier refuses. A context built from the owner of a branch was
therefore refused by the context itself.

The identity of an execution reported the branch identifier and the snapshot hash but not the revision of the
branch, and FR-042 asks for the branch identifier, the branch revision and the base snapshot hash on every trace and
on every answer produced inside a branch.

The end of a session purged the branches of the session and left the case memory of the session behind, so the
memory of an anonymous visitor stayed on the disk under an identifier that nobody could reach again.

## Decision

**The memory folder of a branch is the folder of the session that owns it.** It is
`<runtime_dir>/sessions/<canonical session id>`, the exact folder `RunContext.resolve_memory_dir()` names. The global
runtime folder of the configuration is never the memory of a sandbox session. What a session writes is private to
that session.

**The rule lives in one place.** `ledgerlens/sandbox/memory.py` holds the scope and nothing else. It asks the run
context for the folder and never recomputes it in a divergent way, so the rule of the sandbox and the rule of the
context cannot drift. A test proves that the folder of the sandbox and the folder of the context are the same folder.
The module itself imports neither the FAISS stack of the case memory nor the branch module at runtime, so the rule can
be read and tested without the stack of the memory. The package of the sandbox does import the branch module, and that
is a property of the package and not of this module.

**The run context accepts the canonical form of a session identifier, in addition to the declared form.** This amends
[ADR-015](ADR-015-run-context-in-the-core.md), which stated that the pattern of the identifier refuses the escape
marker. The canonical form is injective over the declared alphabet, so accepting it adds no ambiguity. The invariant is
about the session and not about the string: two identifiers that are different as declared identifiers never name the
same folder, and the canonical form of an identifier names the folder of that same identifier and not the folder of
another one. A string that is the canonical form of an identifier is the same session as that identifier, and that is
why the two of them name the same folder. The pattern of the canonical form is the exact image of the canonical
function over the declared alphabet: the escape of an uppercase letter and the escape of a dot, and nothing else.

**The branch layer accepts the declared alphabet only.** It keeps checking the pattern of a declared identifier and
refuses a canonical form that is not a declared identifier, because the owner of a branch is the name of a folder of
the store and the canonical form is not injective over every string, so a canonical form that is not the form of a
declared identifier could name the folder of another one. The run context accepts the canonical form as well, because
the owner of a branch is stored in that form. The identifiers the sandbox issues are `sess_` plus lowercase
hexadecimal, whose canonical form is the identifier itself, so the identifier that the facade hands to the layer is
also a canonical form and the two name the same owner today.

**The identity of the branch travels in the context.** The context of a branch carries the session that owns it, the
branch identifier, the revision of the branch and the canonical hash of the base of the branch. `identity()` reports
the revision as well, as the decimal text of the integer, because the identity is a map of texts and the interface
never reads a number. When the caller of the context gives no run identifier, the branch names the run, because the
branch is the scope of the execution.

**The memory of a session dies with the session.** The route `DELETE /v1/sessions/current` purges the branches of the
session and then purges the folder of the memory of the session. The purge is tolerant: a folder that does not exist
is not an error, and a folder that cannot be removed is logged and does not fail the route. The purge removes only the
folder of that session inside `<runtime_dir>/sessions/`: the expected path is computed, resolved and compared with
the folder of the sessions before anything is deleted. The purge is a filesystem operation and not a query, because
the domain layer never writes SQL.

**The seeded cases stay shared and read-only by design.** Every session sees the seed of the product. The proof of
the isolation is about what a session writes, exactly like the proof of ADR-015.

## Alternatives considered

- **Keep the case memory of the sandbox in the global runtime folder.** It is what happens without this decision,
  and it is shared state: the case of one visitor shows up in the answer of another one.
- **Give every branch its own folder, under the folder of the session.** The isolation that FR-027 asks for is
  between sessions and not between branches of a session, and the session folder is the one the rest of the product
  already uses. A folder per branch would multiply the folders of the runtime, would scatter the memory of one
  session, and would need a second rule to find them again.
- **Compute the folder in the sandbox without asking the run context.** Two rules for the same folder drift, and the
  drift shows up as the memory of one visitor in the answer of another one.
- **Store the declared identifier of the owner in the branch, so that the context accepts it as it is.** The owner
  lands in a path of the store, and the canonical form is what keeps two identifiers that differ only in the case
  apart. Changing that would change the store that ADR-018 and the contract suite already hold.
- **Purge the memory of a session in the job of the cleanup instead of in the route.** The job would leave the memory
  of a session that ended behind until the next sweep, and the visitor asked for the end of the session.

## Consequences

- The case memory of a sandbox session appears under `data/runtime/sessions/<canonical session id>/` and is removed
  when the session ends.
- ADR-015 is amended in one point: the pattern of a declared identifier still refuses the escape marker, and the
  run context now accepts the canonical form of an identifier as well.
- The identity of an execution that runs inside a branch reports `branch_revision` next to the branch identifier and
  the snapshot hash.
- The facade of the sandbox takes a `runtime_dir` parameter, which defaults to the setting of the configuration. An
  injected folder scopes the key of the sessions, the memory of the sessions and the base of the scenarios. It does not
  scope the branch store, which the factory of the store builds in the runtime folder of the configuration. A test
  points the scope of the session at a temporary folder, so no test touches the runtime folder of the repository.
- The purge of the memory is tolerant on purpose: a failure of the disk is logged and never fails the route that ends
  the session.
