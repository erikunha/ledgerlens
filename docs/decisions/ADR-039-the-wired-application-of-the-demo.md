---
type: adr
status: accepted
date: 2026-11-21
---

# ADR-039: The wired application of the demo, one command, one issuer, one store and one vault

Status: accepted. Date: 2026-11-21.

## Context

The demo has two facades. The sandbox of the visitor serves the branch of the visitor
(`ledgerlens/api/sandbox.py`), and the live mode of the demo serves the credential, the catalogue and the run
(`ledgerlens/api/byok.py`). The live run reads the ledger of the branch of the visitor, so the two facades have
to be the same visitor for a live case to mean anything (ADR-038).

The repository does not serve that today. The two commands of the repository are the simulator and the internal
read-only ledger API (`pyproject.toml:56-58`), and `ledgerlens-api` serves the ledger of the records and
nothing else (`ledgerlens/api/ledger_service.py:1`, `:59`, `:141-147`). Neither facade has a command of its
own. The factory of uvicorn serves the live mode without a branch layer, so it refuses every run with
`503 BRANCH_LAYER_MISSING` (`ledgerlens/api/byok.py:1023-1029`). The deployment that really serves a live case
is a program of 91 lines that the reader of the quickstart has to copy into the root of the repository
(`specs/003-r3-bring-your-own-key/quickstart.md:57-150` in the revision `9a935b8`, the one before this milestone).

Three obstacles stand in the way of one application that serves the two facades.

The first is the session. The two facades define the same two routes, `POST /v1/sessions` and
`DELETE /v1/sessions/current`, and the cookie has the same name in the two
(`ledgerlens/api/sandbox.py:98`, `ledgerlens/api/byok.py:100`). Mounted in one application, the first route
that matches answers (`fastapi/routing.py:3414-3416` of the version 0.162.2), so the identity of the visitor
and the completeness of the end of the session would be decided by the order of two lines of code. The answers
of the two routes are not the same: the one of the sandbox declares the modes of the demo
(`ledgerlens/sandbox/session.py:32`) and the one of the live mode declares the live mode too and carries the
disclosure of the storage, the disclosure of the erasure and the no-store headers
(`ledgerlens/api/byok.py:563-574`). The two ends of the session are not the same either: the one of the
sandbox deletes the branches, purges the memory of the case and drops the credentials when it is given a
vault (`ledgerlens/api/sandbox.py:359-370`), and the one of the live mode drops the credentials and nothing
else (`ledgerlens/api/byok.py:594`).

The second is the handlers of the refusals. They live on the application and not on the router
(`ledgerlens/api/sandbox.py:233-264`, `ledgerlens/api/byok.py:485-508`), and an included router brings its
routes and its lifespan and nothing else (`fastapi/routing.py:3414-3425` of the version 0.162.2). A composed
application that forgets one handler answers `500` where the contract asks for the resource `Error`.

The third is the promise of ADR-035. The two facades are two visitors by default and a deployment MAY give them
the same issuer (`docs/decisions/ADR-035-the-facade-of-the-live-mode.md:94-99`). One application with the two
routers mounted does not decide that: it makes the two facades one application, and the identity of the visitor
becomes a side effect of the order of the mounting.

## Decision

**The repository gets a factory of the wired application, a console script that serves it and a test that runs
a live case end to end against it.** The factory is a deployment, written down in the repository, and it wires
the two facades the way ADR-035 allows: one issuer, one store of branches, one base resolver, one branch layer,
one vault of the credentials and one runtime folder.

**The wired application serves ONE session of each kind, and the choice is written in the factory.**

`POST /v1/sessions` is the route of the live mode, because its answer is the superset: the same three fields
plus the capability of the live mode, plus the two disclosures and the no-store headers.

`DELETE /v1/sessions/current` is the route of the sandbox, because it is the complete one: it deletes the
branches of the session, it purges the memory of the case and it drops the credentials of the session, once the
sandbox is given the shared vault.

The other route of each kind is dropped from the composition, by path and by method, and the drop is pinned by
a test. The order of the mounting never decides anything.

**The wired application installs the handlers of the refusals, so a refusal is the resource `Error` of the
contract and never a `500`.** The handler scrubs the message with the vault, the way the live facade does
(`ledgerlens/api/byok.py:493`).

**The two facades keep their own issuer by default and keep their own code.** ADR-035 is not touched: the two
facades alone are two visitors, and the wired application is one visitor because the factory gives them the
same issuer. The plain factory of uvicorn is not touched either: it still serves a live mode without a branch
layer and it still refuses every run with a readable reason.

**The milestone changes the sandbox facade in exactly two ways: it gains a `build_router` of its own, the way
the live facade already has one (`ledgerlens/api/byok.py:525`), and it gains a helper that installs the handlers of
the refusals on an application, so that a composed application does not have to copy them.** No route of the sandbox
changes its behavior, and the sandbox application alone answers exactly as it answers today.

