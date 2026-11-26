"""The sandbox facade: the routes of the versioned contract of the design package.

Why it exists: the visitor works in a browser and needs two things first, a private branch of a published case and the
status of that branch. The facade follows `docs/design/contracts/openapi.yaml`, so the interface that is paused can be
written against the contract without a translation layer.

What the contract fixes:

* the paths are `/v1/sessions`, `/v1/sandboxes` and `/v1/sandboxes/{sandbox_id}`, and the parameter is `sandbox_id`;
* the body of a sandbox answer is exactly the resource `Sandbox`: `id`, `base_snapshot_id`, `snapshot_sha256`,
  `revision` and `expires_at`, and it accepts no other field;
* the body of a session is exactly the resource `Session`: `id`, `expires_at` and `mode_capabilities`;
* an error is exactly the resource `Error`: `code`, `message`, `retryable` and `request_id`;
* the session is the cookie `ledgerlens_session`, HttpOnly and SameSite Lax, and never a header nor a body field.

Where the rest of the branch lives: the resource `Sandbox` of the contract carries no field for the current canonical
hash of the branch and none for its state, and it accepts no other field. The two therefore travel in the headers
`X-LedgerLens-Branch-Hash` and `X-LedgerLens-Branch-State`, and the version of the answers travels in the header
`X-LedgerLens-Schema-Version` (FR-042). The domain layer keeps them all three.

Four paths of the facade are beyond the contract of the design package, and ADR-023 and ADR-047 declare them: the diff
of the branch, the history of the branch, the undo of the last mutation and the stream of the lifecycle of the branch.
The contract of the package cannot be edited, so the difference is written down here and in the test that guards the
paths.

The cleanup of the expired branches is a job of the process, not a path: the lifespan of the app starts a daemon
thread that sweeps the expired branches every thirty seconds, and the same sweep runs from the command line, so the
two ways of cleaning up cannot disagree (ADR-029).

The end of a session is a path, and it purges the case memory of the session together with its branches: the memory
of an anonymous visitor dies with the visitor, and the folder it lived in does not stay under an identifier that
nobody can reach again (ADR-030).

No route accepts a file path, a SQL statement or a URL, and no route writes to the published snapshot (FR-041).

The runtime folder of the facade holds the key of the sessions, the memory of the sessions and the base of the
scenarios, so a folder that is injected keeps the whole material of the sandbox inside itself.

The facade has a router of its own, the way the live facade has one, so that a deployment may mount the two facades
in one application (ADR-039). The router carries the routes and nothing else: the handlers of the refusals live on the
application, because an included router brings its routes and its lifespan and nothing else. The routes of the
application are the routes of the router, written once, so that the two answer the same thing.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, FastAPI, Header, Query, Request, Security
from fastapi import Path as PathParam
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.security import APIKeyCookie
from pydantic import BaseModel, ConfigDict, Field

from ledgerlens.byok.vault import CredentialVault
from ledgerlens.config import Settings, get_settings
from ledgerlens.sandbox.branch import (
    BRANCH_ID_PREFIX,
    BranchExpired,
    BranchHashMismatch,
    BranchLayer,
    InvalidSessionId,
    SandboxBranch,
)
from ledgerlens.sandbox.events import (
    CLOSED_REASON_EXPIRED,
    CLOSED_REASON_GONE,
    EVENT_BRANCH_EXPIRED,
    EVENT_MUTATION_COMMITTED,
    EVENT_RESET,
    EVENT_STREAM_CLOSED,
    EVENT_UNDONE,
    HEARTBEAT_INTERVAL_SECONDS,
    EventHub,
    StreamEvent,
    committed_fields,
    expired_fields,
    format_event,
    opened_fields,
    reset_fields,
    undone_fields,
)
from ledgerlens.sandbox.factory import build_branch_store
from ledgerlens.sandbox.memory import purge_session_memory
from ledgerlens.sandbox.mutation import (
    CODE_INVALID_PAYLOAD,
    CODE_INVALID_REQUEST,
    CODE_READ_ONLY_FIELD,
    CODE_RESOURCE_LIMIT,
    UNDO_KIND,
    MutationCommand,
    MutationRejected,
    read_only_field_in,
    status_for_code,
)
from ledgerlens.sandbox.rate_limit import RateLimiter
from ledgerlens.sandbox.session import InvalidSession, SessionIssuer
from ledgerlens.sandbox.snapshot import BaseResolver, UnknownScenario
from ledgerlens.sandbox.store import BranchNotFound, BranchStore, SandboxBranchRow
from ledgerlens.sandbox.ttl import CleanupWorker, is_expired

log = logging.getLogger(__name__)

# The version of the shape of the answers. It travels in a header, because the resource `Sandbox` accepts no other
# field and the interface reads that resource.
SCHEMA_VERSION = "1"
SCHEMA_VERSION_HEADER = "X-LedgerLens-Schema-Version"
# The current canonical hash of the branch and its state, which the resource `Sandbox` has no field for.
BRANCH_HASH_HEADER = "X-LedgerLens-Branch-Hash"
BRANCH_STATE_HEADER = "X-LedgerLens-Branch-State"
# The headers of the no store. The state of a branch of a visitor is not to be kept anywhere, and a cache that keeps
# it would keep the answer of another visitor (FR-042).
#
# Why they live here and not in the module of the live mode: this module is BELOW the module of the live mode in the
# graph of the imports, so the live mode imports them from here and there is only one definition of the triad.
NO_STORE_HEADERS = {
    "Cache-Control": "no-store",
    "Pragma": "no-cache",
    "Expires": "0",
}
# The cookie of the contract: the opaque session of the visitor.
SESSION_COOKIE = "ledgerlens_session"
# The security scheme of the contract: an apiKey in the cookie, and it is not the identity of a person.
SESSION_SCHEME = APIKeyCookie(
    name=SESSION_COOKIE,
    scheme_name="anonymousSession",
    description="Opaque signed HttpOnly demo session cookie, not user identity.",
    auto_error=False,
)
BRANCH_ID_PATTERN = rf"^{BRANCH_ID_PREFIX}[0-9a-f]{{24}}$"
SCENARIO_ID_PATTERN = r"^S[0-9]{2}$"
# The refusal of a branch the session does not own. It says nothing about the owner and nothing about the existence.
GENERIC_NOT_FOUND = "no sandbox is available for this session"


class SandboxRequest(BaseModel):
    """The body of a fork: exactly the scenario id.

    The contract accepts no other field, so a body with one is refused.
    """

    model_config = ConfigDict(extra="forbid")

    scenario_id: str = Field(pattern=SCENARIO_ID_PATTERN)


class ContractError(Exception):
    """An answer that is not a resource of the contract, but the resource `Error`."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.retryable = retryable
        # The headers of the answer of the refusal, when the refusal needs one. The wait of a refusal of the rate of
        # the requests travels in the header `Retry-After` and never in the body, because the body of the contract is
        # the resource `Error` field for field (ADR-047).
        self._headers = dict(headers) if headers else {}

    @property
    def headers(self) -> Mapping[str, str]:
        """The headers of the answer of the refusal. Empty when the refusal needs none."""
        return dict(self._headers)

    def body(self) -> dict[str, Any]:
        """The resource `Error` of the contract, field for field."""
        return {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
            "request_id": f"req_{secrets.token_hex(8)}",
        }


