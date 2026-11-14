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


# --- the contract of the design package --------------------------------------------------------------


def test_the_app_declares_the_security_scheme_of_the_contract(app) -> None:
    spec = app.openapi()
    scheme = spec["components"]["securitySchemes"]["anonymousSession"]
    assert scheme["type"] == "apiKey"
    assert scheme["in"] == "cookie"
    assert scheme["name"] == SESSION_COOKIE
    assert spec["paths"]["/v1/sandboxes"]["post"]["security"] == [{"anonymousSession": []}]
    assert spec["paths"]["/v1/sandboxes/{sandbox_id}"]["get"]["security"] == [{"anonymousSession": []}]


def test_every_path_of_the_facade_is_a_path_of_the_contract(app) -> None:
    contract = _contract()
    app_paths = {route.path for route in app.routes if getattr(route, "path", "").startswith("/v1/")}
    assert app_paths <= set(contract["paths"])
    assert {"/v1/sessions", "/v1/sessions/current", "/v1/sandboxes", "/v1/sandboxes/{sandbox_id}"} <= app_paths


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
