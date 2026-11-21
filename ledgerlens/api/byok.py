"""The facade of the live mode: the routes of the credential, of the catalogue and of the run.

Why it exists: the visitor of the demo browses the site with no key at all, and the live mode is an opt-in branch of
it. This module is the server side of that branch: it accepts the key of the visitor and answers with a handle, it
forgets the key on demand, it publishes the catalogue of the models that were really tested, and it runs a case with
the key of the visitor inside a budget.

What the routes promise:

* the answer of the credential route carries the handle, the provider and the expiry, and never the key itself
  (FR-004, FR-005);
* the answer of the credential route carries the headers that say that nothing is stored, and the disclosure that the
  provider of the visitor may charge the visitor (FR-003, FR-008);
* the "forget key" action is always there and takes effect at once (FR-014);
* the catalogue shows only the models of the allowlist that were tested, with their status and their capabilities
  (FR-016, FR-030);
* the price of a model comes with its provenance and the day it was verified, and a model whose price was never
  verified shows no amount at all (FR-011, FR-031);
* the route of the run never accepts a raw key: it takes the handle of a credential and nothing else (FR-007);
* the route of the run resolves the branch of the visitor before the run starts, and it refuses a branch of another
  session, a branch that expired, a branch that cannot prove its own state, an account that is not the account of
  the branch and a revision that moved, with the codes of the contract of the sandbox and without calling any
  provider (ADR-038);
* the route of the run owns the removal of the file of the ledger of a run that never started, whatever the refusal
  of the coordinator was, and it leaves the file of a run that is running alone, because that run removes it when it
  ends (ADR-038);
* a router without a case refuses the run with a readable reason, because a run that answered with the default case
  would never read the ledger of the visitor (ADR-038);
* the cost report shows the observed cost and the estimated cost apart, and no amount when the price is unknown
  (FR-010, FR-011).

What the facade decides and the domain does not:

* the live mode is refused while the product runs offline, with an answer that names the reason, and the replay and
  the sandbox keep working exactly as before (FR-001, FR-029). The rule lives here and not in the vault, because
  the vault never reads a global setting, on purpose (ADR-033);
* the vault of the application holds the keys of its visitors: the facade starts its sweeper and stops it when the
  application stops;
* the session owns its credentials: the end of a session drops the credentials of that session, and the purge is
  tolerant, because a failure of the purge never fails the route;
* a credential never outlives the session that holds it: the time to live of a credential is the smaller of the life
  of the vault and the life that is left in the session, the facade is the only layer that knows both, and it hands
  that life to the vault instead of writing it on the vault (FR-022);
* a refusal of the facade never carries a value of the visitor: the refusal names the reason and the field of the
  contract, and the handler of the refusals scrubs what it writes before it writes it (FR-018, SC-001).

What the facade is given and never goes looking for:

* the vault is a dependency of the application: the facade never reaches for a global, so two applications of the
  same process never share a vault by accident. There is no vault of the process to reach for either, because a
  global that holds the keys of the visitors is a global that a test cannot own. A deployment that runs the sandbox
  facade and the live mode facade gives them the same vault on purpose (ADR-035);
* the session issuer is a dependency of the application too. The two facades are the same visitor when they are
  given the same issuer, and they are two visitors when they are not;
* the branch layer of the sandbox is a dependency of the application too: it holds the ledger of the visitor, and an
  application without one refuses every run that names a branch instead of answering with the ledger of the
  configuration (ADR-038).

Why the live mode has its own application and not a route of the sandbox: the sandbox is the R2 contract of the
design package and its paths are fixed. The live mode brings paths of its own, and by default it has a cookie of its
own: the two facades are the same visitor only when the deployment wires them with the same session issuer, and that
wiring is a decision of the deployment (ADR-035).
"""

from __future__ import annotations

import json
import logging
import secrets
import threading
import time
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, FastAPI, Request, Security
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.security import APIKeyCookie
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, ValidationError, model_validator

from ledgerlens.api.live_case import DemoCase
from ledgerlens.api.live_run import (
    LIVE_MODE,
    CaseExecutor,
    LiveModeOffline,
    LiveRunCoordinator,
    LiveRunPlan,
    remove_the_ledger_file,
    remove_the_ledger_of_the_run,
    resolve_profile,
)
from ledgerlens.api.sandbox import (
    GENERIC_NOT_FOUND,
    SCHEMA_VERSION,
    SCHEMA_VERSION_HEADER,
    SESSION_COOKIE,
    ContractError,
)
from ledgerlens.byok.adapter import ProviderAdapter
from ledgerlens.byok.budget import CostReport
from ledgerlens.byok.errors import ByokError, CapabilityMissing, CredentialRefused, UnknownProvider
from ledgerlens.byok.registry import PROVIDERS, Pricing, ProviderRegistry
from ledgerlens.byok.vault import CredentialHandle, CredentialVault
from ledgerlens.config import get_settings, offline
from ledgerlens.run_context import RunBudget
from ledgerlens.sandbox.branch import BranchExpired, BranchHashMismatch, BranchLayer
from ledgerlens.sandbox.ledger_view import LedgerAccountMismatch, LedgerRevisionMoved, LedgerView
from ledgerlens.sandbox.session import MODE_CAPABILITIES, DemoSession, InvalidSession, SessionIssuer
from ledgerlens.sandbox.store import BranchNotFound

log = logging.getLogger(__name__)

__all__ = [
    "BILLING_DISCLOSURE_HEADER",
    "BILLING_DISCLOSURE_TEXT",
    "CODE_ACCOUNT_MISMATCH",
    "CODE_BRANCH_EXPIRED",
    "CODE_BRANCH_HASH_MISMATCH",
    "CODE_BRANCH_LAYER_MISSING",
    "CODE_CAPABILITY_MISSING",
    "CODE_CASE_MISSING",
    "CODE_CONTRACT_UNAVAILABLE",
    "CODE_CREDENTIAL_REFUSED",
    "CODE_INVALID_REQUEST",
    "CODE_LIVE_MODE_OFFLINE",
    "CODE_MODE_NOT_ALLOWED",
    "CODE_MODEL_NOT_ALLOWED",
    "CODE_NOT_FOUND",
    "CODE_REVISION_MOVED",
    "CODE_RUN_RUNNING",
    "CODE_SESSION_REQUIRED",
    "CODE_UNKNOWN_PROVIDER",
    "CODE_WRONG_MODE",
    "KEY_ERASURE_HEADER",
    "KEY_ERASURE_TEXT",
    "KEY_STORAGE_HEADER",
    "KEY_STORAGE_TEXT",
    "LEDGER_FILE_NAME",
    "NO_STORE_HEADERS",
    "RUN_ID_PREFIX",
    "RUN_REQUEST_SCHEMA_PATH",
    "RUNS_FOLDER_NAME",
    "SESSION_KEY_FILENAME",
    "SESSION_SCHEME",
    "STREAM_TIMEOUT_SECONDS",
    "TERMINAL_EVENTS",
    "CredentialRequest",
    "ForgetRequest",
    "LiveRunRequest",
    "RunLimits",
    "SessionCapabilities",
    "build_router",
    "create_app",
]

