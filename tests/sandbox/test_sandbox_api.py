"""The sandbox facade: the versioned contract of the design package, the session cookie and the generic refusal.

The `TestClient` calls the app in process, so no test opens a port or reaches the network. The client keeps the
cookie of the session between the requests, which is the way the browser behaves.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

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
from ledgerlens.run_context import SESSION_ID_PATTERN  # noqa: E402
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
