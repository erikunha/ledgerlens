"""The sandbox facade: the versioned contract of the design package, the session cookie and the generic refusal.

The `TestClient` calls the app in process, so no test opens a port or reaches the network. The client keeps the
cookie of the session between the requests, which is the way the browser behaves.
"""

from __future__ import annotations

import json
import time
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from ledgerlens.api.sandbox import (  # noqa: E402
    BRANCH_HASH_HEADER,
    BRANCH_STATE_HEADER,
    SCENARIO_ID_PATTERN,
    SCHEMA_VERSION,
    SCHEMA_VERSION_HEADER,
    SESSION_COOKIE,
    create_app,
)
from ledgerlens.run_context import SESSION_ID_PATTERN, canonical_session_id  # noqa: E402
from ledgerlens.sandbox.events import (  # noqa: E402
    CLOSED_REASON_GONE,
    EVENT_BRANCH_EXPIRED,
    EVENT_BRANCH_OPENED,
    EVENT_MUTATION_COMMITTED,
    EVENT_STREAM_CLOSED,
    EVENT_STREAM_HEARTBEAT,
    EVENT_STREAM_RESYNC,
    EventHub,
)
from ledgerlens.sandbox.rate_limit import RateDecision, RateLimiter  # noqa: E402
from ledgerlens.sandbox.snapshot import BaseResolver, BaseSnapshot  # noqa: E402
from ledgerlens.sandbox.store import FileBranchStore  # noqa: E402

# The resource `Sandbox` of the contract, field for field.
RESOURCE_KEYS = {"id", "base_snapshot_id", "snapshot_sha256", "revision", "expires_at"}
# The resource `Session` of the contract.
SESSION_KEYS = {"id", "expires_at", "mode_capabilities"}
# The resource `Error` of the contract.
ERROR_KEYS = {"code", "message", "retryable", "request_id"}
# Every field of an answer that the history carries, field for field. ADR-028 promises that the answers of the
# history carry the same fields they carry everywhere else, so the set is the whole set and not a subset of it: a
# field that disappears from the answer, or that changes its name, has to break the test of the route.
ANSWER_KEYS = {
    "branch_id",
    "idempotency_key",
    "payload_digest",
    "revision",
    "canonical_hash",
    "response_diff",
    "response_verdict",
    "response_invariants",
    "generation",
    "stale",
    "stale_against",
    "undone",
    "undone_event_uid",
}
# The fields of the verdict that every answer of the branch remembers carries.
VERDICT_KEYS = {"label", "measure", "value", "low", "high", "detail"}
# The contract of the design package, which the facade follows.
CONTRACT_PATH = Path(__file__).resolve().parents[2] / "docs" / "v3" / "contracts" / "openapi.yaml"

# The name of the setting of the limit of the committed mutations of one branch, as the configuration names it.
MUTATIONS_LIMIT_ENV = "LEDGERLENS_SANDBOX_MAX_COMMITTED_MUTATIONS"


def _contract() -> dict:
    """The contract of the design package, read from the repository."""
    return yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def app(store: FileBranchStore, base_resolver: BaseResolver, clock):
    return create_app(store=store, base_resolver=base_resolver, clock=clock)


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)


@pytest.fixture
def session_client(client: TestClient) -> TestClient:
    """A client that holds the cookie of a session the server issued."""
    assert client.post("/v1/sessions").status_code == 201
    return client


def _fork(client: TestClient, scenario_id: str):
    return client.post("/v1/sandboxes", json={"scenario_id": scenario_id})


# --- the session of the contract -------------------------------------------------------------------


def test_the_session_route_issues_the_session_and_the_cookie(client: TestClient) -> None:
    response = client.post("/v1/sessions")
    assert response.status_code == 201
    body = response.json()
    assert set(body) == SESSION_KEYS
    assert SESSION_ID_PATTERN.match(body["id"])
    assert body["mode_capabilities"]
    assert client.cookies.get(SESSION_COOKIE)


def test_the_cookie_of_the_session_is_httponly_and_samesite_lax(client: TestClient) -> None:
    response = client.post("/v1/sessions")
    header = response.headers["set-cookie"]
    assert "httponly" in header.lower()
    assert "samesite=lax" in header.lower()
    assert SESSION_COOKIE in header


def test_the_body_of_the_session_carries_the_identifier_the_cookie_carries(client: TestClient) -> None:
    body = client.post("/v1/sessions").json()
    assert body["id"] in client.cookies.get(SESSION_COOKIE)


def test_a_request_without_a_session_is_401(client: TestClient, scenario_id: str) -> None:
    response = _fork(client, scenario_id)
    assert response.status_code == 401
    assert set(response.json()) == ERROR_KEYS
    assert response.json()["code"] == "SESSION_REQUIRED"


def test_a_request_with_a_forged_cookie_is_401(client: TestClient, scenario_id: str) -> None:
    client.cookies.set(SESSION_COOKIE, "sess_00000000000000000000000000000000.9999999999.deadbeef")
    response = _fork(client, scenario_id)
    assert response.status_code == 401
    assert response.json()["code"] == "SESSION_REQUIRED"


def test_the_sandbox_routes_never_read_the_session_from_a_header(client: TestClient, scenario_id: str) -> None:
    response = client.post(
        "/v1/sandboxes",
        json={"scenario_id": scenario_id},
        headers={"X-LedgerLens-Session": "sess_x"},
    )
    assert response.status_code == 401