# The machine-readable codes of the refusals of the live mode, the way the refusals of the sandbox carry a code.
CODE_LIVE_MODE_OFFLINE = "LIVE_MODE_OFFLINE"
CODE_CREDENTIAL_REFUSED = "CREDENTIAL_REFUSED"
CODE_UNKNOWN_PROVIDER = "UNKNOWN_PROVIDER"
CODE_MODEL_NOT_ALLOWED = "MODEL_NOT_ALLOWED"
CODE_CAPABILITY_MISSING = "CAPABILITY_MISSING"
CODE_WRONG_MODE = "WRONG_MODE"
CODE_NOT_FOUND = "NOT_FOUND"
CODE_RUN_RUNNING = "RUN_RUNNING"
CODE_SESSION_REQUIRED = "SESSION_REQUIRED"
CODE_INVALID_REQUEST = "INVALID_REQUEST"
CODE_MODE_NOT_ALLOWED = "MODE_NOT_ALLOWED"
# The refusals of the branch of the visitor. They carry the codes of the contract of the sandbox, so the two facades
# cannot disagree about what a branch holds, and they never carry a value that the visitor sent (ADR-038).
CODE_BRANCH_LAYER_MISSING = "BRANCH_LAYER_MISSING"
CODE_BRANCH_EXPIRED = "BRANCH_EXPIRED"
CODE_BRANCH_HASH_MISMATCH = "HASH_MISMATCH"
CODE_ACCOUNT_MISMATCH = "ACCOUNT_MISMATCH"
CODE_REVISION_MOVED = "REVISION_MOVED"
# The refusal of a deployment that has no case of its own. It is not the fault of the body of the visitor, so it is
# not the code of a bad request.
CODE_CASE_MISSING = "CASE_MISSING"
# The refusal of a deployment that cannot check the contract of the request. It is not the fault of the body of the
# visitor, so it is not the code of a bad request.
CODE_CONTRACT_UNAVAILABLE = "CONTRACT_UNAVAILABLE"

# The refusal of a provider that the live mode does not publish. The name that the visitor sent is not repeated: a
# visitor that pasted the key of their provider in the field of the provider would read their key in the answer
# (FR-018, SC-001).
_MESSAGE_OF_AN_UNKNOWN_PROVIDER = "the provider is not one of the providers of the live mode: " + ", ".join(PROVIDERS)

# The refusal of a deployment without jsonschema. The check of the shape of a request needs the library, and a
# deployment without it cannot serve the route of the run.
_MESSAGE_WITHOUT_JSONSCHEMA = (
    "the check of the shape of a request needs jsonschema, which the api extra and the dev extra install: "
    "this deployment cannot start a live run, and the body of the visitor is not the reason"
)

# The reason of each check of the published contract, in the words of the facade. The reason never carries the value
# that failed: the validator of the contract quotes that value, and the refusal must not (FR-018, SC-001).
_REASONS_OF_THE_VALIDATOR = {
    "enum": "does not carry one of the allowed values",
    "const": "does not carry the allowed value",
    "pattern": "does not have the pattern the contract asks for",
    "type": "is not of the type the contract asks for",
    "minimum": "is below the minimum the contract allows",
    "maximum": "is above the maximum the contract allows",
    "minLength": "is shorter than the minimum length the contract allows",
    "maxLength": "is longer than the maximum length the contract allows",
}

# The header that says that the key of the visitor is not stored. The key lives in the memory of the process and
# the credential is dropped when the session ends, and the answer says so (FR-003, FR-008).
KEY_STORAGE_HEADER = "X-LedgerLens-Key-Storage"
# The header that carries the disclosure of the billing: the provider of the visitor may charge the visitor for the
# calls of the run, and the visitor reads it before the first call (FR-008).
BILLING_DISCLOSURE_HEADER = "X-LedgerLens-Billing-Disclosure"

# The text of the two headers above. They are plain sentences, because a visitor reads them.
KEY_STORAGE_TEXT = (
    "the key is not stored: it lives in the memory of the server and the credential is dropped when the session ends"
)
BILLING_DISCLOSURE_TEXT = "your provider may charge you for the calls of this run"

# The header that carries the limit of the promise of the storage. The server drops the key when the credential
# ends, and nobody can promise that no copy of the text of the key survives in the memory of the interpreter or in a
# swap of the operating system. The answer says so out loud, because a promise that the product cannot keep is not a
# promise (FR-021, ADR-033).
KEY_ERASURE_HEADER = "X-LedgerLens-Key-Erasure"
KEY_ERASURE_TEXT = (
    "the memory of the machine cannot be guaranteed to be erased: the server drops the key when the credential ends, "
    "but no runtime can promise that no copy of the text of the key survives in the memory of the interpreter or in a "
    "swap of the operating system"
)

# The headers that say that the answer is not to be kept anywhere. The answer of the credential route carries the
# handle and nothing else, and it is not to be cached (FR-003).
NO_STORE_HEADERS = {
    "Cache-Control": "no-store",
    "Pragma": "no-cache",
    "Expires": "0",
}

# The cookie of the demo and the scheme that reads it. The cookie of the live mode carries the same name, but it is
# signed with the key of the live mode by default: the two facades are the same visitor when the deployment wires
# them with the same session issuer, and a sharing that nobody wired is a sharing nobody decided (ADR-035).
SESSION_SCHEME = APIKeyCookie(
    name=SESSION_COOKIE,
    scheme_name="anonymousSession",
    description="Opaque signed HttpOnly demo session cookie, not user identity.",
    auto_error=False,
)

# The name of the file with the key of the sessions of the live mode. The live mode has a file of its own: the two
# facades are the same visitor when the deployment gives them the same issuer, and a sharing that nobody wired is a
# sharing nobody decided (ADR-035).
SESSION_KEY_FILENAME = "live-session.key"

# The published contract of the request that starts a live run. The body of the request is checked against it, so
# the server never accepts a body that the contract forbids (FR-007, FR-025).
RUN_REQUEST_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "specs"
    / "003-r3-bring-your-own-key"
    / "contracts"
    / "live-run-request.schema.json"
)

# The prefix of the identifier of a run. The identifier is opaque and it says nothing about the visitor.
RUN_ID_PREFIX = "run_"
# The folder of the runtime that holds the file of the ledger of each run, and the name of that file. The file is
# written before the run starts and removed when the run ends, so the rows of a visitor do not stay on the disk of the
# server longer than the run needs them (ADR-038).
RUNS_FOLDER_NAME = "runs"
LEDGER_FILE_NAME = "ledger.db"
# The time the route of the stream waits for the end of a run before it closes the stream.
STREAM_TIMEOUT_SECONDS = 120.0
# The terminal events of a run. The stream of a run ends with one of them (FR-020).
TERMINAL_EVENTS = ("run.completed", "run.failed", "run.cancelled")

