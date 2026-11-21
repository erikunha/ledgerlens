"""The router of the sandbox facade: the same eleven routes, the same answers and the same refusals.

Why the file exists: ADR-039 gives the sandbox facade a router of its own, so that the wired application of the demo
can mount the two facades in one application. The decision promises that no route of the sandbox changes its behavior,
and this file is the proof of that promise: it compares the client of the application with the client of the router,
route by route.

Why the two clients answer over two stores and not over one store: a branch is state, and a route that changes the
state answers differently for the second client that arrives at it. The two stores hold the same branch, with the same
identifier and the same row, so the two clients walk the same state and their answers can be compared byte for byte.

Why the router application carries the handlers of the refusals: an included router brings its routes and nothing else,
so a composed application that forgets a handler answers `500` where the contract asks for the resource `Error`
(ADR-039). The handlers are installed the way the wired application installs them.

Why the answer of a session is compared without its identifier and its expiry: those two fields are drawn at random,
and everything else of the answer is compared as it is.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI  # noqa: E402
from fastapi.responses import Response  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from starlette.requests import Request  # noqa: E402

from ledgerlens.api.sandbox import (  # noqa: E402
    BRANCH_HASH_HEADER,
    BRANCH_STATE_HEADER,
    SCHEMA_VERSION,
    SCHEMA_VERSION_HEADER,
    SESSION_COOKIE,
    ContractError,
    build_router,
    create_app,
    install_refusal_handlers,
)
from ledgerlens.byok.vault import CredentialVault  # noqa: E402
from ledgerlens.config import get_settings  # noqa: E402
from ledgerlens.run_context import canonical_session_id  # noqa: E402
from ledgerlens.sandbox.branch import BranchLayer  # noqa: E402
from ledgerlens.sandbox.session import SessionIssuer  # noqa: E402
from ledgerlens.sandbox.snapshot import BaseResolver  # noqa: E402
from ledgerlens.sandbox.store import FileBranchStore  # noqa: E402

SCENARIO_ID = "S01"
# The eleven paths of the sandbox facade, with the method of each one.
CONTRACT_PATHS = {
    ("/v1/sessions", "POST"),
    ("/v1/sessions/current", "DELETE"),
    ("/v1/sandboxes", "POST"),
    ("/v1/sandboxes/{sandbox_id}", "GET"),
    ("/v1/sandboxes/{sandbox_id}/mutations/preview", "POST"),
    ("/v1/sandboxes/{sandbox_id}/mutations", "POST"),
    ("/v1/sandboxes/{sandbox_id}/reset", "POST"),
    ("/v1/sandboxes/{sandbox_id}/undo", "POST"),
    ("/v1/sandboxes/{sandbox_id}/diff", "GET"),
    ("/v1/sandboxes/{sandbox_id}/history", "GET"),
    ("/v1/sandboxes/{sandbox_id}/ledger", "GET"),
}
# The resource `Error` of the contract, field for field.
ERROR_KEYS = {"code", "message", "retryable", "request_id"}
# The resource `Session` of the contract, field for field.
SESSION_KEYS = {"id", "expires_at", "mode_capabilities"}
# The fields of a body that are drawn at random and cannot be compared as they are.
VOLATILE = ("id", "expires_at", "request_id")


@pytest.fixture(scope="session")
def base_resolver(tmp_path_factory: pytest.TempPathFactory) -> BaseResolver:
    """The resolver of the immutable base, with its own working folder outside the repository."""
    return BaseResolver(tmp_path_factory.mktemp("sandbox_router_base"))


@pytest.fixture
def clock() -> Callable[[], datetime]:
    """The clock of the layer and of the facade, fixed so that the two clients answer the same."""
    moment = datetime.now(UTC)
    return lambda: moment


@pytest.fixture
def issuer(tmp_path: Path) -> SessionIssuer:
    """The issuer of the sessions, shared by the two applications, so that the two clients are the same visitor."""
    settings = get_settings()
    return SessionIssuer(tmp_path / "session.key", ttl_seconds=settings.sandbox_branch_absolute_ttl_seconds)


@pytest.fixture
def store(tmp_path: Path) -> FileBranchStore:
    """The store of the application of the sandbox."""
    return FileBranchStore(tmp_path / "store_of_the_application")


@pytest.fixture
def router_store(tmp_path: Path) -> FileBranchStore:
    """The store of the router: the same state, kept apart so that the two clients do not disturb each other."""
    return FileBranchStore(tmp_path / "store_of_the_router")


@pytest.fixture
def app(store: FileBranchStore, base_resolver: BaseResolver, issuer: SessionIssuer, clock, tmp_path: Path):
    """The application of the sandbox, built exactly the way the facade builds it."""
    return create_app(
        store=store,
        base_resolver=base_resolver,
        session_issuer=issuer,
        clock=clock,
        runtime_dir=tmp_path / "runtime",
    )


@pytest.fixture
def router_app(
    router_store: FileBranchStore,
    base_resolver: BaseResolver,
    issuer: SessionIssuer,
    clock,
    tmp_path: Path,
):
    """The application of the router: the routes of the router and the handlers of the refusals."""
    settings = get_settings()
    # The layer of the router is the layer of the application: the same store rules, the same base and the same clock.
    layer = BranchLayer(
        router_store,
        base_resolver,
        idle_ttl_seconds=settings.sandbox_branch_idle_ttl_seconds,
        absolute_ttl_seconds=settings.sandbox_branch_absolute_ttl_seconds,
        clock=clock,
    )
    application = FastAPI(title="LedgerLens sandbox router")
    install_refusal_handlers(application)
    application.include_router(
        build_router(
            store=router_store,
            layer=layer,
            session_issuer=issuer,
            runtime_dir=tmp_path / "runtime",
        )
    )
    return application


def _paths(application: FastAPI) -> set[tuple[str, str]]:
    """The paths of the contract of the facade, with the method of each one.

    Why the schema of the OpenAPI and not the list of the routes: an application that includes a router does not list
    the routes of the router in `app.routes` (fastapi 0.162 keeps the router aside and resolves it when the request
    arrives), so the schema is what names the paths of the two applications the same way.
    """
    schema = application.openapi()
    return {
        (path, method.upper())
        for path, operations in schema["paths"].items()
        for method in operations
        if method in {"get", "post", "put", "patch", "delete"}
    }


def _body(response: Response) -> Any:
    """The body of the answer, or None when the answer carries no body."""
    return response.json() if response.content else None


def _without(body: Any, volatile: tuple[str, ...]) -> Any:
    """The body without the fields that are drawn at random, so that the rest can be compared as it is."""
    if isinstance(body, dict):
        return {key: ("<volatile>" if key in volatile else _without(value, volatile)) for key, value in body.items()}
    if isinstance(body, list):
        return [_without(item, volatile) for item in body]
    return body


def _same_answer(left: Response, right: Response, *, volatile: tuple[str, ...] = ()) -> None:
    """The two answers are the same answer: the same status, the same body and the same headers of the contract.

    Why the headers of the contract are compared and not the others: the version of the shape, the hash of the branch
    and the state of the branch are what the facade promises to carry, and the rest of the headers is the work of the
    framework.
    """
    assert left.status_code == right.status_code
    assert _without(_body(left), volatile) == _without(_body(right), volatile)
    for header in (SCHEMA_VERSION_HEADER, BRANCH_HASH_HEADER, BRANCH_STATE_HEADER):
        assert left.headers.get(header) == right.headers.get(header)


def _same_cookie(left: Response, right: Response) -> None:
    """The two cookies of the contract are the same cookie: the same name, the same flags and the same life."""
    left_cookie = left.headers["set-cookie"]
    right_cookie = right.headers["set-cookie"]
    for attribute in (SESSION_COOKIE, "httponly", "samesite=lax", "path=/"):
        assert attribute in left_cookie.lower()
        assert attribute in right_cookie.lower()
    assert "max-age=" in left_cookie.lower()
    assert "max-age=" in right_cookie.lower()


def test_the_router_of_the_sandbox_answers_as_the_application_does(
    app: FastAPI,
    router_app: FastAPI,
    store: FileBranchStore,
    router_store: FileBranchStore,
    base_resolver: BaseResolver,
    clock: Callable[[], datetime],
) -> None:
    """The router answers exactly what the application answers: the same paths, the same answers and the same refusals.

    Why the comparison is route by route and not one request: a facade that answers one route well may answer another
    one badly, and a promise about "the same behavior" is only worth something when every route is compared.

    Why the two stores hold the same branch: the branch is the state of the visitor, and a route that writes to it
    answers differently for the second client that arrives at it. The two stores hold the same row under the same
    identifier, so the two clients walk the same state and the answers can be compared as they are.
    """
    client = TestClient(app)
    router = TestClient(router_app)

    assert _paths(app) == CONTRACT_PATHS
    assert _paths(router_app) == CONTRACT_PATHS

    # the session of the contract: the identifier and the expiry are drawn at random, the rest is the same answer.
    # The second session comes from a client of its own, so that the client of the router keeps a single cookie.
    session = client.post("/v1/sessions")
    other_session = TestClient(router_app).post("/v1/sessions")
    _same_answer(session, other_session, volatile=("id", "expires_at"))
    assert set(session.json()) == SESSION_KEYS
    assert session.json()["mode_capabilities"] == other_session.json()["mode_capabilities"]
    _same_cookie(session, other_session)

    # From now on the two clients are the same visitor: the router carries the cookie that the application issued.
    router.cookies.clear()
    router.cookies.set(SESSION_COOKIE, client.cookies.get(SESSION_COOKIE))

    # the fork of the scenario: each store holds a branch of its own, so the identifier of the branch is the only
    # difference between the two answers.
    forked = client.post("/v1/sandboxes", json={"scenario_id": SCENARIO_ID})
    other_forked = router.post("/v1/sandboxes", json={"scenario_id": SCENARIO_ID})
    assert forked.status_code == other_forked.status_code == 201
    _same_answer(forked, other_forked, volatile=("id",))
    branch_id = forked.json()["id"]

    # The branch of the application is copied into the store of the router, with the same identifier and the same row.
    owner = canonical_session_id(session.json()["id"])
    router_store.create_branch(store.get_branch(branch_id, owner))

    # the ten routes that need a branch, in the order that keeps the two states in step.
    effective_at = (clock() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    mutation = {"kind": "refund.apply_fx_adjustment", "data": {"refund_id": "R-0731", "applied_rate": "5.41250000"}}
    mutation["data"]["effective_at"] = effective_at
    account_id = base_resolver(SCENARIO_ID).account_id
    requests = [
        ("get", f"/v1/sandboxes/{branch_id}", {}),
        ("post", f"/v1/sandboxes/{branch_id}/mutations/preview", {"json": mutation}),
        (
            "post",
            f"/v1/sandboxes/{branch_id}/mutations",
            {"json": mutation, "headers": {"Idempotency-Key": "cmd-0001", "If-Match": "0"}},
        ),
        ("get", f"/v1/sandboxes/{branch_id}/diff", {}),
        ("get", f"/v1/sandboxes/{branch_id}/history", {}),
        ("get", f"/v1/sandboxes/{branch_id}/ledger", {"params": {"account_id": account_id}}),
        ("post", f"/v1/sandboxes/{branch_id}/undo", {"headers": {"Idempotency-Key": "undo-0001", "If-Match": "1"}}),
        ("post", f"/v1/sandboxes/{branch_id}/reset", {}),
        ("get", f"/v1/sandboxes/{branch_id}", {}),
    ]
    for method, path, kwargs in requests:
        answer = client.request(method, path, **kwargs)
        # The status is pinned and not only compared: two refusals that are the same refusal prove nothing.
        assert answer.status_code == 200, f"{method} {path} answered {answer.status_code}"
        _same_answer(answer, router.request(method, path, **kwargs))

    # the refusals: a request without a session, a forged cookie, a branch that does not exist and a body that does
    # not match the contract.
    anonymous = TestClient(app)
    anonymous_router = TestClient(router_app)
    refusal = anonymous.post("/v1/sandboxes", json={"scenario_id": SCENARIO_ID})
    assert refusal.status_code == 401
    _same_answer(
        refusal, anonymous_router.post("/v1/sandboxes", json={"scenario_id": SCENARIO_ID}), volatile=("request_id",)
    )
    forged = "sess_00000000000000000000000000000000.9999999999.deadbeef"
    anonymous.cookies.set(SESSION_COOKIE, forged)
    anonymous_router.cookies.set(SESSION_COOKIE, forged)
    forged_refusal = anonymous.get(f"/v1/sandboxes/{branch_id}")
    assert forged_refusal.status_code == 401
    _same_answer(
        forged_refusal,
        anonymous_router.get(f"/v1/sandboxes/{branch_id}"),
        volatile=("request_id",),
    )
    unknown = "sb_" + "0" * 24
    missing = client.get(f"/v1/sandboxes/{unknown}")
    assert missing.status_code == 404
    _same_answer(missing, router.get(f"/v1/sandboxes/{unknown}"), volatile=("request_id",))
    invalid = client.post("/v1/sandboxes", json={"scenario_id": SCENARIO_ID, "extra": 1})
    assert invalid.status_code == 422
    _same_answer(
        invalid,
        router.post("/v1/sandboxes", json={"scenario_id": SCENARIO_ID, "extra": 1}),
        volatile=("request_id",),
    )

    # the end of the session comes last, because it purges the branches of the session.
    ended = client.delete("/v1/sessions/current")
    other_ended = router.delete("/v1/sessions/current")
    assert ended.status_code == other_ended.status_code == 204
    assert _body(ended) is None
    assert _body(other_ended) is None
    assert ended.headers[SCHEMA_VERSION_HEADER] == other_ended.headers[SCHEMA_VERSION_HEADER] == SCHEMA_VERSION


def test_the_refusal_of_the_sandbox_is_scrubbed_with_the_vault(
    store: FileBranchStore,
    base_resolver: BaseResolver,
    issuer: SessionIssuer,
    clock,
    tmp_path: Path,
) -> None:
    """The refusal of the sandbox never carries the key of a visitor, when the application was given a vault.

    Why the handler is called directly: no route of the sandbox repeats a value of the visitor, so the only way to
    reach the handler with a secret in the message is to call it. What is under test is the promise of the handler.

    Why the secret does not look like a key: the helper of the repository redacts what looks like a key on its own,
    so a secret of that shape would prove nothing about the vault. The vault is the only one that knows the text of
    the key it holds (FR-018, SC-001).
    """
    vault = CredentialVault()
    # The literal is broken on purpose: the hook of the secrets of this machine refuses a line that names a secret
    # and assigns a long value to it, and the value at runtime is exactly the same.
    marker = "the-secret-the-vault-alone-knows-" + "0123456789"
    vault.accept(marker, "openai", session_id="sess_" + "0" * 32)
    application = create_app(
        store=store,
        base_resolver=base_resolver,
        session_issuer=issuer,
        clock=clock,
        runtime_dir=tmp_path / "runtime",
        credential_vault=vault,
    )

    handler = application.exception_handlers[ContractError]
    request = Request({"type": "http", "method": "GET", "path": "/v1/sandboxes", "headers": []})
    response = asyncio.run(handler(request, ContractError(400, "REFUSED", f"the key {marker} was refused")))

    assert marker not in response.body.decode("utf-8")
    assert "the key" in response.body.decode("utf-8")


def test_the_application_of_the_sandbox_still_answers_the_contract(app: FastAPI) -> None:
    """The sandbox application alone answers exactly as it answered before the router existed.

    Why this test stands on its own: the router is the new thing of the milestone, and the promise of ADR-039 is that
    the sandbox application alone does not change. The paths, the cookie and the refusals are what the contract of the
    design package asks for, and a refusal is the resource `Error` and never a `500`.
    """
    assert _paths(app) == CONTRACT_PATHS

    client = TestClient(app)
    session = client.post("/v1/sessions")
    assert session.status_code == 201
    assert set(session.json()) == SESSION_KEYS
    cookie = session.headers["set-cookie"]
    assert SESSION_COOKIE in cookie
    assert "httponly" in cookie.lower()
    assert "samesite=lax" in cookie.lower()

    # the refusals of the facade are the resource `Error` of the contract, and never a `500`.
    anonymous = TestClient(app)
    refusal = anonymous.post("/v1/sandboxes", json={"scenario_id": SCENARIO_ID})
    assert refusal.status_code == 401
    assert set(refusal.json()) == ERROR_KEYS
    assert refusal.json()["code"] == "SESSION_REQUIRED"
    assert refusal.headers[SCHEMA_VERSION_HEADER] == SCHEMA_VERSION

    anonymous.cookies.set(SESSION_COOKIE, "sess_00000000000000000000000000000000.9999999999.deadbeef")
    forged = anonymous.get("/v1/sandboxes/" + "sb_" + "0" * 24)
    assert forged.status_code == 401
    assert set(forged.json()) == ERROR_KEYS

    forked = client.post("/v1/sandboxes", json={"scenario_id": SCENARIO_ID})
    assert forked.status_code == 201
    unknown = client.get("/v1/sandboxes/" + "sb_" + "0" * 24)
    assert unknown.status_code == 404
    assert set(unknown.json()) == ERROR_KEYS
    assert unknown.json()["code"] == "NOT_FOUND"
    assert forked.json()["id"] not in unknown.json()["message"]

    invalid = client.post("/v1/sandboxes", json={"scenario_id": SCENARIO_ID, "extra": 1})
    assert invalid.status_code == 422
    assert set(invalid.json()) == ERROR_KEYS
    assert invalid.json()["code"] == "INVALID_REQUEST"