# --- the resource of the contract -------------------------------------------------------------------


def test_the_body_of_the_fork_is_exactly_the_resource_of_the_contract(
    session_client: TestClient, scenario_id: str
) -> None:
    response = _fork(session_client, scenario_id)
    assert response.status_code == 201
    assert set(response.json()) == RESOURCE_KEYS


def test_the_body_of_the_status_is_exactly_the_resource_of_the_contract(
    session_client: TestClient, scenario_id: str
) -> None:
    created = _fork(session_client, scenario_id).json()
    response = session_client.get(f"/v1/sandboxes/{created['id']}")
    assert response.status_code == 200
    assert set(response.json()) == RESOURCE_KEYS


def test_the_version_of_the_answers_travels_in_a_header(session_client: TestClient, scenario_id: str) -> None:
    created = _fork(session_client, scenario_id)
    assert created.headers[SCHEMA_VERSION_HEADER] == SCHEMA_VERSION
    status = session_client.get(f"/v1/sandboxes/{created.json()['id']}")
    assert status.headers[SCHEMA_VERSION_HEADER] == SCHEMA_VERSION


def test_the_path_parameter_of_the_contract_is_the_sandbox_id(app) -> None:
    assert "/v1/sandboxes/{sandbox_id}" in {route.path for route in app.routes}


def test_the_current_hash_and_the_state_of_the_branch_travel_in_a_header(
    session_client: TestClient, scenario_id: str
) -> None:
    response = _fork(session_client, scenario_id)
    assert response.headers[BRANCH_HASH_HEADER] == response.json()["snapshot_sha256"]
    assert response.headers[BRANCH_STATE_HEADER] == "active"


# --- the identity of the base -----------------------------------------------------------------------


def test_the_base_snapshot_id_names_the_published_snapshot(session_client: TestClient, scenario_id: str) -> None:
    body = _fork(session_client, scenario_id).json()
    assert body["base_snapshot_id"] == "sample-42"


def test_the_snapshot_hash_is_the_canonical_hash_of_the_account_scoped_projection(
    session_client: TestClient, scenario_id: str, base_snapshot: BaseSnapshot
) -> None:
    body = _fork(session_client, scenario_id).json()
    assert body["snapshot_sha256"] == base_snapshot.canonical_hash


def test_two_visitors_of_the_same_scenario_report_the_same_pair(
    app, scenario_id: str, base_snapshot: BaseSnapshot
) -> None:
    first = TestClient(app)
    second = TestClient(app)
    first.post("/v1/sessions")
    second.post("/v1/sessions")
    one = first.post("/v1/sandboxes", json={"scenario_id": scenario_id}).json()
    other = second.post("/v1/sandboxes", json={"scenario_id": scenario_id}).json()
    assert one["base_snapshot_id"] == other["base_snapshot_id"] == "sample-42"
    assert one["snapshot_sha256"] == other["snapshot_sha256"] == base_snapshot.canonical_hash
    assert one["id"] != other["id"]


# --- the creation and the reuse ---------------------------------------------------------------------


def test_the_fork_answers_201_when_it_creates_a_branch(session_client: TestClient, scenario_id: str) -> None:
    assert _fork(session_client, scenario_id).status_code == 201


def test_the_fork_answers_200_when_the_reuse_rule_returns_the_branch_that_exists(
    session_client: TestClient, scenario_id: str
) -> None:
    first = _fork(session_client, scenario_id)
    second = _fork(session_client, scenario_id)
    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json() == first.json()


# --- the generic refusal -----------------------------------------------------------------------------


def test_the_branch_of_another_session_is_404_with_a_generic_message(
    app, session_id: str, other_session_id: str, scenario_id: str
) -> None:
    mine = TestClient(app)
    theirs = TestClient(app)
    mine.post("/v1/sessions")
    theirs.post("/v1/sessions")
    created = mine.post("/v1/sandboxes", json={"scenario_id": scenario_id}).json()
    response = theirs.get(f"/v1/sandboxes/{created['id']}")
    assert response.status_code == 404
    body = response.json()
    assert set(body) == ERROR_KEYS
    assert session_id not in body["message"]
    assert created["id"] not in body["message"]
    assert "exist" not in body["message"].lower()


def test_a_branch_that_does_not_exist_is_404_with_the_same_message(session_client: TestClient) -> None:
    of_missing = session_client.get("/v1/sandboxes/sb_" + "0" * 24)
    assert of_missing.status_code == 404
    assert set(of_missing.json()) == ERROR_KEYS


def test_a_body_that_does_not_match_the_contract_is_422_with_the_error_of_the_contract(
    session_client: TestClient,
) -> None:
    response = session_client.post("/v1/sandboxes", json={"scenario": "S01"})
    assert response.status_code == 422
    assert set(response.json()) == ERROR_KEYS


def test_a_body_with_a_field_the_contract_does_not_have_is_422(session_client: TestClient, scenario_id: str) -> None:
    response = session_client.post("/v1/sandboxes", json={"scenario_id": scenario_id, "account_id": "C-0412"})
    assert response.status_code == 422
    assert set(response.json()) == ERROR_KEYS


# --- the end of the session --------------------------------------------------------------------------