def create_app(
    store: BranchStore | None = None,
    base_resolver: BaseResolver | None = None,
    session_issuer: SessionIssuer | None = None,
    clock: Callable[[], datetime] | None = None,
    runtime_dir: Path | str | None = None,
    credential_vault: CredentialVault | None = None,
    event_hub: EventHub | None = None,
) -> FastAPI:
    """Builds the app over a store, a base resolver and a session issuer.

    Without arguments the store comes from the configuration: the database one when the setting of the database url
    is filled, the file backed one otherwise. The base is built from the published sample and the session is signed
    with a key of the runtime folder, so the facade runs with no database and no key. The clock is the server clock,
    and it is injected so that a test can move the expiry.

    The runtime folder is the one of the configuration, and it is injected so that a test can point the scope of the
    session at a temporary folder: the key of the sessions, the memory of the sessions and the base of the scenario
    live there. Without an injected folder the base is built in the runtime folder of the configuration, exactly as
    it was before.

    The vault of the credentials is given to the application and never read from a global: the end of a session drops
    the credentials of that session from the vault the application was given, and not from a vault of the process
    that may belong to another application (FR-022, ADR-035).

    The hub of the events of the lifecycle is given to the application and never read from a global: it belongs to
    the process, like the job of the cleanup, and it holds the subscribers of a branch and the counter of its
    sequence and never an event (ADR-047).

    The routes of the facade are registered on the application itself and the router of the sandbox carries the same
    routes for the deployment that mounts the two facades in one application, so the sandbox application alone answers
    exactly as it answered before (ADR-039).
    """
    settings = get_settings()
    runtime = Path(runtime_dir) if runtime_dir is not None else settings.runtime_dir
    branch_store = store if store is not None else build_branch_store(settings)
    issuer = session_issuer or SessionIssuer(
        runtime / "sandbox-session.key",
        ttl_seconds=settings.sandbox_branch_absolute_ttl_seconds,
    )
    # The clock of the server, shared by the layer and by the job of the cleanup, so the branch that the layer
    # refuses and the branch that the job deletes are the same branch at the same moment (FR-031, ADR-029).
    server_clock = clock or (lambda: datetime.now(UTC))
    # The counter of the rate of the requests of a session. It lives in the memory of the process, so the limit is
    # per process, and it counts with the clock of the server (ADR-047).
    limiter = RateLimiter(
        limit=settings.sandbox_rate_limit_requests,
        window_seconds=settings.sandbox_rate_limit_window_seconds,
        clock=server_clock,
    )
    # The hub of the events of the lifecycle of a branch. It lives in the memory of the process, like the job of the
    # cleanup, and it holds the subscribers of a branch and the counter of its sequence and never an event (ADR-047).
    hub = event_hub or EventHub(clock=server_clock)
    layer = BranchLayer(
        branch_store,
        # The base of a scenario is built in the runtime folder of the facade, so an injected folder keeps the whole
        # material of the sandbox inside itself and the repository is never written to.
        base_resolver if base_resolver is not None else BaseResolver(runtime / "sandbox-bases"),
        idle_ttl_seconds=settings.sandbox_branch_idle_ttl_seconds,
        absolute_ttl_seconds=settings.sandbox_branch_absolute_ttl_seconds,
        # The limits of the resources of one branch come from the settings of the configuration, so that a
        # deployment can change them without touching the code of the domain (ADR-047).
        max_committed_mutations=settings.sandbox_max_committed_mutations,
        max_events=settings.sandbox_max_events,
        clock=server_clock,
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        """Starts the job of the cleanup when the app starts and stops it when the app stops (ADR-029).

        Why the job lives in the lifespan and not in the module: a thread that starts with the module would run in
        every test that builds the app, and a test that moves the clock would race with the sweep. The sweep is a
        daemon thread, so a process that is killed does not wait for it.

        Why the sweep is the same function the command runs: the two ways of cleaning up cannot disagree.
        """
        worker = CleanupWorker(branch_store, clock=server_clock)
        worker.start()
        try:
            yield
        finally:
            worker.stop()

    app = FastAPI(
        title="LedgerLens sandbox",
        description="Private branches of the published cases.",
        lifespan=lifespan,
    )

    # The handlers of the refusals live on the application and not on the router: an included router brings its routes
    # and its lifespan and nothing else, so a refusal raised inside a route of an included router would be a `500`
    # where the contract asks for the resource `Error` (ADR-039).
    install_refusal_handlers(app, credential_vault=credential_vault)

    # The routes of the facade are registered on the application itself, exactly as they were before the router
    # existed: an application that includes a router does not list the routes of the router in `app.routes`, and the
    # guard of the paths of the facade reads that list (ADR-023, ADR-039).
    _the_routes_of_the_sandbox(
        app,
        store=branch_store,
        layer=layer,
        session_issuer=issuer,
        credential_vault=credential_vault,
        runtime_dir=runtime,
        clock=server_clock,
        rate_limiter=limiter,
        event_hub=hub,
    )
    return app


def install_refusal_handlers(app: FastAPI, *, credential_vault: CredentialVault | None = None) -> None:
    """Installs the handlers of the refusals on an application.

    Why they live on the application and not on the router: an included router brings its routes and its lifespan and
    nothing else, so a composed application that forgets one handler answers `500` where the contract asks for the
    resource `Error` (ADR-039).

    Why the message of a refusal is scrubbed with the vault when the vault was given: a refusal never carries a value
    of the visitor, and the vault is the only one that knows the exact text of the key it holds (FR-018, SC-001). The
    live facade scrubs its refusals the same way.
    """

    @app.exception_handler(ContractError)
    async def contract_error(_request: Request, error: ContractError) -> JSONResponse:
        body = error.body()
        if credential_vault is not None:
            body["message"] = credential_vault.scrub(str(body["message"]))
        # The headers of the refusal are merged into the answer of the facade: the wait of a refusal of the rate of
        # the requests travels in the header `Retry-After`, and the header of the answer is not a field of the body
        # of the contract (ADR-047).
        headers = {SCHEMA_VERSION_HEADER: SCHEMA_VERSION, **error.headers}
        return JSONResponse(
            status_code=error.status_code,
            content=body,
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_request: Request, _error: RequestValidationError) -> JSONResponse:
        # The default body of FastAPI is not the resource `Error` of the contract, so the answer is built here.
        error = ContractError(422, "INVALID_REQUEST", "the request does not match the contract")
        return JSONResponse(
            status_code=error.status_code,
            content=error.body(),
            headers={SCHEMA_VERSION_HEADER: SCHEMA_VERSION},
        )


def build_router(
    *,
    store: BranchStore,
    layer: BranchLayer,
    session_issuer: SessionIssuer,
    credential_vault: CredentialVault | None = None,
    runtime_dir: Path | str | None = None,
    clock: Callable[[], datetime] | None = None,
    event_hub: EventHub | None = None,
    settings: Settings | None = None,
) -> APIRouter:
    """The routes of the sandbox, over the store, the layer and the issuer.

    Why the router exists: ADR-039 mounts the sandbox and the live mode in one application, and a router is what an
    application mounts. The routes are the ones the contract of the design package fixes, and no route of them changes
    its behavior because of the router.

    Why the router takes what it needs and reads no global: the router of the sandbox is mounted by a deployment, and
    that deployment gives the two facades the same issuer, the same store and the same vault on purpose, because the
    two facades are one visitor only when a deployment wires them that way (ADR-035, ADR-039).

    Why the handlers of the refusals are not here: an included router brings its routes and nothing else, so a
    composed application installs the handlers on itself (ADR-039).

    Why the clock is an argument: the rate of the requests and the life of a branch are decided by the server, and a
    deployment that injects a clock into the layer injects the same one into the limits (ADR-047).

    Why the hub is an argument: the hub of the events of the lifecycle belongs to the process, and the deployment
    that mounts the two facades gives them the same hub on purpose, because the two facades are one visitor only
    when a deployment wires them that way (ADR-035, ADR-039, ADR-047).

    Why the settings are an argument: the limits of the facade are read from the configuration, and a deployment
    that INJECTS a configuration expects the limits of the facade to be the ones it injected. A router that read
    the environment behind the back of the deployment would keep the defaults of the environment and would answer
    429 or would accept a branch that the injected configuration forbids (ADR-047).
    """
    router = APIRouter()
    _the_routes_of_the_sandbox(
        router,
        store=store,
        layer=layer,
        session_issuer=session_issuer,
        credential_vault=credential_vault,
        runtime_dir=runtime_dir,
        clock=clock,
        event_hub=event_hub,
        settings=settings,
    )
    return router


def _the_routes_of_the_sandbox(
    target: FastAPI | APIRouter,
    *,
    store: BranchStore,
    layer: BranchLayer,
    session_issuer: SessionIssuer,
    credential_vault: CredentialVault | None = None,
    runtime_dir: Path | str | None = None,
    clock: Callable[[], datetime] | None = None,
    rate_limiter: RateLimiter | None = None,
    event_hub: EventHub | None = None,
    settings: Settings | None = None,
) -> None:
    """The twelve routes of the contract of the sandbox, registered on the target.

    Why the routes are written once and not twice: the application of the sandbox and the router of the sandbox have to
    answer the same thing, and two copies of the same route drift apart.

    Why the application registers the routes on itself and does not include the router: an application that includes a
    router does not list the routes of the router in `app.routes`, and the guard of the paths of the facade reads that
    list (ADR-023). The router exists for the deployment that mounts the two facades in one application (ADR-039).

    Why the target is an application or a router: the decorator of a route is the same on both, so the routes of the
    facade are the routes of the contract in either case.

    Why the counter of the rate and the clock are arguments: the limits of the facade are decided by the server and
    never by the visitor, and the same clock has to answer for the life of a branch and for the rate of the requests
    (ADR-047).

    Why the hub is an argument: the hub of the events of the lifecycle belongs to the process, and the route that
    publishes the events of a branch and the route that opens the stream of that branch have to see the same counter
    (ADR-047).

    Why the settings are an argument: the limits of the facade, the rate of the requests and the cap of the live
    branches of a session, are read from the configuration that the deployment injected. A facade that read the
    environment behind the back of the deployment would keep the defaults of the environment, and the limits that
    the deployment asked for would be limits that nobody enforces (ADR-047).
    """
    the_settings = settings if settings is not None else get_settings()
    runtime = Path(runtime_dir) if runtime_dir is not None else the_settings.runtime_dir
    branch_store = store
    issuer = session_issuer
    server_clock = clock or (lambda: datetime.now(UTC))
    limiter = rate_limiter or RateLimiter(
        limit=the_settings.sandbox_rate_limit_requests,
        window_seconds=the_settings.sandbox_rate_limit_window_seconds,
        clock=server_clock,
    )
    # The hub of the events of the lifecycle of a branch: the subscribers of a branch and the counter of its
    # sequence, and never an event (ADR-047).
    hub = event_hub or EventHub(clock=server_clock)

    def _count_the_request(request: Request) -> None:
        """The rate of the requests of the session: one request is counted and the one over the rate is refused.

        Why the session and never the address of the client: the facade has no trusted address of the visitor, because
        the repository has no policy of the headers of a proxy, and the session is the only identity the facade can
        trust (ADR-047).

        Why a request without a valid session is not counted: the counter holds the requests of a session, and a
        request that carries no session is refused with `401` by the route itself.

        Why the refusal carries the wait: the header `Retry-After` carries the number of seconds until the oldest
        request of the window falls out of it, and the flag `retryable` is true because the same request, later, is
        expected to answer (ADR-047).
        """
        try:
            session = issuer.session_id(request.cookies.get(SESSION_COOKIE))
        except InvalidSession:
            return
        decision = limiter.acquire(session)
        if decision.allowed:
            return
        raise ContractError(
            status_for_code(CODE_RESOURCE_LIMIT),
            CODE_RESOURCE_LIMIT,
            f"the session made more than {limiter.limit} requests in {limiter.window_seconds} seconds",
            retryable=True,
            headers={"Retry-After": str(decision.retry_after_seconds)},
        )

    @target.post("/v1/sessions", status_code=201)
    def issue_session() -> JSONResponse:
        """Issues the session of the visitor and sets the cookie of the contract."""
        session = issuer.issue()
        body = {
            "id": session.id,
            "expires_at": session.expires_at.isoformat(),
            "mode_capabilities": list(session.mode_capabilities),
        }
        response = JSONResponse(status_code=201, content=body, headers={SCHEMA_VERSION_HEADER: SCHEMA_VERSION})
        response.set_cookie(
            SESSION_COOKIE,
            issuer.cookie_value(session),
            httponly=True,
            samesite="lax",
            path="/",
            max_age=issuer.ttl_seconds,
        )
        return response

    # The rate of the requests of the session is a dependency of every route but the one that issues the session: a
    # visitor that asks for a session has no session yet, and the route that issues it spends no quota of one. The
    # dependency is added after the route of the session because the dependencies of a router are copied into the
    # routes that are registered after them, and every route that follows counts one request of its session
    # (ADR-047).
    _the_router_of(target).dependencies.append(Depends(_count_the_request))

    @target.delete("/v1/sessions/current", status_code=204)
    def end_session(cookie: Annotated[str | None, Security(SESSION_SCHEME)]) -> Response:
        """Ends the session of the visitor, purges its branches and purges its case memory.

        The memory of the session dies with the session (ADR-030): the case memory of an anonymous visitor must not
        lie around under an identifier that nobody can reach again. The purge is tolerant: a folder that cannot be
        removed is logged and does not fail the route.

        The credentials of the session die with it too: the key of a visitor lives in the memory of the process and
        nowhere else, so the end of the session drops the credentials that session holds (FR-022). The drop is
        tolerant in the same way, because a vault that refuses never fails the route, and it comes from the vault the
        application was given, so the purge of a session drops from the vault of the application it belongs to.
        """
        session = _session(cookie, issuer)
        for row in branch_store.list_branches(session):
            branch_store.delete_branch(row.branch_id, session)
        # The counter of the rate of the session dies with the session: the memory of an anonymous visitor dies with
        # the visitor (ADR-030, ADR-047).
        limiter.forget(session)
        try:
            purge_session_memory(session, runtime)
        except Exception as error:  # pragma: no cover - the purge of the memory never fails the route.
            log.warning("the memory of the session could not be purged: %s", error)
        if credential_vault is not None:
            try:
                credential_vault.forget_session(session)
            except Exception as error:  # pragma: no cover - the drop of the credentials never fails the route.
                log.warning("the credentials of the session could not be dropped: %s", error)
        # The version of the shape of the answers travels in the header of every answer of the facade (FR-042).
        response = Response(status_code=204, headers={SCHEMA_VERSION_HEADER: SCHEMA_VERSION})
        response.delete_cookie(SESSION_COOKIE, path="/")
        return response

    @target.post("/v1/sandboxes")
    def fork(
        payload: SandboxRequest,
        cookie: Annotated[str | None, Security(SESSION_SCHEME)],
    ) -> JSONResponse:
        """Forks the published case into a private branch of the session.

        The answer is `201` when the fork creates a branch and `200` when the reuse rule returns the branch that
        already exists: the difference matters to a client.

        The cap of the live branches of the session is checked before the fork, and it refuses only a fork that would
        create a branch (ADR-047).
        """
        session = _session(cookie, issuer)
        _check_the_cap_of_the_branches(
            branch_store,
            session,
            payload.scenario_id,
            cap=the_settings.sandbox_session_branch_cap,
            now=server_clock(),
        )
        try:
            outcome = layer.fork(session, payload.scenario_id)
        except UnknownScenario:
            raise ContractError(404, "UNKNOWN_SCENARIO", "no such scenario") from None
        except InvalidSessionId:
            raise ContractError(401, "SESSION_REQUIRED", "no valid session") from None
        return _sandbox_response(outcome.branch, 201 if outcome.created else 200)

    @target.get("/v1/sandboxes/{sandbox_id}")
    def read_sandbox(
        sandbox_id: Annotated[str, PathParam(pattern=BRANCH_ID_PATTERN)],
        cookie: Annotated[str | None, Security(SESSION_SCHEME)],
    ) -> JSONResponse:
        """The state of the branch: the revision, the hashes, the creation and the expiry."""
        session = _session(cookie, issuer)
        try:
            branch = layer.status(session, sandbox_id)
        except BranchNotFound:
            raise ContractError(404, "NOT_FOUND", GENERIC_NOT_FOUND) from None
        except InvalidSessionId:
            raise ContractError(401, "SESSION_REQUIRED", "no valid session") from None
        except BranchExpired as expired:
            raise ContractError(410, "BRANCH_EXPIRED", str(expired)) from None
        except BranchHashMismatch as mismatch:
            raise ContractError(409, mismatch.code, mismatch.message) from None
        return _sandbox_response(branch, 200)

    @target.post("/v1/sandboxes/{sandbox_id}/mutations/preview")
    def preview_mutation(
        sandbox_id: Annotated[str, PathParam(pattern=BRANCH_ID_PATTERN)],
        body: dict[str, Any],
        cookie: Annotated[str | None, Security(SESSION_SCHEME)],
    ) -> JSONResponse:
        """What a typed mutation would do to the branch, computed without writing anything.

        The answer carries the values before and after as decimal texts with their currency, the records the
        mutation touches, the invariants of the domain and the verdict of the case.
        """
        session = _session(cookie, issuer)
        command = _command_of(body)
        try:
            preview = layer.preview_mutation(session, sandbox_id, command)
        except MutationRejected as refusal:
            raise ContractError(status_for_code(refusal.code), refusal.code, refusal.message) from None
        except BranchNotFound:
            raise ContractError(404, "NOT_FOUND", GENERIC_NOT_FOUND) from None
        except InvalidSessionId:
            raise ContractError(401, "SESSION_REQUIRED", "no valid session") from None
        except BranchExpired as expired:
            raise ContractError(410, "BRANCH_EXPIRED", str(expired)) from None
        except BranchHashMismatch as mismatch:
            raise ContractError(409, mismatch.code, mismatch.message) from None
        return _answer(preview.to_dict())

    @target.post("/v1/sandboxes/{sandbox_id}/mutations")
    def commit_mutation(
        sandbox_id: Annotated[str, PathParam(pattern=BRANCH_ID_PATTERN)],
        body: dict[str, Any],
        cookie: Annotated[str | None, Security(SESSION_SCHEME)],
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
        if_match: Annotated[str, Header(alias="If-Match")],
    ) -> JSONResponse:
        """The commit of a typed mutation: the events, the revision and the canonical hash move together.

        The `Idempotency-Key` header names the request and the `If-Match` header carries the revision the visitor
        believes the branch is at. The answer carries the new revision, the new canonical hash and the diff.
        """
        session = _session(cookie, issuer)
        command = _command_of(body, idempotency_key=idempotency_key, expected_revision=_revision_of(if_match))
        try:
            result = layer.commit_mutation(session, sandbox_id, command)
        except MutationRejected as refusal:
            raise ContractError(status_for_code(refusal.code), refusal.code, refusal.message) from None
        except BranchNotFound:
            raise ContractError(404, "NOT_FOUND", GENERIC_NOT_FOUND) from None
        except InvalidSessionId:
            raise ContractError(401, "SESSION_REQUIRED", "no valid session") from None
        except BranchExpired as expired:
            raise ContractError(410, "BRANCH_EXPIRED", str(expired)) from None
        except BranchHashMismatch as mismatch:
            raise ContractError(409, mismatch.code, mismatch.message) from None
        if not result.replayed:
            # The branch moved, so the lifecycle of the branch moves too. A delivery that is replayed moves nothing
            # and publishes nothing, because the branch did not change (ADR-047).
            hub.publish(
                sandbox_id,
                EVENT_MUTATION_COMMITTED,
                committed_fields(
                    revision=result.revision,
                    canonical_hash=result.canonical_hash,
                    command_id=result.command_id,
                    kind=result.kind,
                ),
            )
        return _answer(result.to_dict())

    @target.post("/v1/sandboxes/{sandbox_id}/reset")
    def reset_sandbox(
        sandbox_id: Annotated[str, PathParam(pattern=BRANCH_ID_PATTERN)],
        cookie: Annotated[str | None, Security(SESSION_SCHEME)],
    ) -> JSONResponse:
        """The branch back at the published base: no events, revision zero and the hash of the fork.

        The body of the answer is exactly the resource `Sandbox` of the contract, field for field, and the headers
        carry the version of the schema, the current canonical hash of the branch and its state, like the answers of
        the other routes.
        """
        session = _session(cookie, issuer)
        try:
            branch = layer.reset(session, sandbox_id)
        except BranchNotFound:
            raise ContractError(404, "NOT_FOUND", GENERIC_NOT_FOUND) from None
        except InvalidSessionId:
            raise ContractError(401, "SESSION_REQUIRED", "no valid session") from None
        except BranchExpired as expired:
            raise ContractError(410, "BRANCH_EXPIRED", str(expired)) from None
        except BranchHashMismatch as mismatch:
            raise ContractError(409, mismatch.code, mismatch.message) from None
        hub.publish(
            sandbox_id,
            EVENT_RESET,
            reset_fields(
                revision=branch.revision,
                canonical_hash=branch.current_canonical_hash,
                base_canonical_hash=branch.base_canonical_hash,
            ),
        )
        return _sandbox_response(branch, 200)

    @target.post("/v1/sandboxes/{sandbox_id}/undo")
    def undo_sandbox(
        sandbox_id: Annotated[str, PathParam(pattern=BRANCH_ID_PATTERN)],
        cookie: Annotated[str | None, Security(SESSION_SCHEME)],
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
        if_match: Annotated[str, Header(alias="If-Match")],
    ) -> JSONResponse:
        """The undo of the last mutation of the branch: the revision goes back and the history stays.

        The body of the request is empty, because the undo does not change a record of the case: it changes the log
        of the branch. The `Idempotency-Key` header names the request and the `If-Match` header carries the revision
        the visitor believes the branch is at, exactly like the route of the commit, because a request that is
        delivered twice has to undo one mutation and not two (ADR-024).

        The answer carries the new revision, the new canonical hash, the diff, the invariants and the verdict, plus
        the mark of the undo and the uid of the event that was undone. The route is one of the three paths that
        ADR-023 declares beyond the contract of the design package.
        """
        session = _session(cookie, issuer)
        command = MutationCommand(
            kind=UNDO_KIND,
            payload={},
            expected_revision=_revision_of(if_match),
            idempotency_key=idempotency_key,
        )
        try:
            result = layer.undo(session, sandbox_id, command)
        except MutationRejected as refusal:
            raise ContractError(status_for_code(refusal.code), refusal.code, refusal.message) from None
        except BranchNotFound:
            raise ContractError(404, "NOT_FOUND", GENERIC_NOT_FOUND) from None
        except InvalidSessionId:
            raise ContractError(401, "SESSION_REQUIRED", "no valid session") from None
        except BranchExpired as expired:
            raise ContractError(410, "BRANCH_EXPIRED", str(expired)) from None
        except BranchHashMismatch as mismatch:
            raise ContractError(409, mismatch.code, mismatch.message) from None
        hub.publish(
            sandbox_id,
            EVENT_UNDONE,
            undone_fields(
                revision=result.revision,
                canonical_hash=result.canonical_hash,
                command_id=result.command_id,
                kind=result.kind,
                undone_event_uid=result.undone_event_uid or "",
            ),
        )
        return _answer(result.to_dict())

    @target.get("/v1/sandboxes/{sandbox_id}/diff")
    def read_diff(
        sandbox_id: Annotated[str, PathParam(pattern=BRANCH_ID_PATTERN)],
        cookie: Annotated[str | None, Security(SESSION_SCHEME)],
    ) -> JSONResponse:
        """The difference between the published base of the branch and the state the branch holds now (ADR-028).

        The answer carries the revision, the canonical hash of the base, the canonical hash of the branch, the entries
        of the difference, the invariants of the current state and the verdict of the case over it. The values of the
        entries are texts, so the interface never reads a number and never calculates one.

        The branch is a read like every other read: it is verified before it is answered, so a branch that cannot
        prove its own state is refused with `HASH_MISMATCH` and is never served (ADR-021). The route is one of the
        three paths that ADR-023 declares beyond the contract of the design package.
        """
        session = _session(cookie, issuer)
        try:
            diff = layer.diff(session, sandbox_id)
        except BranchNotFound:
            raise ContractError(404, "NOT_FOUND", GENERIC_NOT_FOUND) from None
        except InvalidSessionId:
            raise ContractError(401, "SESSION_REQUIRED", "no valid session") from None
        except BranchExpired as expired:
            raise ContractError(410, "BRANCH_EXPIRED", str(expired)) from None
        except BranchHashMismatch as mismatch:
            raise ContractError(409, mismatch.code, mismatch.message) from None
        return _answer(diff.to_dict())

    @target.get("/v1/sandboxes/{sandbox_id}/history")
    def read_history(
        sandbox_id: Annotated[str, PathParam(pattern=BRANCH_ID_PATTERN)],
        cookie: Annotated[str | None, Security(SESSION_SCHEME)],
    ) -> JSONResponse:
        """The log of the branch and the answers the branch remembers, with their marks (ADR-028).

        The events come in the order of the log and every one of them carries the mark that says it was undone. The
        answers carry the mark of the staleness of ADR-022 and the mark of the undo of ADR-024.

        The branch is a read like every other read: it is verified before it is answered, so a branch that cannot
        prove its own state is refused with `HASH_MISMATCH` and is never served (ADR-021). The route is one of the
        three paths that ADR-023 declares beyond the contract of the design package.
        """
        session = _session(cookie, issuer)
        try:
            history = layer.history(session, sandbox_id)
        except BranchNotFound:
            raise ContractError(404, "NOT_FOUND", GENERIC_NOT_FOUND) from None
        except InvalidSessionId:
            raise ContractError(401, "SESSION_REQUIRED", "no valid session") from None
        except BranchExpired as expired:
            raise ContractError(410, "BRANCH_EXPIRED", str(expired)) from None
        except BranchHashMismatch as mismatch:
            raise ContractError(409, mismatch.code, mismatch.message) from None
        return _answer(history.to_dict())

    @target.get("/v1/sandboxes/{sandbox_id}/ledger")
    def read_ledger(
        sandbox_id: Annotated[str, PathParam(pattern=BRANCH_ID_PATTERN)],
        account_id: Annotated[str, Query(min_length=1)],
        cookie: Annotated[str | None, Security(SESSION_SCHEME)],
        cursor: Annotated[str | None, Query(min_length=1)] = None,
    ) -> JSONResponse:
        """The ledger of the account of the branch: the rows of the projection and the cursor of the next page.

        The body is exactly the resource of the contract: the rows and the cursor, and no other field.
        """
        session = _session(cookie, issuer)
        try:
            page = layer.ledger(session, sandbox_id, account_id, cursor)
        except MutationRejected as refusal:
            raise ContractError(status_for_code(refusal.code), refusal.code, refusal.message) from None
        except BranchNotFound:
            raise ContractError(404, "NOT_FOUND", GENERIC_NOT_FOUND) from None
        except InvalidSessionId:
            raise ContractError(401, "SESSION_REQUIRED", "no valid session") from None
        except BranchExpired as expired:
            raise ContractError(410, "BRANCH_EXPIRED", str(expired)) from None
        except BranchHashMismatch as mismatch:
            raise ContractError(409, mismatch.code, mismatch.message) from None
        return _answer({"items": list(page.items), "next_cursor": page.next_cursor})

    @target.get("/v1/sandboxes/{sandbox_id}/events")
    def stream_sandbox(
        sandbox_id: Annotated[str, PathParam(pattern=BRANCH_ID_PATTERN)],
        cookie: Annotated[str | None, Security(SESSION_SCHEME)],
        last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
    ) -> StreamingResponse:
        """The stream of the lifecycle of the branch: the eight names of ADR-047.

        The answer is a stream of server sent events and it carries the header of the version of the schema and the
        headers of the no store, because the state of a branch of a visitor is not to be kept anywhere (FR-042).

        The header `Last-Event-ID` carries the last sequence the client holds, and the hub answers with one of the
        three answers of the resume: the stream opens with `branch.opened`, the stream continues with the next
        sequence, or the stream answers with a `stream.resync` and the client re-reads the branch (ADR-047).

        What the second answer proves: the client holds the last event of the branch and it missed NOTHING FROM THE
        MOMENT IT SUBSCRIBED. The counter of the branch is per branch and it is shared by every connection of that
        branch, so a client that connects late never received the events below the sequence it holds. The event of
        the opening carries the state of the branch, so the client is informed of it, and the truth of a branch is the
        answer of `GET /v1/sandboxes/{sandbox_id}` in any case (ADR-047).

        The three events of the stream, `stream.resync`, `stream.closed` and `stream.heartbeat`, belong to THIS
        connection: they move no counter of the branch and they carry no `id:` line, and the disconnect of the client
        publishes nothing (ADR-047).

        The branch of another session is refused with the same generic answer as every other route of the facade,
        BEFORE the stream opens, so nothing about the existence of the branch leaks (ADR-047).

        The route is one of the four paths that ADR-023 and ADR-047 declare beyond the contract of the design
        package.
        """
        session = _session(cookie, issuer)
        try:
            branch = layer.status(session, sandbox_id)
        except BranchNotFound:
            raise ContractError(404, "NOT_FOUND", GENERIC_NOT_FOUND) from None
        except InvalidSessionId:
            raise ContractError(401, "SESSION_REQUIRED", "no valid session") from None
        except BranchExpired as expired:
            raise ContractError(410, "BRANCH_EXPIRED", str(expired)) from None
        except BranchHashMismatch as mismatch:
            raise ContractError(409, mismatch.code, mismatch.message) from None
        return StreamingResponse(
            _events_of_branch(
                hub,
                branch_store,
                session,
                branch,
                last_event_id,
                clock=server_clock,
                heartbeat_seconds=HEARTBEAT_INTERVAL_SECONDS,
                credential_vault=credential_vault,
            ),
            media_type="text/event-stream",
            headers={
                SCHEMA_VERSION_HEADER: SCHEMA_VERSION,
                **NO_STORE_HEADERS,
            },
        )


async def _events_of_branch(
    hub: EventHub,
    store: BranchStore,
    session: str,
    branch: SandboxBranch,
    last_event_id: str | None,
    *,
    clock: Callable[[], datetime],
    heartbeat_seconds: float,
    credential_vault: CredentialVault | None,
) -> AsyncIterator[str]:
    """The events of the lifecycle of the branch, as they arrive, until the branch expires or the client leaves.

    Why the generator is asynchronous: a stream waits for the next event of the branch and the wait is fifteen
    seconds long. A generator that waits in a thread of the threadpool holds that thread for the whole life of the
    stream, and a generator that waits cannot be cancelled at once when the client disconnects, so the end of the
    stream would be late by up to fifteen seconds. The queue of the stream therefore lives in the loop of the server
    and the wait is an await (ADR-047).

    Why the payload is scrubbed with the vault: the payload is written by the same facade that writes the refusals,
    and the rule of ADR-035 holds for it, so no value of the visitor leaves the process (FR-018, SC-001).

    Why the life of the branch is asked to the store and not to the layer: the layer moves the deadline of the branch
    on every read, so a stream that asks the layer every fifteen seconds would keep its own branch alive forever. The
    row is read as it is and the rule of the expiry is the one of `ledgerlens/sandbox/ttl.py` (ADR-029, ADR-047).

    Why the events that the generator publishes itself are yielded and not waited for: the hub hands an event to the
    subscribers of the branch with `call_soon_threadsafe`, so the copy of the event reaches the queue of this stream
    one turn of the loop later. A close that was put in the queue at once would therefore be handed first, the stream
    would end there, and the client would never receive the event of the expiry that came before it (ADR-047).

    Why the opening of the stream is one operation of the hub: the route used to subscribe first and to publish the
    opening after, and a lifecycle event that another route published in that window reached the new stream FIRST,
    before the `branch.opened` that ADR-047 promises as the first event of a stream that opens for the first time
    (ADR-047).
    """
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[StreamEvent] = asyncio.Queue()

    def deliver(event: StreamEvent) -> None:
        """Hands an event of the branch to the queue of this stream, from any thread of the process."""
        loop.call_soon_threadsafe(queue.put_nowait, event)

    # The subscription and the answer of the resume happen under the SAME lock of the hub, and the opening of the
    # branch is published under that lock too. That is what makes the first event of a stream that opens for the
    # first time ALWAYS `branch.opened`: no other route can publish an event of the lifecycle in between, and a resume
    # that is proven never misses an event that was published while the client was away (ADR-047).
    hub.open(
        branch.branch_id,
        deliver,
        last_event_id=last_event_id,
        opening=opened_fields(
            scenario_id=branch.scenario_id,
            base_snapshot_id=branch.base_snapshot_id,
            base_canonical_hash=branch.base_canonical_hash,
            current_canonical_hash=branch.current_canonical_hash,
            revision=branch.revision,
            created_at=branch.created_at,
            expires_at=branch.expires_at,
            state=branch.state,
        ),
    )
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=heartbeat_seconds)
            except TimeoutError:
                # The silence is long enough: the heartbeat keeps the connection alive and lets the client count it.
                yield _text_of(hub.heartbeat(branch.branch_id), credential_vault)
                row = await _row_of_branch(store, session, branch.branch_id)
                if row is None:
                    # The row of the branch is gone, so the server ends THIS connection. The close belongs to the
                    # connection and not to the branch, and it moves no counter (ADR-047).
                    yield _text_of(hub.closed(branch.branch_id, reason=CLOSED_REASON_GONE), credential_vault)
                    break
                if is_expired(row, clock()):
                    # The branch died, and that IS an event of the lifecycle: every connection of the branch has to
                    # know it. The close that follows belongs to THIS connection alone (ADR-047).
                    #
                    # Why the event is yielded and not waited for: the hub hands an event to the subscribers of the
                    # branch with `call_soon_threadsafe`, so the copy of the expiry that comes back to THIS stream
                    # lands in the queue one turn of the loop later. The close is put in the queue at once, so the
                    # queue would hand the close first, the stream would end there, and the client would never hear
                    # that the branch died. The event is therefore yielded here, exactly once and before the close.
                    expiry = hub.publish(
                        branch.branch_id,
                        EVENT_BRANCH_EXPIRED,
                        expired_fields(expires_at=row.expires_at),
                    )
                    yield _text_of(expiry, credential_vault)
                    yield _text_of(hub.closed(branch.branch_id, reason=CLOSED_REASON_EXPIRED), credential_vault)
                    break
                continue
            yield _text_of(event, credential_vault)
            if event.name == EVENT_STREAM_CLOSED:
                break
    finally:
        hub.unsubscribe(branch.branch_id, deliver)
        # Why nothing is published when the client leaves: the client that left is gone, and the other connections
        # of the branch are not affected by it. A `stream.closed` that moved the counter would make the next
        # reconnection of every other connection look stale, because the event that moved it was never received by
        # anyone (ADR-047).