## The interface of the milestone

The two sides of the milestone are coded against each other through this interface, and this ADR fixes it
before the code, so that the two implementers never touch the same file.

In `ledgerlens/api/sandbox.py`, new:

```
def build_router(
    *,
    store: BranchStore,
    layer: BranchLayer,
    session_issuer: SessionIssuer,
    credential_vault: CredentialVault | None = None,
    runtime_dir: Path | str | None = None,
) -> APIRouter:
    """The routes of the sandbox, over the store, the layer and the issuer."""
```

The router holds the eleven routes of the contract of the sandbox, the two routes of the session among them.
`create_app` builds the layer as it does today, builds the router and includes it, so the sandbox application
alone is unchanged.

In `ledgerlens/api/wiring.py`, new:

```
def build_wired_app(
    *,
    settings: Settings | None = None,
    issuer: SessionIssuer | None = None,
    store: BranchStore | None = None,
    vault: CredentialVault | None = None,
    adapter_factory: Callable[[str, str], ProviderAdapter] | None = None,
    runtime_dir: Path | str | None = None,
) -> FastAPI:
    """The application that serves the two facades as one visitor."""


def main(argv: Sequence[str] | None = None) -> None:
    """The command that serves the wired application."""
```

The factory returns one application whose routes are the routes of the two routers, minus the two that are
dropped, with the handlers of the refusals installed on it.

The console script is `ledgerlens-demo = "ledgerlens.api.wiring:main"`, and it takes `--host` and `--port`, the
way `ledgerlens-api` takes them (`ledgerlens/api/ledger_service.py:141-147`).

## What this milestone does not have

- No new route and no new path. The contract of the sandbox and the contract of the live mode stay as they are.
- No call to a real provider. The tests use the fake adapter of the domain.
- No frontend, no page, no component and no client: `apps/web/` is paused and the milestone touches no page.
- No change of the code of the live facade. `ledgerlens/api/byok.py` is not edited.
- No change of the behavior of any route of the sandbox. Only a new `build_router` and a helper that installs the handlers of the refusals.
- No change of the contract of the request of a run and no change of the offline path.
- No change of the promise of ADR-035 and no change of the promise of ADR-038.
- No second process, no new key on the disk and no new dependency.

## What it costs

The repository gains one module, one public function in the sandbox facade, one console script, one test file
and one page of documentation. The deployment gains one command. The reader of the quickstart stops copying a
program of 91 lines.

## Alternatives considered

- **(a) One application, the two routers mounted, the conflict of the two session routes resolved by hand.**
  The cheapest to write and the most fragile: the winner of the two sessions is the order of two lines of
  code, the handlers of the refusals do not travel with the routers, and a drop of one route of each kind
  loses a promise of the visitor.
- **(b) Two processes with the same issuer and the same store.** The visitor is the same visitor, but the vault
  of the credentials lives in the memory of a process, so one process can never drop a key the other holds; the
  file backed store takes its lock per instance (`ledgerlens/sandbox/store.py:400-401`), so the two processes
  have no lock between them; and it is two commands, not one.
- **(c) A program in the repository, under `scripts/`, that the reader runs.** It keeps the promise of ADR-035
  and it is honest, but the reader still copies a file and the program is not tested by the suite: the next
  change of the facades breaks it in silence.
- **(d) The paths of the session of one facade change, so the two never collide.** It breaks the contract of
  the sandbox, which is the published contract of R2, and it breaks the cookie of the visitor.
- **(e) The sandbox application is mounted as a sub-application of the wired one.** The handlers of the refusals
  of the sandbox travel, but the lifespan of the sub-application does not start, so the sweep of the expired
  branches would have to be started by the factory, and the paths of the two sessions would still collide in
  the parent.
- **(f) The live mode keeps its own application and the sandbox is served by it as well, by copying the routes
  of the sandbox into the live application.** It works, but it makes the live facade know the sandbox, and the
  live facade is the branch of the demo, not its parent.

## Consequences

The demo is served with one command: `uv run ledgerlens-demo --port 8010`. The visitor is one visitor over the
two facades, because the issuer is one, and the identity of the visitor is written in the factory instead of
being the order of two lines of code. The end of the session deletes the branch, purges the memory of the case
and drops the key of the visitor, whatever route the visitor used to end it. A refusal of the wired application
is the resource `Error` of the contract and never a `500`. The plain factory of uvicorn keeps its behavior, so
the reader who wants the live mode without a branch layer still gets the readable refusal. The two facades keep
their own issuer by default, so ADR-035 stands: they are two visitors by default, and the factory is a
deployment that gives them the same issuer.