# The number of sessions the live mode remembers the capabilities of. The map is a memory of the process, and it is
# bounded the way the vault is bounded (FR-002).
_MAX_REMEMBERED_SESSIONS = 256


class SessionCapabilities:
    """What the sessions of the live mode may run, as the facade that issued them knows it.

    Why the facade keeps it: the session of the demo is anonymous and its modes are declared when it is issued, and
    a run of the live mode is a run of a mode. The facade asks the session for its capabilities before it accepts a
    live run, so a session that may not run the live mode never does (FR-024).

    Why a session that the facade did not issue has the capabilities of the demo session: the live mode issues the
    sessions of the live flow, and a session of the sandbox is a session of the sandbox (ADR-035).
    """

    def __init__(self) -> None:
        self._capabilities: dict[str, tuple[str, ...]] = {}
        self._lock = threading.Lock()

    def remember(self, session: DemoSession) -> None:
        """Keeps the capabilities of a session that the facade just issued."""
        with self._lock:
            self._capabilities[session.id] = tuple(session.mode_capabilities)
            # The map is bounded, because a session of the demo that nobody uses has to die with the process and
            # not grow it (FR-002).
            while len(self._capabilities) > _MAX_REMEMBERED_SESSIONS:
                self._capabilities.pop(next(iter(self._capabilities)))

    def of(self, session_id: str) -> tuple[str, ...]:
        """The capabilities of a session, or the capabilities of the demo session when it is unknown."""
        with self._lock:
            return self._capabilities.get(session_id, MODE_CAPABILITIES)


class CredentialRequest(BaseModel):
    """The body of the route of the credential: the provider and the key of the visitor.

    Why the body carries the key and the answer does not: the key arrives once, over the request, and what travels
    afterwards is the handle (FR-004, FR-005).
    """

    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1, max_length=64)
    api_key: str = Field(min_length=1, max_length=512)


class ForgetRequest(BaseModel):
    """The body of the route of the "forget key": the handle of the credential that goes away (FR-014).

    Why the handle travels in the body and not in the path: no page of the demo carries a handle in its URL
    (SC-012).
    """

    model_config = ConfigDict(extra="forbid")

    handle: str = Field(min_length=16, max_length=128)