async def _row_of_branch(store: BranchStore, session: str, branch_id: str) -> SandboxBranchRow | None:
    """The row of the branch of the session, and None when the branch is not there any more.

    Why the read is in a thread: the store of a deployment may be a database, and the read of the row blocks.
    """
    try:
        return await asyncio.to_thread(store.get_branch, branch_id, session)
    except BranchNotFound:
        return None


def _text_of(event: StreamEvent, credential_vault: CredentialVault | None) -> str:
    """The text of an event of the stream, with the payload scrubbed by the vault of the credentials."""
    payload: dict[str, Any] = dict(event.payload)
    if credential_vault is not None:
        payload = {
            key: credential_vault.scrub(value) if isinstance(value, str) else value for key, value in payload.items()
        }
    return format_event(StreamEvent(name=event.name, payload=payload, seq=event.seq))


def _the_router_of(target: FastAPI | APIRouter) -> APIRouter:
    """The router that holds the routes of the target: the router of the application, or the target itself.

    Why the helper exists: an application and a router register their routes the same way, but the dependencies of the
    routes live on the router of the application and not on the application itself.
    """
    return target.router if isinstance(target, FastAPI) else target


def _check_the_cap_of_the_branches(
    store: BranchStore, session: str, scenario_id: str, *, cap: int, now: datetime
) -> None:
    """The cap of the live branches of the session, checked before the fork (ADR-047).

    Why the reuse comes FIRST: a fork of a scenario the session already holds a live branch for is a reuse and not a
    creation, so it creates no branch and the cap cannot refuse it.

    Why the life of a branch is the one of the module of the time to live: a branch whose expiry has passed is dead
    and does not count, even before the sweep of the cleanup deletes its row, because the sweep runs every thirty
    seconds and a visitor must not be refused for the branches that are already dead (ADR-029).

    Why the check only reads: the refusal happens before the branch is created, so it leaves nothing behind.

    Why the refusal is not retryable: the branches of the session are alive, and the retry would be refused again.
    """
    rows = store.list_branches(session)
    live = [row for row in rows if not is_expired(row, now)]
    if any(row.scenario_id == scenario_id for row in live):
        return
    if len(live) >= cap:
        raise ContractError(
            status_for_code(CODE_RESOURCE_LIMIT),
            CODE_RESOURCE_LIMIT,
            f"the session holds {len(live)} live branches and the cap is {cap}",
            retryable=False,
        )