def test_the_end_of_the_session_purges_the_branches_of_the_session(app, store, scenario_id: str) -> None:
    client = TestClient(app)
    client.post("/v1/sessions")
    client.post("/v1/sandboxes", json={"scenario_id": scenario_id})
    assert list(store.root.glob("*/*/branch.json"))
    assert client.delete("/v1/sessions/current").status_code == 204
    assert not list(store.root.glob("*/*/branch.json"))


# --- the expiry of the branch ------------------------------------------------------------------------


def test_an_expired_branch_answers_410_with_the_code_of_the_contract(
    app, clock, session_client: TestClient, scenario_id: str
) -> None:
    created = _fork(session_client, scenario_id).json()
    clock.advance(timedelta(hours=2))
    response = session_client.get(f"/v1/sandboxes/{created['id']}")
    assert response.status_code == 410
    body = response.json()
    assert set(body) == ERROR_KEYS
    assert body["code"] == "BRANCH_EXPIRED"


# --- the diff and the history of the branch -------------------------------------------------------------


def _commit(client: TestClient, branch_id: str, payload: dict[str, object], key: str = "cmd-0001", revision: int = 0):
    """The commit of a mutation through the route of the contract."""
    return client.post(
        f"/v1/sandboxes/{branch_id}/mutations",
        json={"kind": "refund.apply_fx_adjustment", "data": payload},
        headers={"Idempotency-Key": key, "If-Match": str(revision)},
    )


def _undo(client: TestClient, branch_id: str, key: str = "undo-0001", revision: int = 1):
    """The undo of the last mutation through the route of the contract."""
    return client.post(
        f"/v1/sandboxes/{branch_id}/undo",
        headers={"Idempotency-Key": key, "If-Match": str(revision)},
    )


# --- the limits of the resources of the branch ---------------------------------------------------------


def test_the_limit_of_the_resources_of_a_branch_comes_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
    store: FileBranchStore,
    base_resolver: BaseResolver,
    clock,
    scenario_id: str,
    adjustment_payload: dict[str, object],
) -> None:
    """The limit of the committed mutations of a branch is the setting of the configuration, and the facade reads it.

    Why the case exists at the level of the facade and not only at the level of the layer: the setting reaches the
    layer through the constructor of the layer, and the constructor is built by the facade. A facade that builds the
    layer without the setting keeps the limits of today whatever the configuration says, and a case that only proves
    the layer would not see it.

    Why the application is built inside the case: the settings are read when the application is built, and a fixture
    that built it before the case set the environment would prove the limits of today and not the ones of the case.
    """
    monkeypatch.setenv(MUTATIONS_LIMIT_ENV, "1")
    application = create_app(store=store, base_resolver=base_resolver, clock=clock)
    client = TestClient(application)
    assert client.post("/v1/sessions").status_code == 201
    created = _fork(client, scenario_id).json()

    first = _commit(client, created["id"], adjustment_payload, key="cmd-0001", revision=0)
    assert first.status_code == 200

    second = _commit(client, created["id"], adjustment_payload, key="cmd-0002", revision=1)
    assert second.status_code == 429
    body = second.json()
    assert set(body) == ERROR_KEYS
    assert body["code"] == "RESOURCE_LIMIT_EXCEEDED"


def test_the_route_of_the_diff_answers_the_shape_of_ADR_028(
    session_client: TestClient, scenario_id: str, adjustment_payload: dict[str, object]
) -> None:
    """The answer of the diff carries the revision, the two hashes, the entries, the invariants and the verdict.

    Why the shape is the one of ADR-028: the contract of the design package does not declare this route, so the shape
    is the one the decision declares, and the interface reads one vocabulary.
    """
    created = _fork(session_client, scenario_id).json()
    _commit(session_client, created["id"], adjustment_payload)

    response = session_client.get(f"/v1/sandboxes/{created['id']}/diff")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "revision",
        "base_canonical_hash",
        "canonical_hash",
        "diff",
        "invariants",
        "verdict",
    }
    assert body["revision"] == 1
    assert body["base_canonical_hash"] == created["snapshot_sha256"]
    assert body["canonical_hash"] != body["base_canonical_hash"]
    entry = body["diff"][0]
    assert set(entry) == {"record", "record_id", "field", "before", "after", "value_kind", "currency"}
    assert isinstance(entry["before"], str)
    assert isinstance(entry["after"], str)
    assert set(body["verdict"]) == VERDICT_KEYS


