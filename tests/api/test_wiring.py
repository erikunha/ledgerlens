"""The wired application of the demo: the two facades as one visitor, over one issuer, one store and one vault.

What the tests of this file guarantee, and why:

(a) the paths of the wired application are the union of the two contracts, with no path missing and no path
    duplicated, because the drop of the two shadowed routes is written in the factory and never left to the order
    of the mounting (ADR-039);
(b) the session of the wired application is the one of the live mode, with the capability of the live mode, the
    two disclosures and the no-store headers, because that answer is the superset of the two (ADR-039);
(c) the end of the session drops the branch, the memory of the case and the credentials of the session, because
    the end of the session is the route of the sandbox and the sandbox is given the shared vault (FR-022, ADR-030,
    ADR-039);
(d) a refusal of the wired application is the resource `Error` of the contract and never a `500`, because the
    handlers of the refusals live on the application and not on the router (ADR-039);
(e) a live case runs end to end against the wired application: the branch is forked in the sandbox, the key is
    handed over, the run starts, and the answer and the cost are read;
(f) the run reads the ledger of the branch of the visitor and never the ledger of the configuration, and the model
    of the run sees the rows of the branch and the rows of no other account (ADR-038);
(g) the wired application is one visitor and the two facades alone are still two visitors (ADR-035);
(h) the wired application starts the sweep of the expired branches and the sweeper of the credentials;
(i) the command builds the wired application and serves it, with the host and the port it was given;
(j) the order of the two mounts of the routers decides nothing: the application answers the same thing in the two
    orders (ADR-039);
(k) the plain factory of the live mode still refuses every run, and a malformed body of the wired application is
    the resource `Error` of the contract and not the answer of the framework (ADR-038, ADR-039);
(l) a refusal of the rate of the requests of the wired application carries the wait of the server in the header
    `Retry-After`, because the front of the browser reads that header and shows the wait (ADR-047).

Everything offline, with no key and no network: the provider is the fake adapter of the domain, and no test of
this file opens a socket.
"""

from __future__ import annotations

import json
import threading
import time
import tomllib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, cast

import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from ledgerlens.api import byok as byok_api  # noqa: E402
from ledgerlens.api import sandbox as sandbox_api  # noqa: E402
from ledgerlens.api.sandbox import SESSION_COOKIE  # noqa: E402
from ledgerlens.api.wiring import build_wired_app, main  # noqa: E402
from ledgerlens.byok.adapter import FakeProviderAdapter  # noqa: E402
from ledgerlens.byok.vault import CredentialVault  # noqa: E402
from ledgerlens.config import get_settings  # noqa: E402
from ledgerlens.sandbox.memory import session_memory_dir  # noqa: E402
from ledgerlens.sandbox.session import SessionIssuer  # noqa: E402
from ledgerlens.sandbox.snapshot import BaseResolver  # noqa: E402
from ledgerlens.sandbox.store import FileBranchStore  # noqa: E402

# The root of the repository, where the console script of the command is declared.
ROOT = Path(__file__).resolve().parents[2]

# The marker of the credential of the visitor: a shape that no known pattern of the repository matches, so only the
# vault and the adapter of the run can scrub it.
MARKER = "ledgerlens-wiring-marker-" + "7c1e4b9d2a60"

# The answer of the triage of the agent of the demo: a plan with the only tool the run needs, so the agent is not
# asked for a second time.
TRIAGE_ANSWER = json.dumps(
    {
        "intent": "status_lookup",
        "entities": {"transaction_ids": ["TX-2048"]},
        "urgency": "normal",
        "plan": [{"id": "S1", "goal": "read the ledger", "tool": "query_ledger", "depends_on": []}],
        "needs_clarification": False,
        "clarification_question": None,
    }
)
# The SQL of the ledger: one read only statement over an allowed table, about the transaction of the account of the
# branch of the visitor.
SQL_ANSWER = "SELECT id, status, amount_minor, currency FROM transactions WHERE id = 'TX-2048'"
# The SQL that counts the rows of the ledger the model reads, and the SQL that groups those rows by the account.
# The two questions tell the ledger of the branch of the visitor and the ledger of the configuration apart: the
# branch holds one row and one account, and the published ledger holds 2114 rows and 1418 accounts.
COUNT_SQL = "SELECT count(*) AS n FROM transactions"
GROUP_SQL = "SELECT customer_id, count(*) AS n FROM transactions GROUP BY customer_id"
# The answer of the agent of the demo, the last thing the provider says.
FINAL_ANSWER = "The payment of TX-2048 was captured and the refund is on its way."

# The model of the allowlist of the repository, the one that was really tested.
PROFILE_ID = "openai-gpt-4.1-mini"

# The scenario of the visitor and the account of that scenario. The branch of the visitor is a branch of that
# scenario, and the account of the request has to be the account of the branch (ADR-038).
SCENARIO_ID = "S01"
ACCOUNT_ID = "C-0412"

# The origin of the site of the demo, the one the deployment of the live mode declares (ADR-040).
CORS_ORIGIN = "http://localhost:3000"

# The resource `Error` of the contract, field for field.
ERROR_KEYS = {"code", "message", "retryable", "request_id"}

# The names of the settings of the rate of the requests, as the decision of ADR-047 names them.
RATE_REQUESTS_ENV = "LEDGERLENS_SANDBOX_RATE_LIMIT_REQUESTS"
RATE_WINDOW_ENV = "LEDGERLENS_SANDBOX_RATE_LIMIT_WINDOW_SECONDS"

# The code of the refusal of the rate of the requests, the one of the domain (ADR-031).
CODE_RESOURCE_LIMIT = "RESOURCE_LIMIT_EXCEEDED"

# The second scenario of the published sample, the one that the cap of the branches refuses. It is a different
# scenario from `SCENARIO_ID` on purpose: a fork of a scenario the session already holds creates no branch, and
# the reuse comes BEFORE the cap (ADR-047).
OTHER_SCENARIO_ID = "S02"