def _session(cookie_value: str | None, issuer: SessionIssuer) -> str:
    """The owner session of the request, taken from the cookie of the contract.

    Why the cookie and never a header: the identifier decides what a visitor may read, so the browser never handles
    it in a place a third party can read, and a cookie that was not issued here is refused.
    """
    try:
        return issuer.session_id(cookie_value)
    except InvalidSession:
        raise ContractError(401, "SESSION_REQUIRED", "no valid session") from None


def _command_of(
    body: dict[str, Any], *, idempotency_key: str | None = None, expected_revision: int | None = None
) -> MutationCommand:
    """The command of the request: the kind, the payload and the reason, and the two names of the request.

    Why the body is read here and not by the framework: the body of a command is the one of the published schema,
    and the rules about it belong to the domain, which knows the kind of the command.
    """
    field = read_only_field_in(body)
    if field is not None:
        raise ContractError(
            422,
            CODE_READ_ONLY_FIELD,
            f"the field {field!r} is a read only field; the visitor may not change it",
        )
    data = body.get("data")
    if not isinstance(data, dict):
        raise ContractError(422, CODE_INVALID_PAYLOAD, "the payload of the command is not an object")
    kind = body.get("kind")
    reason = body.get("reason")
    return MutationCommand(
        kind=kind if isinstance(kind, str) else "",
        payload=data,
        reason=reason if isinstance(reason, str) else None,
        expected_revision=expected_revision,
        idempotency_key=idempotency_key,
    )