def test_the_route_of_the_history_answers_the_shape_of_ADR_028(
    session_client: TestClient, scenario_id: str, adjustment_payload: dict[str, object]
) -> None:
    """The answer of the history carries the events of the log and the answers the branch remembers.

    The event that was undone stays in the log and carries the mark, and the answers carry the mark of the staleness
    and the mark of the undo.

    Why every field of an answer is pinned: ADR-028 promises that the answers of the history carry the same fields
    they carry everywhere else, so the interface reads one vocabulary. A subset of the fields would let a field
    disappear, or change its name, without anything noticing, and the reader of the answer would then read a
    vocabulary that the rest of the facade does not speak.
    """
    created = _fork(session_client, scenario_id).json()
    _commit(session_client, created["id"], adjustment_payload)
    _undo(session_client, created["id"])

    response = session_client.get(f"/v1/sandboxes/{created['id']}/history")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"revision", "canonical_hash", "events", "answers"}
    assert body["revision"] == 0
    event = body["events"][0]
    assert set(event) == {"event_uid", "event_type", "aggregate_id", "occurred_at", "payload", "undone"}
    assert event["undone"] is True
    assert body["events"][1]["event_type"] == "sandbox.branch.undone"
    assert body["events"][1]["undone"] is False

    answers = {answer["idempotency_key"]: answer for answer in body["answers"]}
    assert set(answers) == {"cmd-0001", "undo-0001"}
    for answer in answers.values():
        assert set(answer) == ANSWER_KEYS

    mutation = answers["cmd-0001"]
    assert mutation["branch_id"] == created["id"]
    assert mutation["revision"] == 1
    assert mutation["canonical_hash"]
    assert mutation["payload_digest"]
    assert mutation["response_diff"]
    assert set(mutation["response_verdict"]) == VERDICT_KEYS
    assert isinstance(mutation["response_invariants"], list)
    assert mutation["generation"] == 0
    assert mutation["stale"] is False
    assert mutation["stale_against"] is None
    assert mutation["undone"] is True
    assert mutation["undone_event_uid"] is None

    undone = answers["undo-0001"]
    assert undone["branch_id"] == created["id"]
    assert undone["revision"] == 0
    assert undone["generation"] == 0
    assert undone["stale"] is False
    assert undone["stale_against"] is None
    assert undone["undone"] is False
    assert undone["undone_event_uid"] == body["events"][0]["event_uid"]


def test_the_two_routes_answer_the_version_of_the_schema(session_client: TestClient, scenario_id: str) -> None:
    """FR-042: every answer of the facade carries the version of the shape of the answers."""
    created = _fork(session_client, scenario_id).json()
    for path in ("diff", "history"):
        response = session_client.get(f"/v1/sandboxes/{created['id']}/{path}")
        assert response.status_code == 200
        assert response.headers[SCHEMA_VERSION_HEADER] == SCHEMA_VERSION


def test_the_two_routes_refuse_the_branch_of_another_visitor_with_the_generic_404(
    app, session_client: TestClient, scenario_id: str
) -> None:
    """The refusal says nothing about the owner and nothing about the existence of the branch (ADR-023)."""
    created = _fork(session_client, scenario_id).json()
    other = TestClient(app)
    assert other.post("/v1/sessions").status_code == 201

    for path in ("diff", "history"):
        response = other.get(f"/v1/sandboxes/{created['id']}/{path}")
        assert response.status_code == 404
        body = response.json()
        assert set(body) == ERROR_KEYS
        assert body["code"] == "NOT_FOUND"
        assert created["id"] not in body["message"]


def test_the_two_routes_refuse_an_expired_branch_with_410(
    app, clock, session_client: TestClient, scenario_id: str
) -> None:
    """An expired branch answers 410 with the code of the contract."""
    created = _fork(session_client, scenario_id).json()
    clock.advance(timedelta(hours=2))

    for path in ("diff", "history"):
        response = session_client.get(f"/v1/sandboxes/{created['id']}/{path}")
        assert response.status_code == 410
        body = response.json()
        assert set(body) == ERROR_KEYS
        assert body["code"] == "BRANCH_EXPIRED"


def test_the_two_routes_refuse_a_branch_that_cannot_prove_its_state_with_409(
    app, session_client: TestClient, scenario_id: str, adjustment_payload: dict[str, object], tamper_events
) -> None:
    """A branch that cannot prove its own state answers 409 with the code of the contract (ADR-021)."""
    created = _fork(session_client, scenario_id).json()
    _commit(session_client, created["id"], adjustment_payload)
    # The crash of a commit that wrote the row of the branch and lost the events of the branch.
    tamper_events(created["id"], [])

    for path in ("diff", "history"):
        response = session_client.get(f"/v1/sandboxes/{created['id']}/{path}")
        assert response.status_code == 409
        body = response.json()
        assert set(body) == ERROR_KEYS
        assert body["code"] == "HASH_MISMATCH"
        assert "fork" in body["message"]


def test_the_two_routes_read_the_session_from_the_cookie_and_never_from_a_header(
    app, session_client: TestClient, scenario_id: str
) -> None:
    """The session decides what a visitor may read, so it comes from the cookie of the contract."""
    created = _fork(session_client, scenario_id).json()
    other = TestClient(app)
    assert other.post("/v1/sessions").status_code == 201

    for path in ("diff", "history"):
        response = other.get(
            f"/v1/sandboxes/{created['id']}/{path}",
            headers={"X-LedgerLens-Session": session_client.cookies.get(SESSION_COOKIE)},
        )
        assert response.status_code == 404


def test_the_two_routes_refuse_a_forged_cookie_with_401(app, scenario_id: str) -> None:
    """A cookie that the deployment did not issue is refused at the two new routes, like at the route of the fork.

    Why the same shape as the refusal of the fork: the session decides what a visitor may read, and a cookie that
    was not signed by this deployment names no session, so the two routes refuse it the way the route of the fork
    refuses it. The branch exists and belongs to another visitor, and the refusal still says `SESSION_REQUIRED` and
    not `NOT_FOUND`, because the cookie is refused before the branch is even looked for.
    """
    owner = TestClient(app)
    assert owner.post("/v1/sessions").status_code == 201
    created = owner.post("/v1/sandboxes", json={"scenario_id": scenario_id}).json()
    forged = TestClient(app)
    forged.cookies.set(SESSION_COOKIE, "sess_00000000000000000000000000000000.9999999999.deadbeef")

    for path in ("diff", "history"):
        response = forged.get(f"/v1/sandboxes/{created['id']}/{path}")
        assert response.status_code == 401
        body = response.json()
        assert set(body) == ERROR_KEYS
        assert body["code"] == "SESSION_REQUIRED"


