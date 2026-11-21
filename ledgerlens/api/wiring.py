"""The wired application of the demo: the two facades as one visitor, over one issuer, one store and one vault.

Why it exists: the demo has two facades. The sandbox of the visitor serves the branch of the visitor, and the live
mode serves the credential, the catalogue and the run. A live run reads the ledger of the branch of the visitor
(ADR-038), so the two facades have to be the same visitor for a live case to mean anything. This module is the
deployment that makes them one: it builds one application over one session issuer, one store of branches, one base
resolver, one branch layer, one vault of the credentials and one runtime folder, and it serves the two facades
through it with one command (ADR-039).

What the wiring decides, and why it is written here and not left to the order of two lines of code:

* the two facades declare the same two routes, `POST /v1/sessions` and `DELETE /v1/sessions/current`, and the first
  route that matches would answer (ADR-039). The wired application keeps the session of the live mode, because that
  answer is the superset: the capability of the live mode, the disclosure of the storage, the disclosure of the
  erasure and the no-store headers. It keeps the end of the session of the sandbox, because that one is complete:
  it deletes the branches, it purges the memory of the case and it drops the credentials, because the sandbox is
  given the shared vault. The other route of each kind is dropped by path and by method, here, in the code.
* the handlers of the refusals live on the application and not on the router, because an included router brings its
  routes and its lifespan and nothing else. A composed application that forgets one handler answers `500` where the
  contract asks for the resource `Error`, so this module installs them itself and scrubs the message with the vault,
  the way the live facade does (FR-018, SC-001).

What this module does not decide: the two facades keep their own code and their own issuer by default, and the two
facades alone are two visitors (ADR-035). The plain factory of uvicorn is not touched either: it still serves a live
mode without a branch layer, and it still refuses every run with a readable reason.
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from ledgerlens.api import byok, sandbox
from ledgerlens.api.byok import CODE_INVALID_REQUEST, SessionCapabilities
from ledgerlens.api.cors import install_cors
from ledgerlens.api.live_case import DemoCase
from ledgerlens.api.live_run import LiveRunCoordinator
from ledgerlens.api.sandbox import SCHEMA_VERSION, SCHEMA_VERSION_HEADER, ContractError
from ledgerlens.byok.adapter import ProviderAdapter
from ledgerlens.byok.registry import ProviderRegistry
from ledgerlens.byok.vault import CredentialVault
from ledgerlens.config import Settings, get_settings
from ledgerlens.sandbox.branch import BranchLayer
from ledgerlens.sandbox.factory import build_branch_store
from ledgerlens.sandbox.session import SessionIssuer
from ledgerlens.sandbox.snapshot import BaseResolver
from ledgerlens.sandbox.store import BranchStore
from ledgerlens.sandbox.ttl import CleanupWorker

log = logging.getLogger(__name__)

__all__ = [
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "build_wired_app",
    "main",
]

# The host and the port of the command, the way the internal ledger API takes them. The port is not the one of the
# internal ledger API, because the two commands serve two things and a machine runs both.
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8010
# The name of the file with the key of the sessions of the wired application. The two facades have a file of their
# own, and the wired application has one file of its own: one issuer, one key, one visitor.
SESSION_KEY_FILENAME = "shared-session.key"
# The folder of the runtime that holds the base of the scenarios, the same name the sandbox facade uses.
BASES_FOLDER_NAME = "sandbox-bases"


def _server_clock() -> datetime:
    """The clock of the server: the moment of this process, in UTC.

    Why the clock is never taken from a request: the expiry of a branch is decided by the server and never by the
    visitor (FR-031).
    """
    return datetime.now(UTC)


def build_wired_app(
    *,
    settings: Settings | None = None,
    issuer: SessionIssuer | None = None,
    store: BranchStore | None = None,
    vault: CredentialVault | None = None,
    adapter_factory: Callable[[str, str], ProviderAdapter] | None = None,
    runtime_dir: Path | str | None = None,
) -> FastAPI:
    """The application that serves the two facades as one visitor.

    One issuer, one store of branches, one base resolver, one branch layer, one vault of the credentials and one
    runtime folder: that is what makes the two facades the same visitor (ADR-035, ADR-039). The issuer, the store
    and the vault may be injected, so a test owns them; without them they come from the configuration, the way the
    sandbox facade builds them.

    The branch layer is the layer of the sandbox, and it is what holds the ledger of the visitor: the run reads the
    branch of the visitor and never the ledger of the configuration (ADR-038).

    The two routes that the two facades declare with the same path and the same method are resolved here: the
    session of the live mode is kept, the end of the session of the sandbox is kept, and the other one of each kind
    is dropped by path and by method. The order of the mounting never decides anything (ADR-039).
    """
    the_settings = settings if settings is not None else get_settings()
    runtime = Path(runtime_dir) if runtime_dir is not None else the_settings.runtime_dir
    the_vault = vault if vault is not None else CredentialVault()
    the_store = store if store is not None else build_branch_store(the_settings)
    the_issuer = (
        issuer
        if issuer is not None
        else SessionIssuer(
            runtime / SESSION_KEY_FILENAME,
            ttl_seconds=the_settings.sandbox_branch_absolute_ttl_seconds,
        )
    )
    layer = BranchLayer(
        the_store,
        # The base of a scenario is built in the runtime folder of the application, so an injected folder keeps the
        # whole material of the demo inside itself and the repository is never written to.
        BaseResolver(runtime / BASES_FOLDER_NAME),
        idle_ttl_seconds=the_settings.sandbox_branch_idle_ttl_seconds,
        absolute_ttl_seconds=the_settings.sandbox_branch_absolute_ttl_seconds,
        clock=_server_clock,
    )
    registry = ProviderRegistry()
    # The case of the demo, with the runtime folder of the application: the memory of the case lives in the folder of
    # the session of the visitor and not in the folder of the configuration (ADR-038).
    case = DemoCase(runtime_dir=runtime)
    coordinator = LiveRunCoordinator(
        registry=registry,
        vault=the_vault,
        adapter_factory=adapter_factory,
        executor=case,
    )
    # The capabilities of the sessions the live mode issues. The live mode is the one that issues the sessions of the
    # wired application, so it is the one that remembers what those sessions may run (FR-024).
    capabilities = SessionCapabilities()

    sandbox_router = sandbox.build_router(
        store=the_store,
        layer=layer,
        session_issuer=the_issuer,
        credential_vault=the_vault,
        runtime_dir=runtime,
    )
    live_router = byok.build_router(
        vault=the_vault,
        registry=registry,
        issuer=the_issuer,
        coordinator=coordinator,
        case=case,
        capabilities=capabilities,
        branch_layer=layer,
        runtime_dir=runtime,
    )

    # The session of the wired application is the one of the live mode: its answer is the superset of the two, with
    # the capability of the live mode, the two disclosures and the no-store headers. The session of the sandbox is
    # dropped, because a visitor of the wired application gets one session and not two (ADR-039).
    _drop(
        sandbox_router,
        path="/v1/sessions",
        method="POST",
        why="the session of the wired application is the one of the live mode",
    )
    # The end of the session of the wired application is the one of the sandbox: it deletes the branches of the
    # session, it purges the memory of the case and it drops the credentials, because the sandbox is given the
    # shared vault. The end of the session of the live mode is dropped, because it drops the credentials and nothing
    # else, and the branch of the visitor and the memory of the case would live on (ADR-039).
    _drop(
        live_router,
        path="/v1/sessions/current",
        method="DELETE",
        why="the end of the session of the wired application is the one of the sandbox",
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        """Starts the two sweepers of the deployment and stops them when the application stops.

        Why the sweep of the expired branches lives here: the routers bring their routes and nothing else, so the
        job that deletes the branches nobody touches belongs to the application that serves them (ADR-029).

        Why the sweeper of the credentials lives here: a credential that nobody touches still has to die, and the
        vault of the application is the one that holds it (FR-022, SC-011).
        """
        the_vault.start_sweeper()
        worker = CleanupWorker(the_store, clock=_server_clock)
        worker.start()
        try:
            yield
        finally:
            worker.stop()
            the_vault.stop_sweeper()

    app = FastAPI(
        title="LedgerLens demo",
        description="The demo of the visitor: the branch of the sandbox and the live mode, as one visitor.",
        lifespan=lifespan,
    )

    # The CORS of the browser of the visitor, and only when the deployment declares the origins: a deployment that
    # declares none answers exactly as it answered before (ADR-040). The middleware adds no route, so the list of the
    # routes of the wired application, which ADR-039 pins, does not change.
    install_cors(app, allowed_origins=the_settings.cors_origins)

    @app.exception_handler(ContractError)
    async def contract_error(_request: Request, error: ContractError) -> JSONResponse:
        """The refusals of the wired application are the resource `Error` of the contract.

        The message is scrubbed before it is written: the facade writes what it writes, and a refusal that carries a
        key would carry it out of the process (FR-018, SC-001).
        """
        body = error.body()
        body["message"] = the_vault.scrub(str(body["message"]))
        return JSONResponse(
            status_code=error.status_code,
            content=body,
            headers={SCHEMA_VERSION_HEADER: SCHEMA_VERSION},
        )

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_request: Request, _error: RequestValidationError) -> JSONResponse:
        """The body of the framework is not the resource `Error`, so the answer is built here."""
        error = ContractError(422, CODE_INVALID_REQUEST, "the request does not match the contract")
        return JSONResponse(
            status_code=error.status_code,
            content=error.body(),
            headers={SCHEMA_VERSION_HEADER: SCHEMA_VERSION},
        )

    # The order of the two mounts decides nothing: the two routes that would collide are already dropped above.
    app.include_router(sandbox_router)
    app.include_router(live_router)
    return app


def _drop(router: APIRouter, *, path: str, method: str, why: str) -> None:
    """Drops one route of a router, by path and by method.

    Why the drop is explicit: the two facades declare the same two routes, and the visitor must get the same answer
    whatever the order of two lines of code is (ADR-039).

    Why a drop that finds nothing is an error and not a warning: a deployment that drops a route that is not there
    serves something else than the one it was written for, and it says so instead of answering quietly.
    """
    kept: list[Any] = []
    dropped = 0
    for route in router.routes:
        if _is_the_route(route, path=path, method=method):
            dropped += 1
            continue
        kept.append(route)
    if dropped != 1:
        raise RuntimeError(f"the route {method} {path} is not one of the routes of the router, so it cannot be dropped")
    router.routes[:] = kept
    if any(_is_the_route(route, path=path, method=method) for route in router.routes):
        # The drop has to be visible: a framework that keeps the list of the routes somewhere else would serve the
        # route anyway, and the visitor would get the answer of the other facade.
        raise RuntimeError(f"the route {method} {path} is still in the router, so the drop did not take effect")
    log.info("the route %s %s is dropped from the wired application: %s", method, path, why)


def _is_the_route(route: Any, *, path: str, method: str) -> bool:
    """True when the route answers that path with that method.

    Why the method is read and not only the path: the two facades share the path of the session, and only the method
    says which route of the session is which.
    """
    if not isinstance(route, APIRoute):
        return False
    return route.path == path and method in (route.methods or set())


def _serve(app: FastAPI, *, host: str, port: int) -> None:
    """Serves the application with uvicorn, the way the internal ledger API does."""
    import uvicorn

    uvicorn.run(app, host=host, port=port)


def main(argv: Sequence[str] | None = None) -> None:
    """The `ledgerlens-demo` command: it serves the wired application of the demo.

    Why the command is not the one of the internal ledger API: that one serves the ledger of the records and keeps
    its name, and the demo of the visitor is another thing (ADR-039).
    """
    parser = argparse.ArgumentParser(prog="ledgerlens-demo", description="Serve the wired application of the demo.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    _serve(build_wired_app(), host=args.host, port=args.port)