def _revision_of(if_match: str) -> int:
    """The expected revision of the request, taken from the `If-Match` header of the contract."""
    text = if_match.strip().strip('"')
    try:
        return int(text)
    except ValueError:
        raise ContractError(422, CODE_INVALID_REQUEST, "the If-Match header does not carry a revision") from None


def _answer(content: dict[str, Any]) -> JSONResponse:
    """An answer of the facade, with the version of the shape of the answers in its header (FR-042)."""
    return JSONResponse(status_code=200, content=content, headers={SCHEMA_VERSION_HEADER: SCHEMA_VERSION})


def _sandbox_response(branch: SandboxBranch, status_code: int) -> JSONResponse:
    """The resource `Sandbox` of the contract, and the headers that carry what the resource has no field for."""
    body = {
        "id": branch.branch_id,
        "base_snapshot_id": branch.base_snapshot_id,
        "snapshot_sha256": branch.base_canonical_hash,
        "revision": branch.revision,
        "expires_at": branch.expires_at.isoformat(),
    }
    return JSONResponse(
        status_code=status_code,
        content=body,
        headers={
            SCHEMA_VERSION_HEADER: SCHEMA_VERSION,
            BRANCH_HASH_HEADER: branch.current_canonical_hash,
            BRANCH_STATE_HEADER: branch.state,
        },
    )


__all__ = [
    "BRANCH_HASH_HEADER",
    "BRANCH_STATE_HEADER",
    "ContractError",
    "GENERIC_NOT_FOUND",
    "SCHEMA_VERSION",
    "SCHEMA_VERSION_HEADER",
    "NO_STORE_HEADERS",
    "SESSION_COOKIE",
    "SandboxRequest",
    "build_router",
    "create_app",
    "install_refusal_handlers",
]