# --- the contract of the design package --------------------------------------------------------------


def test_the_app_declares_the_security_scheme_of_the_contract(app) -> None:
    spec = app.openapi()
    scheme = spec["components"]["securitySchemes"]["anonymousSession"]
    assert scheme["type"] == "apiKey"
    assert scheme["in"] == "cookie"
    assert scheme["name"] == SESSION_COOKIE
    assert spec["paths"]["/v1/sandboxes"]["post"]["security"] == [{"anonymousSession": []}]
    assert spec["paths"]["/v1/sandboxes/{sandbox_id}"]["get"]["security"] == [{"anonymousSession": []}]


# The paths that ADR-023 declares beyond the contract of the design package and that have landed. The contract of
# the package cannot be edited, so the difference between the facade and the contract is enumerated here. The
# guard widens as each route of the decision lands: the diff and the history widened it when they landed.
PATHS_BEYOND_THE_CONTRACT = {
    "/v1/sandboxes/{sandbox_id}/diff",
    "/v1/sandboxes/{sandbox_id}/history",
    "/v1/sandboxes/{sandbox_id}/undo",
    # ADR-047 declares the stream of the lifecycle of the branch. The path is a path of the
    # facade and not a path of the contract of the design package, and the contract cannot be
    # edited, so the decision of the record declares it here.
    "/v1/sandboxes/{sandbox_id}/events",
}


def test_every_path_of_the_facade_is_a_path_of_the_contract_or_one_that_ADR_023_declares(app) -> None:
    """ADR-023: the guard of the facade names the paths of the decision that have landed.

    Why the guard names the paths that have landed: the specification of the feature asks for a diff, a history and
    an undo, and the contract of the design package cannot be edited. The test names the paths that exist, so a
    route that nobody decided still cannot appear in the facade.
    """
    contract = _contract()
    app_paths = {route.path for route in app.routes if getattr(route, "path", "").startswith("/v1/")}
    assert app_paths <= set(contract["paths"]) | PATHS_BEYOND_THE_CONTRACT
    assert {"/v1/sessions", "/v1/sessions/current", "/v1/sandboxes", "/v1/sandboxes/{sandbox_id}"} <= app_paths


def test_the_guard_refuses_a_route_that_nobody_decided(app) -> None:
    """The guard of the facade is a real guard: a path that nobody decided is refused by it (ADR-023).

    Why it matters: the constant names the paths of the decision that have landed, and a constant that named a
    path of the facade that does not exist would be a promise the test cannot keep. The guard is therefore checked
    against a path that nobody decided, so a route that appears in the facade without a decision is refused.
    """
    contract = _contract()
    app_paths = {route.path for route in app.routes if getattr(route, "path", "").startswith("/v1/")}
    undecided = "/v1/sandboxes/{sandbox_id}/decisions"

    assert undecided not in contract["paths"]
    assert undecided not in PATHS_BEYOND_THE_CONTRACT
    assert not (app_paths | {undecided}) <= set(contract["paths"]) | PATHS_BEYOND_THE_CONTRACT
    # Every path the guard names is a path of the facade: the guard names the routes that have landed.
    assert PATHS_BEYOND_THE_CONTRACT <= app_paths


def test_the_facade_answers_the_resource_of_the_contract(app, session_client: TestClient, scenario_id: str) -> None:
    resource = _contract()["components"]["schemas"]["Sandbox"]
    body = _fork(session_client, scenario_id).json()
    assert set(body) == set(resource["properties"]) == set(resource["required"])
    assert resource["additionalProperties"] is False


def test_the_cookie_of_the_facade_is_the_cookie_of_the_contract(app) -> None:
    scheme = _contract()["components"]["securitySchemes"]["anonymousSession"]
    assert scheme["in"] == "cookie"
    assert scheme["name"] == SESSION_COOKIE


