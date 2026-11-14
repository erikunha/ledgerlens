"""The sandbox facade: the routes of the versioned contract of the design package.

Why it exists: the visitor works in a browser and needs two things first, a private branch of a published case and the
status of that branch. The facade follows `docs/v3/contracts/openapi.yaml`, so the interface that is paused can be
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

No route accepts a file path, a SQL statement or a URL, and no route writes to the published snapshot (FR-041).
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any

from fastapi import FastAPI, Request, Security
from fastapi import Path as PathParam
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.security import APIKeyCookie
from pydantic import BaseModel, ConfigDict, Field

from ledgerlens.config import get_settings
from ledgerlens.sandbox.branch import (
    BRANCH_ID_PREFIX,
    BranchExpired,
    BranchLayer,
    InvalidSessionId,
    SandboxBranch,
)
from ledgerlens.sandbox.session import InvalidSession, SessionIssuer
from ledgerlens.sandbox.snapshot import BaseResolver, UnknownScenario
from ledgerlens.sandbox.store import BranchNotFound, BranchStore, FileBranchStore

# The version of the shape of the answers. It travels in a header, because the resource `Sandbox` accepts no other
# field and the interface reads that resource.
SCHEMA_VERSION = "1"
SCHEMA_VERSION_HEADER = "X-LedgerLens-Schema-Version"
# The current canonical hash of the branch and its state, which the resource `Sandbox` has no field for.
BRANCH_HASH_HEADER = "X-LedgerLens-Branch-Hash"
BRANCH_STATE_HEADER = "X-LedgerLens-Branch-State"
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

    def __init__(self, status_code: int, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.retryable = retryable

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
) -> FastAPI:
    """Builds the app over a store, a base resolver and a session issuer.

    Without arguments the store is the file backed one in the runtime folder of the configuration, the base is built
    from the published sample and the session is signed with a key of the runtime folder, so the facade runs with no
    database and no key. The clock is the server clock, and it is injected so that a test can move the expiry.
    """
    settings = get_settings()
    app = FastAPI(title="LedgerLens sandbox", description="Private branches of the published cases.")
    branch_store = store if store is not None else FileBranchStore(settings.runtime_dir / "sandbox")
    issuer = session_issuer or SessionIssuer(
        settings.runtime_dir / "sandbox-session.key",
        ttl_seconds=settings.sandbox_branch_absolute_ttl_seconds,
    )
    layer = BranchLayer(
        branch_store,
        base_resolver if base_resolver is not None else BaseResolver(),
        idle_ttl_seconds=settings.sandbox_branch_idle_ttl_seconds,
        absolute_ttl_seconds=settings.sandbox_branch_absolute_ttl_seconds,
        clock=clock,
    )

    @app.exception_handler(ContractError)
    async def contract_error(_request: Request, error: ContractError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content=error.body(),
            headers={SCHEMA_VERSION_HEADER: SCHEMA_VERSION},
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

    @app.post("/v1/sessions", status_code=201)
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

    @app.delete("/v1/sessions/current", status_code=204)
    def end_session(cookie: Annotated[str | None, Security(SESSION_SCHEME)]) -> Response:
        """Ends the session of the visitor and purges its branches."""
        session = _session(cookie, issuer)
        for row in branch_store.list_branches(session):
            branch_store.delete_branch(row.branch_id, session)
        response = Response(status_code=204)
        response.delete_cookie(SESSION_COOKIE, path="/")
        return response

    @app.post("/v1/sandboxes")
    def fork(
        payload: SandboxRequest,
        cookie: Annotated[str | None, Security(SESSION_SCHEME)],
    ) -> JSONResponse:
        """Forks the published case into a private branch of the session.

        The answer is `201` when the fork creates a branch and `200` when the reuse rule returns the branch that
        already exists: the difference matters to a client.
        """
        session = _session(cookie, issuer)
        try:
            outcome = layer.fork(session, payload.scenario_id)
        except UnknownScenario:
            raise ContractError(404, "UNKNOWN_SCENARIO", "no such scenario") from None
        except InvalidSessionId:
            raise ContractError(401, "SESSION_REQUIRED", "no valid session") from None
        return _sandbox_response(outcome.branch, 201 if outcome.created else 200)

    @app.get("/v1/sandboxes/{sandbox_id}")
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
        return _sandbox_response(branch, 200)

    return app


def _session(cookie_value: str | None, issuer: SessionIssuer) -> str:
    """The owner session of the request, taken from the cookie of the contract.

    Why the cookie and never a header: the identifier decides what a visitor may read, so the browser never handles
    it in a place a third party can read, and a cookie that was not issued here is refused.
    """
    try:
        return issuer.session_id(cookie_value)
    except InvalidSession:
        raise ContractError(401, "SESSION_REQUIRED", "no valid session") from None


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
    "SESSION_COOKIE",
    "SandboxRequest",
    "create_app",
]