def _an_integer(value: Any) -> Any:
    """The rule of the published contract for an integer: a number with no fractional part, never a text.

    Why the text is refused: the contract says that the caps of a run are integers, and a cap that arrives as a text
    is a body that the contract does not accept (FR-025). Why a number with no fractional part is accepted: it is an
    integer for the contract, and refusing it would be a difference the server invents.
    """
    if isinstance(value, bool):
        raise ValueError("a boolean is not an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    raise ValueError(f"the value {value!r} is not an integer")


# The rule of the published contract for a count of tokens, of calls or of seconds.
_Integer = Annotated[int, BeforeValidator(_an_integer)]


class RunLimits(BaseModel):
    """The caps of a run: the request of the contract, read into the budget of the run (FR-009, FR-025).

    Why the money is a `Decimal`: a cap of money is money, and a binary float never touches it. The contract carries
    it as text or as a number, and the domain parses it into a `Decimal` (ADR-034).

    Why the bounds are the ones of the published contract: the test of the facade compares this model with the
    schema of the contract, so the two cannot drift apart (FR-025).
    """

    model_config = ConfigDict(extra="forbid")

    max_model_calls: _Integer = Field(ge=1, le=20)
    max_tool_calls: _Integer = Field(ge=1, le=40)
    max_wall_seconds: _Integer = Field(ge=5, le=180)
    max_output_tokens: _Integer = Field(ge=128, le=16000)
    max_input_tokens: _Integer | None = Field(default=None, ge=1)
    max_estimated_usd: Decimal | None = Field(default=None, ge=0)


class LiveRunRequest(BaseModel):
    """The body of the route of the live run: exactly the contract of the request.

    Why the body accepts no other field: the request is the published contract, and a field that the contract does
    not have is a field the server does not read. It is also what keeps a raw key out of the route of the run
    (FR-007).
    """

    model_config = ConfigDict(extra="forbid")

    mode: Literal["live_agent", "deterministic_sandbox"]
    scenario_id: str = Field(pattern=r"^S[0-9]{2}$")
    sandbox_id: str = Field(min_length=1)
    expected_revision: int = Field(ge=0)
    account_id: str = Field(pattern=r"^(?:C-[0-9]{4}|M-[0-9]{2})$")
    question: str = Field(min_length=1, max_length=2000)
    variant: Literal["A", "B", "C", "D"]
    model_profile_id: str | None = None
    credential_handle: str | None = None
    limits: RunLimits

    @model_validator(mode="after")
    def _the_live_mode_needs_a_model_and_a_credential(self) -> LiveRunRequest:
        """The rule of the contract: a live run names a model and a credential.

        Why it is here and not in the route: a request that does not satisfy the contract is not a request, and the
        answer of the framework says so before the route reads anything (FR-007).
        """
        if self.mode == "live_agent" and (not self.model_profile_id or not self.credential_handle):
            raise ValueError("a live run names a model profile and a credential handle")
        return self


def create_app(
    *,
    vault: CredentialVault | None = None,
    registry: ProviderRegistry | None = None,
    session_issuer: SessionIssuer | None = None,
    runtime_dir: Path | str | None = None,
    coordinator: LiveRunCoordinator | None = None,
    adapter_factory: Callable[[str, str], ProviderAdapter] | None = None,
    executor: CaseExecutor | None = None,
    branch_layer: BranchLayer | None = None,
    clock: Callable[[], float] = time.monotonic,
    call_timeout: float | None = None,
) -> FastAPI:
    """Builds the application of the live mode.

    The vault is a dependency of the application: the facade never reaches for a global, so two applications of the
    same process never share the memory of the keys by accident. Without a vault the application owns one of its own.
    The registry is the allowlist of the models, the session issuer reads the cookie of the demo, and the
    coordinator holds the runs. Without any of them the application runs with the allowlist of the repository and
    with the session issuer of the runtime folder of the configuration.

    The sweeper of the vault starts with the application and stops with it, so a credential that nobody touches
    still dies (FR-022, SC-011).

    The branch layer is the layer of the sandbox, and it is what holds the ledger of the visitor: the run reads the
    branch of the visitor and never the ledger of the configuration (ADR-038). Without it the application refuses
    every run that names a branch, with a readable reason.

    The case of the runs is the case of the application: the case the caller gave, or the case of the demo when the
    caller gave none. The case travels with the run, so the coordinator of the caller is never rewritten and keeps
    the case it was built with (ADR-038).
    """
    settings = get_settings()
    runtime = Path(runtime_dir) if runtime_dir is not None else settings.runtime_dir
    the_vault = vault if vault is not None else CredentialVault()
    the_registry = registry if registry is not None else ProviderRegistry()
    issuer = session_issuer or SessionIssuer(
        runtime / SESSION_KEY_FILENAME,
        ttl_seconds=settings.sandbox_branch_absolute_ttl_seconds,
    )
    # The case of the demo, with the runtime folder of the facade: the memory of the case lives in the folder of the
    # session of the visitor and not in the folder of the configuration (ADR-038).
    the_case: CaseExecutor = executor if executor is not None else DemoCase(runtime_dir=runtime)
    the_coordinator = coordinator or LiveRunCoordinator(
        registry=the_registry,
        vault=the_vault,
        adapter_factory=adapter_factory,
        executor=the_case,
        clock=clock,
        call_timeout=call_timeout,
    )
    capabilities = SessionCapabilities()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        """Starts the sweeper of the vault and stops it when the application stops.

        Why the sweeper lives in the lifespan and not in the module: a thread that starts with the module runs in
        every test that builds the application, and the sweep would race with the test that moves the clock.
        """
        the_vault.start_sweeper()
        try:
            yield
        finally:
            the_vault.stop_sweeper()

    app = FastAPI(
        title="LedgerLens live mode",
        description="The live mode of the demo: a visitor runs a case with a key of their own.",
        lifespan=lifespan,
    )

    @app.exception_handler(ContractError)
    async def contract_error(_request: Request, error: ContractError) -> JSONResponse:
        """The refusals of the facade are the resource `Error` of the contract, the way the sandbox answers.

        The message is scrubbed before it is written: the facade writes what it writes, and a refusal that carries
        a key would carry it out of the process (FR-018, SC-001).
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

    app.include_router(
        build_router(
            vault=the_vault,
            registry=the_registry,
            issuer=issuer,
            coordinator=the_coordinator,
            case=the_case,
            capabilities=capabilities,
            branch_layer=branch_layer,
            runtime_dir=runtime,
        )
    )
    return app


def build_router(
    *,
    vault: CredentialVault,
    registry: ProviderRegistry,
    issuer: SessionIssuer,
    coordinator: LiveRunCoordinator,
    case: CaseExecutor | None = None,
    capabilities: SessionCapabilities | None = None,
    branch_layer: BranchLayer | None = None,
    runtime_dir: Path | None = None,
) -> APIRouter:
    """The router of the live mode, over the vault, the allowlist, the session and the coordinator.

    Why the router takes what it needs and reads no global: the live mode is a branch of the demo, and the branch
    is only as good as the pieces it is given. A test builds the router over a vault and a fake provider of its own.

    The branch layer is the layer of the sandbox, and it is what holds the ledger of the visitor: without it the
    route of the run refuses every run that names a branch (ADR-038).

    Why the case is given to the router and not read from the coordinator: the case of a run travels with the run,
    and the coordinator of the caller is never rewritten (ADR-038).

    Why the case is optional: a deployment that builds the router by hand may not have a case yet, and a router
    that cannot be built is worse than a router that refuses a run with a readable reason (ADR-038).
    """
    router = APIRouter()
    the_capabilities = capabilities if capabilities is not None else SessionCapabilities()
    the_runtime = Path(runtime_dir) if runtime_dir is not None else get_settings().runtime_dir

    @router.post("/v1/sessions", status_code=201)
    def issue_session() -> JSONResponse:
        """Issues the session of the visitor and sets the cookie of the demo.

        The session of the live mode is the session of the demo with the capability of the live mode: a session that
        may not run the live mode never runs it (FR-024).
        """
        session = _session_of_the_live_mode(issuer)
        the_capabilities.remember(session)
        body = {
            "id": session.id,
            "expires_at": session.expires_at.isoformat(),
            "mode_capabilities": list(session.mode_capabilities),
        }
        headers = {
            SCHEMA_VERSION_HEADER: SCHEMA_VERSION,
            KEY_STORAGE_HEADER: KEY_STORAGE_TEXT,
            KEY_ERASURE_HEADER: KEY_ERASURE_TEXT,
            **NO_STORE_HEADERS,
        }
        response = JSONResponse(status_code=201, content=body, headers=headers)
        response.set_cookie(
            SESSION_COOKIE,
            issuer.cookie_value(session),
            httponly=True,
            samesite="lax",
            path="/",
            max_age=issuer.ttl_seconds,
        )
        return response

    @router.delete("/v1/sessions/current", status_code=204)
    def end_session(cookie: Annotated[str | None, Security(SESSION_SCHEME)]) -> Response:
        """Ends the session of the visitor and drops the credentials of that session.

        The key of a visitor dies with the session (FR-022). The purge is tolerant: a vault that refuses the drop
        never fails the route.
        """
        session = _session_of(cookie, issuer)
        try:
            vault.forget_session(session)
        except Exception as error:  # pragma: no cover - the purge of the credentials never fails the route.
            log.warning("the credentials of the session could not be dropped: %s", error)
        response = Response(status_code=204, headers={SCHEMA_VERSION_HEADER: SCHEMA_VERSION})
        response.delete_cookie(SESSION_COOKIE, path="/")
        return response

    @router.post("/v1/credentials", status_code=201)
    def accept_credential(
        payload: CredentialRequest,
        cookie: Annotated[str | None, Security(SESSION_SCHEME)],
    ) -> JSONResponse:
        """Accepts the key of the visitor and answers with the handle that stands for it.

        The body of the answer is exactly the resource `CredentialHandle` of the contract: the handle, the provider,
        the creation and the expiry. The key itself never travels back (FR-004, FR-005), and the headers say that
        nothing is stored, that the provider of the visitor may charge the visitor and that the memory of the
        machine cannot be guaranteed to be erased (FR-003, FR-008, FR-021).
        """
        _refuse_when_offline()
        session = _session_of(cookie, issuer)
        try:
            handle = _accept_a_credential(vault, payload.api_key, payload.provider, session, cookie, issuer)
        except UnknownProvider:
            # The name that the visitor sent is not repeated: the field of the provider may hold the key of the
            # visitor, and the refusal of the facade never carries it out (FR-018, SC-001).
            raise ContractError(422, CODE_UNKNOWN_PROVIDER, _MESSAGE_OF_AN_UNKNOWN_PROVIDER) from None
        except CredentialRefused as refusal:
            raise ContractError(422, CODE_CREDENTIAL_REFUSED, str(refusal)) from None
        headers = {
            SCHEMA_VERSION_HEADER: SCHEMA_VERSION,
            KEY_STORAGE_HEADER: KEY_STORAGE_TEXT,
            KEY_ERASURE_HEADER: KEY_ERASURE_TEXT,
            BILLING_DISCLOSURE_HEADER: BILLING_DISCLOSURE_TEXT,
            **NO_STORE_HEADERS,
        }
        return JSONResponse(status_code=201, content=handle.to_public_dict(), headers=headers)

    @router.post("/v1/credentials/forget")
    def forget_credential(
        payload: ForgetRequest,
        cookie: Annotated[str | None, Security(SESSION_SCHEME)],
    ) -> JSONResponse:
        """Drops the credential of the handle and says that the key is gone (FR-014).

        The action is always there: it answers even when there was no key to forget, and a handle of another
        session gets the same answer as a handle that never existed (FR-006, SC-002).
        """
        session = _session_of(cookie, issuer)
        forgotten = vault.forget(payload.handle, session_id=session)
        body = {
            "forgotten": forgotten,
            "message": "the key is gone" if forgotten else "there was no key to forget",
        }
        return JSONResponse(status_code=200, content=body, headers={SCHEMA_VERSION_HEADER: SCHEMA_VERSION})

    @router.get("/v1/models")
    def catalogue() -> JSONResponse:
        """The models the visitor may pick: the tested ones, with their status and their capabilities (FR-030)."""
        body = {"models": [profile.to_contract() for profile in registry.catalogue()]}
        return JSONResponse(status_code=200, content=body, headers={SCHEMA_VERSION_HEADER: SCHEMA_VERSION})

    @router.get("/v1/models/{profile_id}")
    def price_of_model(profile_id: str) -> JSONResponse:
        """The price of a model and its provenance, when the price was verified (FR-031).

        A model whose price was never verified answers that the price is unknown and shows no amount at all
        (FR-011).
        """
        profile = registry.get(profile_id)
        if profile is None:
            raise ContractError(404, CODE_NOT_FOUND, "no such model in the allowlist of the server") from None
        body = {
            "model": profile.to_contract(),
            "price_known": profile.pricing.is_verified,
            "price_note": _price_note(profile.pricing),
        }
        return JSONResponse(status_code=200, content=body, headers={SCHEMA_VERSION_HEADER: SCHEMA_VERSION})

    @router.post("/v1/live-runs", status_code=201)
    async def start_run(
        request: Request,
        cookie: Annotated[str | None, Security(SESSION_SCHEME)],
    ) -> JSONResponse:
        """Starts a live run and answers with its identifier (FR-024).

        The body of the request never carries a key: it carries the handle of a credential, and the vault refuses a
        handle of another session (FR-006, FR-007). The body is checked against the published contract before
        anything else, so a body that the contract forbids never starts a run (FR-025). The answer carries the
        disclosure of the billing, because the visitor reads it before the first call of the provider (FR-008).

        The branch of the visitor is resolved before the run starts: every refusal of the layer happens before the
        first call of the provider, so a refused run spends no money of the visitor (ADR-038).

        The run carries the case of the application, and the coordinator of the caller keeps the case it was built
        with: a coordinator is never rewritten by the facade (ADR-038).

        The file of the ledger of the run goes away when the run does not start, whatever the refusal of the
        coordinator was: the route owns that removal, and a run that started removes the file of its own ledger when
        it ends (ADR-038).

        A router without a case refuses the run with a readable reason, before the branch of the visitor is read
        (ADR-038).
        """
        _refuse_when_offline()
        session = _session_of(cookie, issuer)
        payload = await _payload_of_the_run(request, vault)
        if payload.mode != LIVE_MODE:
            raise ContractError(
                422,
                CODE_WRONG_MODE,
                "this route runs the live mode only, and the deterministic sandbox has its own route",
            ) from None
        _refuse_a_session_that_may_not_run_the_live_mode(session, the_capabilities)
        _refuse_a_model_the_allowlist_does_not_hold(registry, payload)
        _refuse_a_run_without_a_case(case)
        run_id = f"{RUN_ID_PREFIX}{secrets.token_hex(8)}"
        # The ledger of the visitor, materialized in the file of the run. The run never starts without it (ADR-038).
        ledger = _the_ledger_of_the_run(branch_layer, session, payload, the_runtime, run_id)
        plan = LiveRunPlan(
            run_id=run_id,
            session_id=session,
            model_profile_id=payload.model_profile_id or "",
            credential_handle=payload.credential_handle or "",
            question=payload.question,
            budget=_budget_of(payload.limits),
            account_id=payload.account_id,
            scenario_id=payload.scenario_id,
            sandbox_id=payload.sandbox_id,
            expected_revision=payload.expected_revision,
            variant=payload.variant,
            ledger=ledger,
        )
        try:
            _start_the_run_that_never_leaves_the_ledger_behind(coordinator, plan, case, ledger)
        except LiveModeOffline as refusal:
            raise ContractError(503, CODE_LIVE_MODE_OFFLINE, str(refusal)) from None
        except ByokError as refusal:
            code = CODE_CAPABILITY_MISSING if isinstance(refusal, CapabilityMissing) else CODE_MODEL_NOT_ALLOWED
            raise ContractError(422, code, str(refusal)) from None
        body = {
            "run_id": plan.run_id,
            "status": "running",
            "mode": LIVE_MODE,
        }
        headers = {
            SCHEMA_VERSION_HEADER: SCHEMA_VERSION,
            BILLING_DISCLOSURE_HEADER: BILLING_DISCLOSURE_TEXT,
            KEY_ERASURE_HEADER: KEY_ERASURE_TEXT,
            **NO_STORE_HEADERS,
        }
        return JSONResponse(status_code=201, content=body, headers=headers)

    @router.get("/v1/live-runs/{run_id}")
    def state_of_run(
        run_id: str,
        cookie: Annotated[str | None, Security(SESSION_SCHEME)],
    ) -> JSONResponse:
        """The state of a run: its status, its answer and the reason it ended, when it ended."""
        session = _session_of(cookie, issuer)
        _own_run(coordinator, run_id, session)
        result = coordinator.result(run_id)
        body = {
            "run_id": run_id,
            "status": coordinator.status(run_id),
            "answer": result.answer if result is not None else "",
            "error": result.error if result is not None else None,
            "best_effort": result.best_effort if result is not None else False,
            "cancel_requested": coordinator.cancel_requested(run_id),
            "provider": result.provider if result is not None else None,
            "model_profile_id": result.model_profile_id if result is not None else None,
            "model_id": result.model_id if result is not None else None,
        }
        return JSONResponse(
            status_code=200,
            content=body,
            headers={SCHEMA_VERSION_HEADER: SCHEMA_VERSION, KEY_ERASURE_HEADER: KEY_ERASURE_TEXT},
        )

    @router.get("/v1/live-runs/{run_id}/events")
    def stream_of_run(
        run_id: str,
        cookie: Annotated[str | None, Security(SESSION_SCHEME)],
    ) -> StreamingResponse:
        """The stream of the trace of a run, until the terminal event (FR-020).

        The stream carries the events of the trace and nothing else. It never carries the key of the visitor, because
        the trace of a live run never carries it (FR-018).
        """
        session = _session_of(cookie, issuer)
        _own_run(coordinator, run_id, session)
        return StreamingResponse(
            _events_of(coordinator, run_id),
            media_type="text/event-stream",
            headers={
                SCHEMA_VERSION_HEADER: SCHEMA_VERSION,
                KEY_ERASURE_HEADER: KEY_ERASURE_TEXT,
                "Cache-Control": "no-store",
            },
        )

    @router.post("/v1/live-runs/{run_id}/cancel")
    def cancel_run(
        run_id: str,
        cookie: Annotated[str | None, Security(SESSION_SCHEME)],
    ) -> JSONResponse:
        """Cancels a run and says that the cancellation of a call in flight is a best effort (FR-019).

        The calls that have not started never start (SC-010), and the partial trace stays visible. The answer does
        not wait for the end of the run: a call that is already at the provider cannot be stopped, and a route that
        waited for it would wait for the provider.

        The answer says what really happened: a run that is already over was not cancelled, and the message of the
        cancellation is never the answer of a run that finished before the visitor asked (FR-019).
        """
        session = _session_of(cookie, issuer)
        _own_run(coordinator, run_id, session)
        cancelled = coordinator.cancel(run_id)
        status = coordinator.status(run_id) or "cancelling"
        message = (
            "the run was cancelled; the cancellation of a call that was already at the provider is a best effort "
            "and is not a guarantee"
            if cancelled
            else f"the run was already over: its status is '{status}', and there was nothing to stop"
        )
        body = {
            "run_id": run_id,
            "status": status,
            "best_effort": coordinator.best_effort_of(run_id),
            "message": message,
        }
        return JSONResponse(
            status_code=200,
            content=body,
            headers={SCHEMA_VERSION_HEADER: SCHEMA_VERSION, KEY_ERASURE_HEADER: KEY_ERASURE_TEXT},
        )

    @router.get("/v1/live-runs/{run_id}/cost")
    def cost_of_run(
        run_id: str,
        cookie: Annotated[str | None, Security(SESSION_SCHEME)],
    ) -> JSONResponse:
        """What the run consumed: the calls, the tokens, the elapsed time and the two costs (FR-010).

        The observed cost and the estimated cost are two numbers and never one, and a run whose model has no verified
        price shows no amount at all (FR-011).
        """
        session = _session_of(cookie, issuer)
        _own_run(coordinator, run_id, session)
        result = coordinator.result(run_id)
        if result is None:
            raise ContractError(409, CODE_RUN_RUNNING, "the run is still running") from None
        body = _cost_body(run_id, result.status, result.report)
        return JSONResponse(
            status_code=200,
            content=body,
            headers={SCHEMA_VERSION_HEADER: SCHEMA_VERSION, KEY_ERASURE_HEADER: KEY_ERASURE_TEXT},
        )

    return router


def _session_of(cookie_value: str | None, issuer: SessionIssuer) -> str:
    """The owner session of the request, taken from the cookie of the demo.

    Why the cookie and never a header: the identifier decides what a visitor may read, and the browser never handles
    it in a place a third party can read.
    """
    try:
        return issuer.session_id(cookie_value)
    except InvalidSession:
        raise ContractError(401, CODE_SESSION_REQUIRED, "no valid session") from None


def _session_of_the_live_mode(issuer: SessionIssuer) -> DemoSession:
    """The session of the visitor of the live mode: the session of the demo with the live mode among its modes.

    Why the capability is added here and not in the session issuer: the issuer of the demo is the issuer of the
    sandbox as well, and the sandbox has no key of a provider, so a session of the sandbox may not run the live
    mode. The live mode says so when it issues the session of the live flow (FR-024).
    """
    session = issuer.issue()
    return replace(session, mode_capabilities=tuple(sorted({*session.mode_capabilities, LIVE_MODE})))


def _accept_a_credential(
    vault: CredentialVault,
    secret: str,
    provider: str,
    session: str,
    cookie_value: str | None,
    issuer: SessionIssuer,
) -> CredentialHandle:
    """Accepts the key of the visitor with a time to live that never outlives the session that holds it (FR-022).

    Why the life is computed here and not in the vault: the vault is a dependency of the application and it knows
    nothing of the session, and the facade is the only layer that knows both how much life the vault has and how
    much life the session of the visitor has left. The life is handed over to the vault as an argument, and nothing
    of the vault is changed while the acceptance happens: a vault whose life was written by the facade for the
    moment of the acceptance would show a foreign life to every other reader of it, and two acceptances of the same
    process could swap their lives (FR-022).
    """
    ttl = _the_time_to_live_of_a_credential(vault, cookie_value, issuer)
    return vault.accept(secret, provider, session_id=session, ttl_seconds=ttl)


def _the_time_to_live_of_a_credential(vault: CredentialVault, cookie_value: str | None, issuer: SessionIssuer) -> int:
    """The time to live of a credential: the smaller of the life of the vault and the life left in the session.

    Why the life that is left and not the whole life of the session: the session of the visitor was issued some time
    ago, and a credential that lives until the end of that whole life outlives the session that holds it. The
    credential of a visitor dies with the session, and never later (FR-022).
    """
    life = min(float(vault.ttl_seconds), _the_seconds_left_of_the_session(cookie_value, issuer))
    # A credential lives at least one second, because a credential that dies at once is a credential nobody can use.
    return max(1, int(life))


def _the_seconds_left_of_the_session(cookie_value: str | None, issuer: SessionIssuer) -> float:
    """The seconds the session of the visitor has left, and the life of the issuer when the cookie says nothing.

    Why the stamp of the cookie: the issuer signs the expiry of the session inside the cookie of the demo, so the
    stamp is the second the session dies, and the credential of that session has to die no later than that
    (FR-022). The fallback is the life of the issuer, which is the longest life a session of that issuer can have.
    """
    if cookie_value:
        parts = cookie_value.split(".")
        if len(parts) == 3:
            try:
                return float(int(parts[1])) - time.time()
            except ValueError:
                pass
    return float(issuer.ttl_seconds)


def _refuse_a_model_the_allowlist_does_not_hold(registry: ProviderRegistry, payload: LiveRunRequest) -> None:
    """Refuses a model that the server may not run, before the branch of the visitor is even asked (FR-027, FR-015).

    Why the model comes first: the model is a property of the request itself, and a request that names a model the
    server may not run is refused whatever the branch of the visitor says. The coordinator checks the model again
    when the run starts, and this check is here so that the answer comes before the branch of the visitor is read.

    Why the refusal never names the identifier: the identifier is a value the visitor sent (FR-018, SC-001).
    """
    try:
        resolve_profile(registry, payload.model_profile_id or "", variant=payload.variant)
    except CapabilityMissing as refusal:
        raise ContractError(422, CODE_CAPABILITY_MISSING, str(refusal)) from None
    except ByokError as refusal:
        raise ContractError(422, CODE_MODEL_NOT_ALLOWED, str(refusal)) from None


def _refuse_a_run_without_a_case(case: CaseExecutor | None) -> None:
    """Refuses a run of a deployment that has no case, before the branch of the visitor is read (ADR-038).

    Why the refusal and not the case of the coordinator: the coordinator may carry the default case, which asks the
    model once with the question of the request, and a run that answers with it never reads the ledger of the
    visitor. The live route runs the case of the application, and a router that has no case cannot serve a run
    (ADR-038).

    Why the message never carries a value of the visitor: the reason is a property of the deployment, and the body
    of the request may hold the key of the provider of the visitor (FR-018, SC-001).
    """
    if case is not None:
        return
    raise ContractError(
        503,
        CODE_CASE_MISSING,
        "this deployment has no case of its own, so the live route cannot run a run: "
        "the run would answer without reading the ledger of the visitor",
    ) from None


def _start_the_run_that_never_leaves_the_ledger_behind(
    coordinator: LiveRunCoordinator,
    plan: LiveRunPlan,
    case: CaseExecutor | None,
    ledger: LedgerView | None,
) -> None:
    """Starts the run, and the file of the ledger goes away when the run does not start (ADR-038).

    Why the route owns the removal: a refusal that the route does not know is a run that never started, and the rows
    of a visitor may not stay on the disk of the server for a run that never happened. The route cannot know every
    way a coordinator may refuse, so the removal belongs to the one place that sees them all (ADR-038).

    Why the flag and not the clause of the refusal: the file goes away on every path where the run did not start,
    and the path of the success is the only one that leaves the file alone, because a run that started removes the
    file of its own ledger when it ends (ADR-038).

    Why the removal never raises: the file is already gone or already unreadable, and the run has answered.
    """
    started = False
    try:
        coordinator.start(plan, case=case)
        # The run started, so the file of the ledger belongs to the run until the run ends.
        started = True
    finally:
        if not started:
            remove_the_ledger_of_the_run(ledger)


def _the_ledger_of_the_run(
    branch_layer: BranchLayer | None,
    session: str,
    payload: LiveRunRequest,
    runtime: Path,
    run_id: str,
) -> LedgerView:
    """The ledger of the visitor, materialized in the file of the run (ADR-038).

    Why the branch is resolved before the run starts: every refusal of the layer happens before the first call of the
    provider, so a refused run spends no money of the visitor (ADR-038).

    Why an application without a branch layer refuses the run: the fallback of the configuration is the whole
    published ledger of the repository, with the rows of every account of it, and the run of a visitor may never read
    it (ADR-038).

    Why the refusals keep the codes of the contract of the sandbox: the two facades cannot disagree about what a
    branch holds, and the visitor reads the same answers in the sandbox and in the live mode (ADR-038).

    Why the messages never carry a value of the visitor: the refusal names the reason and nothing else, and the
    values of the request may hold the key of the provider of the visitor (FR-018, SC-001).

    Why the route does not create the folder of the run: the materialization creates it, and a folder that a
    refused run leaves behind is a folder of nothing that nobody asked for (ADR-038).

    Why the file goes away when the layer refuses: a file that a refused run leaves behind holds the rows of a
    visitor on the disk of the server for a run that never happened (ADR-038).
    """
    if branch_layer is None:
        raise ContractError(
            503,
            CODE_BRANCH_LAYER_MISSING,
            "this deployment has no branch layer, so there is no ledger of the visitor to read: "
            "the run is refused instead of reading the ledger of the configuration",
        ) from None
    target = runtime / RUNS_FOLDER_NAME / run_id / LEDGER_FILE_NAME
    try:
        return branch_layer.ledger_view(
            session,
            payload.sandbox_id,
            account_id=payload.account_id,
            expected_revision=payload.expected_revision,
            target=target,
        )
    except (
        BranchNotFound,
        BranchExpired,
        BranchHashMismatch,
        LedgerAccountMismatch,
        LedgerRevisionMoved,
    ) as refusal:
        # The layer refused, so no run starts, and the file of the ledger goes away with it (ADR-038).
        remove_the_ledger_file(target)
        raise _the_contract_error_of_the_ledger(refusal) from None


def _the_contract_error_of_the_ledger(refusal: Exception) -> ContractError:
    """The refusal of the layer of the branch, as the refusal of the facade.

    Why the refusals keep the codes of the contract of the sandbox: the two facades cannot disagree about what a
    branch holds, and the visitor reads the same answers in the sandbox and in the live mode (ADR-038).

    Why the messages never carry a value of the visitor: the refusal names the reason and nothing else, and the
    values of the request may hold the key of the provider of the visitor (FR-018, SC-001).
    """
    if isinstance(refusal, BranchNotFound):
        return ContractError(404, CODE_NOT_FOUND, GENERIC_NOT_FOUND)
    if isinstance(refusal, BranchExpired):
        return ContractError(409, CODE_BRANCH_EXPIRED, "the branch expired: fork the scenario again")
    if isinstance(refusal, BranchHashMismatch):
        return ContractError(
            409,
            CODE_BRANCH_HASH_MISMATCH,
            "the branch cannot prove its own state: fork the scenario again",
        )
    if isinstance(refusal, LedgerAccountMismatch):
        return ContractError(
            422,
            CODE_ACCOUNT_MISMATCH,
            "the account of the request is not the account of the branch",
        )
    if isinstance(refusal, LedgerRevisionMoved):
        return ContractError(
            409,
            CODE_REVISION_MOVED,
            "the branch moved to another revision: read it again and try once more",
        )
    # The layer refused with something the facade does not know: the refusal travels as it is, because a facade
    # that answered with the code of another refusal would lie about the branch (ADR-038).
    raise refusal


def _refuse_a_session_that_may_not_run_the_live_mode(session: str, capabilities: SessionCapabilities) -> None:
    """Refuses a live run for a session that may not run the live mode (FR-024).

    Why the facade asks the session: the modes of a session are declared when the session is issued, and a run of
    the live mode is a run of a mode. A session that may not run the live mode never runs it (FR-024).
    """
    if LIVE_MODE not in capabilities.of(session):
        raise ContractError(
            403,
            CODE_MODE_NOT_ALLOWED,
            "this session may not run the live mode: a session of the live flow is the one the live mode issues",
        ) from None


async def _payload_of_the_run(request: Request, vault: CredentialVault) -> LiveRunRequest:
    """The body of the request of a live run, checked against the published contract.

    Why the raw body is checked and not the parsed model: the contract says what the caps of a run are, and a cap
    that arrives as a text is a body the contract does not accept. The model is the second layer, and it turns the
    body into the typed request (FR-007, FR-025).

    Why the message of the refusal carries no value of the visitor: the body of a visitor is untrusted, and the value
    that fails the contract may be the key of the provider of the visitor (FR-018, SC-001).
    """
    raw = await request.body()
    try:
        body = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ContractError(422, CODE_INVALID_REQUEST, "the request does not match the contract") from None
    _refuse_a_body_that_is_not_the_contract(body, vault)
    try:
        return LiveRunRequest.model_validate(body)
    except ValidationError:
        raise ContractError(422, CODE_INVALID_REQUEST, "the request does not match the contract") from None


def _refuse_a_body_that_is_not_the_contract(body: Any, vault: CredentialVault) -> None:
    """Refuses a body that the published contract of the request does not accept (FR-025).

    Why the contract is the judge and not the model of the server: the contract is what a client is written against,
    and a server that accepts a body the contract forbids breaks the contract (FR-007).

    Why the refusal carries no value of the visitor: the message of the validator quotes the value that is wrong, and
    a visitor that pasted the key of their provider into the wrong field would read their key in the answer
    (FR-018, SC-001).
    """
    validator = _validator_of_the_request()
    errors = sorted(validator.iter_errors(body), key=_the_order_of_an_error)
    if errors:
        names = _the_names_of_the_fields_of_the_contract(_the_schema_of_the_request())
        message = vault.scrub(_the_refusal_of_a_body_that_is_not_the_contract(errors[0], names))
        raise ContractError(422, CODE_INVALID_REQUEST, message) from None


def _the_order_of_an_error(error: Any) -> tuple[str, ...]:
    """The order of the errors of the contract: the path of every error as texts, so the order never raises.

    Why the texts and not the values of the path: the path of an error of a contract that carries an array holds the
    index of the item, and a number compared with a text raises, and a route that raises answers `500` to a body that
    the visitor sent (FR-025).
    """
    return tuple(str(part) for part in error.path)


def _the_refusal_of_a_body_that_is_not_the_contract(error: Any, names: set[str]) -> str:
    """The refusal of a body the contract does not accept, without any value of the visitor.

    Why the field is named and the value is not: the visitor needs to know which field the contract refused, and the
    value of that field may be the key of the provider of the visitor (FR-018, SC-001).
    """
    check = str(error.validator)
    if check == "required":
        return "the request does not match the contract: a field the contract requires is missing"
    if check == "additionalProperties":
        return "the request does not match the contract: the body carries a field the contract does not have"
    reason = _REASONS_OF_THE_VALIDATOR.get(check, "does not carry a value the contract allows")
    pointer = _the_pointer_of_the_field_of_the_error(error, names)
    if not pointer:
        return f"the request does not match the contract: {reason}"
    return f"the request does not match the contract: the field '{pointer}' {reason}"


def _the_pointer_of_the_field_of_the_error(error: Any, names: set[str]) -> str:
    """The pointer of the field that the contract refused, named by the contract and never by the visitor.

    Why the names of the contract decide: a body may carry a field that the contract does not have, and the pointer
    of the refusal may name only a field that the contract published (FR-018, SC-001).
    """
    segments = [str(part) for part in error.absolute_path]
    if not segments or any(segment not in names for segment in segments):
        return ""
    return ".".join(segments)


def _the_names_of_the_fields_of_the_contract(schema: dict[str, Any], names: set[str] | None = None) -> set[str]:
    """The names of the fields of the published contract, at every level of it.

    Why the names come from the contract: the pointer of the refusal names a field of the contract, so a body that
    carries a value in the name of a field cannot make the refusal repeat that value (FR-018, SC-001).
    """
    collected = names if names is not None else set()
    for name, sub in (schema.get("properties") or {}).items():
        collected.add(name)
        if isinstance(sub, dict):
            _the_names_of_the_fields_of_the_contract(sub, collected)
    return collected


def _the_schema_of_the_request() -> dict[str, Any]:
    """The published contract of the request that starts a live run, read from the published file.

    Why the schema is read from the published file: the contract is the one thing that may not drift, and a copy of
    it inside the server would drift the day the contract changes (FR-025).
    """
    return json.loads(RUN_REQUEST_SCHEMA_PATH.read_text(encoding="utf-8"))


def _validator_of_the_request() -> Any:
    """The validator of the published contract of the request that starts a live run.

    Why the refusal is not the one of a bad body: the body of the visitor may be perfect, and a status that blames
    it sends the visitor to look in the wrong place. The deployment is what is missing here.
    """
    try:
        from jsonschema import Draft202012Validator
    except ImportError as exc:  # jsonschema belongs to the api extra, and the facade refuses without it
        raise ContractError(503, CODE_CONTRACT_UNAVAILABLE, _MESSAGE_WITHOUT_JSONSCHEMA) from exc
    return Draft202012Validator(_the_schema_of_the_request())


def _refuse_when_offline() -> None:
    """Refuses the live mode while the product runs offline, with an answer that names the reason.

    Why the rule lives here and not in the vault: the vault never reads a global setting, on purpose (ADR-033), and
    the decision to offer a mode at all belongs to the facade (FR-001, FR-029).
    """
    if offline():
        raise ContractError(
            503,
            CODE_LIVE_MODE_OFFLINE,
            "the live mode is off because the product runs offline (LEDGERLENS_OFFLINE=1); "
            "the replay and the sandbox keep working exactly as before",
        )


def _own_run(coordinator: LiveRunCoordinator, run_id: str, session: str) -> None:
    """Refuses the run of another session with the answer of a run that does not exist.

    Why the answer is the same: a visitor must not learn that a run of another visitor exists (FR-006, SC-002).
    """
    owner = coordinator.session_of(run_id)
    if owner is None or owner != session:
        raise ContractError(404, CODE_NOT_FOUND, "no such run") from None


def _budget_of(limits: RunLimits) -> RunBudget:
    """The caps of the request as the budget of the run (FR-025)."""
    return RunBudget(
        max_model_calls=limits.max_model_calls,
        max_tool_calls=limits.max_tool_calls,
        max_input_tokens=limits.max_input_tokens,
        max_output_tokens=limits.max_output_tokens,
        max_estimated_usd=limits.max_estimated_usd,
        max_wall_seconds=float(limits.max_wall_seconds),
    )


def _price_note(pricing: Pricing) -> str:
    """What the visitor reads about the price of a model (FR-011, FR-031)."""
    if not pricing.is_verified:
        return "the price of this model is unknown, so no amount is shown"
    return f"the price was verified on {pricing.last_verified} and comes from {pricing.source}"


def _cost_body(run_id: str, status: str, report: CostReport) -> dict[str, Any]:
    """The cost report as the answer of the route: the two costs apart and no amount when the price is unknown."""
    return {
        "run_id": run_id,
        "status": status,
        "model_calls": report.model_calls,
        "tool_calls": report.tool_calls,
        "calls_by_model": dict(report.calls_by_model),
        "input_tokens": report.input_tokens,
        "output_tokens": report.output_tokens,
        "elapsed_seconds": round(report.elapsed_seconds, 3),
        "observed_cost_usd": None if report.observed_cost_usd is None else str(report.observed_cost_usd),
        "estimated_cost_usd": None if report.estimated_cost_usd is None else str(report.estimated_cost_usd),
        "price_known": report.price_known,
        "money_cap_authoritative": report.money_cap_authoritative,
        "cut_by": report.cut_by,
        "usage_without_reservation": list(report.usage_without_reservation),
        "note": (
            "the observed cost and the estimated cost are two numbers: the first is what the provider reported and the "
            "second is what the run planned"
            if report.price_known
            else "the price of this run is unknown, so no amount is shown"
        ),
    }


def _events_of(coordinator: LiveRunCoordinator, run_id: str) -> Iterator[str]:
    """The events of the trace of a run, as they arrive, until the terminal event.

    Why the stream polls the sink and does not subscribe to it: the sink is the one place the events live, and a
    client that reconnects reads the same events by their number.
    """
    after = 0
    deadline = time.monotonic() + STREAM_TIMEOUT_SECONDS
    while True:
        events = coordinator.events(run_id, after, limit=100)
        for event in events:
            after = event.seq
            yield f"event: {event.event_type}\ndata: {event.to_json()}\n\n"
        if any(event.event_type in TERMINAL_EVENTS for event in events):
            return
        if time.monotonic() > deadline:
            return
        time.sleep(0.05)