def test_the_pattern_of_the_scenario_of_the_body_is_the_one_of_the_contract(app) -> None:
    schema = _contract()["paths"]["/v1/sandboxes"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    assert schema["properties"]["scenario_id"]["pattern"] == SCENARIO_ID_PATTERN
    assert schema["additionalProperties"] is False


# --- the stream of the lifecycle of the branch ------------------------------------------------------------


def _events_of(text: str) -> list[dict[str, Any]]:
    """The events of a chunk of a stream, parsed the way a browser parses them.

    Why the parser is here and not in the library: the answer of the stream is text, and the reader of the browser
    reads the three lines of an event. A test that read the raw text would prove nothing about what a browser sees.

    Why the `id:` line is optional here: the three events of the stream carry no `id:` line, and a parser that
    expected one would hide the very rule that the tests of the stream check.
    """
    parsed: list[dict[str, Any]] = []
    for block in text.split("\n\n"):
        if not block.strip():
            continue
        event: dict[str, Any] = {}
        for line in block.splitlines():
            field, _, value = line.partition(":")
            if field == "data":
                event["data"] = json.loads(value.strip())
            else:
                event[field] = value.strip()
        parsed.append(event)
    return parsed


def _wait_for_the_subscribers(hub: EventHub, branch_id: str, count: int, timeout: float = 5.0) -> None:
    """Waits until the branch of the hub has exactly the number of subscribers the test needs.

    Why the wait exists: the route subscribes the stream to the hub when the generator of the stream starts, and the
    generator starts in the thread of the server. A test that published an event before the subscription would lose
    that event, and the event would never arrive. The wait is what makes the test deterministic.

    Why the private state of the hub is read: the hub tells nobody that a stream subscribed, so a test that waited
    for a state the hub does not expose would wait for ever.
    """
    deadline = time.monotonic() + timeout
    seen: list[int] = []
    while time.monotonic() < deadline:
        current = len(hub._subscribers.get(branch_id, ()))
        if current != (seen[-1] if seen else -1):
            seen.append(current)
        if current == count:
            return
        time.sleep(0.01)
    raise AssertionError(f"the branch {branch_id} did not reach {count} subscribers of the hub, it reached {seen}")


class _CountingRateLimiter(RateLimiter):
    """The counter of the rate of the requests with the number of the requests it counted, so that a test reads it.

    Why the counter is replaced and not observed from the outside: the facade builds its own limiter, and the only
    way to know how many requests it counted is to count them in the limiter itself.
    """

    def __init__(self, **kwargs: Any) -> None:
        """The counter of the rate with the counter of the requests that it counted."""
        super().__init__(**kwargs)
        self.counted = 0

    def acquire(self, session_id: str) -> RateDecision:
        """Counts the request of the session and remembers that it was counted."""
        decision = super().acquire(session_id)
        if decision.allowed:
            self.counted += 1
        return decision


@pytest.fixture
def rate_counter(monkeypatch: pytest.MonkeyPatch) -> list[_CountingRateLimiter]:
    """The limiters that the facade builds, so that a test can read how many requests they counted.

    Why the patch is in the facade and not in the test: the facade builds the limiter when the application is built,
    and the test has to read that very limiter. The patch is undone by pytest when the test ends.
    """
    built: list[_CountingRateLimiter] = []

    def factory(**kwargs: Any) -> _CountingRateLimiter:
        """The limiter of the facade, remembered by the test."""
        limiter = _CountingRateLimiter(**kwargs)
        built.append(limiter)
        return limiter

    monkeypatch.setattr("ledgerlens.api.sandbox.RateLimiter", factory)
    return built


@pytest.fixture
def hub() -> EventHub:
    """The hub of the events of the test, so that the counter of a branch starts fresh and can be read."""
    return EventHub()


@pytest.fixture
def stream_app(store: FileBranchStore, base_resolver: BaseResolver, clock, hub: EventHub):
    """The facade over the hub of the test, so that a test can read the counter of the branch."""
    return create_app(store=store, base_resolver=base_resolver, clock=clock, event_hub=hub)


@pytest.fixture
def stream_client(stream_app) -> TestClient:
    """A client of the facade of the stream, with the cookie of a session the server issued."""
    client = TestClient(stream_app)
    assert client.post("/v1/sessions").status_code == 201
    return client


def test_the_resume_that_is_proven_continues_with_the_next_sequence_and_repeats_nothing(
    stream_client: TestClient, scenario_id: str, adjustment_payload: dict[str, object], hub: EventHub
) -> None:
    """A resume that is proven continues the stream: no resync, no event of the opening again, the next sequence.

    Why the case exists: the counter of the branch exists so that a client can prove that it missed nothing. Before
    the decision of ADR-047 the second answer of the resume, the one that continues without a resync, was
    unreachable in the real flow, because an event of the stream that moved the counter made every reconnection look
    stale to the client that disconnected and never received it.
    """
    branch_id = _fork(stream_client, scenario_id).json()["id"]
    path = f"/v1/sandboxes/{branch_id}/events"

    with stream_client.stream("GET", path) as opening:
        frames = opening.iter_text()
        first = _events_of(next(frames))
    assert first[0]["event"] == EVENT_BRANCH_OPENED
    assert first[0]["id"] == "1"

    # The second connection carries the identifier that the hub gave to the branch: the client proved that it missed
    # nothing, so the stream continues with the next sequence and repeats nothing.
    with stream_client.stream("GET", path, headers={"Last-Event-ID": "1"}) as resumed:
        frames = resumed.iter_text()
        _wait_for_the_subscribers(hub, branch_id, 1)
        assert _commit(stream_client, branch_id, adjustment_payload).status_code == 200
        received = _events_of(next(frames))

    assert len(received) == 1
    assert received[0]["event"] == EVENT_MUTATION_COMMITTED
    assert received[0]["id"] == "2"


def test_the_resume_behind_the_counter_answers_with_a_resync_and_the_reason_not_current(
    stream_client: TestClient, scenario_id: str, adjustment_payload: dict[str, object], hub: EventHub
) -> None:
    """A resume with an identifier behind the counter of the hub answers with a resync and the reason `not_current`.

    Why the reason is pinned: the client reads the reason to know what to do, and a client that cannot tell a stale
    identifier from an unknown one would re-read the branch for the wrong reason.
    """
    branch_id = _fork(stream_client, scenario_id).json()["id"]
    path = f"/v1/sandboxes/{branch_id}/events"

    with stream_client.stream("GET", path) as opening:
        frames = opening.iter_text()
        first = _events_of(next(frames))
    assert first[0]["event"] == EVENT_BRANCH_OPENED
    assert _commit(stream_client, branch_id, adjustment_payload).status_code == 200
    assert hub.counter(branch_id) == 2

    with stream_client.stream("GET", path, headers={"Last-Event-ID": "1"}) as resumed:
        frames = resumed.iter_text()
        received = _events_of(next(frames))

    assert len(received) == 1
    assert received[0]["event"] == EVENT_STREAM_RESYNC
    assert received[0]["data"]["reason"] == "not_current"
    assert received[0]["data"]["last_event_id"] == "1"
    # The resync belongs to the connection that reconnected: it carries no `id:` line and it moves no counter.
    assert "id" not in received[0]
    assert hub.counter(branch_id) == 2


@pytest.mark.parametrize("identifier", ["999", "not-a-sequence"])
def test_the_resume_with_an_identifier_that_the_hub_does_not_know_answers_with_a_resync(
    stream_client: TestClient, scenario_id: str, identifier: str
) -> None:
    """A resume with an identifier that the hub does not know answers with a resync and the reason `unknown`.

    Why the two shapes of the identifier: one is a number that the hub never gave to anybody, and the other is not
    the bare decimal integer of a sequence at all. The hub cannot prove either of them, and it says so instead of
    guessing what the client meant.
    """
    branch_id = _fork(stream_client, scenario_id).json()["id"]

    with stream_client.stream(
        "GET", f"/v1/sandboxes/{branch_id}/events", headers={"Last-Event-ID": identifier}
    ) as resumed:
        frames = resumed.iter_text()
        received = _events_of(next(frames))

    assert len(received) == 1
    assert received[0]["event"] == EVENT_STREAM_RESYNC
    assert received[0]["data"]["reason"] == "unknown"
    assert received[0]["data"]["last_event_id"] == identifier


def test_the_route_of_the_stream_refuses_a_branch_that_expired(
    stream_client: TestClient, scenario_id: str, clock
) -> None:
    """A branch that outlived its time to live is refused with `410` and the code of the contract.

    Why the refusal matters at the route of the stream: the stream is the one path that does not answer with a
    document, and a refusal that arrived as a stream would leave the client without the code it needs.
    """
    branch_id = _fork(stream_client, scenario_id).json()["id"]
    clock.advance(timedelta(hours=2))

    response = stream_client.get(f"/v1/sandboxes/{branch_id}/events")

    assert response.status_code == 410
    body = response.json()
    assert set(body) == ERROR_KEYS
    assert body["code"] == "BRANCH_EXPIRED"


def test_the_opening_of_the_stream_counts_one_request_for_the_rate_of_the_requests(
    rate_counter: list[_CountingRateLimiter],
    monkeypatch: pytest.MonkeyPatch,
    store: FileBranchStore,
    base_resolver: BaseResolver,
    clock,
    scenario_id: str,
) -> None:
    """The opening of a stream counts ONE request of the rate, and the heartbeats of that stream count none.

    Why the counter of the test: the facade builds its own limiter, and the promise of ADR-047 is about the number of
    the requests that the limiter counted. The heartbeats are the second half of the promise: a stream that is open
    for a long time must not spend the quota of the visitor.
    """
    monkeypatch.setattr("ledgerlens.api.sandbox.HEARTBEAT_INTERVAL_SECONDS", 0.05)
    application = create_app(store=store, base_resolver=base_resolver, clock=clock)
    client = TestClient(application)
    assert client.post("/v1/sessions").status_code == 201
    branch_id = _fork(client, scenario_id).json()["id"]
    limiter = rate_counter[0]
    counted_before = limiter.counted

    names: list[str] = []
    with client.stream("GET", f"/v1/sandboxes/{branch_id}/events") as response:
        assert response.status_code == 200
        frames = response.iter_text()
        for chunk in frames:
            names.extend(event["event"] for event in _events_of(chunk))
            if EVENT_STREAM_HEARTBEAT in names:
                break

    assert EVENT_STREAM_HEARTBEAT in names
    assert limiter.counted == counted_before + 1


def test_the_payload_of_an_event_never_carries_the_identifier_of_the_session(
    stream_client: TestClient, scenario_id: str, adjustment_payload: dict[str, object]
) -> None:
    """No payload of the stream carries the identifier of the session of the visitor.

    Why the session and not only the cookie: the cookie carries the identifier, the stamp and the signature, and a
    payload that carried any of the three would give a reader of the stream a way back to the visitor.
    """
    branch_id = _fork(stream_client, scenario_id).json()["id"]
    cookie = stream_client.cookies.get(SESSION_COOKIE)
    assert cookie
    identifier = cookie.split(".")[0]

    with stream_client.stream("GET", f"/v1/sandboxes/{branch_id}/events") as response:
        frames = response.iter_text()
        opening = next(frames)
        assert _commit(stream_client, branch_id, adjustment_payload).status_code == 200
        committed = next(frames)

    for text in (opening, committed):
        assert identifier not in text
        assert cookie not in text


def test_the_answer_of_the_stream_carries_the_three_headers_of_the_no_store(
    stream_client: TestClient, scenario_id: str
) -> None:
    """The answer of the stream holds the state of a branch of a visitor, so it is not to be kept anywhere.

    Why the three headers and not one: the triad is the decision of ADR-047, and the three of them are what the
    intermediaries and the caches of a deployment read.
    """
    branch_id = _fork(stream_client, scenario_id).json()["id"]

    with stream_client.stream("GET", f"/v1/sandboxes/{branch_id}/events") as response:
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["pragma"] == "no-cache"
        assert response.headers["expires"] == "0"


def test_the_stream_of_a_branch_that_dies_says_that_it_died_and_then_closes(
    monkeypatch: pytest.MonkeyPatch, stream_client: TestClient, scenario_id: str, clock
) -> None:
    """The client of a branch that dies hears that the branch died, and then hears that the stream closed.

    Why the case exists: the expiry is an event of the lifecycle, and the hub hands an event to the subscribers of the
    branch with `call_soon_threadsafe`, so the copy of the expiry reaches the queue of the connection one turn of the
    loop later. The close of the connection was put in the queue at once, so the queue handed the close first, the
    stream ended there, and the client never heard that the branch died.
    """
    monkeypatch.setattr("ledgerlens.api.sandbox.HEARTBEAT_INTERVAL_SECONDS", 0.05)
    branch_id = _fork(stream_client, scenario_id).json()["id"]

    with stream_client.stream("GET", f"/v1/sandboxes/{branch_id}/events") as response:
        frames = response.iter_text()
        assert _events_of(next(frames))[0]["event"] == EVENT_BRANCH_OPENED
        clock.advance(timedelta(hours=2))
        received: list[dict[str, Any]] = []
        for chunk in frames:
            received.extend(_events_of(chunk))
            if any(event["event"] == EVENT_STREAM_CLOSED for event in received):
                break

    names = [event["event"] for event in received]
    assert EVENT_BRANCH_EXPIRED in names
    assert names.index(EVENT_BRANCH_EXPIRED) < names.index(EVENT_STREAM_CLOSED)


def test_the_close_belongs_to_its_connection_and_the_disconnect_publishes_nothing(
    monkeypatch: pytest.MonkeyPatch,
    stream_client: TestClient,
    scenario_id: str,
    adjustment_payload: dict[str, object],
    hub: EventHub,
    store: FileBranchStore,
) -> None:
    """The close of one connection is not given to the other connections, and a disconnect publishes nothing.

    Why the case exists: the counter of the branch exists so that a client can prove that it missed nothing. A close
    that was published to the branch would move the counter, and the client that never received it would look stale at
    its next reconnection. The disconnect of a client is not an event at all: the client that left is gone and the
    other connections of the branch are not affected by it.

    Why the closed frame carries no `id:` line: a published event of the branch always carries one, so the line that
    is missing is the proof that the close was not given to the branch.
    """
    monkeypatch.setattr("ledgerlens.api.sandbox.HEARTBEAT_INTERVAL_SECONDS", 0.05)
    branch_id = _fork(stream_client, scenario_id).json()["id"]
    path = f"/v1/sandboxes/{branch_id}/events"

    with stream_client.stream("GET", path) as first:
        first_frames = first.iter_text()
        next(first_frames)
        with stream_client.stream("GET", path) as second:
            second_frames = second.iter_text()
            next(second_frames)
            _wait_for_the_subscribers(hub, branch_id, 2)
            counted = hub.counter(branch_id)

            # The first client disconnects. The disconnect is not an event, so the counter of the branch stays.
            first.close()
            _wait_for_the_subscribers(hub, branch_id, 1)
            assert hub.counter(branch_id) == counted

            # The second connection is alive: it receives the event of the commit and no close.
            assert _commit(stream_client, branch_id, adjustment_payload).status_code == 200
            received = _events_of(next(second_frames))

    assert [event["event"] for event in received] == [EVENT_MUTATION_COMMITTED]

    # The row of the branch disappears, and the server ends the connections of the branch. Every connection ends with
    # its OWN close, and the close of one connection is not given to the other one: the counter of the branch does not
    # move, because a close that moved it would make every reconnection look stale.
    other = _fork(stream_client, scenario_id).json()["id"]
    other_path = f"/v1/sandboxes/{other}/events"
    cookie = stream_client.cookies.get(SESSION_COOKIE)
    assert cookie
    owner = canonical_session_id(cookie.split(".")[0])

    with stream_client.stream("GET", other_path) as one:
        one_frames = one.iter_text()
        with stream_client.stream("GET", other_path) as two:
            two_frames = two.iter_text()
            _wait_for_the_subscribers(hub, other, 2)
            counted = hub.counter(other)
            assert store.delete_branch(other, owner)
            frames_one = _events_of("".join(one_frames))
            frames_two = _events_of("".join(two_frames))

    assert hub.counter(other) == counted
    for frames in (frames_one, frames_two):
        closed = [event for event in frames if event["event"] == EVENT_STREAM_CLOSED]
        assert len(closed) == 1
        assert "id" not in closed[0]
        assert closed[0]["data"]["reason"] == CLOSED_REASON_GONE
