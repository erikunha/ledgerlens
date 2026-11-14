---
type: adr
status: accepted
date: 2026-11-14
---

# ADR-023: The facade serves the routes the specification of the feature requires and the design package does not declare

Status: accepted. Date: 2026-11-14.

## Context

The facade of the sandbox follows the versioned contract of the design package,
`docs/v3/contracts/openapi.yaml`, and the test that guards it says that every path of the facade is a path of the
contract (ADR-019).

The contract declares seven paths of the sandbox: the session, the fork, the status, the ledger, the preview, the commit
and the reset. The specification of the feature of this repository asks for three more reads and one more action:

* the diff of the branch as a read of its own, so that the interface can show the before and after of a revision
  (FR-034, and the task list asks for the route `GET /v1/sandboxes/{sandbox_id}/diff`);
* the history of the branch, so that the visitor can read the events of the branch and see which one was undone
  (the acceptance scenario of the undo asks for it explicitly);
* the answers the branch remembers, marked stale after a reset, because the requirement asks for the answers of the past
  to be marked and not presented as the current result (FR-022, FR-034);
* the undo of the last mutation, which is an action of the visitor and not a mutation of the catalog (FR-037).

The contract of the design package cannot be edited: `docs/v3/` is a converted copy of a package that lives outside the
repository, and the check of the import refuses any difference between the two. So the four routes cannot be declared
there.

## Decision

**The facade serves the routes the specification of the feature requires, and the difference is written down here.**

The four routes are:

| Route | What it answers |
| --- | --- |
| `GET /v1/sandboxes/{sandbox_id}/diff` | The diff of the current revision of the branch, the verdict of the case and the two hashes. |
| `GET /v1/sandboxes/{sandbox_id}/history` | The events of the branch, with the undone one marked, and the answers the branch remembers, each one marked stale or not. |
| `POST /v1/sandboxes/{sandbox_id}/undo` | The undo of the last mutation of the branch, with the revision and the hash of the state it returns to. |

**The shape of the answers of these routes is the shape of the contract of the package wherever the package declares
one.** The reset keeps the resource `Sandbox` of the contract, field for field, and the answers of the routes above
carry the same error resource `Error` and the same header of the version of the schema, so the interface reads one
vocabulary.

**The difference between the facade and the contract is a known and enumerated one.** The guard of the facade changes
from "every path of the facade is a path of the contract" to "every path of the facade is a path of the contract or one
of the paths this decision declares", and the test names the three paths, so a route that nobody decided cannot appear
in the facade. The change of the guard lands with the routes it names, and not before: until then the guard still says
that every path of the facade is a path of the contract, which is true.

**The reset stays exactly as the contract declares it.** The package already declares the reset, so nothing about it
changes: the body of the answer is the resource `Sandbox` and nothing else.

## Alternatives considered

- **Edit the contract of the package.** The folder `docs/v3/` is a converted copy of material that lives outside the
  repository, and the check of the import refuses any difference. An edit would be undone by the next import and would
  make the gate red in the meantime.
- **Refuse the diff, the history and the undo until the frontend is opened.** The specification of the feature asks for
  them, and the value of the sandbox does not depend on the frontend. The routes are the contract of the feature, not of
  the interface.
- **Serve the diff inside the status of the branch.** The resource `Sandbox` of the contract accepts no other field, and
  the diff is a read of its own with its own size, so it does not belong to the status.
- **Model the undo as a kind of the mutation catalog.** The undo is not a change of a record of the case, and the
  catalog holds the kinds that change a record. Mixing them would make the preview of an undo mean something it does
  not.

## Consequences

- The facade has eight paths today, and it serves nothing beyond the contract. It will have eleven when the three
  routes of this decision land, and every one of them is either a path of the contract or a path this decision names.
- The interface has one vocabulary: the error resource, the header of the version and the session cookie of the contract.
- The difference between the package and the repository is visible in the code and in the test, and not hidden in a
  route that nobody declared.
- The reset, the diff, the history and the undo can be read by the interface that is paused, without a translation
  layer.