@pytest.fixture(autouse=True)
def online(monkeypatch: pytest.MonkeyPatch) -> None:
    """The live mode is enabled for the tests of the wired application.

    Why the mode is online here: the live mode refuses every credential and every run while the product is offline
    (FR-001), and the promise of this milestone is a live case that runs.
    """
    monkeypatch.setenv("LEDGERLENS_OFFLINE", "0")


@pytest.fixture(scope="module")
def store(tmp_path_factory: pytest.TempPathFactory) -> FileBranchStore:
    """The store of the branches of the tests: the file backed one, in a temporary folder.

    Why the store is given to the application: the wired application is given the store of the deployment, and the
    test reads the same store to know that the branch of the visitor is gone (ADR-039).
    """
    return FileBranchStore(tmp_path_factory.mktemp("sandbox"))


@pytest.fixture(scope="module")
def runtime(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The runtime folder of the wired application of the tests.

    Why the folder is one for the module: the base of the scenarios is built in it and it is expensive to build, so
    the tests of the module share it the way a deployment shares one runtime folder.
    """
    return tmp_path_factory.mktemp("runtime")


@pytest.fixture
def issuer(tmp_path: Path) -> SessionIssuer:
    """The issuer of the sessions of the tests, the one issuer of the wired application.

    Why the issuer is given to the application: the two facades are the same visitor when they are given the same
    issuer, and they are two visitors when they are not (ADR-035, ADR-039).
    """
    return SessionIssuer(tmp_path / "demo-session.key")


@pytest.fixture
def vault() -> CredentialVault:
    """The vault of the credentials of the tests, the one vault of the wired application."""
    return CredentialVault()


@pytest.fixture
def adapter() -> FakeProviderAdapter:
    """The fake provider of the tests, with the answers of the agent of the demo in order.

    Why the answers are those of the agent of the demo: the case of the wired application is the case of the demo,
    so the run asks the model four times and the script has to answer the four.
    """
    the_adapter = FakeProviderAdapter(provider="openai", api_key=MARKER)
    the_adapter.script_answer(TRIAGE_ANSWER)
    the_adapter.script_tool_call("query_ledger", json.dumps({"question": "the status of TX-2048"}), call_id="call_sql")
    the_adapter.script_answer(SQL_ANSWER)
    the_adapter.script_answer(FINAL_ANSWER)
    return the_adapter


@pytest.fixture
def app(
    store: FileBranchStore,
    issuer: SessionIssuer,
    vault: CredentialVault,
    adapter: FakeProviderAdapter,
    runtime: Path,
) -> FastAPI:
    """The wired application of the tests, over the fake provider and with no key of its own."""
    return build_wired_app(
        issuer=issuer,
        store=store,
        vault=vault,
        adapter_factory=lambda _provider, _key: adapter,
        runtime_dir=runtime,
    )


@pytest.fixture
def counting_adapter() -> FakeProviderAdapter:
    """The fake provider that answers the two questions about the ledger that the model read.

    Why the questions are two and not one: the count of the rows tells the ledger of the branch of the visitor and
    the ledger of the configuration apart, and the group by the account tells them apart once more, because the
    branch holds one account and the published ledger holds 1418 of them.

    Why the questions are one after the other: the run asks the model six times, and the script answers the six in
    the order they come, so the answer of each question is the answer of that question.
    """
    the_adapter = FakeProviderAdapter(provider="openai", api_key=MARKER)
    the_adapter.script_answer(TRIAGE_ANSWER)
    the_adapter.script_tool_call(
        "query_ledger", json.dumps({"question": "how many rows does the ledger hold"}), call_id="call_count"
    )
    the_adapter.script_answer(COUNT_SQL)
    the_adapter.script_tool_call(
        "query_ledger", json.dumps({"question": "which accounts does the ledger hold"}), call_id="call_group"
    )
    the_adapter.script_answer(GROUP_SQL)
    the_adapter.script_answer(FINAL_ANSWER)
    return the_adapter


@pytest.fixture
def counting_app(
    store: FileBranchStore,
    issuer: SessionIssuer,
    vault: CredentialVault,
    counting_adapter: FakeProviderAdapter,
    runtime: Path,
) -> FastAPI:
    """The wired application over the fake provider that counts the rows of the ledger.

    Why the application is another one: the script of a fake provider answers one run, and the run that counts needs
    the two questions about the ledger instead of the question of the demo.
    """
    return build_wired_app(
        issuer=issuer,
        store=store,
        vault=vault,
        adapter_factory=lambda _provider, _key: counting_adapter,
        runtime_dir=runtime,
    )


@pytest.fixture
def client(app: FastAPI) -> Any:
    """The client of the wired application, with the session of the visitor already issued.

    Why the client enters the application: the lifespan of the application starts the two sweepers, and a test that
    never enters it proves nothing about them.

    Why the session is issued here: the visitor of the demo arrives with a session, and every route of the two
    facades reads the cookie of that session.
    """
    with TestClient(app) as the_client:
        cast(Any, the_client).session = the_client.post("/v1/sessions").json()
        yield the_client


def _the_routes(app: FastAPI) -> list[Any]:
    """Every route of the application, with the included routers unfolded.

    Why the routers are unfolded: fastapi keeps an included router as one entry of the list of the routes, so a
    reader that does not unfold it sees no path of the contract at all.
    """
    routes: list[Any] = []
    for route in app.routes:
        inner = getattr(route, "original_router", None)
        routes.extend(inner.routes if inner is not None else [route])
    return routes


def _the_pairs(routes: list[Any]) -> list[tuple[str, str]]:
    """The pairs of path and method of the routes of a contract.

    Why the methods are read and not only the paths: the two contracts share the path of the session, and only the
    method says which route of the session is which.
    """
    pairs: list[tuple[str, str]] = []
    for route in routes:
        path = getattr(route, "path", "")
        if not path.startswith("/v1/"):
            continue
        for method in sorted(getattr(route, "methods", None) or set()):
            if method in {"HEAD", "OPTIONS"}:
                continue
            pairs.append((path, method))
    return pairs


def _the_two_contracts(
    store: FileBranchStore, issuer: SessionIssuer, vault: CredentialVault, runtime: Path
) -> tuple[FastAPI, FastAPI]:
    """The two applications of the facades, each one on its own.

    Why the two applications and not the two routers: the applications are the contracts of the two facades, and
    the set of the paths of the wired application has to be the union of the two of them.
    """
    sandbox_app = sandbox_api.create_app(
        store=store,
        base_resolver=BaseResolver(runtime / "bases-of-the-contracts"),
        session_issuer=issuer,
        credential_vault=vault,
        runtime_dir=runtime,
    )
    live_app = byok_api.create_app(
        vault=vault,
        session_issuer=issuer,
        runtime_dir=runtime,
    )
    return sandbox_app, live_app


def _the_branch_of_the_visitor(client: TestClient) -> str:
    """The branch of the visitor, forked in the sandbox of the wired application."""
    response = client.post("/v1/sandboxes", json={"scenario_id": SCENARIO_ID})
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def _the_credential_of_the_visitor(client: TestClient) -> str:
    """The handle of the credential of the visitor."""
    response = client.post("/v1/credentials", json={"provider": "openai", "api_key": MARKER})
    assert response.status_code == 201, response.text
    return str(response.json()["handle"])


def _the_body_of_the_run(branch_id: str, handle: str, **overrides: Any) -> dict[str, Any]:
    """The body of the route of the live run, as the published contract of the request asks for it.

    Why the body names the branch of the visitor: the run reads the ledger of the branch the visitor forked, and a
    body that names a branch of nobody is refused before the run starts (ADR-038).
    """
    body: dict[str, Any] = {
        "mode": "live_agent",
        "scenario_id": SCENARIO_ID,
        "sandbox_id": branch_id,
        "expected_revision": 0,
        "account_id": ACCOUNT_ID,
        "question": "What happened to the refund of TX-2048?",
        "variant": "B",
        "model_profile_id": PROFILE_ID,
        "credential_handle": handle,
        "limits": {
            "max_model_calls": 8,
            "max_tool_calls": 4,
            "max_wall_seconds": 30,
            "max_output_tokens": 512,
        },
    }
    body.update(overrides)
    return body


def _wait_for_the_end(client: TestClient, run_id: str, timeout: float = 20.0) -> dict[str, Any]:
    """Waits for the end of a run and answers the state of it."""
    deadline = time.monotonic() + timeout
    state: dict[str, Any] = {}
    while time.monotonic() < deadline:
        response = client.get(f"/v1/live-runs/{run_id}")
        assert response.status_code == 200, response.text
        state = dict(response.json())
        if state["status"] != "running":
            return state
        time.sleep(0.01)
    return state


def _the_event_of_the_stream(text: str, event_type: str) -> dict[str, Any]:
    """The event of the given type of the stream of the trace of a run."""
    for line in text.splitlines():
        if not line.startswith("data: "):
            continue
        event = json.loads(line[len("data: ") :])
        if event.get("event_type") == event_type:
            return dict(event)
    raise AssertionError(f"the stream of the run carries no event of the type {event_type}")


def _the_data_of_the_tools(adapter: FakeProviderAdapter) -> list[dict[str, Any]]:
    """The data of every answer of a tool of the run, one answer per query.

    Why the answers are collected by their SQL and not one by one: the history of the agent carries the answer of a
    tool in every request that follows it, so the same answer is read more than once.
    """
    by_query: dict[str, dict[str, Any]] = {}
    for call in adapter.calls:
        for message in call.messages:
            if message.role != "tool":
                continue
            data = dict(json.loads(str(message.content)).get("data") or {})
            by_query.setdefault(str(data.get("sql") or ""), data)
    return list(by_query.values())


def _the_rows_of(data: list[dict[str, Any]], *, grouped: bool) -> list[Any]:
    """The rows the model read, for the query that counts or for the one that groups by the account.

    Why the query is named and not the position: the guard rewrites the SQL of every query, so the answer of a query
    is found by the shape of the SQL that ran and not by the order of the answers.
    """
    for answer in data:
        if ("GROUP BY" in str(answer.get("sql") or "")) == grouped:
            return list(answer.get("rows") or [])
    raise AssertionError("the run never asked the ledger the question the test needs")


# --- the paths of the wired application ------------------------------------------------------------------


def test_the_paths_of_the_wired_application_are_the_two_contracts(
    app: FastAPI, store: FileBranchStore, issuer: SessionIssuer, vault: CredentialVault, runtime: Path
) -> None:
    """ADR-039: the /v1 paths are the union of the two contracts, without a repetition.

    Why the two routes are removed from the union: the session of the wired application is the one of the live mode
    and the end of the session is the one of the sandbox, so the session of the sandbox and the end of the session
    of the live mode are not part of the composition.
    """
    sandbox_app, live_app = _the_two_contracts(store, issuer, vault, runtime)
    sandbox_pairs = set(_the_pairs(_the_routes(sandbox_app)))
    live_pairs = set(_the_pairs(_the_routes(live_app)))
    expected = (sandbox_pairs - {("/v1/sessions", "POST")}) | (live_pairs - {("/v1/sessions/current", "DELETE")})

    pairs = _the_pairs(_the_routes(app))

    assert set(pairs) == expected
    # No path is duplicated: every pair of the union is answered by exactly one route of the application.
    assert len(pairs) == len(set(pairs))


def _the_positions_of_the_two_mounts(app: FastAPI) -> tuple[int, int]:
    """Find the two included routers that own the /v1 contracts.

    Why the routers are found by the attribute that carries them: fastapi keeps an included router as one entry of
    the list of the routes, and that entry is the one that carries the router it brought.
    """
    positions = []
    for index, route in enumerate(app.router.routes):
        inner = getattr(route, "original_router", None)
        if inner is not None and _the_pairs(inner.routes):
            positions.append(index)
    assert len(positions) == 2, "the application does not carry the two /v1 routers"
    return positions[0], positions[1]


def _swap_the_two_mounts(app: FastAPI) -> None:
    """Swaps the two included routers in the list of the routes of the application.

    Why the swap is the proof of the promise: the promise is that the order of the two mounts decides nothing, and
    the only way to show it is to answer the same requests with the two orders and to compare the answers.
    """
    first, second = _the_positions_of_the_two_mounts(app)
    routes = app.router.routes
    routes[first], routes[second] = routes[second], routes[first]


def _the_answers_of_the_application(
    app: FastAPI, store: FileBranchStore, vault: CredentialVault, issuer: SessionIssuer
) -> dict[str, Any]:
    """What the application answers to the visitor, in a shape that two orders of the mounts can be compared with.

    Why the identifiers are left out: the identifier of the branch, the identifier of the run and the moment of the
    expiry change from one answer to the next, and what the promise is about is the shape of the answer and its
    effect on the branch, on the memory and on the key.
    """
    with TestClient(app) as client:
        session = client.post("/v1/sessions")
        body = session.json()
        branch = client.post("/v1/sandboxes", json={"scenario_id": SCENARIO_ID})
        credential = client.post("/v1/credentials", json={"provider": "openai", "api_key": MARKER})
        refused = client.post(
            "/v1/live-runs",
            json=_the_body_of_the_run("sb_000000000000000000000000", str(credential.json()["handle"])),
        )
        owner = issuer.session_id(client.cookies[SESSION_COOKIE])
        ended = client.delete("/v1/sessions/current")
        pairs = sorted(_the_pairs(_the_routes(app)))
    return {
        "session": (session.status_code, sorted(body), sorted(body["mode_capabilities"])),
        "disclosure": (
            session.headers.get(byok_api.KEY_STORAGE_HEADER),
            session.headers.get(byok_api.KEY_ERASURE_HEADER),
            session.headers.get("cache-control"),
        ),
        "branch": (branch.status_code, sorted(branch.json())),
        "credential": credential.status_code,
        "refusal": (refused.status_code, refused.json().get("code")),
        "end_of_the_session": ended.status_code,
        "branches_left": len(store.list_branches(owner)),
        "keys_left": len(vault),
        "paths": pairs,
    }


def test_the_order_of_the_two_mounts_decides_nothing(
    app: FastAPI, store: FileBranchStore, vault: CredentialVault, issuer: SessionIssuer
) -> None:
    """ADR-039: the order of the two mounts of the routers decides nothing about what the visitor gets.

    Why the swap is the proof and not the reading of the code: the two routes that would collide are dropped by the
    factory, so the order of the mounts is not supposed to matter, and a promise without a test is a promise that
    nobody checked. The test mounts the two routers in the other order and asks for the same thing.

    Why the comparison is of the whole answer and not of the paths: the order of the mounts could leave the paths
    alone and change which route answers one of them, and only the answer of the route tells the two apart.
    """
    before = _the_answers_of_the_application(app, store, vault, issuer)

    _swap_the_two_mounts(app)

    after = _the_answers_of_the_application(app, store, vault, issuer)

    assert after == before


# --- the session of the wired application -----------------------------------------------------------------


def test_the_session_of_the_wired_application_is_the_one_of_the_live_mode(client: TestClient) -> None:
    """ADR-039: the session of the wired application is the one of the live mode, the superset of the two.

    Why the capability matters: a session that may not run the live mode never runs it (FR-024).
    """
    response = client.post("/v1/sessions")

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "expires_at", "mode_capabilities"}
    assert "live_agent" in body["mode_capabilities"]
    # The two disclosures and the headers that say that the answer is not to be kept anywhere.
    assert response.headers[byok_api.KEY_STORAGE_HEADER]
    assert response.headers[byok_api.KEY_ERASURE_HEADER]
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"


# --- the end of the session ------------------------------------------------------------------------------


def test_the_end_of_the_session_drops_the_branch_the_memory_and_the_key(
    client: TestClient, store: FileBranchStore, vault: CredentialVault, issuer: SessionIssuer, runtime: Path
) -> None:
    """ADR-039: the end of the session is the route of the sandbox, and it is the complete one.

    Why the memory is written before the end: a purge that purges nothing proves nothing, so the test leaves a
    folder of the case memory behind and asks whether it is gone afterwards (ADR-030).
    """
    owner = issuer.session_id(client.cookies[SESSION_COOKIE])
    _the_branch_of_the_visitor(client)
    _the_credential_of_the_visitor(client)
    memory = session_memory_dir(owner, runtime)
    memory.mkdir(parents=True)
    (memory / "note.txt").write_text("the memory of the case of the visitor", encoding="utf-8")
    assert store.list_branches(owner)
    assert len(vault) == 1

    response = client.delete("/v1/sessions/current")

    assert response.status_code == 204
    assert store.list_branches(owner) == []
    assert not memory.exists()
    assert len(vault) == 0


# --- the refusals of the wired application ----------------------------------------------------------------


def test_a_refusal_of_the_wired_application_is_the_error_of_the_contract(app: FastAPI, issuer: SessionIssuer) -> None:
    """ADR-039: a refusal of the wired application is the resource `Error` of the contract, and never a `500`.

    Why the two refusals: the forged cookie is the refusal of the session, and the session that may not run the live
    mode is the refusal of the mode (FR-024).

    Why the client is a fresh one: the cookie jar of a client that already has a session carries two cookies of the
    contract, and the refusal that is under test would be the refusal of the other one.

    Why the client never raises: a route that answers `500` is an answer, and the promise of this test is that the
    refusal is the resource `Error` and never a `500`.
    """
    with TestClient(app, raise_server_exceptions=False) as client:
        client.cookies.set(SESSION_COOKIE, "forged.cookie.value")
        forged = client.post("/v1/sandboxes", json={"scenario_id": SCENARIO_ID})

        assert forged.status_code == 401
        assert set(forged.json()) == ERROR_KEYS
        assert forged.json()["code"] == "SESSION_REQUIRED"

        # A session of the demo: it carries the modes of the demo and not the capability of the live mode.
        demo_session = issuer.issue()
        client.cookies.set(SESSION_COOKIE, issuer.cookie_value(demo_session))
        handle = _the_credential_of_the_visitor(client)
        refused = client.post("/v1/live-runs", json=_the_body_of_the_run("sb_000000000000000000000000", handle))

        assert refused.status_code == 403
        assert set(refused.json()) == ERROR_KEYS
        assert refused.json()["code"] == byok_api.CODE_MODE_NOT_ALLOWED
        assert refused.status_code != 500

        # A body that the contract refuses is a refusal of the contract and not the answer of the framework: the
        # default of the framework is a list of details, and the wired application answers the resource `Error`.
        malformed = client.post("/v1/sandboxes", json={"scenario": SCENARIO_ID})

        assert malformed.status_code == 422
        assert set(malformed.json()) == ERROR_KEYS
        assert "detail" not in malformed.json()
        assert malformed.json()["code"] == byok_api.CODE_INVALID_REQUEST


@pytest.fixture
def rate_limited_app(
    monkeypatch: pytest.MonkeyPatch,
    store: FileBranchStore,
    issuer: SessionIssuer,
    vault: CredentialVault,
    adapter: FakeProviderAdapter,
    runtime: Path,
) -> FastAPI:
    """The wired application of a deployment whose rate of the requests is two requests a minute.

    Why the rate comes from the environment and not from an argument: the rate of the deployment is a setting of the
    configuration, and the wired application reads it the way a deployment reads it (ADR-047).

    Why the rate is lowered and not waited for: a test that waits a whole minute proves nothing, and the window of the
    setting is the window the wait of the refusal is taken from.
    """
    monkeypatch.setenv(RATE_REQUESTS_ENV, "2")
    monkeypatch.setenv(RATE_WINDOW_ENV, "60")
    return build_wired_app(
        issuer=issuer,
        store=store,
        vault=vault,
        adapter_factory=lambda _provider, _key: adapter,
        runtime_dir=runtime,
    )


def test_a_refusal_of_the_rate_of_the_wired_application_carries_the_wait(rate_limited_app: FastAPI) -> None:
    """ADR-047: the refusal of the rate of the wired application carries the wait of the server.

    Why the wait belongs to the wired application and not only to the facade: the wired application is the one that
    the command serves and the one that the browser of the visitor reads, and the front shows the number of seconds
    the server wrote, so a header that never reaches the answer is a visitor that never sees the wait (ADR-047,
    decisions 5 and 6).

    Why the two requests of the quota are spent on purpose: the fork is the first request of the session and the read
    of the branch is the second one, so the next read of the branch is the request over the rate.

    Why the wait is asserted as a positive number of seconds and not as an exact one: the wait is the number of
    seconds until the oldest request of the window falls out of it, and the clock of the server moves.
    """
    with TestClient(rate_limited_app) as client:
        session = client.post("/v1/sessions")
        assert session.status_code == 201, session.text
        forked = client.post("/v1/sandboxes", json={"scenario_id": SCENARIO_ID})
        assert forked.status_code == 201, forked.text
        branch_id = str(forked.json()["id"])

        # The two requests of the quota of the session are spent by now.
        assert client.get(f"/v1/sandboxes/{branch_id}").status_code == 200
        refused = client.get(f"/v1/sandboxes/{branch_id}")

    assert refused.status_code == 429, refused.text
    body = refused.json()
    assert body["code"] == CODE_RESOURCE_LIMIT
    # The flag is true: the same request, later, is expected to answer.
    assert body["retryable"] is True
    # The wait of the server reaches the answer, because the front of the browser reads this header.
    assert "Retry-After" in refused.headers
    assert int(refused.headers["Retry-After"]) > 0


def test_the_settings_that_the_deployment_injects_reach_the_rate_of_the_facade(
    issuer: SessionIssuer,
    store: FileBranchStore,
    vault: CredentialVault,
    runtime: Path,
) -> None:
    """ADR-047: the settings that a deployment INJECTS are the ones that the limits of the facade enforce.

    Why this test exists: the rate of the requests and the cap of the live branches were read from the
    ENVIRONMENT by the router of the sandbox, and the configuration that a deployment injected never reached
    them. The limits of the facade were therefore the defaults of the environment and not the ones that the
    deployment asked for, and a deployment that lowered the rate to refuse a flood of requests was not
    refused at all.

    Why the environment is NOT touched here: the test has to prove that the INJECTED configuration is the one
    that counts. A test that set the environment would pass with the defect, because the environment and the
    injection would agree.

    Why the quota is two: the fork is the first request of the session and the read of the branch is the second
    one, so the next read is the request over the rate.
    """
    settings = get_settings().model_copy(
        update={"sandbox_rate_limit_requests": 2, "sandbox_rate_limit_window_seconds": 60}
    )
    application = build_wired_app(
        settings=settings,
        issuer=issuer,
        store=store,
        vault=vault,
        adapter_factory=lambda _provider, _key: FakeProviderAdapter(provider="openai", api_key=MARKER),
        runtime_dir=runtime,
    )

    with TestClient(application) as client:
        session = client.post("/v1/sessions")
        assert session.status_code == 201, session.text
        forked = client.post("/v1/sandboxes", json={"scenario_id": SCENARIO_ID})
        assert forked.status_code == 201, forked.text
        branch_id = str(forked.json()["id"])
        assert client.get(f"/v1/sandboxes/{branch_id}").status_code == 200
        refused = client.get(f"/v1/sandboxes/{branch_id}")

    assert refused.status_code == 429, refused.text
    assert refused.json()["code"] == CODE_RESOURCE_LIMIT


def test_the_settings_that_the_deployment_injects_reach_the_cap_of_the_branches(
    issuer: SessionIssuer,
    store: FileBranchStore,
    vault: CredentialVault,
    runtime: Path,
) -> None:
    """ADR-047: the cap of the live branches of a session is the cap that the deployment injected.

    Why the two forks are of two scenarios: a fork of a scenario the session already holds creates no branch,
    and the reuse comes BEFORE the cap, so a cap of one would never refuse the second fork of the same scenario.

    Why the flag is false: the two limits answer with the same code and the same status, and the flag is what
    tells them apart. The cap of the branches is not retryable and the rate of the requests is.
    """
    settings = get_settings().model_copy(update={"sandbox_session_branch_cap": 1})
    application = build_wired_app(
        settings=settings,
        issuer=issuer,
        store=store,
        vault=vault,
        adapter_factory=lambda _provider, _key: FakeProviderAdapter(provider="openai", api_key=MARKER),
        runtime_dir=runtime,
    )

    with TestClient(application) as client:
        session = client.post("/v1/sessions")
        assert session.status_code == 201, session.text
        first = client.post("/v1/sandboxes", json={"scenario_id": SCENARIO_ID})
        assert first.status_code == 201, first.text
        second = client.post("/v1/sandboxes", json={"scenario_id": OTHER_SCENARIO_ID})

    assert second.status_code == 429, second.text
    body = second.json()
    assert body["code"] == CODE_RESOURCE_LIMIT
    assert body["retryable"] is False


def test_the_plain_factory_of_the_live_mode_still_refuses_every_run(
    vault: CredentialVault, issuer: SessionIssuer, tmp_path: Path
) -> None:
    """ADR-038, ADR-039: the plain factory of the live mode still refuses every run, with a readable reason.

    Why the promise belongs to this file: the wired application is a deployment that the factory of uvicorn does
    not build, and a deployment that lost the refusal would answer a run with the ledger of the configuration, the
    one that holds the rows of every account of the repository.

    Why no provider is called: a refused run spends no money of the visitor, so the refusal happens before the first
    call of the provider, and the fake provider of the test never even gets built.
    """
    built: list[str] = []

    def adapter_factory(provider: str, api_key: str) -> FakeProviderAdapter:
        """Remembers that the deployment asked for a provider, which a refused run never does."""
        built.append(provider)
        return FakeProviderAdapter(provider=provider, api_key=api_key)

    app = byok_api.create_app(
        vault=vault,
        session_issuer=issuer,
        adapter_factory=adapter_factory,
        runtime_dir=tmp_path / "runtime-of-the-plain-factory",
    )
    with TestClient(app) as client:
        client.post("/v1/sessions")
        handle = _the_credential_of_the_visitor(client)

        refused = client.post("/v1/live-runs", json=_the_body_of_the_run("sb_000000000000000000000000", handle))

    assert refused.status_code == 503
    assert set(refused.json()) == ERROR_KEYS
    assert refused.json()["code"] == byok_api.CODE_BRANCH_LAYER_MISSING
    assert built == [], "a refused run asked the provider for a client"


# --- the live case ---------------------------------------------------------------------------------------


def test_a_live_case_runs_end_to_end_against_the_wired_application(client: TestClient) -> None:
    """ADR-039: the whole promise of the milestone: a live case runs against the wired application.

    Why the branch is forked in the sandbox and not made up: the run reads the ledger of the branch of the visitor,
    and the layer refuses a branch that belongs to nobody (ADR-038).
    """
    branch_id = _the_branch_of_the_visitor(client)
    handle = _the_credential_of_the_visitor(client)

    started = client.post("/v1/live-runs", json=_the_body_of_the_run(branch_id, handle))

    assert started.status_code == 201, started.text
    run_id = str(started.json()["run_id"])
    state = _wait_for_the_end(client, run_id)
    assert state["status"] == "completed", state
    assert state["answer"] == FINAL_ANSWER
    cost = client.get(f"/v1/live-runs/{run_id}/cost")
    assert cost.status_code == 200
    assert cost.json()["observed_cost_usd"] is not None
    assert cost.json()["estimated_cost_usd"] is not None


def test_the_run_of_the_wired_application_reads_the_ledger_of_the_branch(
    client: TestClient, adapter: FakeProviderAdapter
) -> None:
    """ADR-038: the run reads the ledger of the branch of the visitor, and never the ledger of the configuration.

    Why the row of the transaction is not enough on its own: the transaction TX-2048 is in the ledger of the branch
    and in the published ledger of the repository with the same values, so a row that came back is a row of both.
    The count of the rows is what tells the two ledgers apart, and the test that counts them is the one below.
    """
    branch_id = _the_branch_of_the_visitor(client)
    handle = _the_credential_of_the_visitor(client)

    started = client.post("/v1/live-runs", json=_the_body_of_the_run(branch_id, handle))

    assert started.status_code == 201, started.text
    run_id = str(started.json()["run_id"])
    state = _wait_for_the_end(client, run_id)
    assert state["status"] == "completed", state
    answers_of_the_tools = [
        message.content for call in adapter.calls for message in call.messages if message.role == "tool"
    ]
    assert answers_of_the_tools, "the agent of the demo never called a tool of the ledger"
    assert "TX-2048" in answers_of_the_tools[0]
    # The trace says which state was read, so the reader of the run knows the branch behind the answer.
    stream = client.get(f"/v1/live-runs/{run_id}/events")
    assert stream.status_code == 200
    started_event = _the_event_of_the_stream(stream.text, "run.started")
    assert started_event["payload"]["branch_id"] == branch_id
    assert started_event["payload"]["branch_revision"] == 0


def test_the_model_of_the_run_sees_the_rows_of_the_branch_and_the_rows_of_no_other_account(
    counting_app: FastAPI, counting_adapter: FakeProviderAdapter
) -> None:
    """ADR-038: the model of the run sees the rows of the branch of the visitor, and nothing else.

    Why the count of the rows is the discriminator: the row of the transaction TX-2048 is in the ledger of the branch
    and in the published ledger of the repository with the same values, so a row that came back is a row of both
    and a test that only reads it proves nothing. The count tells the two ledgers apart: the branch of the visitor
    holds one row and the published ledger holds 2114 of them.

    Why the group by the account is the second discriminator: the branch of the visitor holds the rows of one account
    and the published ledger holds the rows of 1418 accounts, so the group tells the two ledgers apart even when
    the count of the rows is the same. Together the two questions kill every mutant that hands the model a ledger
    that is not the one of the branch: the wrong file, the file of the configuration and the branch of another
    account.

    Why the run asks the two questions: the tool of the ledger answers one query per call, and the answers carry the
    SQL that produced them, so the test reads the answer of each question and not the answer of a position.
    """
    with TestClient(counting_app) as client:
        client.post("/v1/sessions")
        branch_id = _the_branch_of_the_visitor(client)
        handle = _the_credential_of_the_visitor(client)

        started = client.post("/v1/live-runs", json=_the_body_of_the_run(branch_id, handle))

        assert started.status_code == 201, started.text
        state = _wait_for_the_end(client, str(started.json()["run_id"]))
        assert state["status"] == "completed", state
        data = _the_data_of_the_tools(counting_adapter)

    assert len(data) == 2, "the run did not ask the ledger the two questions of the test"
    # The number of rows the model sees is the number of rows of the branch, and not the 2114 of the published one.
    assert _the_rows_of(data, grouped=False) == [[1]]
    # The only account the model sees is the account of the branch, so no row of another customer is visible.
    assert _the_rows_of(data, grouped=True) == [[ACCOUNT_ID, 1]]


# --- one visitor -----------------------------------------------------------------------------------------


def test_the_wired_application_is_one_visitor_and_the_two_facades_alone_are_two(
    client: TestClient,
    store: FileBranchStore,
    issuer: SessionIssuer,
    vault: CredentialVault,
    runtime: Path,
    tmp_path: Path,
) -> None:
    """ADR-035, ADR-039: the wired application is one visitor, and the two facades alone are still two.

    Why the two facades are built alone with an issuer of their own: the two facades are two visitors by default,
    and only a deployment that wires them with the same issuer makes them one (ADR-035).
    """
    client.post("/v1/sessions")
    assert client.post("/v1/sandboxes", json={"scenario_id": SCENARIO_ID}).status_code == 201
    assert client.post("/v1/credentials", json={"provider": "openai", "api_key": MARKER}).status_code == 201
    cookie = client.cookies[SESSION_COOKIE]

    sandbox_alone = sandbox_api.create_app(
        store=store,
        base_resolver=BaseResolver(tmp_path / "bases"),
        session_issuer=SessionIssuer(tmp_path / "other-session.key"),
        credential_vault=vault,
        runtime_dir=tmp_path / "other-runtime",
    )
    with TestClient(sandbox_alone) as other:
        other.cookies.set(SESSION_COOKIE, cookie)
        refused = other.delete("/v1/sessions/current")

    assert refused.status_code == 401

    live_alone = byok_api.create_app(
        vault=vault,
        session_issuer=SessionIssuer(tmp_path / "other-live-session.key"),
        runtime_dir=tmp_path / "other-live-runtime",
    )
    with TestClient(live_alone) as other:
        other.cookies.set(SESSION_COOKIE, cookie)
        refused = other.delete("/v1/sessions/current")

    assert refused.status_code == 401


# --- the two sweepers ------------------------------------------------------------------------------------


def test_the_wired_application_starts_the_two_sweepers(app: FastAPI) -> None:
    """ADR-039: the wired application starts the sweep of the expired branches and the sweeper of the credentials.

    Why the two matter: a branch that nobody touches still has to die, and a credential that nobody touches still
    has to die (FR-022, FR-024).
    """
    with TestClient(app):
        names = {thread.name for thread in threading.enumerate()}

    assert "ledgerlens-cleanup" in names
    assert "ledgerlens-credential-sweep" in names


# --- the command -----------------------------------------------------------------------------------------


def test_the_command_serves_the_two_facades_over_one_issuer(monkeypatch: pytest.MonkeyPatch) -> None:
    """ADR-039: the command builds the wired application and serves it, with the host and the port it was given.

    Why the server is replaced and not really started: the test is about what the command builds and serves, and a
    server that really listens would open a port of the machine of the developer.
    """
    served: dict[str, Any] = {}

    def fake_run(application: Any, *, host: str, port: int) -> None:
        served["app"] = application
        served["host"] = host
        served["port"] = port

    monkeypatch.setattr("uvicorn.run", fake_run)

    main(["--host", "127.0.0.1", "--port", "8123"])

    assert served["host"] == "127.0.0.1"
    assert served["port"] == 8123
    application = served["app"]
    assert isinstance(application, FastAPI)
    pairs = set(_the_pairs(_the_routes(application)))
    assert ("/v1/sessions", "POST") in pairs
    assert ("/v1/sandboxes", "POST") in pairs
    assert ("/v1/live-runs", "POST") in pairs
    # The console script of the command is declared in the package, and it does not take the name of the internal
    # ledger API, which keeps its own command.
    scripts = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["scripts"]
    assert scripts["ledgerlens-demo"] == "ledgerlens.api.wiring:main"
    assert scripts["ledgerlens-api"] == "ledgerlens.api.ledger_service:main"


# --- the CORS of the deployment --------------------------------------------------------------------------


@pytest.fixture
def cors_app(
    store: FileBranchStore,
    issuer: SessionIssuer,
    vault: CredentialVault,
    adapter: FakeProviderAdapter,
    runtime: Path,
) -> FastAPI:
    """The wired application of a deployment that declares the origin of the site.

    Why the setting is given and not read from the environment: a test that changes the environment of the machine is
    a test that depends on the machine (ADR-040).
    """
    settings = get_settings().model_copy(update={"cors_origins": (CORS_ORIGIN,)})
    return build_wired_app(
        settings=settings,
        issuer=issuer,
        store=store,
        vault=vault,
        adapter_factory=lambda _provider, _key: adapter,
        runtime_dir=runtime,
    )


def _the_pairs_of_the_schema(app: FastAPI) -> set[tuple[str, str]]:
    """The pairs of path and method of the application, read from the schema of the OpenAPI.

    Why the schema and not the list of the routes: fastapi keeps an included router as one entry of the list of the
    routes, so the list does not carry the paths of the contract and the schema is what carries them.
    """
    pairs: set[tuple[str, str]] = set()
    for path, item in app.openapi()["paths"].items():
        for method in item:
            if method in {"parameters", "summary", "description", "servers", "tags"}:
                continue
            pairs.add((path, method))
    return pairs


def test_the_wired_application_answers_the_browser_with_the_cors_headers(cors_app: FastAPI) -> None:
    """ADR-040: the wired application answers the browser of the visitor with the headers of the CORS.

    Why the session route is the one that is called: it is a route of the live mode, it needs no body and it answers
    in the process, so the test reads the headers of the answer of the application and not of a mock.
    """
    with TestClient(cors_app) as client:
        response = client.post("/v1/sessions", headers={"Origin": CORS_ORIGIN})

    assert response.status_code == 201, response.text
    assert response.headers["access-control-allow-origin"] == CORS_ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"


def test_the_list_of_the_routes_does_not_change_when_the_cors_is_installed(app: FastAPI, cors_app: FastAPI) -> None:
    """ADR-040: the CORS is a middleware and adds no route, so the list of the routes is the same list.

    Why it matters: ADR-039 pins the list of the routes of the wired application, and a CORS that added a route would
    change the contract of the deployment without anybody deciding it.
    """
    assert _the_pairs_of_the_schema(cors_app) == _the_pairs_of_the_schema(app)


def test_active_run_preserves_the_session_and_branch(client, adapter, vault, issuer, runtime, monkeypatch):
    """An unfinished run retains its session resources while another visitor can leave."""
    entered = threading.Event()
    release = threading.Event()
    complete = adapter.complete

    def blocked(request):
        entered.set()
        assert release.wait(10)
        return complete(request)

    monkeypatch.setattr(adapter, "complete", blocked)
    branch = _the_branch_of_the_visitor(client)
    handle = _the_credential_of_the_visitor(client)
    owner_cookie = client.cookies[SESSION_COOKIE]
    memory = session_memory_dir(issuer.session_id(owner_cookie), runtime)
    memory.mkdir(parents=True, exist_ok=True)
    marker = memory / "active-session.txt"
    marker.write_text("keep", encoding="utf-8")
    run = client.post("/v1/live-runs", json=_the_body_of_the_run(branch, handle)).json()["run_id"]
    try:
        assert entered.wait(10)
        responses = client.get("/openapi.json").json()["paths"]["/v1/sessions/current"]["delete"]["responses"]
        assert "RUN_RUNNING (retryable)" in responses["409"]["description"]
        schema = responses["409"]["content"]["application/json"]["schema"]
        assert schema["$ref"].endswith("/ContractErrorBody")
        refused = client.delete("/v1/sessions/current")
        assert refused.status_code == 409
        assert refused.json()["code"] == "RUN_RUNNING"
        assert client.cookies[SESSION_COOKIE] == owner_cookie
        assert marker.read_text(encoding="utf-8") == "keep"
        other = client.post("/v1/sessions")
        assert other.status_code == 201
        assert client.delete("/v1/sessions/current").status_code == 204
        client.cookies.set(SESSION_COOKIE, owner_cookie)
        assert len(vault) == 1
        assert client.get(f"/v1/sandboxes/{branch}").status_code == 200
    finally:
        release.set()
    assert _wait_for_the_end(client, run)["status"] == "completed"
    assert client.delete("/v1/sessions/current").status_code == 204

def test_waiting_for_session_teardown_keeps_other_requests_responsive(client, vault, monkeypatch):
    """A run waiting for the visitor's teardown must release the ASGI event loop."""
    branch = _the_branch_of_the_visitor(client)
    handle = _the_credential_of_the_visitor(client)
    payload = _the_body_of_the_run(branch, handle)
    ending = threading.Event()
    admission = threading.Event()
    release = threading.Event()
    forget = vault.forget_session
    session_lock = byok_api.LiveRunCoordinator.session_lock

    def pause_teardown(session):
        ending.set()
        assert release.wait(10)
        return forget(session)

    def observe_admission(coordinator, session):
        if ending.is_set():
            admission.set()
        return session_lock(coordinator, session)

    monkeypatch.setattr(vault, "forget_session", pause_teardown)
    monkeypatch.setattr(byok_api.LiveRunCoordinator, "session_lock", observe_admission)
    with ThreadPoolExecutor(max_workers=3) as pool:
        teardown = pool.submit(client.delete, "/v1/sessions/current")
        try:
            assert ending.wait(5)
            run = pool.submit(client.post, "/v1/live-runs", json=payload)
            assert admission.wait(5)
            catalog = pool.submit(client.get, "/v1/models")
            assert catalog.result(timeout=2).status_code == 200
        finally:
            release.set()
        assert teardown.result(timeout=5).status_code == 204
        assert run.result(timeout=5).status_code == 404
